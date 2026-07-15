#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request


API = "http://127.0.0.1:8765"


def post(path: str, payload: dict, expected: int = 200) -> dict:
    request = urllib.request.Request(
        API + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode())
            if response.status != expected:
                raise AssertionError(f"{path}: expected {expected}, got {response.status}: {body}")
            return body
    except urllib.error.HTTPError as exc:
        body = json.loads(exc.read().decode())
        if exc.code == expected:
            return body
        raise AssertionError(f"{path}: expected {expected}, got {exc.code}: {body}") from exc


def sql(statement: str) -> str:
    completed = subprocess.run(
        ["docker", "exec", "-i", "ai_os_postgres", "psql", "-U", "ai_os", "-d", "ai_os", "-At", "-v", "ON_ERROR_STOP=1"],
        input=statement,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip())
    return completed.stdout.strip()


def main() -> int:
    suffix = str(int(time.time() * 1000))[-10:]
    client_code = f"AIOSVAL{suffix}"
    account_code = f"VAL{suffix}"
    ids: dict[str, int] = {}
    checks: list[str] = []
    try:
        staged = post(
            "/api/client-office/onboarding/stage",
            {
                "client_code": client_code,
                "display_name": "AI OS Validation Client",
                "risk_profile": "moderate",
                "objectives": ["validate governed Client Office lifecycle"],
                "constraints": ["validation only"],
                "investment_horizon": "5 years",
                "liquidity_needs": "low",
                "risk_tolerance": "moderate",
                "risk_capacity": "moderate",
                "suitability_status": "suitable",
                "suitability_notes": "Synthetic operational validation record; delete after test.",
                "source_evidence": [{"kind": "validation", "ref": client_code}],
                "account": {"account_code": account_code, "account_name": "Validation Account", "broker": "Validation Broker", "base_currency": "INR"},
                "actor": "Client Office Validator",
            },
            201,
        )
        ids["case"] = int(staged["id"])
        ids["onboarding_approval"] = int(staged["approval_id"])
        assert sql(f"SELECT count(*) FROM portfolio.clients WHERE client_code='{client_code}'") == "0"
        checks.append("onboarding stages without activating client")

        bypass = post(
            "/api/approvals/resolve",
            {"approval_id": ids["onboarding_approval"], "status": "approved", "decided_by": "Client Office Validator"},
            400,
        )
        assert "dedicated resolve endpoint" in str(bypass)
        checks.append("generic approval bypass blocked")

        applied = post(
            "/api/client-office/onboarding/resolve",
            {"case_id": ids["case"], "decision": "approved", "decision_notes": "Validation reviewed suitability and evidence.", "decided_by": "Client Office Validator"},
        )
        ids["client"] = int(applied["client_id"])
        ids["account"] = int(applied["account_id"])
        assert sql(f"SELECT lifecycle_status FROM portfolio.clients WHERE id={ids['client']}") == "active"
        assert sql(f"SELECT status FROM portfolio.client_suitability_reviews WHERE onboarding_case_id={ids['case']}") == "suitable"
        checks.append("dedicated onboarding approval atomically activates client, account, and suitability")

        account_change = post(
            "/api/client-office/accounts/stage",
            {"client_code": client_code, "account_code": account_code, "change_type": "update", "requested_values": {"broker": "Validation Broker Updated"}, "reason": "exercise account lifecycle", "source_evidence": [{"kind": "validation", "ref": account_code}], "actor": "Client Office Validator"},
            201,
        )
        ids["account_change"] = int(account_change["id"])
        ids["account_approval"] = int(account_change["approval_id"])
        post(
            "/api/client-office/accounts/resolve",
            {"request_id": ids["account_change"], "decision": "approved", "decision_notes": "Validation reviewed account mapping.", "decided_by": "Client Office Validator"},
        )
        assert sql(f"SELECT broker FROM portfolio.accounts WHERE id={ids['account']}") == "Validation Broker Updated"
        checks.append("account maintenance is approval-gated and atomic")

        holding = post(
            "/api/portfolio/holding-updates/stage",
            {"client_code": client_code, "account_code": account_code, "symbol": "AIOSVAL", "quantity": 10, "average_price": 100, "market_price": 110, "as_of": "2026-07-15T00:00:00Z", "update_reason": "exercise holding approval", "actor": "Client Office Validator"},
            201,
        )
        ids["holding_update"] = int(holding["id"])
        ids["holding_approval"] = int(holding["approval_id"])
        assert sql(f"SELECT count(*) FROM portfolio.positions WHERE account_id={ids['account']}") == "0"
        resolved = post(
            "/api/portfolio/holding-updates/resolve",
            {"update_id": ids["holding_update"], "decision": "approved", "decision_notes": "Validation matched source evidence.", "evidence": [{"kind": "validation", "ref": str(ids["holding_update"])}], "decided_by": "Client Office Validator"},
        )
        ids["position"] = int(resolved["position_id"])
        assert sql(f"SELECT status FROM portfolio.manual_holding_updates WHERE id={ids['holding_update']}") == "applied"
        checks.append("holding update cannot alter position book before dedicated approval")

        observations = post(
            "/api/client-office/holding-observations",
            {"client_code": client_code, "account_code": account_code, "source_label": "validation_statement", "as_of": "2026-07-15T00:00:00Z", "positions": [{"symbol": "AIOSVAL", "quantity": 10, "average_price": 100, "market_price": 110, "evidence": [{"ref": "matching-row"}]}, {"symbol": "SOURCEONLY", "quantity": 2, "average_price": 50, "evidence": [{"ref": "source-only-row"}]}], "actor": "Client Office Validator"},
            201,
        )
        assert observations["inserted_count"] == 2
        reconciliation = post(
            "/api/client-office/reconciliation/run",
            {"account_code": account_code, "source_label": "validation_statement", "actor": "Client Office Validator"},
            201,
        )
        ids["reconciliation"] = int(reconciliation["id"])
        assert reconciliation["status"] == "breaks_found"
        assert int(reconciliation["break_count"]) == 1
        assert reconciliation["breaks"][0]["break_type"] == "source_only"
        checks.append("multi-source reconciliation identifies symbol-level breaks without auto-apply")

        snapshot = json.loads(urllib.request.urlopen(API + "/api/portfolio-office/snapshot", timeout=30).read().decode())
        assert any(int(row["id"]) == ids["reconciliation"] for row in snapshot["holding_reconciliation"])
        assert any(int(row["id"]) == ids["case"] for row in snapshot["client_onboarding"])
        checks.append("Client Office read model exposes lifecycle and reconciliation evidence")

        print(json.dumps({"status": "passed", "checks": checks, "temporary_client": client_code}, indent=2))
        return 0
    finally:
        approval_ids = [ids[key] for key in ("onboarding_approval", "account_approval", "holding_approval") if key in ids]
        sql(
            f"""
            BEGIN;
            DELETE FROM agent.inbox_items WHERE title LIKE '%{client_code}%' OR title LIKE '%{account_code}%';
            DELETE FROM portfolio.holding_reconciliation_runs WHERE account_id IN (SELECT id FROM portfolio.accounts WHERE account_code='{account_code}');
            DELETE FROM portfolio.holding_source_observations WHERE account_id IN (SELECT id FROM portfolio.accounts WHERE account_code='{account_code}');
            DELETE FROM books.book_positions WHERE account_id IN (SELECT id FROM portfolio.accounts WHERE account_code='{account_code}');
            DELETE FROM portfolio.positions WHERE account_id IN (SELECT id FROM portfolio.accounts WHERE account_code='{account_code}');
            DELETE FROM portfolio.manual_holding_updates WHERE client_code='{client_code}';
            DELETE FROM portfolio.account_change_requests WHERE client_id IN (SELECT id FROM portfolio.clients WHERE client_code='{client_code}');
            DELETE FROM portfolio.client_suitability_reviews WHERE onboarding_case_id IN (SELECT id FROM portfolio.client_onboarding_cases WHERE client_code='{client_code}') OR client_id IN (SELECT id FROM portfolio.clients WHERE client_code='{client_code}');
            DELETE FROM portfolio.client_onboarding_cases WHERE client_code='{client_code}';
            DELETE FROM portfolio.accounts WHERE account_code='{account_code}';
            DELETE FROM portfolio.clients WHERE client_code='{client_code}';
            {('DELETE FROM agent.approvals WHERE id IN (' + ','.join(map(str, approval_ids)) + ');') if approval_ids else ''}
            COMMIT;
            """
        )


if __name__ == "__main__":
    raise SystemExit(main())
