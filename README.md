# vast-reporting

A minimal FastAPI service that accepts VAST tracking requests and logs them to Azure Blob Storage. Events are appended to an hourly JSONL blob stored in a date-based folder (`events/YYYY/MM/DD/HH.jsonl`) using Azure Append Blobs, so payloads are accumulated rather than overwritten when multiple writes occur within the same hour.

## Installation

1. Create and activate a virtual environment (optional).
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file with Azure connection details:

```env
AZURE_STORAGE_ACCOUNT_NAME="<your storage account name>"
AZURE_STORAGE_ACCOUNT_KEY="<your storage account key>"
AZURE_CONTAINER="vast"      # optional, defaults to "vast"
AZURE_BLOB_PREFIX="events"  # optional, defaults to "events"
```

## Running locally

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Visit `http://localhost:8000/healthz` for a health check.

## Tracking URL example

Use `http://vast.podhub.in/track?` as the base URL (note the trailing `?` so additional query parameters can be appended). For example:

```
http://vast.podhub.in/track?advertiser=shopify&client=574d66fb-1a31-43ec-bd16-a28cd84d396c&clname=undrthecoshukshopifyuk_gb_shopify_218545&dt=%%delivery_time%%&eid=%%episodeid%%&event_type=imp&ip=%%ip%%&ord=%%cachebuster%%&pid=%%podcastid%%&plt=megaphone&pub=voiceworkssportslimited&ua=%%ua%%&v=1
```

This mirrors the format used by similar services but targets the VAST reporting endpoint.

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
