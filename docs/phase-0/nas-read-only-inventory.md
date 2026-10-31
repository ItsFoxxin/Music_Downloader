# Existing NAS read-only inventory checklist

Status: Checklist only; no live NAS inspection has been performed or claimed.

## Safety rules

- Collect information read-only.
- Do not stop, restart, recreate, update, prune, rename, chmod, chown, move, or delete anything.
- Do not run Compose up, down, pull, build, or config migrations.
- Do not open a production database with a newer application.
- Do not copy secrets into tickets, logs, commits, or screenshots.
- Redact passwords, API keys, private keys, tokens, cookies, and magnet tracker passkeys.
- Record commands and timestamps used for collection.
- If a platform screen obscures an exact value, mark it unknown rather than infer it.

## Host and platform

- [ ] NAS vendor/model and operating-system version.
- [ ] CPU architecture.
- [ ] Docker Engine and Compose versions.
- [ ] Compose implementation supplied by the NAS, if vendor-modified.
- [ ] Available memory, CPU, and free space on config, staging, download, and library filesystems.
- [ ] Filesystem type and mount options for each host path.
- [ ] Snapshot/backup capability and available snapshot space.
- [ ] SELinux, AppArmor, rootless Docker, user namespaces, or vendor security restrictions.
- [ ] /dev/net/tun availability and permissions.
- [ ] Host timezone and NTP/time health.

## Deployment topology

For every relevant container:

- [ ] Container and Compose project/service name.
- [ ] Exact image name, tag, and digest.
- [ ] Created/start time and restart policy.
- [ ] Health status.
- [ ] Published ports and bind addresses.
- [ ] Docker networks, aliases, and network mode.
- [ ] User/UID/GID and supplemental groups.
- [ ] Capability additions/drops, devices, privileged status, and security options.
- [ ] Read-only root filesystem and tmpfs mounts.
- [ ] Bind mounts: host path, container path, and read/write mode.
- [ ] Named volumes, if any.
- [ ] Resource limits.
- [ ] Redacted environment-variable names and whether each is set; do not collect secret values.
- [ ] Secret/config file mount locations and modes.

Capture the exact effective Compose configuration only after arranging a redaction method that cannot print secret values.

## Music application

- [ ] Deployed Music application version, commit if known, and image digest.
- [ ] CONFIG_PATH and database filename.
- [ ] Database schema version using a read-only SQLite query.
- [ ] Database journal mode and presence of WAL/SHM files.
- [ ] Counts of jobs by state, acquisitions, imports, events, inventory tracks, albums, and artists.
- [ ] Active, queued, interrupted, failed, and needs-review jobs.
- [ ] STAGING_PATH and contents summary.
- [ ] DOWNLOAD_INBOX_PATH and partial/unprocessed file summary.
- [ ] MUSIC_PATH; verify the previously supplied /mnt/@usb/sdc2/Media/Music value rather than assuming it.
- [ ] /music/.imports existence, ownership, incomplete entries, and filesystem identity relative to the final Music path.
- [ ] Library size and file count without changing timestamps or tags.
- [ ] UID/GID, directory modes, ACLs, and umask.
- [ ] MusicBrainz/provider configuration presence, with values redacted where sensitive.
- [ ] Browser integration state and profile path.
- [ ] Jellyfin enablement, URL hostname only where safe, and key source location without key contents.
- [ ] Current backup mechanism and most recent verified restore test.

## Movies and TV application

- [ ] Deployed Media version and image digest.
- [ ] MEDIA_CONFIG_PATH and media.db location.
- [ ] Tables/columns and row counts through read-only queries.
- [ ] Jobs and requests by state.
- [ ] TORRENT_STAGING_PATH and its read/write mode in each container.
- [ ] Movies and TV host paths and corresponding container paths.
- [ ] Hidden .imports directories, incomplete imports, and receipts.
- [ ] Current validation/import failures needing reconciliation.
- [ ] UID/GID, modes, ACLs, and filesystem types.
- [ ] Atomic no-replace rename support or known filesystem limitations.

## qBittorrent

