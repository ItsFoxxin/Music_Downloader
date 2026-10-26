# Music preservation and monorepo migration criteria

Status: Revised Phase 0 contract  
Music_Downloader remains independently owned until consolidation gates pass.

## Authoritative source

Music_Downloader dev at the approved independent release checkpoint is the only Music implementation source.

Media_Downloader music is excluded. It may be referenced only to identify integration behavior that Media currently supplies around Music.

## Behavior to preserve during path migration

- Music web and worker commands and separation.
- Web exclusion from the writable Music library.
- Worker ownership of Music import and scanning.
- secure archive and audio validation.
- MusicBrainz resolution, tagging, year and identifier behavior.
- request workflow, acquisition adapters, browser handoff, and server inbox.
- single-track and complete-release semantics.
- duplicate detection, no-overwrite behavior, and atomic publishing.
- schema migration, job/event/import history, library inventory, and interrupted-job recovery.
- optional Jellyfin refresh with retryable failure.
- non-root/read-only container hardening, health checks, and stop behavior.
- documented environment variables and secret-file behavior.
- frontend assets, responsive browser behavior, accessibility checks, and tests.

## Integration behavior to preserve from Media

- authenticated same-origin browser routing in integrated mode;
- upload buffering and long timeout behavior;
- browser websocket forwarding;
- shared platform navigation and session behavior, moved to Portal ownership;
- Compose mount contracts and health dependencies that remain valid;
- full-stack CI coverage;
- safe human interaction for login, CAPTCHA, consent, and selection.

Movies/TV authentication is not preserved as the platform authority. Portal replaces that responsibility.

## Migration gates

### Independent Music gate

- active bug-fix work completed under its own review;
- dependency audit passes;
- dev/release CI is green;
- version, schema, environment contract, release notes, and rollback requirements are recorded;
- exact authoritative commit approved.

### Path-move gate

- verified repository mirror exists;
- migration branch starts at the authoritative commit;
- history-preserving moves place code under apps/music;
- no generated data, credentials, media, or local environment enters the repository;
- imports/build contexts/workflows/docs update mechanically;
- old and new test results are compared;
- no schema migration occurs because of the move.

### Portal integration gate

- Music exposes versioned health/capability/activity endpoints without secrets or host paths;
- integrated identity assertions are validated;
- Music Only does not require Movies/TV;
- Portal unavailability does not grant unauthenticated module access;
- Portal handles Music unavailable/disabled without failure;
- direct database access is absent.

### Deployment gate

- Music Only and Full modes pass environment, preflight, container, gateway, browser, database-copy, and filesystem fixtures;
- existing variables remain compatible;
- no production database or NAS path is used;
- manual NAS/provider/Jellyfin evidence remains separately labeled.

## Release model after consolidation

Music no longer requires a separately maintained product repository. It remains a separately built process/image within the monorepo.

The platform release pins the Music image produced from the same commit. Music schema and contract versions remain independently visible for migration and diagnostics.

Historical standalone releases and their upgrade paths remain documented.
