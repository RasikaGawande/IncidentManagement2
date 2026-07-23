# ServiceNow Incident API

A small FastAPI service that exposes ServiceNow incidents to a frontend.

## Endpoints

- `GET /api/v1/incidents/active` — unresolved active incidents.
- `GET /api/v1/incidents/historical` — resolved historical incidents.

The API permits browser requests from any origin. It does not support browser credentials or authentication sessions.

## Configuration

Set all three variables to load live ServiceNow data:

```bash
export SERVICENOW_INSTANCE_URL="https://your-instance.service-now.com"
export SERVICENOW_USERNAME="admin"
export SERVICENOW_PASSWORD="your-password"
```

`SERVICENOW_INCIDENT_LIMIT` defaults to `200`.

If ServiceNow is down, slow, unreachable, or only partially configured, both endpoints return local demo records from `data/servicenow-fallback-incidents.json`. The backend writes an INFO log whenever it uses fallback data, so the frontend always receives JSON instead of a 503 response.

## Run locally

```bash
pip install -e ".[dev]"
uvicorn api.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the API documentation.
