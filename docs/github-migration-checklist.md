# GitHub repository migration checklist

No item in this checklist is authorized by the consolidation branch itself.

- Record the final Music, Music integration, Media integration, and monorepo SHAs.
- Export repository bundles and verify they contain branches and tags.
- Record open PRs, issues, milestones, releases, discussions, and default branch.
- Record Actions variables, secret names, environments, required checks, and rulesets without exporting secret values.
- Record GHCR package names, tags, digests, retention rules, and consumers.
- Record deploy keys, webhooks, GitHub Apps, Dependabot configuration, badges, clone URLs, and documentation links.
- Pass the monorepo strict gate and retain its test/audit artifacts.
- Obtain explicit approval before renaming `Music_Downloader` to `FoxDen_Media`.
- Update remotes, package paths, badges, documentation, Caddy links, and automation after the rename.
- Keep `Media_Downloader` available during rollback validation.
- Archive it only after production acceptance; delete it only under a separate deletion approval.
