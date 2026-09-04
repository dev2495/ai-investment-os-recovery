# Messages and handoffs — preserved baseline and pending M3

The current `agent.agent_messages`, mailboxes, task references, graph runs/checkpoints and committee registry/packets/positions/sessions/followups remain authoritative. No second message queue or committee decision engine is introduced.

This increment adds only runtime status/control tools to the existing MCP server. It does not implement the full requested persistent conversation or handoff lifecycle.

M3 must add durable message IDs, threads, scope, sender/recipient identity, bounded context references, acknowledgement and delivery receipts through existing tables. Handoffs must persist requested → acknowledged → accepted → working → returned → validated transitions, deadlines, failure reasons, idempotency keys and artifact references. Retry must not duplicate tasks, paid calls or accepted artifacts.

Charlie and room summaries should expose concise actions, evidence, decisions and blockers, never hidden chain of thought. Committee deliberation cannot authorize broker or capital actions. Production thread/client isolation, restart delivery and specialist/committee handoff demonstrations remain unchecked in the acceptance checklist.
