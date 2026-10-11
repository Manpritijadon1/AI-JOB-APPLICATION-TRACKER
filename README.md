# AI-Powered Job Application Tracker

A local-first job search tracker built with FastAPI, SQLite, SQLAlchemy,
Pydantic, Streamlit, and Ollama. Track applications from a Streamlit dashboard,
view personal application statistics, and use a locally running language model
to compare resume text with job descriptions or suggest next steps for a saved
application.

> This is a development/portfolio project. Use the security guidance below
> before exposing it beyond your own machine.

## Problem and objectives

Job seekers often spread application details across spreadsheets, email, and
notes. This project brings application records and progress statistics into one
authenticated application. Its objectives are to:

- Keep job application records private to their owning account.
- Provide a documented REST API and a practical Streamlit interface.
- Calculate dashboard statistics on the server using database queries.
- Offer optional resume/application assistance through a local Ollama service,
  without a paid cloud AI API.
- Keep setup and test data local; automated tests use temporary SQLite
  databases and mocked Ollama responses.

## Features

- User registration, login, and JWT bearer authentication.
- Argon2 password hashing; plaintext passwords are not stored.
- Per-user job application create, read, update, delete, search, filters,
  sorting, and pagination.
- Dashboard statistics for status, employment type, location, application
  dates, interview/offer/rejection counts, and conversion rates.
- Optional local Ollama resume analysis and saved-application assistance.
- Streamlit UI for authentication, dashboard charts, application management,
  and AI requests.
- Pytest coverage for the API, ownership, error handling, AI mocks, and
  frontend HTTP helper behavior.

## Technologies

- Python 3.13
- FastAPI and Uvicorn
- SQLite and SQLAlchemy 2
- Pydantic and Pydantic Settings
- PyJWT and `pwdlib[argon2]`
- HTTPX
- Streamlit
- Ollama with the locally managed `qwen2.5:3b` model (default)
- Pytest

## Architecture and project structure

FastAPI owns authentication, authorization, validation, persistence, dashboard
queries, and AI orchestration. Streamlit is a separate UI client that calls the
API. The backend sends AI requests to the configured local Ollama HTTP service.
There is no model-generated SQL path.

```text
.
├── app/
│   ├── api/          # Auth, jobs, dashboard, and AI routes
│   ├── core/         # Settings, JWT/password security, request-size limit
│   ├── db/           # SQLAlchemy base, engine, and session dependency
│   ├── models/       # User and job application tables
│   ├── schemas/      # Validated API request/response models
│   ├── services/     # Ollama local HTTP integration
│   └── main.py       # FastAPI app factory and route registration
├── frontend/
│   ├── api_client.py     # HTTP client and safe API error messages
│   └── streamlit_app.py  # Streamlit user interface
├── tests/            # Temporary-database and mocked-service tests
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

The default database URL is `sqlite:///./job_tracker.db`. SQLAlchemy creates
tables when the API starts. The SQLite database is local and excluded from
Git.

## Authentication and security

- `POST /auth/register` hashes passwords with Argon2 and returns only public
  user fields.
- `POST /auth/login` returns an HS256 JWT. The signing key must be supplied as
  `JWT_SECRET_KEY`; authentication returns HTTP 503 when it is unset or shorter
  than 32 characters.
- Protected routes require `Authorization: Bearer <JWT>`. Tokens have a
  configurable expiry (`ACCESS_TOKEN_EXPIRE_MINUTES`, default 30).
- Job queries and mutations include the authenticated user's ID. Requests for
  another user's job return 404.
- The Streamlit UI keeps a token in session-scoped state, does not display or
  log it, and clears it on logout or an authenticated 401 response.
- Do not commit `.env`, keys, database files, resumes, or personal data. The
  supplied `.gitignore` excludes common local secret, cache, database, upload,
  and private-data paths.
- Use a trusted API URL. For remote access, configure HTTPS and appropriate
  production deployment controls; the default local URLs are for development.

## Job application records

Each record contains company, title, optional URL/location/employment type,
status, applied date, optional notes, and timestamps. Supported statuses are
`Applied`, `Interview`, `Offer`, `Rejected`, and `Withdrawn`. The API validates
inputs and is the source of truth for business rules.

## Dashboard statistics

`GET /dashboard/stats` is authenticated and returns statistics for the current
user only: total applications, counts for all statuses, grouped employment
types and locations (including an unset `null` category when applicable),
counts by applied date, interview/offer/rejection totals, and interview/offer
conversion percentages. Empty totals produce zero rates.

