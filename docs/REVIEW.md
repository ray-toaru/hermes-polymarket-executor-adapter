# Executor Adapter Review — v0.3

## Improved

- Python models match public OpenAPI schema field sets.
- Python validation rejects non-canonical decimals and invalid prices/quantities.
- Admin methods require admin token locally.
- Client exposes no signing, raw CLOB, or database methods.
- Hermes plugin tools now expose the adapter through native Hermes tool
  registration without adding signing, CLOB, or database authority.
- Admin plugin tools are split into their own toolset and gated on admin token
  availability.

## Remaining risks

- Client is still handwritten. Static parity checks reduce drift but do not eliminate it.
- Runtime HTTP behavior depends on Rust executor tests and current evidence from
  the pinned execution-engine submodule.
- Plugin tests use local fake contexts. A local Hermes profile now also
  validates runtime entry-point discovery and toolset visibility, but full
  end-to-end executor calls still require a running executor API.

## Next step

After API stabilizes, generate this client and Hermes schemas from OpenAPI rather
than maintaining them by hand.
