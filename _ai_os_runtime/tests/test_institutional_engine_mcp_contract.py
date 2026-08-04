import importlib.util
import json
from pathlib import Path
from unittest.mock import patch


SERVER_PATH = Path(__file__).parents[1] / "mcp_server" / "ai_os_mcp_server.py"
SPEC = importlib.util.spec_from_file_location("ai_os_mcp_server_institutional_contract", SERVER_PATH)
assert SPEC and SPEC.loader
SERVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SERVER)


TOOL_CASES = {
    "ai_os_run_institutional_fundamental_factory": (
        "/api/research/fundamental-factory/run",
        {"company_key": "reliance-industries", "as_of": "2026-08-04T12:00:00+05:30", "actor": "Research Director"},
    ),
    "ai_os_run_sector_intelligence_engine": (
        "/api/sector-intelligence/run",
        {"index_key": "india-private-banks", "as_of_date": "2026-08-04", "horizon": "3M"},
    ),
    "ai_os_run_institutional_options_engine": (
        "/api/options/institutional-analytics/run",
        {
            "underlying": "NIFTY", "exchange": "NFO", "expiry_date": "2026-08-27",
            "as_of": "2026-08-04T12:00:00+05:30", "model": "black_76",
        },
    ),
}


def decoded_tool_result(result: dict) -> dict:
    return json.loads(result["content"][0]["text"])


def test_tools_are_registered_with_safe_paper_only_contracts() -> None:
    for name in TOOL_CASES:
        tool = SERVER.TOOLS[name]
        schema = tool["inputSchema"]
        description = tool["description"].lower()
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert "paper-only" in description
        assert "execut" in description
        assert "order" not in schema["properties"]
        assert "broker" not in schema["properties"]
        assert "capital" not in schema["properties"]


def test_handlers_call_expected_api_and_force_safety_envelope() -> None:
    for name, (path, arguments) in TOOL_CASES.items():
        with patch.object(SERVER, "post_api_json", return_value={"status": "accepted"}) as post:
            result = SERVER.TOOLS[name]["handler"](arguments)

        assert decoded_tool_result(result) == {"status": "accepted"}
        called_path, payload = post.call_args.args[:2]
        assert called_path == path
        assert payload["paper_only"] is True
        assert payload["live_execution_allowed"] is False
        assert payload["capital_action_allowed"] is False
        assert post.call_args.kwargs["timeout"] == 620


def test_handlers_drop_unregistered_execution_fields() -> None:
    for name, (_, arguments) in TOOL_CASES.items():
        hostile = {
            **arguments,
            "order": {"side": "BUY"},
            "broker_write": True,
            "live_execution_allowed": True,
            "capital_action_allowed": True,
        }
        with patch.object(SERVER, "post_api_json", return_value={"status": "accepted"}) as post:
            SERVER.TOOLS[name]["handler"](hostile)

        payload = post.call_args.args[1]
        assert "order" not in payload
        assert "broker_write" not in payload
        assert payload["live_execution_allowed"] is False
        assert payload["capital_action_allowed"] is False


def test_sector_tool_is_tradingview_artifact_only() -> None:
    _, arguments = TOOL_CASES["ai_os_run_sector_intelligence_engine"]
    with patch.object(SERVER, "post_api_json", return_value={"status": "accepted"}) as post:
        SERVER.run_sector_intelligence_engine(arguments)

    assert post.call_args.args[1]["tradingview_artifacts_only"] is True


def test_institutional_data_operations_are_registered_and_route_to_scoped_apis() -> None:
    cases = {
        "ai_os_materialize_institutional_options": (
            "/api/options/institutional-analytics/materialize", {"limit": 2}
        ),
        "ai_os_upsert_option_valuation_policy": (
            "/api/options/valuation-policy/upsert",
            {"policy_key": "p", "provider": "Zerodha", "exchange": "NFO", "underlying": "NIFTY"},
        ),
        "ai_os_import_sector_intelligence_package": (
            "/api/sector-intelligence/import", {"package": {"source": {}}, "persist": False}
        ),
    }
    for name, (path, arguments) in cases.items():
        tool = SERVER.TOOLS[name]
        assert tool["inputSchema"]["additionalProperties"] is False
        with patch.object(SERVER, "post_api_json", return_value={"status": "accepted"}) as post:
            result = tool["handler"](arguments)
        assert decoded_tool_result(result) == {"status": "accepted"}
        assert post.call_args.args[0] == path
        payload = post.call_args.args[1]
        assert payload.get("broker_write_allowed") is not True
        assert payload.get("capital_action_allowed") is not True
