# Layered GitHub Actions checks

This is CI, not automatic deployment. No NAS credentials, MusicBrainz account,
Jellyfin API key, or repository secrets are needed. The application version is
read from `backend/pyproject.toml`; CI validates version and Compose parity.

| Layer | Push/PR to dev | PR to main / push to main |
| --- | --- | --- |
| Python unit and regression tests on Linux | Required | Required |
| Dependency consistency, version/Compose parity, tracked-private-file checks | Required | Required |
| JavaScript syntax, Compose validation, Actions lint | Required | Required |
| Installable wheel package artifact | Required | Required |
| Actual Docker image build; non-root web/worker startup; packaged UI assets | Required | Required |
| Python 3.12 and 3.13 full suites, real FLAC upload/tag/import/duplicate test | — | Required |
| Minimum 78% line coverage | Report only | Required |
| Chromium and WebKit, desktop and phone layout; queue/start/cancel/upload | — | Required |
| Runtime dependency vulnerability audit | — | Required |

Stable required-check names: **Dev gate** and **Main gate**. Gate jobs run even
when prerequisite jobs fail and require every result to be `success`; a skipped,
cancelled, or failed prerequisite is not accepted. Workflow runs have timeouts,
read-only tokens, SHA-pinned actions, and cancellation of superseded runs. There
are no path filters that could leave a required check missing on a docs-only PR.
Merge queues are supported via `merge_group`.

The development path is deliberately ordered `Validation -> Tests -> Packaging
and container smoke -> Dev gate`. Main-only work starts after that gate, so a
release check never hides a failure in the cheaper development layers.
The 78% release floor matches the measured v2.5.0 baseline and should only move
up as coverage improves; it prevents future releases from silently regressing.

## Enable enforcement in GitHub (owner action)

Workflows alone report failures; branch rules make them block merging. The
connected GitHub integration cannot administer branch protection. No protection
changes are made by these files, and existing classic protection cannot be read
with this integration. Configure Settings → Rules → Rulesets (or Branches):

1. Target `dev`, require pull requests and **Dev gate** status check. This is the
   recommended future development flow: feature branch → PR → dev. Without a PR
   rule, direct dev pushes run CI only *after* the code has landed.
2. Target `main`, require pull requests, **Dev gate** and **Main gate**, and
   require branches to be up to date before merging (or use a merge queue).
3. Disable force pushes/deletion and avoid bypass actors for these rules.
4. Require resolved conversations. If another reviewer is available, require
   one approval and dismiss stale approvals. A solo owner cannot approve their
   own PR, so do not require an unavailable second reviewer.
5. Do not make the individually conditional release jobs required on `dev`.
   Only the gate names above should be required. Select GitHub Actions as source.

The first workflow push bootstraps CI on `dev`. Promote through a dev → main
PR when ready; this change does not merge older dev features into main.
The PR runs the strict checks *before* merging. A run on a direct main push is
only a post-push signal, not a way to undo an unsafe push.

## Running and diagnosing checks

Open Actions → Fox Den CI. For a manual full rehearsal, use Run workflow, choose
`dev`, and enable `strict`. GitHub may not expose the manual-run button until the
workflow is present on the default branch; the REST dispatch endpoint can be
used with a branch ref when GitHub permits it. A main-targeting PR is the normal
release gate. Never merge merely to make the manual-run UI appear.

Read the failed job first. Reports and screenshots are kept for 14 days.
Vulnerability findings block the main gate; update affected dependencies and
retest rather than suppressing the audit. Audit/network outages also fail closed.
Dependabot proposes weekly action-pin updates against `dev`.

Local equivalents (from the GitHub checkout, not the flat NAS ZIP):

```sh
python -m pip install -r backend/requirements-dev.txt
python -m pip install --no-deps -e backend
python ci/check_repository.py
python -m pytest backend/tests -m 'not integration'
python -m pip wheel --no-deps --wheel-dir dist ./backend
# Install ffmpeg and ffprobe first for the full suite:
python -m pytest backend/tests --cov=foxden_music --cov-fail-under=78
docker build -t foxden-ci:local backend
python ci/container_smoke.py
python -m pip install -r ci/requirements.txt
python -m playwright install --with-deps chromium webkit
python ci/browser_smoke.py
```

`check_test_report.py` permits only the two named Windows-only tests to skip on
Linux. Archive symlink and hard-link security tests must actually run there.
The real-audio test fails if ffmpeg/ffprobe are missing, rather than skipping.

## What a green run does not prove

MusicBrainz/Jellyfin HTTP behavior is covered with controlled tests, not live
production accounts. Browser CI stubs the remote viewer; it does not solve a
CAPTCHA or download from third parties. Container smoke uses the real application
image with isolated Docker volumes and no network; it does not boot the entire
Firefox/Nginx/NAS stack. Live provider, WebSocket, permission, NAS deployment,
and real-phone acceptance checks still belong in release testing.
