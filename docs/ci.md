# Versioning and CI layers

`VERSION` contains the unified app's `MAJOR.MINOR.PATCH` release number. The API
and dashboard read it, and Docker copies it into the image. CI requires the media
image tag, README, and dated changelog entry to match. The bundled Music component
retains its separate version.

| Layer | Push/PR to dev | PR/push to master or main |
| --- | --- | --- |
| Version metadata and JavaScript syntax | Required | Required |
| Default/custom-port Compose topology and legacy compatibility | Required | Required |
| Media and Music tests with real FFmpeg fixtures | Python 3.12 | Python 3.12 and 3.13 |
| Dependency consistency (`pip check`) | Required | Required |
| JUnit test reports | Uploaded | Uploaded; no skipped cases allowed |
| Build media and Music images | Required | Required |
| Real container gateway, shared login/logout, API version, non-root users, read-only staging | Required | Required |
| Container full decode, reviewed import, checksum audit, overwrite refusal, source retention, restart persistence | - | Required |
| Version increase compared with stable target | - | Required |
| Aggregate `CI gate` | Required | Required |

Stable checks run on pull requests **before merging**, based on the target branch,
and again on pushes. Both stable names are covered because this repository currently
uses `main` while the planned stable branch was called `master`. No stable branch
is created or merged by CI. Use Actions -> Validate Fox Den Media -> Run workflow
with `strict` enabled to exercise stable-level tests on `dev` ahead of promotion.

Each job has a time limit; superseded runs are cancelled. Failed or skipped layers
fail the aggregate gate. Tests run on isolated temporary data and containers;
cleanup runs even on failure. CI never uses production paths or private VPN keys.
The container test intentionally excludes the real VPN, qBittorrent, and downloader
browser. Their live connectivity, killswitch, browser interaction, and real seeding
behavior remain deployment checks. CI does not deploy or merge code.

## Release procedure

1. Update `VERSION`, the media image tag in `compose.yaml`, README, and changelog.
2. Push to `dev`; require a green `CI gate` and review test reports.
3. Run the strict manual workflow on `dev` if desired, then open a stable PR.
4. Stable CI requires a version higher than the stable target and all strict checks.
5. Merge only after review and separately authorized deployment verification.

Configure a GitHub branch ruleset requiring **CI gate** and a pull request on the
stable branch to enforce merge blocking. The workflow supplies the check; it does
not itself enable repository branch protection. Repository settings have not been
changed by this update. Direct administrative pushes can otherwise bypass PR review.
