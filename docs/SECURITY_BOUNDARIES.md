# Executor Adapter Security Boundaries

The Python project must never contain or request:

- private keys
- Polymarket CLOB API secrets
- HMAC preimages
- raw signed order payloads
- direct database credentials for executor writes

The only executor credentials are service/admin API tokens.

Admin token usage must be explicit and should not silently fall back to service token.

Assistant-facing tools must remain separate from executor authority. The
assistant-v0 safe session contract may validate local drafting, review, dry-run,
and status tools, but it must reject tool names that imply signing, posting live
orders, canceling live orders, direct CLOB access, direct executor database
writes, secret creation, fund transfer, or approval granting.
