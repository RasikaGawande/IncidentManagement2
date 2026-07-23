# Incident Management API

A FastAPI application that searches historical incidents using Azure OpenAI embeddings, gathers deployment and code evidence for weak matches, and uses Azure OpenAI chat completions to return bounded operational guidance.

## Request flow

1. At startup, the API loads `data/historical-incidents.json` and builds an in-memory embedding index.
2. `POST /api/v1/incidents/analyze` embeds the incoming incident and returns the closest historical incidents.
3. If the top similarity is below `SIMILARITY_THRESHOLD` (default `0.85`), the Deployment Check Agent adds the latest successful deployment for the affected service.
4. A low-similarity incident that includes optional `logs` also runs the Code Investigation Agent. It extracts the most specific error signature, searches configured code, and supplies matching source excerpts as evidence.
5. The chat model receives only the incident, matched history, and agent evidence, then produces an RCA hypothesis and safe resolution steps.

## Project layout

- `api/` — FastAPI application and routes
- `agents/` — deployment and code-investigation agents
- `core/` — configuration
- `domain/` — request and response models
- `repositories/` — JSON data and code-search adapters
- `services/` — orchestration, Azure OpenAI client, and advisor
- `vector/` — in-memory embedding search
- `data/` — banking incident fixtures, logs, deployment history, and simulated code-search results
- `banking-demo/` — six small Java 17 services arranged in a three-layer banking payment flow

## Prerequisites

Create an Azure OpenAI resource with one chat-model deployment and one embedding-model deployment. The deployment names, rather than base model names, are used by the API.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
export AZURE_OPENAI_API_KEY="your-azure-openai-key"
export AZURE_OPENAI_CHAT_DEPLOYMENT="your-chat-deployment"
export AZURE_OPENAI_EMBEDDING_DEPLOYMENT="your-embedding-deployment"
uvicorn api.main:app --reload
```

Configuration is through environment variables:

- `AZURE_OPENAI_ENDPOINT` — required, for example `https://your-resource.openai.azure.com`
- `AZURE_OPENAI_API_KEY` — required Azure OpenAI API key
- `AZURE_OPENAI_API_VERSION` (default `2024-10-21`)
- `AZURE_OPENAI_CHAT_DEPLOYMENT` (default `gpt-4o-mini`)
- `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` (default `text-embedding-3-small`)
- `SIMILARITY_THRESHOLD` (default `0.85`)
- `DATA_DIRECTORY` (default `./data`)
- `GITHUB_REPOSITORY` and `GITHUB_TOKEN` — optional. Set both to search your real `owner/repository` with GitHub's code-search API. Without them, the demo uses `data/simulated-github-code.json`.
- `SERVICENOW_INSTANCE_URL`, `SERVICENOW_USERNAME`, and `SERVICENOW_PASSWORD` — required together to use the ServiceNow incident endpoints. Resolved and closed incidents are loaded from the ServiceNow Table API.
- `SERVICENOW_INCIDENT_LIMIT` (default `200`) — maximum number of historical ServiceNow incidents to import.

## ServiceNow Personal Developer Instance

Create dummy incidents in your PDI, resolve a few of them, and configure the three ServiceNow variables locally:

```bash
export SERVICENOW_INSTANCE_URL="https://your-instance.service-now.com"
export SERVICENOW_USERNAME="admin"
export SERVICENOW_PASSWORD="your-pdi-admin-password"
```

The application imports only `active=false` incidents and requests a restricted set of fields. Do not commit these credentials or use company production incident data without approval.

`GET /api/v1/incidents/historical` fetches resolved/closed records from ServiceNow on demand (for example, `http://127.0.0.1:8000/api/v1/incidents/historical`). `GET /api/v1/incidents/active` likewise fetches active tickets on demand; active tickets are intentionally excluded from the historical similarity index.

Both incident endpoints include nested attachment metadata (`id`, `fileName`, `contentType`, and `sizeBytes`) fetched from ServiceNow's `sys_attachment` table. `.txt` attachments additionally include a bounded UTF-8 `fileContent` string; other attachment types return `fileContent: null`.

Active incident responses include `createdAt` and `updatedAt`. Historical incident responses include `createdAt` and `resolvedAt`. Values are `null` when ServiceNow has not populated the corresponding date.

The API permits cross-origin browser requests from frontend applications. It does not allow browser credentials; configure a specific origin before adding cookie- or browser-session-based authentication.

If ServiceNow is unavailable or times out, the incident endpoints return demo records from `data/servicenow-fallback-incidents.json` and log that the fallback was used.

On Cloud Run, the API opens its port even when an integration is not configured. Check `GET /health`: it returns `status: "error"` with the missing configuration detail; integration-dependent endpoints return `503` until the required settings are supplied. Historical analysis is built on the first analyze request.

Open the API documentation at `http://127.0.0.1:8000/docs`. Send an incident to `POST /api/v1/incidents/analyze` using an `incident` object from `data/new-incident.json`.

To run the tests:

```bash
pytest
```
app runs on : http://127.0.0.1:8000/docs
Update `data/historical-incidents.json` to add historical cases and `data/new-incident.json` to maintain sample incoming incidents.

## Banking demo fixtures

`banking-demo/` contains two services in each layer: channel, processing, and data. Each service is a self-contained Maven application. See [banking-demo/README.md](banking-demo/README.md) for the flow and commands.

`INC-NEW-BNK-01` and `INC-NEW-BNK-02` are intentional low-similarity incidents with runnable Java error logs: a risk-decision `IndexOutOfBoundsException` and database connection-pool exhaustion. They activate both agents: deployment history identifies releases `DEP-BNK-2003` and `DEP-BNK-2004`, while the code agent locates the matching Java source excerpt in `data/simulated-github-code.json`.
