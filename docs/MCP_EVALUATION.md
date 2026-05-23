# MCP Facade Evaluation

## Decision

Do not implement MCP as the first integration path. The primary integration is a
Hermes plugin because Hermes already provides a native plugin tool registry and
this adapter is a Python package with an existing typed executor client.

## Why Plugin First

- Fewer moving parts: no extra server process, transport, or lifecycle manager.
- The package can reuse `ExecutorClient`, Pydantic models, and local tests
  directly.
- Hermes can gate service/admin tools with its normal plugin and toolset model.
- The security boundary is easier to audit because tokens remain in the Hermes
  runtime environment and all calls pass through the executor API.

## When MCP Becomes Useful

MCP is worth adding if at least one of these becomes true:

- Non-Hermes agents need to reuse the same executor adapter tools.
- The executor adapter must run as an isolated external process.
- A remote tool server is required for deployment or governance.
- Dynamic cross-agent tool discovery is more valuable than native Hermes
  integration.

## Constraints for a Future MCP Server

A future MCP facade must:

- reuse the existing adapter client and Pydantic models
- expose the same service/admin split
- require explicit admin token configuration for admin tools
- return only redacted references and public executor API responses
- avoid signing, direct CLOB calls, executor DB writes, and secret-bearing data

The MCP facade must not become a second execution authority. It is only another
transport over this adapter's existing safe surface.
