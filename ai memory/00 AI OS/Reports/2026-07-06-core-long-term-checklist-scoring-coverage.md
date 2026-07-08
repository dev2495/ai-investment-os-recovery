# Core Long-Term Checklist Scoring Coverage

Date: 2026-07-06
Owner: Long-Term Investing Office
Status: Done and verified

## What Changed

Expanded the source-backed structured checklist engine from two modules to the full core Long-Term checklist set currently installed for USHAMART.

Covered modules:

- `business_model`
- `moat_scorecard`
- `industry_structure`
- `management_scorecard`
- `governance_scorecard`
- `capital_allocation`
- `financial_quality`
- `forensic_accounting`

Each module now writes:

- checklist status
- numeric score
- structured checklist JSON
- item-level questions
- matched source terms
- evidence snippets
- negative/red-flag terms if present
- no-action guardrails

## Source Base

Primary source used:

- Usha Martin Annual Report 2024-25
- Official URL: `https://ushamartin.com/public/upload/investorrelations/annual-report-d-2024-25.pdf`
- Source document id: `1`
- Extraction id: `1`
- Pages: `172`
- Extracted chars: `1,020,683`

## Code Updated

File:

```text
_ai_os_runtime/scripts/execute_long_term_specialist_assignment.py
```

Added:

- structured rules for industry, management, governance, capital allocation, financial quality, and forensic accounting
- negative-term handling
- mitigated-negative detection for phrases like `moving away from`
- red-flag item status propagation
- structured score persistence to `portfolio.holding_thesis_checklists`

## Verification Commands

Compile:

```bash
python3 -m py_compile _ai_os_runtime/scripts/execute_long_term_specialist_assignment.py
```

Rerun assignments:

```bash
python3 _ai_os_runtime/scripts/execute_long_term_specialist_assignment.py --assignment-id 3 --actor "Industry Analyst"
python3 _ai_os_runtime/scripts/execute_long_term_specialist_assignment.py --assignment-id 4 --actor "Management Analyst"
python3 _ai_os_runtime/scripts/execute_long_term_specialist_assignment.py --assignment-id 5 --actor "Management Analyst"
python3 _ai_os_runtime/scripts/execute_long_term_specialist_assignment.py --assignment-id 6 --actor "Management Analyst"
python3 _ai_os_runtime/scripts/execute_long_term_specialist_assignment.py --assignment-id 7 --actor "Financial Statement Analyst"
python3 _ai_os_runtime/scripts/execute_long_term_specialist_assignment.py --assignment-id 8 --actor "Forensic Accounting Agent"
```

All six reruns returned:

- `source_status = source_ready`
- `output_status = needs_review`
- `missing_sources = []`
- `capital_action_allowed = false`
- `live_execution_allowed = false`

## Final Checklist Score Table

Database proof from `portfolio.v_long_term_thesis_checklists` for holding thesis `2`:

| Checklist | Status | Score | Owner |
|---|---:|---:|---|
| business_model | needs_review | 97.5 | Company Analyst |
| moat_scorecard | needs_review | 97.5 | Company Analyst |
| industry_structure | needs_review | 100.0 | Industry Analyst |
| management_scorecard | needs_review | 100.0 | Management Analyst |
| governance_scorecard | needs_review | 95.0 | Management Analyst |
| capital_allocation | needs_review | 92.5 | Management Analyst |
| financial_quality | needs_review | 92.5 | Financial Statement Analyst |
| forensic_accounting | needs_review | 77.5 | Forensic Accounting Agent |

Snapshot proof:

```json
[
  {"key":"business_model","status":"needs_review","score":97.5,"has_structured":true},
  {"key":"capital_allocation","status":"needs_review","score":92.5,"has_structured":true},
  {"key":"financial_quality","status":"needs_review","score":92.5,"has_structured":true},
  {"key":"forensic_accounting","status":"needs_review","score":77.5,"has_structured":true},
  {"key":"governance_scorecard","status":"needs_review","score":95.0,"has_structured":true},
  {"key":"industry_structure","status":"needs_review","score":100.0,"has_structured":true},
  {"key":"management_scorecard","status":"needs_review","score":100.0,"has_structured":true},
  {"key":"moat_scorecard","status":"needs_review","score":97.5,"has_structured":true}
]
```

## Corrected False Positive

The first industry run produced a red flag because the negative matcher saw `regional silos`. In context, the annual report says the company is `moving away from regional silos`, which is not a negative signal.

Fix:

- Added mitigated-negative detection for phrases including `moving away from`, `reduced`, `reducing`, `absence of`, `no material`, `without`, and `resolved`.
- Reran industry assignment.
- Final `industry_structure` status is `needs_review`, score `100.0`, no red-flag items.

## Latest Output Notes

- `ai memory/02 Portfolio/Long-Term Specialist Outputs/20260706T091002Z-ushamart-industry-structure.md`
- `ai memory/02 Portfolio/Long-Term Specialist Outputs/20260706T090920Z-ushamart-management-scorecard.md`
- `ai memory/02 Portfolio/Long-Term Specialist Outputs/20260706T090921Z-ushamart-governance-scorecard.md`
- `ai memory/02 Portfolio/Long-Term Specialist Outputs/20260706T090921Z-ushamart-capital-allocation.md`
- `ai memory/02 Portfolio/Long-Term Specialist Outputs/20260706T090921Z-ushamart-financial-quality.md`
- `ai memory/02 Portfolio/Long-Term Specialist Outputs/20260706T090921Z-ushamart-forensic-accounting.md`

## Remaining Gaps

- These scores are deterministic source-evidence scores, not final investment ratings.
- Forensic score is lower because related-party/notes evidence is still shallow and should be parsed from the financial-statement notes section directly.
- Valuation, bear case, portfolio fit, and risk review modules still need their own structured workflows.
- Committee memo should now be upgraded to consume these structured checklist rows directly.

## Checklist Updated

Marked complete:

- Source-backed structured scoring for core Long-Term checklist modules.
- Build source-backed structured scoring for core Long-Term checklist modules.

