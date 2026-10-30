# Recovery and backups

- Stop the project before making a consistent copy of the **entire** music and
  movie/TV config directories; SQLite WAL files belong with their databases.
- Preserve your original music `.env`, appdata, and previous image/source before
  upgrading. Never commit the populated environment or private keys.
- Movie/TV source files remain in staging after import, including after failures.
- A failed validation leaves the library unchanged. Resolve its error and validate
  again. A failed import can be retried after checking its destination.
- A server restart marks active jobs interrupted. Published imports with matching
  receipts are registered and checksum-audited on startup; incomplete hidden
  directories stay under `.imports` for inspection. Do not blindly retry or delete
  directories without reviewing the corresponding job and final destination.
- If publication succeeded but recording the result failed without a process
  restart, check the destination receipt and database before retrying. The current
  automatic recovery handles interrupted jobs, not every possible database outage.
- `Verify library` marks missing or changed imported files as `issues found`.
  It never repairs, deletes, or replaces files. Restore from a known-good source
  through a separately reviewed operation.
- Atomic directory publication requires a supported local Windows/Linux filesystem.
  Network shares and unsupported rename implementations are not deployment-tested.
- Rollback: stop the new project, preserve its changed data, and restore the saved
  previous project/config state. Do not use `docker compose down -v` or prune data.
