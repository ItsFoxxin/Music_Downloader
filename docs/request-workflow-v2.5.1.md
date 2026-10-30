# Fox Den Music v2.5.1 - single-recording release support

## What changed

A track request and an album request now have different completeness rules:

- Spotify track, artist/song, and MusicBrainz recording requests expect exactly
  the requested MusicBrainz recording.
- The selected release still supplies canonical album title, artist, date,
  artwork, disc/track position, track total, and MusicBrainz identifiers.
- Extra tracks on that edition, such as an instrumental B-side, are not required
  and are not silently imported.
- Spotify album, artist/album, and MusicBrainz release requests still require the
  complete selected edition.
- If the requested recording is missing from or repeated in an edition, the
  request stops for review instead of guessing.

No new accounts, secrets, paths, or environment variables are required.

## Manual regression test

1. On **Add music**, request a Spotify track or exact MusicBrainz recording whose
   release contains the vocal track plus an instrumental.
2. Resolve and confirm the metadata. On the request detail page, verify **Import
   scope** says **Requested recording only** and **Expected tracks** says one.
3. Download only the requested vocal track. Do not download the instrumental.
4. Let the server watcher detect it, or use the manual upload fallback.
5. Confirm validation reports one expected and one acquired track. With automatic
   import disabled, review and approve the import.
6. Open the final file in Jellyfin or a tag inspector. Confirm the title,
   artist, album, year, release ID, recording ID, original track number, and full
   edition track total are retained.
7. Repeat with the instrumental instead of the requested recording. Confirm the
   request stops for review or fails metadata/fingerprint validation.
8. As a guardrail, submit the MusicBrainz **release** link for the same two-track
   edition and upload only one file. Confirm Fox Den still rejects it as
   incomplete.

## Validation boundaries

Automated tests cover manifest scoping and the importer selection of one
recording from a multi-track edition. GitHub CI covers Linux regression tests,
the installable wheel, the deployment image, real-audio suites, browser
viewports, and dependency auditing. A real provider download and NAS/Jellyfin
import still require the manual test above.
