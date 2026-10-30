# Movie and TV requests

Fox Den Media 0.3 adds a durable request inbox in front of the existing
qBittorrent validation and reviewed-import workflow.

## Request lifecycle

`waiting for user -> acquiring -> downloading -> validating -> needs review -> importing -> complete`

- A magnet request is submitted to qBittorrent immediately. Fox Den derives its
  info hash locally and never returns the magnet or tracker parameters through
  the browser API.
- A title or HTTP(S) metadata link is recorded as `waiting for user`. Add the
  matching download through qBittorrent, then attach that torrent from the
  Requests page. URL query strings and fragments are discarded before storage.
- Fox Den follows the attached torrent. When qBittorrent reports that every
  selected file is complete, the normal FFprobe/FFmpeg, stability, size, and
  SHA-256 validation job starts automatically.
- Successful validation pauses at `needs review`. The user still chooses the
  Movies or TV destination and approves the import. The existing verified,
  atomic, no-overwrite copy then runs and the request becomes `complete`.

## Deliberate safety boundary

Fox Den does not choose a torrent from a plain title. Torrent names, editions,
release groups, languages, and bundled files are not trustworthy enough to make
that choice without a metadata/indexer policy. This release automates everything
after a torrent is selected while keeping that selection visible.

A later resolver adapter can connect the inbox to an explicitly configured
request manager or indexer. It must preserve the current validation and review
states, and it must never bypass login or CAPTCHA challenges.

## Guided browser handoff

Version 0.4 adds **Guided browser** to title and metadata-link requests. The page
reuses Fox Den Music's authenticated Firefox/noVNC container, copies the request
text, and can navigate the visible browser to `MEDIA_BROWSER_HOME_URL`.

The administrator performs searches, login, consent, CAPTCHA, and result
selection. After adding the result to qBittorrent, return to Requests and attach
the matching torrent. The existing request worker handles completion, validation,
review, and import from that point.

The shared browser has its existing music-download inbox and browser-profile
mounts. It has no Movie/TV library, torrent-staging, media database, qBittorrent
credentials, Docker socket, or application secret mounts. The handoff does not
copy browser downloads into the Movie/TV library.
