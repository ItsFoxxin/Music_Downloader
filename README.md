# Fox Den Media

Fox Den Media is a modular self-hosted media platform with one Portal, one
ingress boundary, and independently deployable Music and Movies/TV modules.
The repository preserves Fox Den Music as its canonical Git lineage and imports
the non-Music history from Media Downloader.

This branch is a production-readiness candidate. It does not deploy to a NAS or
modify existing application state.

Current platform milestone: **0.5.0**.

## Deployment modes

Copy the matching example from `deploy/examples`, replace every placeholder,
then validate before starting anything:

```bash
python scripts/foxden.py init --env .env
python scripts/foxden.py validate music --env .env
python scripts/foxden.py deploy music --env .env
```

Supported modes are `music`, `media`, `full-external`, and `full-managed`.
Add `--browser` to enable the optional contained Firefox service. `deploy`
prints the exact Compose command unless `--execute` is supplied.

See [deployment](docs/deployment.md), [migration rehearsal](docs/migration-runbook.md),
and the [GitHub migration checklist](docs/github-migration-checklist.md).

## Safety boundary

- Portal and ingress start independently of optional modules.
- Music and Movies/TV keep separate processes and databases.
- qBittorrent shares Gluetun's network namespace in managed mode.
- No application container receives the Docker socket.
- Jellyfin remains external in the first production migration.
- Production cutover requires a separate approval after backup and rollback
  evidence is reviewed.
