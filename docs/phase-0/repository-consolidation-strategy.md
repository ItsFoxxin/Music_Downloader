# Repository consolidation strategy

Status: Proposed; no repository operation authorized

## Recommendation

Use Music_Downloader as the canonical Git lineage, then rename it to FoxDen_Media after the independent Music work reaches a stable checkpoint.

Do not use Media_Downloader as the canonical base because its music subtree is older. Do not create the final repository by copying two working trees together because that discards useful lineage and makes provenance ambiguous.

## Why rename Music_Downloader

A GitHub rename retains the existing repository object, branches, tags, issues, releases, and pull-request context. Git operations targeting the old URL are normally redirected, but local remotes should still be updated.

Important exceptions and follow-up work:

- calls to a GitHub Action hosted by the renamed repository are not redirected;
- GitHub Pages project URLs are an exception;
- old names must not be reused because that can break redirects;
- badges, raw links, webhooks, deployment integrations, reusable workflows, CODEOWNERS references, package associations, and external documentation still require an audit;
- GHCR packages are account-scoped and associated with repositories independently, so image names and permissions must be deliberately selected and tested rather than assumed to follow the repository rename.

## Preconditions

Before rename or history import:

1. Independent Music work has a reviewed stable checkpoint.
2. Its current draft PR is merged or deliberately closed, not carried unknowingly through a major path migration.
3. Dev/main/default-branch policy is decided.
4. All current branch heads, tags, releases, open issues/PRs, Actions workflows, environments, secrets names, branch rules, webhooks, deploy keys, Pages settings, and package links are inventoried.
5. Backup bundles and bare mirrors of both repositories are created and verified.
6. Source heads are tagged or otherwise recorded:
   - authoritative Music source commit;
   - Media unique-source commit;
   - Phase 0 documentation commit.
7. A dry-run rename and history import is rehearsed in temporary repositories.
8. The target name FoxDen_Media and image names are approved.
9. No production deployment pulls moving repository artifacts during the maintenance operation.

## Filtered Media history

Use a fresh mirror or bare clone of Media_Downloader.

Create a deterministic filtered branch that:

- excludes music/ at every imported revision;
- excludes generated files, populated configuration, secrets, database files, browser profiles, media, downloads, and deployment state;
- retains Movies/TV application history;
- retains relevant gateway, browser-handoff, qBittorrent/Gluetun, tests, documentation, and infrastructure history;
- moves retained paths into a collision-free import namespace before merging;
- writes a source-to-filtered commit mapping and records the original Media dev head.

Recommended staging namespace:

- legacy-import/media-downloader/app
- legacy-import/media-downloader/infra
- legacy-import/media-downloader/docs
- legacy-import/media-downloader/tests

After the unrelated histories are merged on a dedicated migration branch, reviewed moves place the canonical files under apps/media, infra/gateway, deploy, docs, and tests/integration. The temporary namespace makes accidental overwrites obvious.

The original repository remains the authoritative location for original commit SHAs. Rewritten filtered commits retain authors, dates, and messages where the filter permits.

## Branch and rename sequence

Recommended sequence:

1. Complete Phase 1 Portal/contracts work in Media_Downloader without touching Music.
2. Complete the independent Music release gate.
3. Create verified bare mirrors and repository-setting inventories.
4. Create monorepo/bootstrap from the approved Music stable checkpoint.
5. Rehearse path relocation of Music into apps/music using history-preserving moves.
6. Produce and review the Media filtered-history branch.
7. Merge filtered history into monorepo/bootstrap with unrelated histories explicitly allowed.
8. Resolve path ownership using the source ownership map; never take imported music content.
9. Add Portal/contracts work from the approved Media commit.
10. Run full repository, contract, and deployment-mode gates.
11. Rename Music_Downloader to FoxDen_Media only after the bootstrap branch is reviewable and rollback is prepared.
12. Update remotes, workflows, links, packages, settings, and documentation.
13. Merge through the approved branch process.
14. Retain Media_Downloader unchanged until deployment migration and an observation period pass.
15. Archive or mark legacy repositories only under a later explicit approval.

Alternative: rename after bootstrap merges. This reduces rename-time uncertainty but temporarily develops the monorepo under the Music_Downloader name. The final sequencing choice remains an approval decision.

## Acceptance gates

### Provenance gate

- authoritative Music commit and Media source commit recorded;
- music excluded from filtered Media history;
- no credentials, appdata, databases, downloads, browser profiles, or media imported;
- author/date/message preservation report produced;
- source-to-filtered commit mapping stored;
- repository mirrors verified.

### Source gate

- one active Music implementation under apps/music;
- one Media implementation under apps/media;
- Portal and contracts have explicit owners;
- no duplicate module package or route names;
- module tests pass from their new paths;
- generated dependency and build contexts resolve only canonical paths.

### Repository gate

- branch strategy, default branch, protections, environments, secrets names, issue templates, Dependabot, CODEOWNERS, Actions permissions, Pages, webhooks, and release permissions reviewed;
- open PRs have an explicit disposition;
- old remote redirect tested;
- references to hosted actions under the old name updated;
- package/image association and pull permissions tested;
- no old-name reuse.

### Runtime gate

- all deployment modes render and pass preflight;
- Portal works with every combination of disabled/unhealthy modules;
- no database format changes occur merely because source moved;
- no production mount or path is used in CI;
- ingress, auth, browser, qBittorrent, and VPN boundaries match ADR 0002.

## Rollback

Before canonical rename:

- abandon the bootstrap branch and restore from verified mirrors; neither original repository changes.

After canonical rename but before merge:

- rename back only if redirects, integrations, and package effects have been inventoried and the reversal is approved;
- restore repository settings from inventory;
- do not create a new repository at the old name.

After merge but before deployment:

- revert the merge or reset only through a reviewed recovery branch; preserve the merged history for audit;
- existing production continues using old artifacts and is unaffected.

Production cutover rollback is a separate later plan. Repository consolidation must not be coupled to NAS migration.
