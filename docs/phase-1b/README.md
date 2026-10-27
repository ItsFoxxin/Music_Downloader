# Phase 1B integration notes

Status: in progress on Fox Den Media 0.4.1

## First integration slice

Movies/TV now implements the versioned `GET /api/platform/v1/summary` contract.
The endpoint reports only:

- module ID, name, and release version;
- worker health with a bounded generic summary;
- boolean availability for requests, library, acquisition, and browser features.

It does not query request, job, import, torrent, or library records. Activity is
an empty list until authenticated Portal-to-module requests are implemented.
Tests create deliberately private records and prove that titles, source URLs,
magnet data, tracker tokens, host paths, and application credentials are absent.

This keeps the initial endpoint no more sensitive than a conventional service
health/capability response while allowing the real Movies/TV process to validate
against Portal contract v1.

## Next approval boundary

Activity summaries and unified module navigation require a trusted ingress and
identity path. Before adding them, approve:

1. dedicated ingress versus extending the existing gateway process;
2. HS256 contract v1 versus asymmetric internal assertion signing;
3. the canonical same-origin Movies/TV route;
4. which activity fields may cross the module boundary.

No production Compose, gateway routing, NAS state, Music source, or application
database migration is changed by this slice.
