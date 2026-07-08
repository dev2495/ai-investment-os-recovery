---
type: workflow_evidence
tags:
  - ai-os
  - client-data
  - transaction-ledger
  - dashboard
created: 2026-07-01
---

# Attached Client Transaction Import - 3081282

## Status

Imported and modeled.

## Source Files

- `/Users/devarshthakkar/Downloads/3081282_Transactions (1).xls`
- `/Users/devarshthakkar/Downloads/3081282_Transactions.xls`
- `/Users/devarshthakkar/Desktop/option log.xlsx`

## Warehouse Tables

- `client_data.attached_transaction_files`
- `client_data.attached_broker_transactions`
- `client_data.attached_option_log_transactions`

## Read Models

- `client_data.v_attached_client_trade_ledger`
- `client_data.v_attached_client_positions_by_symbol`
- `client_data.v_client_3081282_trade_timeline`
- `client_data.v_client_3081282_symbol_dates`
- `client_data.v_client_3081282_dashboard_summary`

## Evidence

Broker files for client `3081282` imported `1,696` rows from `2026-02-01` to `2026-06-30`.

Old option log imported `531` rows from `2019-06-18` to `2020-07-06`. Those rows do not belong to client `3081282`; the visible option-log client codes are separate historical accounts:

- `3010617.0`: `140` rows
- `3011648.0`: `122` rows
- `3016743.0`: `94` rows
- `3011043.0`: `60` rows
- `3010106.0`: `47` rows
- `3018050.0`: `36` rows

Client `3081282` dashboard summary:

- Ledger rows: `1,696`
- Symbols: `47`
- Gross buy amount: `26254754.4071`
- Gross sell amount: `24376699.5204`
- Open symbol rows: `14`

## Browser Dashboard

Static dashboard:

`/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime/dashboards/client_3081282_transactions/index.html`

The dashboard has:

- Summary cards
- Symbol-level first/last buy and sell dates: `103` grouped rows
- Full broker trade timeline
- Separate old option-log client summary
- Recent old option-log rows

Embedded dashboard payload verification:

- Summary metrics: `7`
- Symbol date rows: `103`
- Broker timeline rows: `1,696`
- Option-log client buckets: `9`
- Recent option-log rows: `300`

## Commands

```bash
/Users/devarshthakkar/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 _ai_os_runtime/scripts/ingest_attached_transactions.py
/Users/devarshthakkar/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 _ai_os_runtime/scripts/build_client_transaction_dashboard.py
```

## Next

- Add p2 cursor extraction for exact buy/sell history across all clients.
- Link broker client IDs to internal client master records.
- Add realized/unrealized P&L once holdings/current prices are connected.
- Expose this read model through MCP as a read-only client ledger tool.
