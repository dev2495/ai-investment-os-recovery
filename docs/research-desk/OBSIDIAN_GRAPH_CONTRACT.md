# Obsidian and Knowledge Graph Contract

Postgres owns entities, facts, lineage and state. Obsidian owns readable memory. Qdrant supplies retrieval. The graph links them; it does not create a competing truth store.

## Managed writes

Generated updates are atomic, idempotent and confined to versioned markers:

```markdown
<!-- AIOS:BEGIN AUTO company_summary v1 -->
generated text
<!-- AIOS:END AUTO company_summary v1 -->
```

Human text outside the block is preserved byte-for-byte. Conflicting or malformed markers fail closed and create a repair item.

## Incremental indexing

- content hash and modified time decide changed notes;
- only changed note links/chunks are updated;
- missing notes are soft-deleted before later reviewed purge;
- unresolved wikilinks are retained as a queue;
- Qdrant upserts precede stale-point deletion;
- every run records counts, revision and errors;
- full rebuild requires explicit `--rebuild`.

## Retrieval

Search is scope-bound and bounded: exact SQL/entity matches, point-in-time facts/evidence, scoped semantic matches, then a graph expansion of at most depth two. Results preserve evidence versus interpretation and rank authority, freshness and confidence.
