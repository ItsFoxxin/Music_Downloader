# Fox Den Music v2.5.0 - automated music requests

## What changed

- The shared **Request Music** form accepts `Artist - Song`, artist/album
  searches, artist requests, Spotify track/album/playlist links, and
  MusicBrainz recording/release links.
- The worker resolves requests to a persisted MusicBrainz manifest containing
  artist, release/recording IDs, edition details, ordered expected tracks,
  durations, ISRCs, and preferred quality.
- Spotify Client Credentials are optional and metadata-only. Without them,
  Spotify requests pause in `WAITING_FOR_USER`; no scraping fallback is used.
- Playlists follow all Spotify API pages and become independent child track
  requests, so one failure does not invalidate siblings.
- Provider adapters support a configured contained-browser handoff and a
  request-scoped filesystem drop. Provider URLs, credentials, paths, format,
  thresholds, and policy are environment-backed.
- Every request owns `/staging/acquisitions/<id>` and `/downloads/<id>`.
  Contained Firefox finishes files at the top of `/downloads`; with only one
  browser request active, the worker first routes the settled file into that
  request's private directory, then the request-scoped watcher stages it.
  Existing inbox checks reject `.part`, `.tmp`, `.crdownload`, undersized,
  unsettled, unsupported, and unsafe archive input.
- The Stage 1 importer remains the only route to `/music`. It still performs
  archive protection, ffprobe inspection, tag normalization, duplicate checks,
  no-overwrite handling, prepared-album verification, atomic publication, and
  Jellyfin refresh.
- A request-specific validation record exposes codec, duration, bitrate,
  sample rate, channels, hashes, duplicate status, track-count agreement, and
  confidence reasons. Optional `fpcalc` + AcoustID evidence is fail-closed for
  automatic import policy.
- Automatic importing is `false` by default. The worker pauses after validating
  the prepared album and before atomic publication. Approval reruns validation.
- Ambiguous/no-result searches expose a form for an exact MusicBrainz recording
  or release link, which clears stale resolution evidence and safely requeues
  only that request.

## Configuration

Copy `.env.example` to `.env` and set at least:

```dotenv
MUSICBRAINZ_CONTACT=you@example.com
MUSIC_REQUEST_PROVIDER=MANUAL_BROWSER
MUSIC_REQUEST_PROVIDER_URL=https://your-configured-provider.example/
MUSIC_REQUEST_AUTO_IMPORT=false
```

For Spotify link metadata, create a Spotify developer application and add its
Client Credentials. Those credentials do not grant audio access:

```dotenv
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
```

For an external service that deposits completed files without a browser:

```dotenv
MUSIC_REQUEST_PROVIDER=FILESYSTEM_DROP
DOWNLOAD_INBOX_PATH=/your/host/request-downloads
DOWNLOAD_INBOX_DIR=/downloads
```

Place each request's completed output in `/downloads/<request-id>`. Never place
provider output directly in the final music library.

Optional fingerprints require `fpcalc` in the worker image and, for remote
matching, an AcoustID application key:

```dotenv
CHROMAPRINT_ENABLED=true
FPCALC_PATH=fpcalc
ACOUSTID_API_KEY=
```

The stock image has not been changed to install `fpcalc`; leave this disabled
unless your derived worker image includes it.

## Manual acceptance test

1. Back up `/config`, set the v2.5.0 variables, rebuild, and start the web and
   worker services. Do not delete the existing SQLite database; schema 2 is
   upgraded additively to schema 3.
2. Open **Add music**, choose **Album**, and enter a known `Artist - Album`.
   Confirm the request shows `REQUESTED`, then `RESOLVING`, and a manifest.
3. Submit a MusicBrainz release URL. Confirm the exact release reaches 100%
   resolution confidence and lists ordered expected tracks and durations.
4. Submit a Spotify playlist with metadata credentials configured. Confirm all
   API pages are read, the parent completes, and independently tracked child
   requests are created.
5. Open one resolved request. Confirm it pauses for the contained browser,
   opens only the configured provider URL, and never claims to solve a CAPTCHA.
6. Download a valid file. Confirm partial files remain ignored, the completed
   file moves into request staging, and the request enters `VALIDATING`.
7. Confirm codec, duration, bitrate, sample rate, channels, track-count,
   duplicate, and confidence evidence appears. With the default policy, verify
   the request stops at `NEEDS_REVIEW` before anything appears in `/music`.
8. Approve it. Confirm validation reruns, the complete album is atomically
   published, the request records its final location, and Jellyfin refresh
   status is visible.
9. Repeat with a wrong edition, live/remaster variant, incomplete album,
   undersized file, `.part` file, unsafe ZIP, and duplicate. Confirm these are
   reviewed, ignored, rejected, or skipped without overwriting library files.

## Evidence boundaries

The local milestone tests exercise parsing, exact MusicBrainz manifests,
request persistence/state changes, request-scoped provider handoffs,
fingerprint adapters, schema migration, and existing importer regressions with
controlled data. GitHub CI builds the image and runs the layered `dev` gate;
the stricter `main` gate adds Linux hard-link/symlink checks, real ffmpeg audio
imports, coverage, browser viewports, and dependency auditing. CI does not prove
a real provider account, CAPTCHA handoff, phone/browser networking, NAS mounts,
Jellyfin credentials, or production deployment. Those remain manual acceptance
tests, and this release is not deployed by CI.
