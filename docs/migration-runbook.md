# Existing deployment migration runbook

This runbook does not authorize a live cutover. Commands default to dry-run.

## 1. Inventory

Record image versions, container names, UID/GID, bind mounts, filesystem types,
free space, reverse-proxy routes, and application versions. Generate a
content-free path inventory:

```bash
python scripts/migration.py inventory --env production.env --output reports/inventory.json
python scripts/migration.py readiness --env production.env --mode full-managed --output reports/readiness.json
```

Separately record qBittorrent categories, tags, save paths, incomplete paths,
active seeding, and Gluetun's provider, endpoint, DNS, firewall, and port-forward
behavior. Do not copy credentials into the report.

## 2. Backup rehearsal

Use copied synthetic state first. The backup command refuses execution without
an explicit writer-stop confirmation:

```bash
python scripts/migration.py backup --env rehearsal.env --destination /safe/backups
python scripts/migration.py backup --env rehearsal.env --destination /safe/backups --writers-stopped --execute
python scripts/migration.py verify /safe/backups/foxden-state-TIMESTAMP.tar.gz
python scripts/migration.py restore-rehearsal /safe/backups/foxden-state-TIMESTAMP.tar.gz --destination /isolated/restore --execute
```

The archive includes Portal, Music, Movies/TV, qBittorrent, and Gluetun configuration roots
that exist in the environment file, plus a SHA-256 sidecar. Media libraries and
torrent payloads should normally be reused in place and protected by a separate
storage snapshot rather than copied through this small-state archive.

## 3. Staged validation

1. Restore copied state into isolated paths.
2. Keep production containers running while isolated testing uses only copied
   databases/configuration and synthetic media.
3. Verify Music schema startup, queue/history counts, single-recording imports,
   album completeness, and Jellyfin refresh configuration.
4. Verify qBittorrent torrent count, categories, tags, trackers, save paths,
   fastresume state, and paused/active status without announcing real torrents.
5. Confirm qBittorrent uses `network_mode: service:gluetun`, has no independent
   port or network, and cannot egress while the VPN fixture is unhealthy.
6. Test Portal login, module routing, permissions, restart persistence, and
   unavailable-module behavior.

## 4. Live cutover gate

After separate approval: stop Music workers and qBittorrent first, confirm no
writer remains, make a final consistent backup/storage snapshot, then start the
new stack against the preserved paths. Never run old and new qBittorrent against
the same appdata or torrent directory concurrently.

## 5. Rollback

Stop every new writer. Restore the verified configuration archive and storage
snapshot, restore the prior ownership and bind mounts, then start the original
Gluetun before the original qBittorrent. Start the original Music services only
after its database is restored. Validate torrent counts, seeding paths, Music
history, and Jellyfin access before reopening ingress.

If an application performs an irreversible SQLite migration, rollback requires
restoring the pre-cutover database; never point the old binary at the migrated
database.
