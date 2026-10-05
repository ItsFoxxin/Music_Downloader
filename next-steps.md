# Next steps

## Before a NAS release / stable-branch merge

- Build and start all images on the actual Linux Docker host; verify UID/group and
  bind permissions using the existing music and torrent configurations.
- Exercise shared login, music navigation/browser, and the qBittorrent API live.
- Import a small known-good completed torrent through validation, review, copy,
  and checksum audit; confirm the original still seeds.
- Confirm movie/TV folder conventions against the actual media server libraries.
- Inspect the live torrent/VPN settings before any optional stack consolidation.
- Verify rollback backups. Decide the stable branch name (`main` is the repository
  default; the requested eventual merge target was `master`).

## Follow-on product work

- Movie/TV identity matching and reviewed metadata/filename suggestions.
- Series-aware incremental episode imports into existing season folders while
  preserving no-overwrite behavior and crash recovery.
- Inventory and audit of pre-existing media, with an explicit baseline approval.
- Optional Jellyfin refresh for movie/TV imports, independently retryable.
- Optional hardlinks when source and destination share a filesystem and preserving
  shared inode semantics is explicitly acceptable.
- Per-file long-job progress/cancellation, paginated history, and duplicate-content
  comparison across libraries.
- Granular accounts/roles and coordinated per-session revocation if multi-user
  access is needed; current access is a shared administrator token with 8-hour sessions.

No automatic torrent deletion, source cleanup, or library replacement is planned
without a separate, explicit policy.
