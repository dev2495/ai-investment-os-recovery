---
type: architecture_evidence
tags:
  - ai-os
  - research
  - dashboards
  - warehouse
created: 2026-07-01
---

# AI Research Output Inventory

## Status

Indexed as warehouse metadata. Source files stay in their original locations.

## Scanned Locations

- `/Users/devarshthakkar/Downloads/cowork reseaarch`
- `/Users/devarshthakkar/Downloads/codex outputs`
- `/Users/devarshthakkar/Downloads/ultimate foils data`
- Selected standalone research/report/dashboard files in `/Users/devarshthakkar/Downloads`

## Warehouse View

`research.v_ai_output_inventory`

Backed by `core.raw_artifacts` with source system:

`AI generated research outputs`

## Inventory Counts

- Research reports: `35`
- Dashboards: `25`
- Financial models: `11`
- Source audits: `3`
- Executive summaries: `3`
- Data packs: `3`
- Research notes: `2`
- Total: `82`

## Covered Topics

Examples now discoverable by Charlie Munger through Jarvis runtime:

- SJS Enterprises
- Shivalik Bimetal Controls
- Unicommerce
- Emmvee Photovoltaic
- Inox India
- Equitas SFB
- Anant Raj
- PDS Limited
- Jai Balaji Industries
- Copper commodity research
- Pyrolysis feasibility models
- Zaggle deep dive

## Scripts

```bash
/Users/devarshthakkar/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 _ai_os_runtime/scripts/inventory_ai_research_outputs.py
```

The scanner extracts lightweight summaries from Markdown, HTML, PDF, JSON, and workbook metadata. It stores hashes and file paths so future agents can retrieve the original artifact when needed.

## Next

- Add MCP tool: `research.search_ai_outputs`.
- Add entity linking from artifact titles to `research.companies`.
- Add a summarizer agent that turns each report into a normalized investment memo.
- Add dashboard launcher links inside the future AI office GUI.
