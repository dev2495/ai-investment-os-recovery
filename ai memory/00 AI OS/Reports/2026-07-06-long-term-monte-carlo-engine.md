# Long-Term Monte Carlo Simulation Engine

Date: 2026-07-06
Owner: Long-Term Office / Quant Risk Analyst
Runtime: `_ai_os_runtime`
Checklist: [[AI Investment OS - Master Build Checklist v6.0]]
Status: verified engine slice

## What Changed

Built the real Long-Term Monte Carlo engine for holding theses.

The engine now:

- runs deterministic seeded simulations,
- stores run history in Postgres,
- updates the existing `long_term_monte_carlo` valuation model row,
- updates thesis-level `monte_carlo_payload`,
- writes a memo back into Obsidian,
- registers an MCP/tool-layer entry,
- exposes runs through the live API snapshot,
- exposes a POST API action,
- shows Monte Carlo runs in the AI Office Long-Term dashboard panel.

It does not approve buy/sell/hedge/live execution.

## Files Added Or Changed

Added:

```text
_ai_os_runtime/postgres/init/067_long_term_monte_carlo_engine.sql
_ai_os_runtime/scripts/run_long_term_monte_carlo.py
ai memory/02 Portfolio/Long-Term Monte Carlo/20260706T115307Z-ushamart-monte-carlo.md
```

Changed:

```text
_ai_os_runtime/api/ai_os_api_server.py
_ai_os_runtime/ai-office-ui/src/api/live.ts
_ai_os_runtime/ai-office-ui/src/App.tsx
ai memory/00 AI OS/Roadmap/AI Investment OS - Master Build Checklist v6.0.md
```

Because the live API is launchd-managed from:

```text
/Users/devarshthakkar/Library/Application Support/AIOS/service/api/ai_os_api_server.py
```

the updated API file was synced there too. The service still reports the SSD runtime root:

```text
/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime
```

## Database Objects

Migration:

```bash
python3 _ai_os_runtime/scripts/apply_sql_file.py postgres/init/067_long_term_monte_carlo_engine.sql
```

Result:

```text
CREATE TABLE
CREATE INDEX
CREATE INDEX
CREATE INDEX
CREATE VIEW
INSERT 0 1
UPDATE 3
```

Created:

```text
portfolio.long_term_monte_carlo_runs
portfolio.v_long_term_monte_carlo_runs
```

Registered tool:

```text
ai_os_run_long_term_monte_carlo
owning_agent: Quant Risk Analyst
permission_level: write_with_approval
enabled: true
```

## Engine Method

Method:

```text
fundamental_driver_monte_carlo_v1
```

Main sampled drivers:

- revenue growth distribution,
- terminal PAT margin distribution,
- terminal valuation multiple distribution,
- annual dilution/buyback distribution,
- annual volatility for drawdown paths,
- source-quality haircut.

Outputs:

- terminal price percentiles,
- CAGR percentiles,
- max drawdown percentiles,
- final value index percentiles,
- probability of negative CAGR,
- probability of permanent loss over 30 percent,
- probability of doubling or better,
- probability of 30 percent drawdown.

Guardrail:

- if the starting valuation multiple is operator-provided without source reference, run status remains `needs_review`.

## Usha Martin Run

Command:

```bash
python3 _ai_os_runtime/scripts/run_long_term_monte_carlo.py --holding-thesis-id 2 --actor "Quant Risk Analyst" --horizon-years 5 --simulations 5000 --seed 20260706 --starting-multiple 35 --terminal-multiple-low 12 --terminal-multiple-base 18 --terminal-multiple-high 28 --annual-volatility 0.32
```

API smoke command:

```bash
curl -s -X POST http://127.0.0.1:8765/api/portfolio/long-term-thesis/monte-carlo -H 'Content-Type: application/json' -d '{"holding_thesis_id":2,"actor":"Quant Risk Analyst","horizon_years":5,"simulations":1000,"seed":20260707,"starting_multiple":35}'
```

Latest API-created run:

```json
{
  "run_id": 3,
  "symbol": "USHAMART",
  "run_status": "needs_review",
  "median_cagr": -0.0412,
  "negative_cagr_probability": 0.753,
  "note_path": "ai memory/02 Portfolio/Long-Term Monte Carlo/20260706T115307Z-ushamart-monte-carlo.md",
  "warnings": [
    "Starting valuation multiple was provided without a source reference; committee review must validate it before treating the run as complete."
  ]
}
```

Latest database proof:

```json
{
  "runs": 3,
  "latest": {
    "id": 3,
    "symbol": "USHAMART",
    "run_status": "needs_review",
    "simulation_count": 1000,
    "seed": 20260707,
    "probability_summary": {
      "negative_cagr_probability": 0.753,
      "drawdown_30pct_probability": 0.768,
      "double_or_better_probability": 0.0,
      "permanent_loss_30pct_probability": 0.322
    }
  },
  "valuation": {
    "model_key": "long_term_monte_carlo",
    "status": "needs_review",
    "latest_run_id": "3"
  }
}
```

## API Evidence

Health:

```json
{
  "ok": true,
  "runtime_root": "/Volumes/Devarsh SSD/Obsidian memory /_ai_os_runtime",
  "tradingview_cdp": {
    "available": true,
    "port": 9222
  }
}
```

Snapshot check:

```json
{
  "snapshot_mc_count": 3,
  "latest_run_id": 3,
  "latest_status": "needs_review",
  "valuation_latest_run": 3,
  "issues": []
}
```

## Obsidian Memo Evidence

Latest memo:

```text
ai memory/02 Portfolio/Long-Term Monte Carlo/20260706T115307Z-ushamart-monte-carlo.md
```

Memo markers:

```text
Method: fundamental_driver_monte_carlo_v1
Start price: 502.4
Starting multiple: 35.0 on pat_proxy
Median CAGR: -0.0412
Negative CAGR probability: 0.753
Source extractions: 1
```

## UI Evidence

AI Office UI now has a Long-Term panel section:

```text
Monte Carlo runs
```

Frontend build:

```bash
npm run build
```

Result:

```text
tsc && vite build
49 modules transformed
built successfully
```

## Checklist Updates

Marked complete:

- `[x] Long-term Monte Carlo module.`
- `[x] Long-term Monte Carlo simulation engine.`
- `[x] Build Long-Term Monte Carlo simulation engine.`

Still open:

- Reverse DCF workflow.
- Scenario builder with bull/base/bear probabilities.
- Full Long-Term Office definition of done.
- Sourced starting multiple/share-count/current market-cap reference for Usha Martin.
- Committee review before any capital action.

## Next Build Slice

The next correct build is the Symbol Intelligence page:

- aggregate every exposure by symbol,
- show Long-Term/Tactical/Quant/Active Trading books separately,
- show purpose and thesis/setup per book,
- link latest valuation, Monte Carlo, checklist, news, filings, strategy signals, and committee status,
- flag cross-book conflicts,
- make Charlie able to answer: "What should I do with this symbol today?"

