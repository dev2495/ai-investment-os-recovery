# Runtime Scripts

Planned scripts:

- `apply_sql_file.py`: apply checked-in SQL migrations to the running Postgres container.
- `index_obsidian_vault.py`: parse notes, links, tags, and frontmatter into `knowledge.*`.
- `ingest_trade_journals.py`: parse old trade journals into `trading.trade_journals`.
- `ingest_old_trading_dbs.py`: copy/read old SQLite trading DBs into staging.
- `ingest_filings.py`: collect NSE/BSE/global filings into `research.corporate_filings`.
- `ingest_news_social.py`: collect curated news/social items into `market.*`.
- `create_qdrant_collections.py`: create vector collections and register chunks.
- `inventory_sources.py`: metadata-only source inventory for p2 cursor archive and old algo system.
- `p2cursor_extract_candidates.py`: safely extracts only data-shaped p2cursor files into quarantine.
- `p2cursor_profile_candidates.py`: profiles quarantined p2cursor candidates without printing raw client rows.
- `register_p2cursor_profiles.py`: registers p2cursor candidate metadata in `client_data.source_files`.
- `ingest_p2cursor_csv_staging.py`: stages p2cursor CSV rows as raw JSONB for Data Steward mapping.
- `inventory_source_components.py`: extracts/registers reusable source components and requirements from p2cursor and old algo software.
- `ingest_algo_sqlite.py`: imports old algo SQLite accounts, positions, trades, journals, signals, ticks, daily bars, ideas, and backtests into the warehouse.
- `writeback_obsidian_note.py`: write approved agent outputs to the vault.

All scripts should default to read-only source access and write only inside `_ai_os_runtime` or approved Obsidian output folders.
