# vast-reporting

A minimal FastAPI service that accepts VAST tracking requests and logs them to Azure Blob Storage. Events are appended to an hourly JSONL blob stored in a date-based folder (`events/YYYY/MM/DD/HH.jsonl`).

## Installation

1. Create and activate a virtual environment (optional).
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file with Azure connection details:

```env
AZURE_STORAGE_CONNECTION_STRING="<your connection string>"
AZURE_CONTAINER="vast-logs"  # optional
AZURE_BLOB_PREFIX="events"   # optional
```

## Running locally

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Visit `http://localhost:8000/healthz` for a health check.

## Systemd service example

A sample unit file is provided as `vast.service`.

`vast.service`:

```ini
[Unit]
Description=VAST reporting service
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/vast-reporting
EnvironmentFile=/opt/vast-reporting/.env
ExecStart=/usr/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable vast.service
sudo systemctl start vast.service
```

## Development

Run tests and lints:

```bash
ruff app
pytest
```
