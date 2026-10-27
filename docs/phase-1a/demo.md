# Portal mock demonstration

Phase 1A never contacts live modules or identity providers.

Install the Portal development dependencies, then provide three unrelated demo
secrets without committing them:

    PORTAL_SECRET_KEY=<random 32+ characters>
    PORTAL_INTERNAL_ASSERTION_SECRET=<different random 32+ characters>
    PORTAL_BOOTSTRAP_SECRET=<third random 32+ characters>

Run:

    python portal/scripts/demo.py

Open http://127.0.0.1:8020. Claim the initial administrator with the bootstrap
secret. The dashboard shows a healthy mocked Music module and an unhealthy mocked
Movies/TV module plus one sanitized activity item from each adapter. No real
module, database, NAS path, provider, or credential is used.

To demonstrate failure isolation, stop and restart the process or use the automated
module tests, which exercise offline, timeout, invalid, unhealthy, recovery,
Music-only, Movies-only, Full, and zero-module configurations.
