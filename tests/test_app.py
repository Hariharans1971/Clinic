import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

_temp_dir = tempfile.TemporaryDirectory()
os.environ["CLINIC_DB_PATH"] = str(Path(_temp_dir.name) / "test-clinic.db")

from app.main import app  # noqa: E402


class AppointmentApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client_context = TestClient(app)
        cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        _temp_dir.cleanup()

    def test_health_check(self):
        response = self.client_context.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_create_and_list_appointment(self):
        response = self.client_context.post(
            "/api/appointments",
            json={
                "patient_name": "Demo Patient",
                "doctor_name": "Dr. Sample",
                "appointment_at": "2026-11-01T10:30",
                "reason": "General consultation",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        created = response.json()
        self.assertEqual(created["patient_name"], "Demo Patient")
        self.assertEqual(created["status"], "Scheduled")

        listed = self.client_context.get("/api/appointments")
        self.assertEqual(listed.status_code, 200)
        self.assertTrue(any(item["id"] == created["id"] for item in listed.json()))

    def test_rejects_invalid_datetime(self):
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


if __name__ == "__main__":
    unittest.main()