## Local AI with Ollama

The AI endpoints use the Ollama local HTTP API at `OLLAMA_BASE_URL` and model
`OLLAMA_MODEL` (defaults: `http://127.0.0.1:11434` and `qwen2.5:3b`). Ollama
and the model are separate local prerequisites: install Ollama and download
the model manually if it is not already present. The application never
downloads a model automatically.

Resume analysis returns a resume summary, job-match summary, matching skills,
missing/underrepresented job skills, relevant experience highlights, and
improvement suggestions. Response fields are validated and include source-text
evidence; unsupported evidence is rejected. Application assistance uses only
the authenticated user's saved job fields and returns a summary and next steps.
AI output is advisory and should be checked by the user.

The backend does not persist submitted resume text, send it to a cloud AI
provider, or execute SQL generated by a model. Requests have configurable body
and text-size limits. Do not include passwords, tokens, or other unnecessary
sensitive content in resume text or notes.

## Windows installation and configuration

Run the following commands in PowerShell from the project root:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Activate the environment if desired:

```powershell
.\.venv\Scripts\Activate.ps1
```

Create a local `.env` from the safe template:

```powershell
Copy-Item .env.example .env
$secret = & .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
$envLines = (Get-Content .env) -replace '^JWT_SECRET_KEY=.*', "JWT_SECRET_KEY=$secret"
$envLines | Set-Content -Encoding ascii .env
```

Keep `.env` private and untracked. The template lists every setting currently
read by the application:

| Variable | Default / example | Purpose |
| --- | --- | --- |
| `APP_NAME` | `AI-Powered Job Application Tracker` | FastAPI title and root response |
| `DATABASE_URL` | `sqlite:///./job_tracker.db` | SQLAlchemy database URL |
| `JWT_SECRET_KEY` | Empty in `.env.example` | Required random signing key; minimum 32 characters |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | JWT lifetime in minutes |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Local Ollama URL; configuration accepts loopback HTTP only |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Model name already available to local Ollama |
| `OLLAMA_TIMEOUT_SECONDS` | `60` | Ollama request timeout |
| `AI_MAX_REQUEST_BYTES` | `65536` | Maximum request body for `/ai` endpoints |
| `AI_MAX_INPUT_CHARACTERS` | `20000` | Maximum characters per AI text input |

Environment variables override `.env` values. The Streamlit client separately
reads `API_BASE_URL`, defaulting to `http://127.0.0.1:8000`.

### Ollama setup

Install Ollama for Windows using its official installer, start the local
service, then explicitly pull the model only if you choose and it is not
already installed:

```powershell
ollama list
ollama pull qwen2.5:3b
```

The pull command is optional setup for the user, not run by this application.
To use a different locally installed model, set `OLLAMA_MODEL` in `.env`.

## Run the applications

Start FastAPI in a PowerShell terminal from the project root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

The API defaults to `http://127.0.0.1:8000`. Interactive OpenAPI docs are at
`http://127.0.0.1:8000/docs`; the health endpoint is `/health`.

In a second terminal, start Streamlit:

```powershell
$env:API_BASE_URL = "http://127.0.0.1:8000"
.\.venv\Scripts\python.exe -m streamlit run frontend/streamlit_app.py
```

Open the local Streamlit URL printed in the terminal (normally
`http://localhost:8501`).

## API reference and examples

All routes except `/`, `/health`, `/auth/register`, and `/auth/login` require a
JWT bearer token. Examples below use placeholders; do not paste real passwords
or tokens into shared logs or source files.

### Authentication

| Method and path | Description | Success |
| --- | --- | --- |
| `POST /auth/register` | Create an account (`name`, `email`, `password`) | `201` |
| `POST /auth/login` | Verify credentials; returns `access_token` and `token_type` | `200` |
| `GET /auth/me` | Return the authenticated user's public profile | `200` |

Register and log in through the UI, or send JSON to the API. Example registration
body:

```json
{
  "name": "Demo User",
  "email": "demo@example.com",
  "password": "replace-with-a-private-password"
}
```

Use the login response as the bearer token on protected API calls:

```text
Authorization: Bearer <access_token>
```

### Job applications

| Method and path | Description | Success |
| --- | --- | --- |
| `POST /jobs` | Create an owned application | `201` |
| `GET /jobs` | List/search/filter/sort/page the current user's applications | `200` |
| `GET /jobs/{job_id}` | Read one owned application | `200` |
| `PATCH /jobs/{job_id}` | Update supplied fields | `200` |
| `DELETE /jobs/{job_id}` | Delete an owned application | `204` |

