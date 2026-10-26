# ADR 0001: Versioned cross-repository Fox Den architecture

- Status: Superseded by ADR 0002
- Original decision date: 2026-10-26
- Superseded date: 2026-10-26
- Original option: Option C with contract-only Option D

This ADR is retained as decision history. It proposed separate Media_Downloader and Music_Downloader repositories with Media consuming a versioned Music image.

The product direction changed after review. Fox Den Media will instead become a modular monorepo with an independent Portal and separate runtime processes. See ADR 0002.

No implementation of ADR 0001 removed the bundled Music tree, changed Compose, migrated a database, or changed a deployment.
