# ClinicDesk — Full-Stack Appointment Manager

A small, runnable full-stack clinic appointment demo built with **FastAPI, SQLite, and vanilla HTML/CSS/JavaScript**. It demonstrates REST API design, validation, persistence, filtering, and automated tests.

> Educational demo only. Do not store real patient or health information in this project.

## Features

- Create, list, update, and cancel appointments
- Validate required fields, ISO date/time values, and appointment status
- Make cancellation idempotent and reject cancellation of completed appointments
- Filter appointments by status
- SQLite persistence with parameterized SQL
- Responsive browser UI served by FastAPI
- API documentation at `/docs`
- Unit tests and GitHub Actions syntax/test workflow

## Architecture

```text
Browser (HTML/CSS/JS)
        |
        | fetch() / JSON
        v
FastAPI REST API
        |
        v
SQLite database
```

## Run locally

Requires Python 3.10+.

```bash
git clone https://github.com/Hariharans1971/Clinic.git
cd Clinic
python -m venv .venv
```

Activate the environment:

- Windows PowerShell: `.venv\Scripts\Activate.ps1`
- macOS/Linux: `source .venv/bin/activate`

Install and run:

```bash
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. Interactive API docs: http://127.0.0.1:8000/docs.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/appointments` | List appointments; optional `?status=Scheduled` |
| POST | `/api/appointments` | Create an appointment |
| PATCH | `/api/appointments/{id}` | Partially update appointment fields |
| POST | `/api/appointments/{id}/cancel` | Mark an appointment cancelled; safe to repeat |
| GET | `/health` | Health check |

Example request:

```bash
curl -X POST http://127.0.0.1:8000/api/appointments \
  -H "Content-Type: application/json" \
  -d '{"patient_name":"Demo Patient","doctor_name":"Dr. Sample","appointment_at":"2026-11-01T10:30","reason":"General consultation"}'
```

## Tests

```bash
python -m unittest discover -s tests -v
```

## Engineering notes

- Input is validated at the API boundary.
- SQL values are passed as parameters rather than interpolated into query strings.
- The database path can be configured with `CLINIC_DB_PATH`.
- This starter intentionally does not implement authentication, authorization, audit trails, encryption, or regulatory controls. It is not suitable for real clinical use without substantial security and privacy work.

## Roadmap

- Authentication and role-based access control
- PostgreSQL deployment profile and migrations
- Integration tests and frontend error states
- Docker-based local environment

## License

MIT
