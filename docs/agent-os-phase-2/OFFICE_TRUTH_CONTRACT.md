# Office truth contract

The existing React shell, Office query, 2D view and 3D view remain the presentation layer. No additional agent database or office event authority is introduced.

Implemented rules:

- A configured profile or historical activity record cannot produce a working indicator.
- Live work requires `has_live_lease=true`, an unexpired lease timestamp and the server's healthy-worker assertion. The browser expires its copy every two seconds even when disconnected.
- An expired lease is STALE until reconciliation, not completed or silently idle. Missing runtime evidence is UNVERIFIED, not a fabricated working state.
- The connection badge says **live events**; it describes transport, not whether an agent is working.
- One bounded SSE consumer invalidates the existing Office query and the open task-step query. It does not maintain a second task-state store. Cursor replay/reset handles reconnects; snapshot polling stays available.
- Task pause/cancel waits for safe boundaries. Cancellation requires confirmation and retains history. Resume is offered only without recorded side effects; receipt uncertainty is explained instead of hiding a generic retry button.
- Shared responses contain operational metadata, not private client narrative, prompts, secrets, local paths or chain of thought.

Verified locally on a production Vite build with an actual synthetic PostgreSQL worker/API: pause, resume back to running, new steps visible, reconnect, cancel/keep confirmation, 390px layout and checked-panel accessibility. [Desktop](evidence/phase2-office-desktop.png) and [mobile](evidence/phase2-office-mobile.png) screenshots are synthetic test evidence, not production screenshots.

Not yet accepted: full handoff/committee visualization, every agent detail/hover field and state, complete 2D/3D parity, real client scope, Safari, full-population M4 performance and 24-hour soak. The test checks serious/critical axe issues in `.aios-panel`; it is not a complete accessibility certification of the entire application.
