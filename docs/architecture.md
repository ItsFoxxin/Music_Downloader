# Architecture

```text
Browser -> gateway :8000 -> media :8010       /transfers/
                       -> music web :8000   /
                       -> download-browser  /server-browser/

media -> qBittorrent Web API (server-side credentials)
media -> read-only torrent staging -> isolated copy -> media/Movies or media/TV
music web -> music SQLite/staging -> music worker -> music library
```

The gateway checks a media session before serving music or its browser. The media
login/static page is public; its API requires the same cookie or a bearer token.
Movie/TV jobs use a dedicated SQLite database in `MEDIA_CONFIG_PATH`, never the
music database. One durable queue is consumed by one background thread in one
media Uvicorn process. qBittorrent HTTP calls are serialized with a session lock.

## State and import protocol

Jobs move from `queued` to `running` to `succeeded` or `failed`. Process restarts
mark running jobs `interrupted`; queued jobs remain queued. An interrupted import
with a matching published receipt is reconciled and audited on restart. Other
interrupted jobs are not automatically replayed.

Validation results contain source-relative filenames, stat signatures, hashes,
media metadata/decode results, excluded files, and explicit caveats. Imports refer
to a successful validation job, check the torrent again when linked, and reject
source stat changes before copying. The copy must hash to the reviewed SHA-256.

Each import is assembled under `/media/.imports/<unique-job-id>`, including its
receipt. Only after all files pass does it become `/media/Movies/<name>` or
`/media/TV/<name>`. Windows uses its no-replace rename behavior; Linux requires
`renameat2(RENAME_NOREPLACE)`. Unsupported kernels/filesystems fail closed.

Ordinary failures remove only that job's unpublished temporary directory. A crash
can leave a hidden temporary directory for manual review. The source is never
removed. Database insertion follows publication; the on-disk receipt supports
reconciliation if the process dies in that interval.

## Mount mapping example

| View | Configured path |
| --- | --- |
| NAS host downloads | `TORRENT_STAGING_PATH=/srv/downloads` |
| qBittorrent save root | `QBIT_DOWNLOAD_ROOT=/downloads` |
| Fox Den read-only root | `/staging` |
| qBittorrent file | `/downloads/finished/Movie/movie.mkv` |
| Fox Den source | `/staging/finished/Movie/movie.mkv` |
| Reviewed destination | `/media/Movies/Movie (2026)/movie.mkv` |

Sources outside the configured qBittorrent root, relative traversal, Windows
device paths, symlinks/junctions, nonregular files, empty files, incomplete torrents,
and case-conflicting names are rejected. The configured storage directories must
be controlled by trusted administrators; this is not a hostile multi-tenant
filesystem sandbox. Do not let untrusted users replace parent directories while
imports run. Use a local filesystem with supported atomic rename behavior.

Movies/TV metadata identification, scanner refresh, torrent deletion, and source
cleanup are separate future features. A checksum audit detects byte changes; it
does not independently re-run a media decoder or compare against torrent piece hashes.