- [ ] Exact qBittorrent image, application version, and Web API version.
- [ ] Appdata host path and container path.
- [ ] Download host paths and exact qBittorrent container-side paths.
- [ ] Default save path and incomplete path.
- [ ] Categories and category-specific save paths.
- [ ] Torrent count by downloading, completed, seeding, paused, checking, and error state.
- [ ] Active seeding and forced-start state.
- [ ] BT_backup/resume-data location and size.
- [ ] Web UI bind address, port, allowed hostnames, HTTPS, CSRF, and authentication mode.
- [ ] Whether localhost authentication bypass is enabled and its scope.
- [ ] Existing reverse-proxy route, if any.
- [ ] Ownership/permissions of appdata and payloads.
- [ ] Whether payload paths contain symlinks or cross-filesystem mounts.
- [ ] Current backup and restore procedure.
- [ ] Do not export magnet URLs or tracker credentials into the inventory report.

## Gluetun and Proton VPN

- [ ] Exact Gluetun image digest and version.
- [ ] VPN service-provider and VPN type.
- [ ] WireGuard configuration and secret-file locations; never record the private key.
- [ ] Endpoint hostname/IP, port, interface address, and allowed IPs where safe.
- [ ] Firewall input/output settings.
- [ ] qBittorrent network namespace relationship.
- [ ] Port-forwarding enablement, assigned-port handling, and synchronization hooks.
- [ ] Public egress IP result and timestamp, without changing configuration.
- [ ] DNS behavior.
- [ ] Existing health status and recent redacted errors.
- [ ] Kill-switch behavior from existing documentation or prior test evidence; do not induce an outage during inventory.
- [ ] Config/appdata host paths, ownership, and backup method.

## Jellyfin

- [ ] Jellyfin version and deployment ownership.
- [ ] Existing Music, Movies, and TV library names.
- [ ] Jellyfin-side container mount paths for each host library.
- [ ] Whether paths will remain unchanged during Fox Den migration.
- [ ] API key source/owner and rotation plan; do not capture the key.
- [ ] Reverse-proxy URL and authentication dependencies.
- [ ] Current refresh behavior and last known successful Fox Den-triggered refresh.
- [ ] Jellyfin backup location and restore documentation.

## Reverse proxy and authentication

- [ ] Proxy product and version.
- [ ] Public/internal hostnames and path prefixes.
- [ ] TLS termination and certificate ownership.
- [ ] Forwarded headers and trusted-proxy configuration.
- [ ] Websocket support and timeout settings for the contained browser.
- [ ] Upload/body-size and timeout limits.
- [ ] Authentication provider, session lifetime, and logout behavior.
- [ ] Current Music, Media, browser, and qBittorrent exposure.
- [ ] Cookie secure, SameSite, path, and domain behavior.
- [ ] DNS/Tailscale/LAN dependencies, recorded without assuming they are required by the target architecture.

## Ownership and permissions

For every persistent host directory:

- [ ] Resolved absolute path.
- [ ] Filesystem/device identity.
- [ ] Owner UID/GID and group membership.
- [ ] POSIX mode and default ACL.
- [ ] Extended ACLs/xattrs where supported.
- [ ] Whether files are created with the expected owner from each container.
- [ ] Read/write requirements by service.
- [ ] Snapshot and backup inclusion.
- [ ] Symlinks, bind nesting, or overlapping roots.
- [ ] Available space and inode headroom.

## Backup readiness

- [ ] Music config and consistent SQLite backup.
- [ ] Media config and consistent SQLite backup.
- [ ] qBittorrent appdata and resume data.
- [ ] Gluetun configuration and separately protected WireGuard credentials.
- [ ] Compose, environment, secret references, and reverse-proxy configuration.
- [ ] Browser profile if session preservation is required.
- [ ] Library and torrent-payload snapshot/backup strategy.
- [ ] Ownership/ACL manifest.
- [ ] Image digests and prior deployment files needed for rollback.
- [ ] Backup checksums.
- [ ] Documented restore order and a safe place to rehearse it.

## Inventory output classification

Every collected item must be labeled:

- Verified live read-only observation;
- User-provided but not independently verified;
- Repository default, not necessarily deployed;
- Secret location recorded, value intentionally omitted;
- Unknown or requires maintenance-window testing.

Completion of this checklist authorizes analysis only. It does not authorize migration or cutover.
