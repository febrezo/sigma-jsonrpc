# sigma-jsonrpc

Professional HTTP microservice for Sigma with a primary **JSON-RPC 2.0** endpoint:

- `POST /jsonrpc`

It also exposes auxiliary HTTP endpoints for human use and operations:

- `GET /`
- `GET /health`
- `GET /version`
- `POST /api/translate/sigma-bundle` (STIX Bundle translation)

## Architecture

Implemented modular structure:

- `app/main.py`
- `app/config.py`
- `app/auth.py`
- `app/errors.py`
- `app/models.py`
- `app/engine.py`
- `app/rpc.py`
- `app/routes/http.py`
- `app/routes/jsonrpc.py`
- `app/templates/home.html`

Detailed design documentation:

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/CI_GHCR.md](docs/CI_GHCR.md)
- [docs/AI_MCP_USAGE.md](docs/AI_MCP_USAGE.md)

## Available JSON-RPC Methods

- `rpc.discover`
- `sigma.backends.list`
- `sigma.pipelines.list`
- `sigma.plugins.list`
- `sigma.validate`
- `sigma.convert`
- `sigma.indicator.bundle`

## Installed Sigma Backends (Container Build)

The container build installs this curated backend set via [scripts/install_plugins.sh](scripts/install_plugins.sh):

- `pysigma-backend-splunk`
- `pysigma-backend-elasticsearch`
- `pysigma-backend-opensearch`
- `pysigma-backend-microsoft365defender`
- `pysigma-backend-crowdstrike`
- `pysigma-backend-loki`
- `pysigma-backend-secops`
- `pysigma-backend-chronicle` (optional; may be skipped if unavailable/incompatible)
- `pysigma-backend-insightidr`
- `pysigma-backend-qradar`
- `pysigma-backend-sentinelone`
- `pysigma-backend-carbonblack`

Note: installed packages and convert targets are related but not always identical naming. To see effective targets exposed by this service, call `sigma.backends.list`.

## Local Run

```bash
cd sigma-jsonrpc
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.sample .env
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## Tests

```bash
cd sigma-jsonrpc
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -p 'test_*.py'
```

## Docker Compose Run

```bash
cd sigma-jsonrpc
cp .env.sample .env
docker compose up --build
```

Service will be available at `http://localhost:8080/`.

## GHCR Tagged Images

This repository publishes container images to GHCR for tagged releases (`v*.*.*`) via GitHub Actions.

Image reference pattern:

- `ghcr.io/<owner>/<repository>:<version>`

Examples:

```bash
docker pull ghcr.io/<owner>/<repository>:2.1.0
docker pull ghcr.io/<owner>/<repository>:2.1
docker pull ghcr.io/<owner>/<repository>:2
```

You can also use image tags directly in your compose files instead of local builds.

```yaml
services:
  sigma-jsonrpc:
    image: ghcr.io/<owner>/<repository>:2.1.0
    ports:
      - "127.0.0.1:8080:8080"
```

## Authentication

`/jsonrpc` uses Bearer token authentication according to configuration:

- `SIGMA_AUTH_REQUIRED=true`
- `SIGMA_RPC_TOKEN=<token>`

If no `SIGMA_RPC_TOKEN` is defined in `.env` (or environment), the service allows requests without authentication.

Expected header:

```text
Authorization: Bearer <token>
```

Modes:

- Recommended secure mode:
  - `SIGMA_AUTH_REQUIRED=true`
  - `SIGMA_ALLOW_INSECURE_WITHOUT_TOKEN=false`
  - `SIGMA_RPC_TOKEN` must be set
- Insecure development mode:
  - `SIGMA_AUTH_REQUIRED=true`
  - `SIGMA_ALLOW_INSECURE_WITHOUT_TOKEN=true`
  - no token configured

## CI Quality Gates and PR Requirements

GitHub Actions workflows in this repository:

- `.github/workflows/ci.yml`: unit tests and syntax gates for pull requests and `main`.
- `.github/workflows/release-ghcr.yml`: tagged image publishing to GHCR.

To block merges when tests fail, enable branch protection in GitHub and require the `Quality Gates` status check.

## Allowlists

Allowed backends:

- `SIGMA_ALLOWED_BACKENDS=splunk,es-qs,eql,cortexxdr`

Allowed pipelines (optional):

- `SIGMA_ALLOWED_PIPELINES=windows,crowdstrike`

If `sigma.convert` receives a target or pipeline outside the allowlist, it returns a clear RPC error.

## Environment Variables

- `PORT` (default `8080`)
- `LOG_LEVEL` (default `INFO`)
- `SIGMA_BINARY` (default `sigma`)
- `SIGMA_COMMAND_TIMEOUT` (default `20`)
- `MAX_RULE_SIZE_BYTES` (default `131072`)
- `SIGMA_DISCOVERY_CACHE_TTL_SECONDS` (default `60`)
- `SIGMA_AUTH_REQUIRED` (default `true`)
- `SIGMA_ALLOW_INSECURE_WITHOUT_TOKEN` (default `true`)
- `SIGMA_RPC_TOKEN` (no default)
- `SIGMA_ALLOWED_BACKENDS` (default empty = no restriction)
- `SIGMA_ALLOWED_PIPELINES` (default empty = no restriction)

