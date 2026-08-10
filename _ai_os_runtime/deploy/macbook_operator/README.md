# MacBook Operator Node

The iMac owns the durable warehouse, SSD data, queues, schedulers, and production API. The MacBook owns the portable operator UI and stronger local model runtimes.

`macbook_operator_gateway.py` keeps the local UI contract stable at `http://127.0.0.1:8765` while forwarding application requests over Tailscale to the iMac API. `/api/node/health` verifies the upstream warehouse and the MacBook model endpoints without granting broker authority.

The gateway binds to loopback only. It does not store broker credentials, database state, or client data, and it redacts credential-like query parameters from logs.

Run `INSTALL_ON_MACBOOK.command` to replace any stale standalone MacBook API with this gateway. Existing local model LaunchAgents remain unchanged.
