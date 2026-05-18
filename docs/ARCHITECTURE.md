# sigma-jsonrpc architecture

This document describes the repository internals and request flow.

## High-level design

The service exposes one main API:

- JSON-RPC over HTTP at POST /jsonrpc

And three operational endpoints:

- GET /
- GET /health
- GET /version

Main modules:

- app/main.py: application wiring and startup.
- app/config.py: environment-based settings.
- app/auth.py: JSON-RPC bearer-token enforcement.
- app/routes/jsonrpc.py: JSON-RPC transport and protocol behavior.
- app/rpc.py: method dispatch and domain-level error mapping.
- app/engine.py: sigma-cli interaction, plugin/target/pipeline discovery, validation, conversion.
- app/routes/http.py: home page, health/version HTTP endpoints, and `/api/translate/sigma-bundle`.
- app/sigma_bundle.py: STIX bundle translation logic (models, normalization, conversion evaluation, bundle assembly).

## Request lifecycle (JSON-RPC)

1. HTTP request arrives at POST /jsonrpc or POST /api/translate/sigma-bundle.
2. app/auth.py validates Authorization header according to current settings.
3. JSON body is parsed and validated against JSON-RPC 2.0 schema.
4. app/rpc.py dispatches method call to one of:
   - rpc.discover
   - sigma.plugins.list
   - sigma.backends.list
   - sigma.pipelines.list
   - sigma.validate
   - sigma.convert
5. app/engine.py executes sigma-cli command safely using subprocess without shell=True.
6. Response is encoded as JSON-RPC success or error payload.

## Engine behavior details

- list_backends tries sigma list targets first (fast path), then falls back to plugin parsing.
- list_pipelines can filter by target and caches results.
- validate_rule uses sigma validate, with fallback to a safe conversion command for sigma-cli variants.
- convert_rule validates identifiers and allowlists, writes rule to a temporary file, and returns normalized metadata.

## Caching model

The engine caches:

- plugins list
- backends list
- pipeline list (global and per target)

Cache TTL is configured by SIGMA_DISCOVERY_CACHE_TTL_SECONDS.

## Configuration model

Configuration is loaded from environment variables (and .env file by default) via pydantic-settings.

Important security-related settings:

- SIGMA_AUTH_REQUIRED
- SIGMA_RPC_TOKEN
- SIGMA_ALLOW_INSECURE_WITHOUT_TOKEN
- SIGMA_ALLOWED_BACKENDS
- SIGMA_ALLOWED_PIPELINES

## Error model

JSON-RPC protocol errors:

- -32700 Parse error
- -32600 Invalid Request
- -32601 Method not found
- -32602 Invalid params
- -32603 Internal error

Server extension errors:

- -32001 authentication failed
- -32010 sigma engine error
- -32011 sigma timeout
- -32012 input size error