## HTTP Endpoints

The home page (`GET /`) is internationalized for:

- `en` (English)
- `es` (español)
- `fr` (français)
- `it` (italiano)
- `pt` (português)
- `de` (deutsch)
- `ru` (русский)

Language can be selected from the top combo box or forced with the query parameter:

- `/?lang=en`
- `/?lang=es`
- `/?lang=fr`
- `/?lang=it`
- `/?lang=pt`
- `/?lang=de`
- `/?lang=ru`

If the browser language is unsupported, the UI defaults to English (`en`).

## Interface Screenshots

Home page:

![sigma-jsonrpc home](docs/sigma-jsonrpc-home.png)

Live converter panel:

![sigma-jsonrpc live converter](docs/sigma-jsonrpc-example.png)

### `GET /health`

Response:

```json
{
  "status": "ok",
  "service": "sigma-jsonrpc",
  "version": "2.0.0",
  "sigma_available": true
}
```

### `GET /version`

Response:

```json
{
  "service": "sigma-jsonrpc",
  "version": "2.0.0"
}
```

## cURL Examples

### rpc.discover

```bash
curl -X POST http://localhost:8080/jsonrpc \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer CHANGE_ME" \
  -d '{"jsonrpc":"2.0","id":"1","method":"rpc.discover","params":{}}'
```

### sigma.backends.list

```bash
curl -X POST http://localhost:8080/jsonrpc \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer CHANGE_ME" \
  -d '{"jsonrpc":"2.0","id":"2","method":"sigma.backends.list","params":{}}'
```

### sigma.pipelines.list

List pipelines compatible with a specific backend:

```bash
curl -X POST http://localhost:8080/jsonrpc \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer CHANGE_ME" \
  -d '{"jsonrpc":"2.0","id":"2b","method":"sigma.pipelines.list","params":{"target":"splunk"}}'
```

### sigma.convert

```bash
curl -X POST http://localhost:8080/jsonrpc \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer CHANGE_ME" \
  -d '{"jsonrpc":"2.0","id":"3","method":"sigma.convert","params":{"target":"splunk","pipeline":"splunk_windows","rule":"title: Test Rule\nlogsource:\n  category: process_creation\ndetection:\n  selection:\n    Image|endswith: '\''\\\\cmd.exe'\''\n  condition: selection"}}'
```

If your backend supports it and you want to force conversion without a pipeline:

```bash
curl -X POST http://localhost:8080/jsonrpc \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer CHANGE_ME" \
  -d '{"jsonrpc":"2.0","id":"3b","method":"sigma.convert","params":{"target":"splunk","without_pipeline":true,"rule":"title: Test Rule\nlogsource:\n  category: process_creation\ndetection:\n  selection:\n    Image|endswith: '\''\\\\cmd.exe'\''\n  condition: selection"}}'
```

## Sigma indicator to STIX bundle

This endpoint translates a STIX 2.1 Indicator with `pattern_type: "sigma"` into a STIX Bundle containing the original Sigma indicator, derived indicators for each target backend, and `derived-from` relationships between them.

### `POST /api/translate/sigma-bundle`

```bash
curl -sS -X POST http://localhost:8080/api/translate/sigma-bundle \
  -H "Authorization: Bearer ${SIGMA_RPC_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
  "indicator": {
    "type": "indicator",
    "id": "indicator--22222222-2222-4222-8222-222222222222",
    "name": "Sigma process creation example",
    "description": "Source Sigma rule",
    "pattern_type": "sigma",
    "pattern": "title: Suspicious Cmd\nlogsource:\n  category: process_creation\ndetection:\n  selection:\n    Image|endswith: '\''\\\\cmd.exe'\''\n  condition: selection",
    "confidence": 80
  },
  "targets": ["splunk", "eql"],
  "without_pipeline": true
}'
```

### `sigma.indicator.bundle` (JSON-RPC)

```bash
curl -sS -X POST http://localhost:8080/jsonrpc \
  -H "Authorization: Bearer ${SIGMA_RPC_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"sigma.indicator.bundle","params":{"indicator":{"type":"indicator","id":"indicator--22222222-2222-4222-8222-222222222222","name":"Sigma process creation","pattern_type":"sigma","pattern":"title: Suspicious Cmd\ndetection:\n  selection:\n    Image|endswith: '\''\\\\cmd.exe'\''\n  condition: selection","confidence":80},"targets":["splunk"]}}'
```

### Request fields

