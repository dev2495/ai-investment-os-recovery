# Source-Backed Structured Checklist Scoring

Date: 2026-07-06
Owner: Company Analyst
Status: Done and verified

## What Changed

Upgraded the Long-Term specialist worker so source-ready outputs no longer stop at generic notes. The worker now converts extracted annual-report text into structured checklist items, evidence snippets, item scores, module score, and checklist-row persistence.

This is deterministic source-backed scoring, not an LLM opinion. Each checklist item must be supported by extracted text snippets from a registered source document.

## Modules Covered

Implemented first structured rule sets for:

- `business_model`
- `moat_scorecard`

Both currently use:

```text
deterministic_source_term_score_v1
```

## Source Used

Registered and extracted source:

- Usha Martin Annual Report 2024-25
- Source document id: `1`
- Extraction id: `1`
- Raw text artifact id: `136`
- Pages: `172`
- Extracted chars: `1,020,683`
- Local text: `_ai_os_runtime/artifacts/source_documents/long_term/source-document-1-ushamart-36c769d4e7e5.txt`

## Code Path

Updated:

```text
_ai_os_runtime/scripts/execute_long_term_specialist_assignment.py
```

Added:

- checklist rule definitions
- extracted-text evidence builder
- term-to-snippet matcher
- structured checklist evaluator
- checklist score persistence
- structured checklist note rendering
- research-update score audit

## Verification Commands

Compile:

```bash
python3 -m py_compile _ai_os_runtime/scripts/execute_long_term_specialist_assignment.py
```

Rerun specialists:

```bash
python3 _ai_os_runtime/scripts/execute_long_term_specialist_assignment.py --assignment-id 1 --actor "Company Analyst"
python3 _ai_os_runtime/scripts/execute_long_term_specialist_assignment.py --assignment-id 2 --actor "Company Analyst"
```

Results:

```json
{
  "business_model": {
    "source_status": "source_ready",
    "output_status": "needs_review",
    "missing_sources": []
  },
  "moat_scorecard": {
    "source_status": "source_ready",
    "output_status": "needs_review",
    "missing_sources": []
  }
}
```

## Database Proof

Checklist rows:

```json
[
  {
    "checklist_key": "business_model",
    "status": "needs_review",
    "score": 97.5,
    "owner_agent": "Company Analyst",
    "structured_checklist_present": true
  },
  {
    "checklist_key": "moat_scorecard",
    "status": "needs_review",
    "score": 97.5,
    "owner_agent": "Company Analyst",
    "structured_checklist_present": true
  }
]
```

Snapshot proof:

```json
{
  "checklists": [
    {
      "key": "business_model",
      "status": "needs_review",
      "score": 97.5,
      "has_structured": true
    },
    {
      "key": "moat_scorecard",
      "status": "needs_review",
      "score": 97.5,
      "has_structured": true
    }
  ]
}
```

## Output Notes

Latest notes:

- `ai memory/02 Portfolio/Long-Term Specialist Outputs/20260706T090530Z-ushamart-business-model.md`
- `ai memory/02 Portfolio/Long-Term Specialist Outputs/20260706T090530Z-ushamart-moat-scorecard.md`

Each note now includes:

- source status
- evidence counts
- structured checklist section
- item questions
- item scores
- matched terms
- source snippets
- no-action guardrail

## Important Caveat

The scores are source-evidence coverage scores, not final investment-quality ratings. They prove the annual report contains relevant evidence for each checklist area. They do not yet prove independent industry validation, competitor benchmarking, customer checks, forensic review, or valuation attractiveness.

## Remaining Gaps

- Add structured rule sets for `management_scorecard`, `governance_scorecard`, `capital_allocation`, `financial_quality`, and `forensic_accounting`.
- Improve scoring from term coverage into weighted institutional scoring with positive, negative, and missing evidence.
- Add contradiction/red-flag extraction.
- Add committee memo integration so Charlie sees structured checklist scores and source snippets directly.
- Add human review/override fields for checklist scores.

## Checklist Updated

Marked complete:

- Source-backed structured checklist scoring workflow.
- Build source-backed structured checklist scoring workflow.

