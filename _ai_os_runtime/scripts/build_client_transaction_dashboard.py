#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import subprocess
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = RUNTIME_ROOT / "dashboards" / "client_3081282_transactions"
OUTPUT_PATH = DASHBOARD_DIR / "index.html"


def run_psql_json(query: str) -> list[dict]:
    sql = f"SELECT coalesce(json_agg(row_to_json(result_rows)), '[]'::json)::text FROM ({query}) result_rows;"
    command = ["docker", "exec", "-i", "ai_os_postgres", "psql", "-q", "-t", "-A", "-U", "ai_os", "-d", "ai_os"]
    completed = subprocess.run(command, input=sql, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout).strip())
    return json.loads(completed.stdout.strip() or "[]")


def json_script(value: object) -> str:
    return html.escape(json.dumps(value, default=str), quote=False)


def build_dashboard() -> str:
    summary = run_psql_json("SELECT metric, value FROM client_data.v_client_3081282_dashboard_summary ORDER BY metric")
    symbol_dates = run_psql_json(
        """
        SELECT symbol, instrument_type, option_type, strike_price, first_buy_date, last_buy_date,
               first_sell_date, last_sell_date, bought_quantity, sold_quantity, net_quantity, trade_rows
        FROM client_data.v_client_3081282_symbol_dates
        ORDER BY last_trade_date DESC NULLS LAST, symbol
        """
    )
    timeline = run_psql_json(
        """
        SELECT source_type, entry_date, exit_date, trade_time, exchange, symbol, instrument_type, side,
               quantity, entry_price, exit_price, net_rate, amount, expiry_date, option_type, strike_price, external_trade_ref
        FROM client_data.v_client_3081282_trade_timeline
        ORDER BY entry_date DESC NULLS LAST, trade_time DESC NULLS LAST, symbol
        """
    )
    option_clients = run_psql_json(
        """
        SELECT client_code, min(entry_date) AS first_entry, max(coalesce(exit_date, entry_date)) AS last_activity,
               count(*) AS rows, count(DISTINCT stock_ticker) AS tickers
        FROM client_data.attached_option_log_transactions
        GROUP BY client_code
        ORDER BY rows DESC
        """
    )
    option_recent = run_psql_json(
        """
        SELECT client_code, trade_id, trade_status, trade_type, entry_date, exit_date, stock_ticker,
               side, call_put, strike_price, contracts, option_value, exit_option_value
        FROM client_data.attached_option_log_transactions
        ORDER BY coalesce(exit_date, entry_date) DESC NULLS LAST, trade_id
        LIMIT 300
        """
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Client 3081282 Transactions</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0f1216;
      --panel: #171c22;
      --panel-2: #1d242c;
      --line: #313a45;
      --text: #edf1f5;
      --muted: #a8b2bd;
      --accent: #57b8a8;
      --warn: #f2b15d;
      --loss: #ef767a;
      --gain: #7bd389;
      --blue: #7aa7ff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 13px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 5;
      background: rgba(15, 18, 22, 0.96);
      border-bottom: 1px solid var(--line);
      padding: 14px 18px 12px;
    }}
    h1 {{ margin: 0; font-size: 20px; font-weight: 650; letter-spacing: 0; }}
    h2 {{ margin: 0 0 10px; font-size: 15px; font-weight: 650; letter-spacing: 0; }}
    .subtitle {{ color: var(--muted); margin-top: 3px; }}
    main {{ padding: 16px 18px 28px; display: grid; gap: 16px; }}
    .stats {{ display: grid; grid-template-columns: repeat(7, minmax(120px, 1fr)); gap: 10px; }}
    .stat {{ background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 10px 12px; min-height: 70px; }}
    .stat .label {{ color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em; }}
    .stat .value {{ font-size: 20px; font-weight: 700; margin-top: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    section {{ background: var(--panel); border: 1px solid var(--line); border-radius: 6px; overflow: hidden; }}
    .section-head {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px; border-bottom: 1px solid var(--line); }}
    .tools {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
    input, select {{
      background: #0c0f13;
      color: var(--text);
      border: 1px solid var(--line);
      border-radius: 5px;
      height: 32px;
      padding: 0 9px;
      min-width: 160px;
    }}
    .table-wrap {{ overflow: auto; max-height: 64vh; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 980px; }}
    th, td {{ border-bottom: 1px solid #252c35; padding: 7px 9px; text-align: left; white-space: nowrap; }}
    th {{ position: sticky; top: 0; background: var(--panel-2); z-index: 2; color: #d9e0e8; font-size: 11px; text-transform: uppercase; letter-spacing: 0.03em; }}
    td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .buy {{ color: var(--gain); font-weight: 650; }}
    .sell {{ color: var(--loss); font-weight: 650; }}
    .tag {{ display: inline-flex; align-items: center; height: 20px; padding: 0 7px; border-radius: 999px; background: #27313b; color: #dbe4ee; font-size: 11px; }}
    .muted {{ color: var(--muted); }}
    .grid-2 {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 16px; }}
    @media (max-width: 1100px) {{
      .stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .grid-2 {{ grid-template-columns: 1fr; }}
      header {{ position: static; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Client 3081282 Transaction Ledger</h1>
    <div class="subtitle">Broker reports from 2026-02-01 to 2026-06-30, plus separate old option-log history from 2019-2020.</div>
  </header>
  <main>
    <div class="stats" id="stats"></div>
    <section>
      <div class="section-head">
        <h2>Symbol Buy/Sell Date Map</h2>
        <div class="tools">
          <input id="symbolSearch" placeholder="Filter symbol" />
          <select id="instrumentFilter"><option value="">All instruments</option><option>equity</option><option>option</option></select>
        </div>
      </div>
      <div class="table-wrap"><table id="symbolTable"></table></div>
    </section>
    <section>
      <div class="section-head">
        <h2>All Broker Rows</h2>
        <div class="tools">
          <input id="timelineSearch" placeholder="Search symbol / ref" />
          <select id="sideFilter"><option value="">All sides</option><option value="B">Buy</option><option value="S">Sell</option></select>
        </div>
      </div>
      <div class="table-wrap"><table id="timelineTable"></table></div>
    </section>
    <div class="grid-2">
      <section>
        <div class="section-head"><h2>Old Option Log by Client</h2></div>
        <div class="table-wrap"><table id="optionClientTable"></table></div>
      </section>
      <section>
        <div class="section-head"><h2>Recent Old Option Log Rows</h2></div>
        <div class="table-wrap"><table id="optionRecentTable"></table></div>
      </section>
    </div>
  </main>
  <script id="data" type="application/json">{json_script({"summary": summary, "symbolDates": symbol_dates, "timeline": timeline, "optionClients": option_clients, "optionRecent": option_recent})}</script>
  <script>
    const data = JSON.parse(document.getElementById('data').textContent);
    const fmt = new Intl.NumberFormat('en-IN', {{ maximumFractionDigits: 2 }});
    const money = new Intl.NumberFormat('en-IN', {{ maximumFractionDigits: 0 }});
    function val(x) {{ return x === null || x === undefined ? '' : x; }}
    function num(x) {{ return x === null || x === undefined || x === '' ? '' : fmt.format(Number(x)); }}
    function renderStats() {{
      const labels = {{
        ledger_rows: 'Broker ledger rows', broker_rows: 'Broker rows', symbols: 'Symbols',
        gross_buy_amount: 'Gross buy amount', gross_sell_amount: 'Gross sell amount',
        open_symbol_rows: 'Open symbol rows', option_log_rows: 'Option log rows in 3081282'
      }};
      document.getElementById('stats').innerHTML = data.summary.map(r => `
        <div class="stat"><div class="label">${{labels[r.metric] || r.metric}}</div><div class="value">${{r.metric.includes('amount') ? money.format(Number(r.value)) : fmt.format(Number(r.value))}}</div></div>
      `).join('');
    }}
    function renderTable(id, rows, cols) {{
      const table = document.getElementById(id);
      table.innerHTML = `<thead><tr>${{cols.map(c => `<th>${{c.label}}</th>`).join('')}}</tr></thead><tbody>${{rows.map(row => `<tr>${{cols.map(c => {{
        const raw = c.get ? c.get(row) : row[c.key];
        const cls = c.num ? ' class="num"' : '';
        return `<td${{cls}}>${{raw === null || raw === undefined ? '' : raw}}</td>`;
      }}).join('')}}</tr>`).join('')}}</tbody>`;
    }}
    function sideCell(side) {{
      const s = String(side || '').toUpperCase();
      return `<span class="${{s === 'B' || s === 'BUY' ? 'buy' : s === 'S' || s === 'SELL' ? 'sell' : ''}}">${{s}}</span>`;
    }}
    function filterAndRender() {{
      const symbolQ = document.getElementById('symbolSearch').value.toLowerCase();
      const inst = document.getElementById('instrumentFilter').value;
      const symbols = data.symbolDates.filter(r =>
        (!symbolQ || String(r.symbol || '').toLowerCase().includes(symbolQ)) &&
        (!inst || r.instrument_type === inst)
      );
      renderTable('symbolTable', symbols, [
        {{label:'Symbol', key:'symbol'}}, {{label:'Type', key:'instrument_type'}}, {{label:'Opt', key:'option_type'}},
        {{label:'Strike', get:r=>num(r.strike_price), num:true}}, {{label:'First buy', key:'first_buy_date'}},
        {{label:'Last buy', key:'last_buy_date'}}, {{label:'First sell', key:'first_sell_date'}}, {{label:'Last sell', key:'last_sell_date'}},
        {{label:'Bought', get:r=>num(r.bought_quantity), num:true}}, {{label:'Sold', get:r=>num(r.sold_quantity), num:true}},
        {{label:'Net', get:r=>num(r.net_quantity), num:true}}, {{label:'Rows', get:r=>num(r.trade_rows), num:true}}
      ]);
      const timelineQ = document.getElementById('timelineSearch').value.toLowerCase();
      const side = document.getElementById('sideFilter').value;
      const rows = data.timeline.filter(r =>
        (!timelineQ || String(r.symbol || '').toLowerCase().includes(timelineQ) || String(r.external_trade_ref || '').toLowerCase().includes(timelineQ)) &&
        (!side || String(r.side || '').toUpperCase() === side)
      );
      renderTable('timelineTable', rows, [
        {{label:'Date', key:'entry_date'}}, {{label:'Time', key:'trade_time'}}, {{label:'Exch', key:'exchange'}},
        {{label:'Symbol', key:'symbol'}}, {{label:'Type', key:'instrument_type'}}, {{label:'Side', get:r=>sideCell(r.side)}},
        {{label:'Qty', get:r=>num(r.quantity), num:true}}, {{label:'Market', get:r=>num(r.entry_price), num:true}},
        {{label:'Net Rate', get:r=>num(r.net_rate), num:true}}, {{label:'Amount', get:r=>num(r.amount), num:true}},
        {{label:'Expiry', key:'expiry_date'}}, {{label:'Opt', key:'option_type'}}, {{label:'Strike', get:r=>num(r.strike_price), num:true}},
        {{label:'Trade Ref', key:'external_trade_ref'}}
      ]);
    }}
    renderStats();
    filterAndRender();
    renderTable('optionClientTable', data.optionClients, [
      {{label:'Client', key:'client_code'}}, {{label:'First Entry', key:'first_entry'}}, {{label:'Last Activity', key:'last_activity'}},
      {{label:'Rows', get:r=>num(r.rows), num:true}}, {{label:'Tickers', get:r=>num(r.tickers), num:true}}
    ]);
    renderTable('optionRecentTable', data.optionRecent, [
      {{label:'Client', key:'client_code'}}, {{label:'Trade', key:'trade_id'}}, {{label:'Status', key:'trade_status'}},
      {{label:'Entry', key:'entry_date'}}, {{label:'Exit', key:'exit_date'}}, {{label:'Ticker', key:'stock_ticker'}},
      {{label:'Side', get:r=>sideCell(r.side)}}, {{label:'CP', key:'call_put'}}, {{label:'Strike', get:r=>num(r.strike_price), num:true}},
      {{label:'Cont', get:r=>num(r.contracts), num:true}}, {{label:'Entry Val', get:r=>num(r.option_value), num:true}}, {{label:'Exit Val', get:r=>num(r.exit_option_value), num:true}}
    ]);
    ['symbolSearch', 'instrumentFilter', 'timelineSearch', 'sideFilter'].forEach(id => document.getElementById(id).addEventListener('input', filterAndRender));
  </script>
</body>
</html>"""


def main() -> int:
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(build_dashboard(), encoding="utf-8")
    print(json.dumps({"dashboard_path": str(OUTPUT_PATH)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