| Field | Required | Description |
|-------|----------|-------------|
| `indicator` | yes | STIX Indicator object with `pattern_type: "sigma"` |
| `indicator.type` | yes | Must be `"indicator"` |
| `indicator.pattern_type` | yes | Must be `"sigma"` |
| `indicator.pattern` | yes | Non-empty Sigma YAML rule |
| `targets` | yes | List of backend targets (e.g. `["splunk", "eql"]`) |
| `pipelines` | no | Optional mapping `{"<target>": "<pipeline>"}` |
| `without_pipeline` | no | Default `true` |
| `include_source` | no | Default `true` — include the source Sigma indicator in output |
| `upstream_objects` | no | Optional array of STIX objects to preserve (for chaining) |

### Response

```json
{
  "type": "bundle",
  "spec_version": "2.1",
  "id": "bundle--<uuid>",
  "objects": [
    {
      "type": "indicator",
      "spec_version": "2.1",
      "id": "indicator--22222222-2222-4222-8222-222222222222",
      "name": "Sigma process creation example",
      "description": "Source Sigma rule",
      "pattern_type": "sigma",
      "pattern": "title: Suspicious Cmd\n...",
      "confidence": 80,
      "labels": ["sigma-jsonrpc", "source", "sigma"]
    },
    {
      "type": "indicator",
      "spec_version": "2.1",
      "id": "indicator--<uuid>",
      "name": "Sigma process creation example [splunk]",
      "description": "Source Sigma rule\n\nSTIX Indicator automatically generated from the source Sigma rule.",
      "pattern_type": "splunk",
      "pattern": "converted_splunk",
      "confidence": 80,
      "labels": ["sigma-jsonrpc", "auto-generated", "splunk"],
      "x_sigma_jsonrpc_target": "splunk",
      "x_sigma_jsonrpc_engine": "sigma-cli"
    },
    {
      "type": "relationship",
      "spec_version": "2.1",
      "id": "relationship--<uuid>",
      "relationship_type": "derived-from",
      "source_ref": "indicator--<derived-uuid>",
      "target_ref": "indicator--22222222-2222-4222-8222-222222222222",
      "confidence": 80
    }
  ]
}
```

### Error handling

- `401` — missing or invalid Bearer token
- `400` — invalid payload, unsupported `pattern_type`, empty `pattern`, empty `targets`
- `200` with `"status": "error"` — all conversions failed
- `200` with `x_sigma_jsonrpc_conversion_errors` — partial conversion failures

### Chaining with SPUC

This endpoint is designed to chain with SPUC's `/api/translate/stix-bundle`:

1. SPUC receives a STIX Pattern indicator → returns a bundle with a derived Sigma indicator
2. Extract the Sigma indicator from SPUC's bundle
3. Send it to sigma-jsonrpc's `/api/translate/sigma-bundle`
4. The output bundle can include `upstream_objects` from SPUC's bundle
5. The full chain: `STIX Pattern <- Sigma <- Splunk/EQL/Elastic` via `derived-from` relationships

Note: `derived-from` expresses transformation lineage, not semantic equivalence. If a conversion loses fidelity, that should be reflected in `description`, `confidence`, or `x_*` fields.

### sigma.validate

```bash
curl -X POST http://localhost:8080/jsonrpc \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer CHANGE_ME" \
  -d '{"jsonrpc":"2.0","id":"4","method":"sigma.validate","params":{"rule":"title: Test Rule\nlogsource:\n  category: process_creation\ndetection:\n  selection:\n    Image|endswith: '\''\\\\cmd.exe'\''\n  condition: selection"}}'
```

## Implementation Notes

- Engine logic is encapsulated in `SigmaEngine` (subprocess + sigma-cli).
- External calls use configurable timeout values.
- No `shell=True` usage.
- Inputs (`target`/`pipeline`/`format`) are validated using allowlists and a safe regex.
- Plugin discovery includes robust table parsing and in-memory TTL caching.
- If `sigma-cli` capabilities vary by version, the service keeps a stable RPC contract and returns clear engine errors.

## SPUC Default Remote Discovery

By default, SPUC now tries to reach a Sigma JSON-RPC service at:

- `http://localhost:8080/jsonrpc`

This fallback is used when `SIGMA_RPC_URL` is not set and is intentionally probed with a short timeout.

## Using this Service from AI Tools (with or without MCP)

You can use this repository directly as a machine tool through JSON-RPC without MCP.

- Direct integration: call `POST /jsonrpc` from your AI orchestrator.
- MCP integration: optional; create a thin MCP adapter that maps MCP tools to JSON-RPC methods.

See full integration guidance:

- [docs/AI_MCP_USAGE.md](docs/AI_MCP_USAGE.md)

## Podman Troubleshooting

If `podman-compose up` fails with errors such as:

- `name "pod_sigma-jsonrpc" is in use`
- `container name ... is already in use`

clean stale resources and start again:

```bash
cd sigma-jsonrpc
podman-compose down
podman pod rm -f pod_sigma-jsonrpc || true
podman rm -f sigma-jsonrpc || true
podman-compose up --build
```

Notes:

- This compose file no longer pins `container_name`, which reduces name collisions.
- The service command explicitly binds Uvicorn to port `8080`.

## License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0).
See the full license text in [COPYING](COPYING).
