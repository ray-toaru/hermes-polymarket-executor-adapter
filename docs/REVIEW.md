# Control Plane Review — v0.3

## Improved

- Python models match public OpenAPI schema field sets.
- Python validation rejects non-canonical decimals and invalid prices/quantities.
- Admin methods require admin token locally.
- Client exposes no signing, raw CLOB, or database methods.

## Remaining risks

- Client is still handwritten. Static parity checks reduce drift but do not eliminate it.
- Runtime HTTP behavior depends on Rust executor tests not yet executed.

## Next step

After API stabilizes, generate this client from OpenAPI rather than maintaining it by hand.
