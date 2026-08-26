# SocialIQ Analytics

The frontend is a finished static UI. The FastAPI backend supplies its campaign-aware
analysis data through `GET /analysis`.

## Run on Windows

Install a supported Python version (3.11 or 3.12 recommended), then create a fresh
virtual environment from the project root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
$env:SOCIALIQ_DATA_MODE = "demo"
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --port 8001
```

Open `http://127.0.0.1:8001/docs` to explore the API. Serve the frontend with VS Code
Live Server (port 5500), then open its generated localhost address. This is allowed by
the default CORS configuration.

## Test

With the environment active:

```powershell
pytest
Invoke-RestMethod "http://127.0.0.1:8001/analysis?topic=Education%20Policy&platform=Instagram&period=Last%2030%20Days&chart_period=Monthly"
```

## Data modes

The default `SOCIALIQ_DATA_MODE=empty` returns zero values and `No information`; it is
the correct mode before authorised platform APIs are connected. To test UI loading with
clearly labelled development samples, set `SOCIALIQ_DATA_MODE=demo` before starting
the API. Copy `.env.example` as a reference—environment variables are intentionally
read from the operating system rather than hard-coded in source.

Future authorised Instagram, YouTube, Facebook, and X integrations belong behind the
`PlatformDataProvider` interface in `backend/services/analysis_service.py`. The
`ml/`, `models/`, and `data/` folders remain available for trained artefacts and
processed data; no large model or database is required for this foundation.
