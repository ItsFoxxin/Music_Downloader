# Consolidation record

This branch preserves Music Downloader as the canonical first-parent lineage.
Authoritative Music was relocated to `apps/music` from integration commit
`85904c45a79421cd4a1e00378c231bb08c1a03fc`, which includes release security
fix `c0443de55d3d5f83ef051d79e923539c95860f39`.

Media Downloader head `9656a0cc653659a92e48c9c2cc81e2c53344ed60`
was rewritten in a disposable clone. The `music/` subtree was removed from
every commit before the histories were joined. Twenty-one original commits map
one-to-one to twenty-one rewritten commits; author name, email, author date, and
subject were compared before import. The rewritten head is
`5e5c6c5a4dcb2d86eff3e3a0057214c7020ac808`.

See `media-commit-map.csv` for the complete mapping.

The original repositories, branches, releases, PRs, and production deployment
were not renamed, merged, deleted, or deployed as part of this operation.
