#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from decimal import Decimal

from run_capital_allocation_analysis import run_psql_json


TOLERANCE = Decimal("0.001")


def number(value: object) -> Decimal:
    return Decimal(str(value or 0))


def main() -> int:
    books = run_psql_json(
        "SELECT book_key FROM books.investment_books WHERE status='active' ORDER BY book_key"
    )
    clients = run_psql_json(
        "SELECT id, client_code FROM portfolio.clients WHERE active=true ORDER BY client_code"
    )
    board = run_psql_json(
        """
        SELECT client_id, client_code, book_key, current_exposure, current_pct,
               proposal_id, control_status, legacy_policy_status,
               capital_action_allowed, live_execution_allowed
        FROM books.v_capital_policy_control_board
        ORDER BY client_code, book_key
        """
    )
    execution = run_psql_json(
        """
        SELECT global_execution_locked, live_broker_writes_allowed
        FROM trading.v_execution_control_state
        LIMIT 1
        """
    )
    summary = run_psql_json(
        "SELECT metric, value FROM books.v_capital_allocation_control_summary"
    )

    expected_books = {row["book_key"] for row in books}
    expected_clients = {int(row["id"]): row["client_code"] for row in clients}
    assert expected_books, "no active investment books"
    assert expected_clients, "no active clients"
    assert len(board) == len(expected_books) * len(expected_clients), (
        f"expected {len(expected_books) * len(expected_clients)} control rows, found {len(board)}"
    )

    for client_id, client_code in expected_clients.items():
        rows = [row for row in board if int(row["client_id"]) == client_id]
        assert {row["book_key"] for row in rows} == expected_books, f"book coverage mismatch for {client_code}"
        assert abs(sum((number(row["current_pct"]) for row in rows), Decimal(0)) - Decimal(100)) <= TOLERANCE, (
            f"observed allocation does not total 100% for {client_code}"
        )

    assert all(row["legacy_policy_status"] == "legacy_unverified" for row in board)
    assert all(row["capital_action_allowed"] is False for row in board)
    assert all(row["live_execution_allowed"] is False for row in board)
    assert execution and execution[0]["global_execution_locked"] is True
    assert execution[0]["live_broker_writes_allowed"] is False

    proposal_ids = {row["proposal_id"] for row in board if row["proposal_id"] is not None}
    no_policy_clients = {
        row["client_id"] for row in board if row["proposal_id"] is None
    }
    summary_map = {row["metric"]: int(row["value"]) for row in summary}
    assert summary_map["active_clients"] == len(expected_clients)
    assert summary_map["clients_without_policy"] == len(no_policy_clients)

    analysis_invariants = run_psql_json(
        """
        SELECT count(*) AS row_count,
               count(*) FILTER (WHERE capital_action_allowed OR broker_order_allowed OR live_execution_allowed) AS unsafe_count
        FROM books.capital_allocation_analysis_lines
        """
    )[0]
    assert int(analysis_invariants["unsafe_count"]) == 0

    print(json.dumps({
        "status": "passed",
        "active_clients": len(expected_clients),
        "active_books": len(expected_books),
        "control_rows": len(board),
        "operator_policy_count": len(proposal_ids),
        "clients_without_policy": len(no_policy_clients),
        "analysis_lines": int(analysis_invariants["row_count"]),
        "unsafe_analysis_lines": int(analysis_invariants["unsafe_count"]),
        "legacy_policy_status": "legacy_unverified",
        "execution_locked": True,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, RuntimeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}), file=sys.stderr)
        raise SystemExit(1)
