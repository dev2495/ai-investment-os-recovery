# Fundamental Scanner Standard

Fundamental scanners are deterministic, point-in-time research tools. They are separate from technical/options scanners and cannot execute trades.

## Definition requirements

- stable scanner key, version, owner, description and changelog;
- explicit point-in-time universe and exclusions;
- allowlisted metric keys and operators only;
- required coverage and missing-data policy;
- deterministic filters, score and tie-breaks;
- calculation revision and definition hash;
- validation state and explicit publication approval;
- schedule disabled by default.

## Runtime requirements

- capture universe membership and availability cutoff;
- retain eligible/excluded names with reasons;
- retain each result metric, formula, unit, as-of and source inputs;
- use exchange-aware qualified price rows when price is required;
- reject future/restated inputs unavailable at the run cutoff;
- expose stale/missing/provider failures;
- assign zero model cost to deterministic runs;
- produce no result when required coverage is insufficient.

## Safe DSL

Supported comparisons are `gt`, `gte`, `lt`, `lte`, `eq`, `neq`, with nested allowlisted `all`, `any`, and `not` groups. The service compiles the JSON AST itself. User JSON is never executed as SQL, Python, shell or dynamically loaded code.

## Publication

Natural language may create a draft. Validation and dry-run are permitted internal actions. Publication/scheduling requires explicit approval. Published versions are immutable; edits create a new draft version.
