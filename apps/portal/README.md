# Fox Den Portal foundation

Phase 1A provides an isolated Portal with local authentication, optional OIDC,
Portal-owned SQLite state, mocked module contracts, and failure-isolated module
status aggregation. It is not connected to the production gateway or Compose
stack.

See `docs/phase-1a` for architecture, threat model, demo, and Authentik setup.
The language-neutral v1 module and identity contracts live in `contracts/v1`.
