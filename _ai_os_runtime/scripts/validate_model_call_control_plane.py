#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

from run_capital_allocation_analysis import run_psql_json


def scalar(query: str, key: str = "count") -> int:
    return int(run_psql_json(query)[0][key])


def main() -> int:
    active_agents = scalar("SELECT count(*) FROM agent.profiles WHERE status='active'")
    assignments = scalar(
        """SELECT count(*) FROM agent.agent_model_assignments assignment
           JOIN agent.profiles profile USING(agent_name) WHERE profile.status='active'"""
    )
    cost_caps = scalar(
        """SELECT count(*) FROM agent.model_cost_caps cap
           JOIN agent.profiles profile USING(agent_name) WHERE profile.status='active'"""
    )
    assert active_agents > 0
    assert assignments == active_agents, f"model assignment coverage {assignments}/{active_agents}"
    assert cost_caps == active_agents, f"model cost-cap coverage {cost_caps}/{active_agents}"

    policies = run_psql_json(
        """SELECT privacy_class, local_model_allowed, cloud_model_allowed,
                  cache_allowed, retention_days, max_context_chars
           FROM agent.model_privacy_policies ORDER BY privacy_class"""
    )
    assert {row["privacy_class"] for row in policies} == {
        "public", "internal", "client_private", "restricted"
    }
    private = {row["privacy_class"]: row for row in policies}
    for privacy_class in ("client_private", "restricted"):
        assert private[privacy_class]["cloud_model_allowed"] is False
        assert private[privacy_class]["cache_allowed"] is False
        assert int(private[privacy_class]["retention_days"]) == 0

    routes = run_psql_json(
        "SELECT route_name, runtime_status FROM agent.v_model_route_runtime_control ORDER BY route_name"
    )
    required_routes = {
        "agent_worker_deterministic",
        "always_on_daily_driver",
        "charlie_munger_orchestration",
        "daily_brief",
        "filing_analysis",
        "jarvis_intake",
        "jarvis_runtime",
        "local_embedding_retrieval",
        "multimodal_document_analysis",
        "news_curation",
        "research_company_analysis",
        "strategy_backtest",
        "strategy_generation",
        "strategy_optimizer",
        "trade_journal_learning",
    }
    route_names = {row["route_name"] for row in routes}
    assert required_routes <= route_names, f"missing governed routes: {sorted(required_routes - route_names)}"
    route_counts: dict[str, int] = {}
    for row in routes:
        route_counts[row["runtime_status"]] = route_counts.get(row["runtime_status"], 0) + 1
    assert route_counts.get("blocked_secret") == 2, route_counts
    assert route_counts.get("ready") == len(routes) - 2, route_counts
    assert not ({"degraded", "endpoint_missing", "model_unavailable"} & route_counts.keys()), route_counts

    unsafe = run_psql_json(
        """SELECT
               count(*) FILTER (WHERE autonomous_cloud_allowed) AS autonomous_cloud_agents,
               coalesce(sum(unapproved_cloud_events_today),0) AS unapproved_cloud_events_today
           FROM agent.v_agent_model_cost_cap_status"""
    )[0]
    assert int(unsafe["autonomous_cloud_agents"]) == 0
    assert int(unsafe["unapproved_cloud_events_today"]) == 0
    assert scalar(
        "SELECT count(*) FROM agent.model_response_cache WHERE privacy_class IN ('client_private','restricted')"
    ) == 0
    assert scalar(
        """SELECT count(*) FROM information_schema.columns
           WHERE table_schema='agent' AND table_name='model_call_decisions'
             AND column_name IN ('prompt','raw_prompt','prompt_text')"""
    ) == 0

    execution = run_psql_json(
        """SELECT global_execution_locked, live_broker_writes_allowed
           FROM trading.v_execution_control_state LIMIT 1"""
    )[0]
    assert execution["global_execution_locked"] is True
    assert execution["live_broker_writes_allowed"] is False

    print(json.dumps({
        "status": "passed",
        "active_agents": active_agents,
        "complete_assignments": assignments,
        "complete_cost_caps": cost_caps,
        "privacy_policies": len(policies),
        "routes": len(routes),
        "route_status_counts": route_counts,
        "autonomous_cloud_agents": 0,
        "unapproved_cloud_events_today": 0,
        "private_cache_entries": 0,
        "raw_prompt_columns": 0,
        "execution_locked": True,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, RuntimeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}), file=sys.stderr)
        raise SystemExit(1)
