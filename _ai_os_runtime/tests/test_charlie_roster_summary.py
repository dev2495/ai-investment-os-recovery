from _ai_os_runtime.api.agent_charlie import roster_summary

def test_roster_is_bounded_visible_and_does_not_infer_work_from_profile():
    overview = {
        "generated_at": "2026-09-07T12:00:00Z",
        "agents": [{"agent_name": "Asha", "state": "WORKING", "has_live_lease": True, "task_id": 8},
                   {"agent_name": "Private specialist", "state": "OFFLINE", "task_id": 99}]
                  + [{"agent_name": f"Agent {i}", "state": "OFFLINE"} for i in range(24)],
        "tasks": [{"id": 8, "task_class": "filing_analysis"}],
    }
    result = roster_summary(overview)
    assert "26 registered agents; 1 have live worker leases" in result
    assert "25 offline, 1 working" in result
    assert "Asha — working · task #8 · filing_analysis" in result
    assert "Showing 20 of 26" in result
    assert result.count("• ") == 20
    assert "task #99" not in result
    assert "2026-09-07T12:00:00Z" in result

def test_empty_roster_is_explicit():
    result = roster_summary({"agents": [], "tasks": []})
    assert "0 registered agents; 0 have live worker leases" in result
    assert "Recorded states: none" in result