Create example:

```json
{
  "company_name": "Example Company",
  "job_title": "Backend Engineer",
  "job_url": "https://jobs.example.com/backend",
  "location": "Remote",
  "employment_type": "Full-time",
  "status": "Applied",
  "applied_date": "2026-10-11",
  "notes": "Follow up next week"
}
```

`company_name` and `job_title` are required. `GET /jobs` supports `skip` (zero
or more), `limit` (1–100), `status`, `search` (company or job title), `sort_by`
(`created_at`, `applied_date`, `company_name`, `job_title`, or `status`), and
`sort_order` (`asc` or `desc`). For example:

```text
GET /jobs?status=Interview&search=Example&skip=0&limit=10&sort_by=applied_date&sort_order=desc
```

The list response contains `items`, filtered `total`, `skip`, and `limit`.
Unknown and other users' job IDs both return `404`. Invalid request fields or
query parameters return `422`.

### Dashboard

`GET /dashboard/stats` returns `total_applications`,
`applications_by_status`, `applications_by_employment_type`,
`applications_by_location`, `applications_over_time`, `interview_count`,
`offer_count`, `rejection_count`, `interview_conversion_rate`, and
`offer_conversion_rate`. Rates are percentages rounded to two decimal places;
with no applications they are `0.0`.

### AI endpoints

| Method and path | Description |
| --- | --- |
| `POST /ai/analyze-resume` | Compare `resume_text` and `job_description`; returns structured summaries, skill lists, highlights, and suggestions with evidence |
| `POST /ai/jobs/{job_id}/assistance` | Summarize an owned saved application and suggest next steps |

Resume analysis request:

```json
{
  "resume_text": "Backend engineer experienced with Python and PostgreSQL.",
  "job_description": "Seeking Python, PostgreSQL, and Docker experience."
}
```

The response contains `resume_summary`, `resume_summary_evidence`,
`job_match_summary`, `job_match_summary_evidence`, `matching_skills`,
`missing_or_underrepresented_skills`, `relevant_experience_highlights`, and
`actionable_improvement_suggestions`. Evidence is included with claims.

Application assistance response shape:

```json
{
  "summary": "Application summary based on saved application fields.",
  "summary_evidence": ["source text from the application"],
  "next_steps": [
    {
      "suggestion": "A practical suggested next step.",
      "evidence": ["supporting application text"]
    }
  ]
}
```

AI routes require authentication. Typical errors are `401` for missing/invalid
authentication, `404` for an application not owned by the caller, `413` for
oversized input, `502` for malformed/unsupported model output, `503` when
Ollama or the configured model is unavailable, and `504` for an Ollama timeout.

## Streamlit usage

1. Create an account or sign in.
2. Review application totals and charts on the dashboard.
3. Add, search, filter, sort, edit, and delete applications on the
   **Applications** page. Deletion requires confirmation.
4. Submit resume text and a job description on **Resume analysis**.
5. Select one of your saved applications on **Application assistance**.
6. Use **Log out** to clear the current session's authentication state.

## Screenshots

Add screenshots captured from your own local run in this section before
publishing. No screenshot assets are currently included.

<!-- Screenshot placeholder: Dashboard -->
<!-- Screenshot placeholder: Job applications -->
<!-- Screenshot placeholder: Resume analysis -->

## Tests

Run all automated tests from the project root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests use temporary SQLite databases and mocked HTTP/Ollama responses; the test
suite does not require real user data, a running Ollama server, or a downloaded
model.

## Limitations and future improvements

### Known limitations

- AI quality depends on the locally installed model; evidence validation checks
  that cited text is present, but cannot guarantee semantic correctness.
- Real Ollama inference requires Ollama and the configured model to be installed
  and running locally.
- The application currently uses SQLite and creates tables on startup; no
  migration workflow is included.
- The Streamlit app is a local development UI, not a hardened multi-tenant
  public deployment.
- The API has no password-reset, email-verification, or login rate-limiting
  workflow.

### Possible future improvements

- Add database migrations and production database support.
- Add password-reset/email-verification flows and configurable rate limiting.
- Add export/backup options and richer application reminders.
- Improve AI evaluation and add optional user-controlled analysis history.
- Add browser-level UI tests and screenshots.
- Add deployment guidance, HTTPS configuration, and operational monitoring.

These are potential improvements, not current features.

## License

No license is currently specified in this repository. No license terms are
granted by this README. Choose and add a license file before redistributing or
requesting reuse of the project.
