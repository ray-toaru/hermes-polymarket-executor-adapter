# Control Plane Security Boundaries

The Python project must never contain or request:

- private keys
- Polymarket CLOB API secrets
- HMAC preimages
- raw signed order payloads
- direct database credentials for executor writes

The only executor credentials are service/admin API tokens.

Admin token usage must be explicit and should not silently fall back to service token.
