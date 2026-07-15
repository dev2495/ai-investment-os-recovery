#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
PSQL = os.environ.get("AI_OS_PSQL_BIN", "/opt/homebrew/opt/postgresql@15/bin/psql")
PASSWORD = os.environ.get("AI_OS_POSTGRES_PASSWORD", "ai_os_local_dev_change_me")
PORT = os.environ.get("AI_OS_POSTGRES_PORT", "54329")
CLIENT_CODE = "validation_accounting_v1"
ACCOUNT_CODE = "validation_accounting_v1"


def sql(text: str) -> str:
    env = os.environ.copy()
    env["PGPASSWORD"] = PASSWORD
    commands = [
        [PSQL, "-h", "127.0.0.1", "-p", PORT, "-U", "ai_os", "-d", "ai_os", "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1"],
        ["/usr/local/bin/docker", "exec", "-i", "ai_os_postgres", "psql", "-U", "ai_os", "-d", "ai_os", "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1"],
    ]
    errors: list[str] = []
    for command in commands:
        result = subprocess.run(command, input=text, text=True, capture_output=True, check=False, env=env)
        if result.returncode == 0:
            return result.stdout.strip()
        errors.append(result.stderr.strip())
    raise RuntimeError(" | ".join(errors))


def cleanup() -> None:
    sql(f"""
        DELETE FROM portfolio.performance_periods WHERE account_id IN (SELECT id FROM portfolio.accounts WHERE account_code='{ACCOUNT_CODE}');
        DELETE FROM portfolio.nav_snapshots WHERE account_id IN (SELECT id FROM portfolio.accounts WHERE account_code='{ACCOUNT_CODE}');
        DELETE FROM portfolio.tax_lot_runs WHERE account_id IN (SELECT id FROM portfolio.accounts WHERE account_code='{ACCOUNT_CODE}');
        DELETE FROM portfolio.cash_ledger_entries WHERE account_id IN (SELECT id FROM portfolio.accounts WHERE account_code='{ACCOUNT_CODE}');
        DELETE FROM portfolio.positions WHERE account_id IN (SELECT id FROM portfolio.accounts WHERE account_code='{ACCOUNT_CODE}');
        DELETE FROM portfolio.snapshots WHERE account_id IN (SELECT id FROM portfolio.accounts WHERE account_code='{ACCOUNT_CODE}');
        DELETE FROM portfolio.trades WHERE account_id IN (SELECT id FROM portfolio.accounts WHERE account_code='{ACCOUNT_CODE}');
        DELETE FROM portfolio.accounts WHERE account_code='{ACCOUNT_CODE}';
        DELETE FROM portfolio.clients WHERE client_code='{CLIENT_CODE}';
    """)


def main() -> int:
    cleanup()
    checks: list[dict[str, object]] = []
    try:
        sql(f"""
            WITH c AS (
                INSERT INTO portfolio.clients(client_code,display_name,risk_profile,investment_policy,sensitivity,active)
                VALUES('{CLIENT_CODE}','Accounting Validation','moderate','{{}}'::jsonb,'internal',true) RETURNING id
            ), a AS (
                INSERT INTO portfolio.accounts(account_code,account_name,account_type,broker,base_currency,active,client_id)
                SELECT '{ACCOUNT_CODE}','Accounting Validation','validation','none','INR',true,id FROM c RETURNING id
            ), trades AS (
                INSERT INTO portfolio.trades(account_id,symbol,exchange,instrument_type,side,quantity,price,trade_ts,external_ref,raw_payload)
                SELECT id,'TESTFIFO','NSE','equity','buy',10,100,'2026-01-02 10:00+05:30'::timestamptz,'validation-buy-1','{{"source":"validation"}}'::jsonb FROM a
                UNION ALL SELECT id,'TESTFIFO','NSE','equity','buy',5,120,'2026-01-03 10:00+05:30'::timestamptz,'validation-buy-2','{{"source":"validation"}}'::jsonb FROM a
                UNION ALL SELECT id,'TESTFIFO','NSE','equity','sell',12,150,'2026-01-04 10:00+05:30'::timestamptz,'validation-sell-1','{{"source":"validation"}}'::jsonb FROM a
            ), position AS (
                INSERT INTO portfolio.positions(account_id,symbol,exchange,instrument_type,quantity,average_price,market_price,market_value,unrealized_pnl,as_of,payload)
                SELECT id,'TESTFIFO','NSE','equity',3,120,140,420,60,'2026-01-04 16:00+05:30','{{"source":"validation"}}'::jsonb FROM a
            )
            INSERT INTO portfolio.snapshots(ts,account_id,equity,cash,margin_used,pnl_day,pnl_total,payload)
            SELECT '2026-01-02 16:00+05:30'::timestamptz,id,1000,0,0,0,0,'{{"source":"validation"}}'::jsonb FROM a
            UNION ALL SELECT '2026-01-04 16:00+05:30'::timestamptz,id,1600,0,0,600,600,'{{"source":"validation"}}'::jsonb FROM a;
        """)
        result = subprocess.run(
            [sys.executable, str(RUNTIME_ROOT / "scripts" / "run_client_accounting.py"), "--account-code", ACCOUNT_CODE, "--actor", "validation"],
            text=True, capture_output=True, check=False, timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        checks.append({"check": "accounting run completed", "passed": payload.get("status") == "completed"})

        values = sql(f"""
            WITH run AS (SELECT id,status,position_break_count FROM portfolio.tax_lot_runs WHERE account_id=(SELECT id FROM portfolio.accounts WHERE account_code='{ACCOUNT_CODE}') ORDER BY completed_at DESC LIMIT 1)
            SELECT
                (SELECT status FROM run)||'|'||
                (SELECT position_break_count FROM run)||'|'||
                (SELECT match_count FROM portfolio.tax_lot_runs WHERE id=(SELECT id FROM run))||'|'||
                (SELECT realized_pnl FROM portfolio.tax_lot_runs WHERE id=(SELECT id FROM run))||'|'||
                (SELECT sum(remaining_quantity) FROM portfolio.tax_lots WHERE run_id=(SELECT id FROM run) AND status='open')||'|'||
                (SELECT sum(cost_basis) FROM portfolio.tax_lots WHERE run_id=(SELECT id FROM run) AND status='open');
        """).split("|")
        expected = ["completed", "0", "2", "560", "3", "360"]
        labels = ["lot coverage complete", "no position breaks", "two FIFO matches", "FIFO realized PnL is 560", "open quantity is 3", "open cost basis is 360"]
        checks.extend({"check": label, "passed": actual == wanted if wanted == "completed" else Decimal(actual) == Decimal(wanted), "actual": actual, "expected": wanted} for label, actual, wanted in zip(labels, values, expected))

        return_value = sql(f"SELECT twr_return_pct FROM portfolio.performance_periods WHERE account_id=(SELECT id FROM portfolio.accounts WHERE account_code='{ACCOUNT_CODE}') AND period_type='since_inception' ORDER BY calculated_at DESC LIMIT 1;")
        checks.append({"check": "Modified Dietz return is 60 percent", "passed": abs(float(return_value) - 60.0) < 0.000001, "actual": return_value, "expected": "60"})
        failed = [row for row in checks if not row["passed"]]
        print(json.dumps({"status": "passed" if not failed else "failed", "checks": checks, "failed_count": len(failed)}, indent=2))
        return 1 if failed else 0
    finally:
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
