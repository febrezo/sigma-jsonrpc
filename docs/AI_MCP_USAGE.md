# Using sigma-jsonrpc from AI tools and MCP clients

This guide explains how an AI assistant can use this repository as a tool.

## Important concept

sigma-jsonrpc is already a machine-friendly tool interface because it exposes JSON-RPC 2.0 over HTTP.

That means:

- You do not need MCP to use it.
- MCP is optional glue if your AI platform prefers MCP tool contracts.

## Option A: direct JSON-RPC tool usage (recommended first)

Use POST /jsonrpc with methods:

- rpc.discover
- sigma.backends.list
- sigma.pipelines.list
- sigma.validate
- sigma.convert

Typical AI flow:

1. Call rpc.discover to learn capabilities and limits.
2. Call sigma.backends.list and sigma.pipelines.list to choose conversion target.
3. Call sigma.validate with user-provided Sigma rule.
4. Call sigma.convert with target and optional pipeline.
5. Return query text to user.

### Minimal request example

POST /jsonrpc
Content-Type: application/json
Authorization: Bearer <token>

{
  "jsonrpc": "2.0",
  "id": "convert-1",
  "method": "sigma.convert",
  "params": {
    "target": "splunk",
    "without_pipeline": true,
    "rule": "title: Example\nlogsource:\n  category: process_creation\ndetection:\n  condition: selection"
  }
}

## Option B: expose as MCP tool

If your AI platform requires MCP, create a thin MCP adapter server that:

1. Registers MCP tools mapping to JSON-RPC methods.
2. For each MCP tool call, forwards to /jsonrpc.
3. Maps JSON-RPC errors to MCP tool errors.

Suggested MCP tool names:

- sigma_discover -> rpc.discover
- sigma_list_backends -> sigma.backends.list
- sigma_list_pipelines -> sigma.pipelines.list
- sigma_validate_rule -> sigma.validate
- sigma_convert_rule -> sigma.convert

## Authentication strategy

For production AI integrations:

- Set SIGMA_AUTH_REQUIRED=true
- Set SIGMA_RPC_TOKEN to a strong random value
- Set SIGMA_ALLOW_INSECURE_WITHOUT_TOKEN=false

Then configure the AI adapter/client to send:

- Authorization: Bearer <SIGMA_RPC_TOKEN>

## Docker-first usage for AI stacks

Tagged images can be consumed in compose files:

services:
  sigma-jsonrpc:
    image: ghcr.io/<owner>/<repository>:2.1.0
    ports:
      - "127.0.0.1:8080:8080"
    environment:
      SIGMA_AUTH_REQUIRED: "true"
      SIGMA_ALLOW_INSECURE_WITHOUT_TOKEN: "false"
      SIGMA_RPC_TOKEN: "replace-me"

Then AI components call:

- http://sigma-jsonrpc:8080/jsonrpc (inside compose network), or
- http://localhost:8080/jsonrpc (from host).

## Reliability guidance for AI orchestration

- Always call rpc.discover at startup to detect enabled methods.
- Handle timeout error code -32011 with retries and backoff.
- Treat -32602 and -32012 as user-fixable input problems.
- Cache backends/pipelines responses for short periods to reduce discovery traffic.
