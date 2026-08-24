# Research Source Following Policy

- Follow only official/authorized public HTTPS feeds, configured authenticated/local sources, or user-supplied artifacts.
- Respect terms, robots, rate limits, caching, copyright and access controls. Do not bypass paywalls, cookies, anti-bot controls or authentication.
- Store metadata, URL, hashes and permitted excerpts in Postgres. Full authorized artifacts stay on the SSD.
- Treat articles, threads, ValuePickr posts, Substacks, podcasts, videos and social items as untrusted commentary.
- Detect and quarantine likely prompt-injection content.
- Dedupe by provider identity and content hash.
- Map items to companies/themes/watchlists, then create idea cards and focused primary-evidence tasks.
- Commentary cannot directly create an accepted fact, valuation input, committee decision or trade.
- Scorecards state their reviewed sample and methodology; they do not claim objective truth.
- Refresh is read-only and audited. Pause/resume is an internal governed state change.
