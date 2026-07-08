# Long-Term Decision Modules - Valuation, Bear Case, Portfolio Fit, Risk

Date: 2026-07-06
Owner: Long-Term Office
Runtime: `_ai_os_runtime`
Checklist: [[AI Investment OS - Master Build Checklist v6.0]]
Status: verified workflow slice

## What Changed

The Long-Term Specialist execution workflow now produces structured decision modules for:

- valuation suite,
- bear case,
- portfolio fit,
- independent risk review.

These modules are source-backed and write to:

- `portfolio.v_long_term_specialist_outputs`,
- `portfolio.v_long_term_valuation_models`,
- Obsidian specialist output notes,
- the live API snapshot at `http://127.0.0.1:8765/api/snapshot`.

The valuation module is intentionally marked `needs_review`. It stores current price and source-backed assumption context, but it does not fabricate a fair value, DCF result, reverse DCF, expected CAGR, or Monte Carlo distribution before the real valuation engines exist.

## Code Evidence

Verified script:

```text
_ai_os_runtime/scripts/execute_long_term_specialist_assignment.py
```

Relevant implementation markers:

```text
def build_structured_decision_module(...)
source_backed_preliminary_valuation_context_v1
source_backed_bear_case_v1
portfolio_fit_source_context_v1
independent_risk_review_context_v1
structured_decision_score
structured_decision_red_flags
```

Compile check:

```bash
python3 -m py_compile _ai_os_runtime/scripts/execute_long_term_specialist_assignment.py
```

Result: passed.

## Runtime Evidence

Docker services:

```text
ai_os_postgres   Up 17 hours (healthy)
ai_os_redis      Up 17 hours (healthy)
ai_os_qdrant     Up 17 hours
```

API snapshot endpoint responded:

```text
http://127.0.0.1:8765/api/snapshot
```

## Source Evidence

Verified source document:

```json
{
  "id": 1,
  "symbol": "USHAMART",
  "document_type": "annual_report",
  "document_title": "Usha Martin Annual Report 2024-25",
  "raw_artifact_id": 134,
  "provenance_status": "verified",
  "note_path": "ai memory/05 Filings and Transcripts/Long-Term Source Documents/request-3-ushamart-annual-report-36c769d4e7e5.md"
}
```

Source extraction:

```json
{
  "id": 1,
  "source_document_id": 1,
  "extraction_status": "extracted",
  "page_count": 172,
  "extracted_chars": 1020683,
  "local_text_path": "_ai_os_runtime/artifacts/source_documents/long_term/source-document-1-ushamart-36c769d4e7e5.txt"
}
```

Market quote:

```json
{
  "symbol": "USHAMART",
  "price": 502.4,
  "provider": "TradingView",
  "quote_ts": "2026-07-02T19:50:01.031758+00:00",
  "source_key": "tradingview_scanner_quotes"
}
```

## Portfolio Context

Verified current Usha Martin rows:

```json
[
  {
    "display_name": "Naval",
    "account_code": "p2cursor_account_3",
    "symbol": "USHAMART",
    "exchange": "NSE",
    "quantity": 2800,
    "average_price": 99.82142857142857,
    "market_price": 502.4,
    "market_value": 1406720.0,
    "as_of": "2024-11-05T00:00:00+00:00"
  },
  {
    "display_name": "Tushit",
    "account_code": "tushit_3081282_statement",
    "symbol": "USHAMART",
    "exchange": "NSE",
    "quantity": 1000.00,
    "average_price": 83.98,
    "market_price": 492.55,
    "market_value": 492550.00,
    "as_of": "2026-06-30T18:30:00+00:00"
  }
]
```

## Specialist Output Evidence

Database output from `portfolio.v_long_term_specialist_outputs`:

```json
[
  {
    "module_key": "bear_case",
    "output_status": "needs_review",
    "source_status": "source_ready",
    "decision_score": "92",
    "decision_red_flags": "0",
    "note_path": "ai memory/02 Portfolio/Long-Term Specialist Outputs/20260706T091459Z-ushamart-bear-case.md"
  },
  {
    "module_key": "portfolio_fit",
    "output_status": "needs_review",
    "source_status": "source_ready",
    "decision_score": "85",
    "decision_red_flags": "0",
    "note_path": "ai memory/02 Portfolio/Long-Term Specialist Outputs/20260706T091459Z-ushamart-portfolio-fit.md"
  },
  {
    "module_key": "risk_review",
    "output_status": "needs_review",
    "source_status": "source_ready",
    "decision_score": "90",
    "decision_red_flags": "0",
    "note_path": "ai memory/02 Portfolio/Long-Term Specialist Outputs/20260706T091459Z-ushamart-risk-review.md"
  },
  {
    "module_key": "valuation_suite",
    "output_status": "needs_review",
    "source_status": "source_ready",
    "decision_score": null,
    "decision_red_flags": "0",
    "note_path": "ai memory/02 Portfolio/Long-Term Specialist Outputs/20260706T091445Z-ushamart-valuation-suite.md"
  }
]
```

Obsidian note markers:

```text
valuation_suite: Method `source_backed_preliminary_valuation_context_v1`, Status `needs_review`
bear_case: Method `source_backed_bear_case_v1`, Status `needs_review`, Score `92`
portfolio_fit: Method `portfolio_fit_source_context_v1`, Status `needs_review`, Score `85`
risk_review: Method `independent_risk_review_context_v1`, Status `needs_review`, Score `90`
```

## Valuation Model Rows

Rows in `portfolio.v_long_term_valuation_models` for thesis `2`:

```json
[
  "dcf",
  "expected_cagr",
  "historical_valuation",
  "long_term_monte_carlo",
  "peer_comparison",
  "reverse_dcf",
  "scenario_builder",
  "sum_of_parts"
]
```

All eight rows now carry:

```text
status: needs_review
current_price: 502.4
method: source_backed_preliminary_valuation_context_v1
```

This means valuation context is wired, but actual DCF/reverse DCF/scenario/Monte Carlo engines remain open checklist items.

## API Evidence

Filtered API snapshot returned:

```json
{
  "outputs": [
    {"module": "bear_case", "source_status": "source_ready", "output_status": "needs_review", "score": 92, "red_flags": 0},
    {"module": "portfolio_fit", "source_status": "source_ready", "output_status": "needs_review", "score": 85, "red_flags": 0},
    {"module": "risk_review", "source_status": "source_ready", "output_status": "needs_review", "score": 90, "red_flags": 0},
    {"module": "valuation_suite", "source_status": "source_ready", "output_status": "needs_review", "score": null, "red_flags": 0}
  ]
}
```

## Checklist Updates

Updated:

- `[x] Structured valuation, bear case, portfolio fit, and risk review workflows.`
- `[x] Finish Long-Term valuation, bear case, portfolio fit, and risk review workflows to verified checklist status.`

Not marked complete:

- Reverse DCF workflow.
- Scenario builder with bull/base/bear probabilities.
- Long-term Monte Carlo simulation engine.
- Full Long-Term Office definition of done.

## Next Build Slice

The next correct build step is the real Long-Term Monte Carlo simulation engine:

- define inputs from source-backed financial snapshot and valuation assumptions,
- store scenario distributions,
- run deterministic seeded simulations,
- persist output percentiles,
- write Monte Carlo memo to Obsidian,
- expose output in Long-Term Office dashboard,
- feed result into committee memo.

