import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

_temp_dir = tempfile.TemporaryDirectory()
os.environ["CLINIC_DB_PATH"] = str(Path(_temp_dir.name) / "test-clinic.db")

from app.main import app, connect_db  # noqa: E402


class AppointmentApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client_context = TestClient(app)
        cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        _temp_dir.cleanup()

    def create_appointment(self, **overrides):
        payload = {
            "patient_name": "Demo Patient",
            "doctor_name": "Dr. Sample",
            "appointment_at": "2026-11-01T10:30",
            "reason": "General consultation",
        }
        payload.update(overrides)
        response = self.client_context.post("/api/appointments", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_health_check(self):
        response = self.client_context.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_create_and_list_appointment(self):
        created = self.create_appointment()
        self.assertEqual(created["patient_name"], "Demo Patient")
        self.assertEqual(created["status"], "Scheduled")

        listed = self.client_context.get("/api/appointments")
        self.assertEqual(listed.status_code, 200)
        self.assertTrue(any(item["id"] == created["id"] for item in listed.json()))

    def test_rejects_invalid_datetime_on_create(self):
        response = self.client_context.post(
            "/api/appointments",
            json={
                "patient_name": "Demo Patient",
                "doctor_name": "Dr. Sample",
                "appointment_at": "not-a-date",
                "reason": "General consultation",
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_rejects_unknown_status_filter(self):
        response = self.client_context.get("/api/appointments?status=Unknown")
        self.assertEqual(response.status_code, 400)

    def test_patch_updates_only_supplied_fields(self):
        created = self.create_appointment()
        response = self.client_context.patch(
            f"/api/appointments/{created['id']}",
            json={"doctor_name": "Dr. New"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        updated = response.json()
        self.assertEqual(updated["doctor_name"], "Dr. New")
        self.assertEqual(updated["patient_name"], created["patient_name"])
        self.assertEqual(updated["appointment_at"], created["appointment_at"])

    def test_patch_normalizes_iso_datetime(self):
        created = self.create_appointment()
        response = self.client_context.patch(
            f"/api/appointments/{created['id']}",
            json={"appointment_at": "2026-11-02T09:45:59"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["appointment_at"], "2026-11-02T09:45")

    def test_patch_rejects_invalid_datetime(self):
        created = self.create_appointment()
        response = self.client_context.patch(
            f"/api/appointments/{created['id']}",
            json={"appointment_at": "not-a-date"},
        )
        self.assertEqual(response.status_code, 422)

    def test_patch_rejects_empty_patch(self):
        created = self.create_appointment()
        response = self.client_context.patch(
            f"/api/appointments/{created['id']}",
            json={},
        )
        self.assertEqual(response.status_code, 400)

    def test_patch_rejects_blank_text(self):
        created = self.create_appointment()
        response = self.client_context.patch(
            f"/api/appointments/{created['id']}",
            json={"reason": "   "},
        )
        self.assertEqual(response.status_code, 422)

    def test_update_missing_appointment_returns_404(self):
        response = self.client_context.patch("/api/appointments/999999", json={"reason": "Updated"})
        self.assertEqual(response.status_code, 404)

    def test_cancel_changes_status_and_is_idempotent(self):
        created = self.create_appointment()
        first = self.client_context.post(f"/api/appointments/{created['id']}/cancel")
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["status"], "Cancelled")

        second = self.client_context.post(f"/api/appointments/{created['id']}/cancel")
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json()["status"], "Cancelled")

        filtered = self.client_context.get("/api/appointments?status=Cancelled")
        self.assertTrue(any(item["id"] == created["id"] for item in filtered.json()))

    def test_cancel_missing_appointment_returns_404(self):
        response = self.client_context.post("/api/appointments/999999/cancel")
        self.assertEqual(response.status_code, 404)

    def test_completed_appointment_cannot_be_cancelled(self):
        created = self.create_appointment()
        with connect_db() as connection:
            connection.execute(
                "UPDATE appointments SET status = 'Completed' WHERE id = ?",
                (created["id"],),
            )
        response = self.client_context.post(f"/api/appointments/{created['id']}/cancel")
        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
