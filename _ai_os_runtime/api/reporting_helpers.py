"""External-SSD-only generation for cited Long-Term Thesis HTML reports."""

from __future__ import annotations

import hashlib
import html
import json
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

from financial_quality import build_financial_quality


def _esc(value):
    return html.escape(str(value or ""), quote=True)


def _metric_value(metric, scale, suffix=""):
    if not isinstance(metric, dict) or metric.get("value") is None:
        return "Not computable"
    value = float(metric["value"]) / scale
    return f"{value:,.1f}{suffix}"


def _model_value(row, key, suffix=""):
    status = str(row.get("status") or "").strip().lower()
    if status not in {"validated", "human_reviewed", "approved", "complete"}:
        return "Not validated"
    value = row.get(key)
    return f"{value}{suffix}" if value is not None else "Not available"


def _compact_text(value, limit=520):
    text = str(value or "").replace("`", "").replace("#", "").replace("\n", " ")
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"

def _source_anchor(url, label):
    return f"<a href='{_esc(url)}'>{_esc(label or 'Source')}</a>" if url else _esc(label or "Source unavailable")

def _source_list(value):
    entries = value if isinstance(value, list) else []
    links = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        title = entry.get("source_title") or entry.get("title") or entry.get("source_kind") or "Source"
        url = entry.get("source_url") or entry.get("url")
        page = (entry.get("citation_locator") or {}).get("page") if isinstance(entry.get("citation_locator"), dict) else None
        suffix = f" p.{page}" if page else ""
        links.append(_source_anchor(url, f"{title}{suffix}"))
    return "; ".join(links) or "No source link recorded"

def _locator_summary(value):
    locator = value if isinstance(value, dict) else {}
    page = locator.get("page_number") or locator.get("source_page") or locator.get("page")
    line = locator.get("reported_line") or locator.get("line")
    bits = [f"p.{page}" if page else "Page not recorded"]
    if line:
        bits.append(_compact_text(line, 110))
    return " · ".join(bits)

def _ratio_inputs_summary(inputs):
    rows = inputs if isinstance(inputs, list) else []
    items = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        role = str(item.get("input_role") or item.get("fact_key") or "input").replace("_", " ")
        page = item.get("source_page")
        source = item.get("source_url")
        label = f"{role} p.{page}" if page else role
        items.append(_source_anchor(source, label))
    return "; ".join(items) or "No source inputs recorded"

def _model_evidence_summary(assumptions):
    source_evidence = assumptions.get("source_evidence") if isinstance(assumptions, dict) else []
    return _source_list(source_evidence)


def _nested(value, *keys, default=None):
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current


def _pct(value, digits=1):
    if value is None:
        return "Not available"
    return f"{float(value) * 100:.{digits}f}%"

def generate_thesis_report(*, thesis_id, actor, run_rows, run_statement, sql_literal, sql_jsonb):
    thesis = run_rows(f"""
        SELECT thesis.*,company.id company_id,company.legal_name,
               company.primary_symbol,company.primary_exchange
        FROM portfolio.holding_theses thesis
        LEFT JOIN research.companies company
          ON upper(company.primary_symbol)=upper(thesis.symbol)
         AND upper(company.primary_exchange)=upper(thesis.exchange)
        WHERE thesis.id={int(thesis_id)} LIMIT 1
    """)
    if not thesis:
        raise ValueError("holding thesis was not found")
    selected = thesis[0]
    company_id = int(selected.get("company_id") or 0)
    facts = run_rows(f"""
        SELECT fact_key,canonical_name,statement_type,fiscal_year,fiscal_period,
               period_start,period_end,statement_scope,value_numeric,value_text,currency,
               unit,scale_power,source_as_of_date,available_at,evidence_id,source_type,
               source_name,source_url,verification_status,source_locator
        FROM research.v_company_statement_facts_current
        WHERE company_id={company_id or -1}
        ORDER BY fiscal_year DESC,fact_key LIMIT 240
    """)
    quality = build_financial_quality(facts)
    matrix = run_rows(f"""
        SELECT requirement_key,section_key,requirement_label,coverage_status,
               coverage_debt,latest_captured_at,latest_publication_date,sources
        FROM research.v_thesis_source_matrix WHERE company_id={company_id or -1}
        ORDER BY section_order,requirement_key LIMIT 80
    """)
    sections = run_rows(f"""
        SELECT section.section_key,section.section_title,section.section_status,
               section.content_markdown,section.evidence_as_of,evidence.source_title,
               evidence.source_url,evidence.verification_status
        FROM research.investment_dossier_sections section
        LEFT JOIN research.fundamental_evidence evidence ON evidence.id=section.primary_evidence_id
        WHERE section.dossier_version_id=(
          SELECT dossier_version_id FROM research.v_latest_investment_dossiers
          WHERE company_id={company_id or -1}
          ORDER BY updated_at DESC LIMIT 1
        ) ORDER BY section.section_order,section.id LIMIT 40
    """)
    all_models = run_rows(f"""
        SELECT model_name,model_type,status,fair_value_low,fair_value_base,
               fair_value_high,expected_cagr_pct,assumptions,outputs,updated_at
        FROM portfolio.holding_valuation_models WHERE holding_thesis_id={int(thesis_id)}
        ORDER BY updated_at DESC,model_key LIMIT 40
    """)
    models = [row for row in all_models if row.get("model_type") != "monte_carlo"]
    models_by_type = {str(row.get("model_type")): row for row in all_models}
    guidance = run_rows(f"""
        SELECT score.*,e.source_url,e.source_title,e.verification_status,
               outcome.source_url outcome_source_url,outcome.source_title outcome_source_title
        FROM research.v_management_claim_scorecard score
        LEFT JOIN research.fundamental_evidence e ON e.id=score.claim_evidence_id
        LEFT JOIN research.fundamental_evidence outcome ON outcome.id=score.outcome_evidence_id
        WHERE score.company_id={company_id or -1} ORDER BY score.claim_date DESC LIMIT 20
    """)
    segments = run_rows(f"""
        SELECT s.segment_name,s.segment_type,f.fiscal_year,d.fact_key,d.canonical_name,
               f.value_numeric,f.currency,f.unit,f.source_as_of_date,f.source_locator,
               e.source_url,e.source_title,e.verification_status
        FROM research.company_segment_facts f
        JOIN research.company_segments s ON s.id=f.segment_id
        JOIN research.statement_fact_definitions d ON d.id=f.fact_definition_id
        LEFT JOIN research.fundamental_evidence e ON e.id=f.evidence_id
        WHERE f.company_id={company_id or -1}
        ORDER BY s.segment_name,f.fiscal_year DESC,d.fact_key LIMIT 160
    """)
    operational_kpis = run_rows(f"""
        SELECT definition.kpi_key,definition.kpi_name,definition.description,definition.unit,definition.frequency,
          observation.period_start,observation.period_end,observation.value_numeric,observation.value_text,
          observation.source_as_of_date,observation.source_locator,observation.metadata,
          evidence.source_title,evidence.source_url,evidence.verification_status
        FROM research.operational_kpi_observations observation
        JOIN research.operational_kpi_definitions definition ON definition.id=observation.kpi_definition_id
        JOIN research.fundamental_evidence evidence ON evidence.id=observation.evidence_id
        WHERE observation.company_id={company_id or -1}
        ORDER BY definition.kpi_key,observation.period_end LIMIT 240
    """)
    industry_observations = run_rows(f"""
        SELECT observation.id,observation.observation_key,observation.category,observation.conclusion,
          observation.value_numeric,observation.unit,observation.metric_availability,observation.period_end,
          observation.source_page,observation.source_excerpt,observation.verification_status,
          evidence.source_title,evidence.source_url
        FROM research.industry_competitive_observations observation
        JOIN research.fundamental_evidence evidence ON evidence.id=observation.evidence_id
        WHERE observation.company_id={company_id or -1}
          AND observation.verification_status NOT IN ('rejected','superseded')
        ORDER BY observation.period_end DESC,observation.category,observation.id DESC LIMIT 80
    """)
    market_shares = run_rows(f"""
        SELECT share.id,share.market_name,share.product_or_service,share.geography,share.period_end,share.share_pct,
          share.measurement_basis,share.methodology,evidence.source_title,evidence.source_url,
          evidence.verification_status
        FROM research.market_share_observations share
        JOIN research.fundamental_evidence evidence ON evidence.id=share.evidence_id
        WHERE share.company_id={company_id or -1}
        ORDER BY share.period_end DESC,share.market_key,share.geography LIMIT 80
    """)
    operating_peers = run_rows(f"""
        SELECT peer_set.peer_set_name,peer_set.methodology,membership.membership_role,membership.inclusion_reason,
          peer.legal_name,peer.primary_symbol,peer.primary_exchange,evidence.source_title,evidence.source_url,
          evidence.verification_status
        FROM research.peer_sets peer_set
        JOIN research.peer_set_memberships membership ON membership.peer_set_id=peer_set.id
        JOIN research.companies peer ON peer.id=membership.peer_company_id
        JOIN research.fundamental_evidence evidence ON evidence.id=membership.evidence_id
        WHERE peer_set.subject_company_id={company_id or -1}
          AND (peer_set.valid_to IS NULL OR peer_set.valid_to>=current_date)
        ORDER BY peer_set.valid_from DESC,membership.membership_role,peer.legal_name LIMIT 40
    """)
    history_facts = run_rows(f"""
        SELECT sf.fact_key,sf.fiscal_year,sf.value,sf.unit,sf.source_page,
               sf.reported_line,sf.extraction_status,run.source_url
        FROM research.financial_source_facts sf
        JOIN research.financial_production_runs run ON run.id=sf.production_run_id
        WHERE sf.company_id={company_id or -1}
          AND sf.fiscal_year BETWEEN 2017 AND 2026
          AND sf.extraction_status IN ('validated','human_reviewed')
        ORDER BY sf.fiscal_year,sf.fact_key LIMIT 640
    """)
    segment_history = run_rows(f"""
        SELECT fiscal_year,segment_type,segment_key,segment_name,metric_key,value,
               source_page,extraction_status,exception_reason
        FROM research.financial_segment_facts
        WHERE company_id={company_id or -1} AND fiscal_year BETWEEN 2017 AND 2026
        ORDER BY fiscal_year,segment_type,segment_key,metric_key LIMIT 180
    """)
    history_gaps = run_rows(f"""
        SELECT section_key,metric_key,gap_status,reason,next_source
        FROM research.financial_history_gaps WHERE company_id={company_id or -1}
        ORDER BY section_key,metric_key LIMIT 40
    """)
    production_ratios = run_rows(f"""
        SELECT fd.formula_key,fd.label,fd.expression,fd.basis,fd.unit,rr.period_end,rr.value,
               rr.calculation_status,rr.caveats,
               jsonb_agg(jsonb_build_object('input_role',ri.input_role,'fact_key',sf.fact_key,'fiscal_year',sf.fiscal_year,
                 'value',sf.value,'unit',sf.unit,'source_page',sf.source_page,'source_url',source_run.source_url,'reported_line',sf.reported_line)
                 ORDER BY ri.input_role) inputs
        FROM research.financial_ratio_results rr
        JOIN research.financial_formula_definitions fd ON fd.id=rr.formula_definition_id
        LEFT JOIN research.financial_ratio_inputs ri ON ri.ratio_result_id=rr.id
        LEFT JOIN research.financial_source_facts sf ON sf.id=ri.fact_id
        LEFT JOIN research.financial_production_runs source_run ON source_run.id=sf.production_run_id
        WHERE rr.company_id={company_id or -1}
        GROUP BY rr.id,fd.id ORDER BY rr.period_end DESC,fd.label LIMIT 200
    """)
    validation_checks = run_rows(f"""
        SELECT vc.check_type,vc.period_end,vc.status,vc.left_value,vc.right_value,
               vc.explanation,vc.source_pages
        FROM research.financial_validation_checks vc
        JOIN research.financial_production_runs run ON run.id=vc.production_run_id
        WHERE run.company_id={company_id or -1}
        ORDER BY vc.period_end DESC,vc.check_key LIMIT 80
    """)
    risks = run_rows(f"""
        SELECT o.category,o.severity,o.conclusion,o.disclosed_value,o.disclosed_unit,
               o.period_end,o.source_page,o.verification_status,e.source_title,e.source_url
        FROM research.governance_forensic_observations o
        JOIN research.fundamental_evidence e ON e.id=o.evidence_id
        WHERE o.company_id={company_id or -1} AND o.verification_status NOT IN ('rejected','superseded')
        ORDER BY CASE o.severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 ELSE 3 END,o.id DESC LIMIT 20
    """)
    filings = run_rows(f"""
        SELECT title,event_type,filed_at,source_url,attachment_url,extraction_status
        FROM research.corporate_filings WHERE upper(symbol)=upper({sql_literal(selected.get('symbol'))})
        ORDER BY filed_at DESC,id DESC LIMIT 20
    """)
    covered = sum(1 for row in matrix if row.get("coverage_status") == "covered")
    pending = sum(1 for row in matrix if row.get("coverage_status") == "pending_review")
    missing = sum(1 for row in matrix if row.get("coverage_status") == "missing")
    stale = sum(1 for row in matrix if row.get("coverage_status") == "stale")
    debt = sum(int(row.get("coverage_debt") or 0) for row in matrix)
    version_row = run_rows(f"SELECT coalesce(max(report_version),0)+1 next_version FROM research.thesis_reports WHERE holding_thesis_id={int(thesis_id)}")
    version = int((version_row or [{}])[0].get("next_version") or 1)
    as_of = date.today().isoformat()
    generated_at = datetime.now(timezone.utc).isoformat()
    symbol = str(selected.get("symbol") or selected.get("primary_symbol") or "company").upper()
    report_key = f"thesis-{thesis_id}-v{version}-{as_of}"
    report_root = Path("/Volumes/Devarsh SSD/AI OS Data/reports/long-term-thesis") / symbol
    if not Path("/Volumes/Devarsh SSD").is_mount():
        raise RuntimeError("Devarsh SSD is not mounted; report generation refuses internal-disk fallback")
    report_root.mkdir(parents=True, exist_ok=True)
    report_path = report_root / f"{report_key}.html"

    group = (quality.get("basis_groups") or [{}])[0]
    series = list(group.get("series") or [])[-10:]
    scale = 100.0 if group.get("unit") == "lakh" else 1.0
    unit_label = "₹ crore" if group.get("currency") == "INR" and group.get("unit") == "lakh" else f"{group.get('currency','')} {group.get('unit','')}"
    financial_rows = "".join(
        "<tr>" +
        f"<th>FY{row.get('fiscal_year')}</th>" +
        f"<td>{_metric_value((row.get('metrics') or {}).get('revenue_from_operations'),scale)}</td>" +
        f"<td>{_metric_value((row.get('metrics') or {}).get('profit_after_tax'),scale)}</td>" +
        f"<td>{_metric_value((row.get('metrics') or {}).get('operating_cash_flow'),scale)}</td>" +
        f"<td>{_metric_value((row.get('derived') or {}).get('fcf'),scale)}</td>" +
        f"<td>{_metric_value((row.get('derived') or {}).get('cfo_pat_conversion_pct'),1,'%')}</td>" +
        f"<td>{_metric_value((row.get('derived') or {}).get('net_debt'),scale)}</td>" +
        f"<td>{_esc(row.get('verification_status'))}</td></tr>"
        for row in series
    ) or "<tr><td colspan='8'>Not available: no comparable annual series.</td></tr>"
    section_rows = "".join(
        f"<article class='section-summary'><strong>{_esc(row.get('section_title') or row.get('section_key'))}</strong>"
        f"<p>{_esc(_compact_text(row.get('content_markdown'), 460))}</p>"
        f"<small>{_esc(row.get('verification_status') or 'Source status unavailable')} · "
        f"{_source_anchor(row.get('source_url'), row.get('source_title') or 'Primary evidence')}</small></article>"
        for row in sections
    ) or "<p class='missing'>No source-linked dossier sections are available.</p>"
    valuation_rows = "".join(
        f"<tr><th>{_esc(row.get('model_name'))}</th><td>{_esc(row.get('updated_at') or 'Not recorded')}</td>"
        f"<td>{_esc(row.get('status') or 'Missing')}</td><td>{_esc(row.get('model_type') or 'model scenario')}</td>"
        f"<td>{_esc(_model_value(row,'fair_value_low'))}</td><td>{_esc(_model_value(row,'fair_value_base'))}</td>"
        f"<td>{_esc(_model_value(row,'fair_value_high'))}</td><td>{_esc(_model_value(row,'expected_cagr_pct','%'))}</td>"
        f"<td>{_model_evidence_summary(row.get('assumptions') or {})}</td></tr>"
        for row in models
    ) or "<tr><td colspan='9'>No validated valuation scenario is available. No forecast has been invented.</td></tr>"
    source_rows = "".join(
        f"<tr><th>{_esc(row.get('requirement_label'))}</th><td>{_esc(row.get('section_key'))}</td>"
        f"<td>{_esc(row.get('coverage_status'))}</td><td>{_esc(row.get('coverage_debt'))}</td>"
        f"<td>{_esc(row.get('latest_publication_date') or 'Not recorded')}</td>"
        f"<td>{_source_list(row.get('sources'))}</td></tr>" for row in matrix
    )
    latest = series[-1] if series else {}
    latest_derived = latest.get("derived") or {}
    capital_rows = "".join(
        f"<tr><th>{_esc(label)}</th><td>{_esc(_metric_value(latest_derived.get(key), scale if key in {'closing_invested_capital','average_invested_capital','nopat'} else 1, '%' if key in {'roce_pct','roic_pct','roe_pct','capex_reinvestment_pct','reinvestment_rate'} else ''))}</td>"
        f"<td>{_esc((latest_derived.get(key) or {}).get('formula') or 'Formula unavailable')}</td><td>{_esc(', '.join((latest_derived.get(key) or {}).get('missing_inputs') or []))}</td></tr>"
        for key,label in (("closing_invested_capital","Closing invested capital"),("average_invested_capital","Average invested capital"),("nopat","NOPAT"),("capital_turnover","Capital turnover"),("roce_pct","ROCE"),("roic_pct","ROIC"),("roe_pct","ROE"),("capex_reinvestment_pct","Capex / revenue"),("reinvestment_rate","Reinvestment rate"))
    )
    production_ratio_rows = "".join(
        f"<tr><th>{_esc(row.get('label'))}</th><td>{_esc(row.get('period_end'))}</td>"
        f"<td>{float(row.get('value')):,.2f} {_esc(row.get('unit'))}</td>"
        f"<td>{_esc(row.get('expression'))}</td><td>{_ratio_inputs_summary(row.get('inputs'))}</td></tr>"
        for row in production_ratios if row.get('value') is not None
    ) or "<tr><td colspan='5'>No reconciled ratio-production run is available.</td></tr>"
    validation_rows = "".join(
        f"<tr><th>{_esc(row.get('check_type'))}</th><td>{_esc(row.get('period_end'))}</td><td>{_esc(row.get('status'))}</td><td>{_esc(row.get('explanation'))}</td><td>{_esc(row.get('source_pages'))}</td></tr>"
        for row in validation_checks
    ) or "<tr><td colspan='5'>No reconciliation checks are available.</td></tr>"
    guidance_rows = "".join(
        f"<tr><th>{_esc(row.get('metric_key'))}</th><td>{_esc(row.get('target_operator'))} {_esc(row.get('target_value'))} {_esc(row.get('target_unit'))}</td><td>{_esc(row.get('target_period_end'))}<br><small>Given {_esc(row.get('claim_date'))}</small></td><td>{_esc(row.get('actual_value') if row.get('actual_value') is not None else 'No outcome yet')} {_esc(row.get('actual_unit'))}</td><td>{_esc(row.get('outcome_status') or row.get('claim_status'))}</td><td><a href='{_esc(row.get('source_url'))}'>{_esc(row.get('source_title'))}</a></td></tr>" for row in guidance
    ) or "<tr><td colspan='6'>No exact management guidance is captured.</td></tr>"
    segment_rows = "".join(
        f"<tr><th>{_esc(row.get('segment_name'))}</th><td>FY{_esc(row.get('fiscal_year'))}</td><td>{_esc(row.get('canonical_name'))}</td>"
        f"<td>{float(row.get('value_numeric') or 0)/(100 if row.get('unit')=='lakh' else 1):,.1f} {_esc('INR crore' if row.get('currency')=='INR' and row.get('unit')=='lakh' else row.get('unit'))}</td>"
        f"<td>{_esc(_locator_summary(row.get('source_locator')))}</td><td>{_source_anchor(row.get('source_url'), row.get('source_title') or 'Source')}</td></tr>" for row in segments
    ) or "<tr><td colspan='6'>No segment facts are captured; no segment economics are inferred.</td></tr>"
    history_by_year = {}
    for row in history_facts:
        history_by_year.setdefault(int(row.get("fiscal_year") or 0), {})[str(row.get("fact_key"))] = row

    history_aliases = {
        "revenue": "revenue_from_operations", "pat_continuing": "profit_after_tax",
        "pat_total": "profit_after_tax", "cfo": "operating_cash_flow",
        "capex": "capital_expenditure", "cash": "cash_and_cash_equivalents",
        "ppe": "property_plant_equipment", "cwip": "capital_work_in_progress",
        "current_assets": "total_current_assets", "current_liabilities": "total_current_liabilities",
        "depreciation": "depreciation_amortisation", "material_cost": "cost_of_materials_consumed",
        "employee_expense": "employee_benefit_expense", "other_expense": "manufacturing_other_expenses",
        "total_expense": "total_expenses", "pbt_pre_jv_exceptional": "profit_before_joint_venture",
        "pbt_continuing": "profit_before_tax",
    }

    def history_row(year, key):
        rows_for_year = history_by_year.get(year, {})
        return rows_for_year.get(key) or rows_for_year.get(history_aliases.get(key, "")) or {}

    def history_value(year, key):
        row = history_row(year, key)
        value = row.get("value")
        return float(value) if value is not None else None

    def crore_cell(year, key):
        row = history_row(year, key)
        value = row.get("value")
        if value is None:
            return "—"
        source = row.get("source_url")
        citation = f"<a class='cite' href='{_esc(source)}'>p.{int(row.get('source_page') or 0)}</a>" if source else ""
        numeric = float(value) / 100.0
        shown = f"({abs(numeric):,.1f})" if numeric < 0 else f"{numeric:,.1f}"
        return f"{shown}{citation}"

    def raw_cell(year, key, suffix=""):
        row = history_row(year, key)
        value = row.get("value")
        if value is None:
            return "—"
        source = row.get("source_url")
        citation = f"<a class='cite' href='{_esc(source)}'>p.{int(row.get('source_page') or 0)}</a>" if source else ""
        return f"{float(value):,.2f}{suffix}{citation}"

    history_years = sorted(year for year in history_by_year if year > 0)[-10:]
    history_head = "".join(f"<th>FY{str(year)[-2:]}</th>" for year in history_years)
    historical_line_rows = []
    for label, key, kind in (
        ("Revenue", "revenue", "crore"),
        ("EBITDA", "ebitda", "derived"),
        ("EBIT before exceptional", "ebit", "derived"),
        ("Continuing PAT", "pat_continuing", "crore"),
        ("Total PAT", "pat_total", "crore"),
        ("Cash from operations", "cfo", "crore"),
        ("Capital expenditure", "capex", "crore"),
        ("Free cash flow", "fcf", "derived"),
        ("Total assets", "total_assets", "crore"),
        ("Total equity", "total_equity", "crore"),
        ("Borrowings", "borrowings", "derived"),
        ("Cash", "cash", "crore"),
        ("Dividends paid", "dividends_paid", "crore"),
        ("Basic EPS total", "eps_basic_total", "raw"),
    ):
        cells = []
        for year in history_years:
            if kind == "crore":
                cells.append(crore_cell(year, key))
            elif kind == "raw":
                cells.append(raw_cell(year, key))
            else:
                if key == "ebitda":
                    value = sum(history_value(year, metric) or 0 for metric in ("pbt_pre_jv_exceptional", "finance_cost", "depreciation"))
                elif key == "ebit":
                    value = sum(history_value(year, metric) or 0 for metric in ("pbt_pre_jv_exceptional", "finance_cost"))
                elif key == "fcf":
                    value = (history_value(year, "cfo") or 0) - abs(history_value(year, "capex") or 0)
                else:
                    value = sum(history_value(year, metric) or 0 for metric in ("current_borrowings", "non_current_borrowings"))
                cells.append(f"{value / 100:,.1f}")
        historical_line_rows.append(f"<tr><th>{_esc(label)}</th>{''.join(f'<td>{cell}</td>' for cell in cells)}</tr>")
    historical_model_rows = "".join(historical_line_rows)

    def statement_rows(spec):
        rows = []
        for label, key in spec:
            rows.append(f"<tr><th>{_esc(label)}</th>{''.join(f'<td>{crore_cell(year,key)}</td>' for year in history_years)}</tr>")
        return "".join(rows)

    income_statement_rows = statement_rows((
        ("Revenue","revenue"),("Other income","other_income"),("Total income","total_income"),
        ("Materials","material_cost"),("Inventory change","inventory_change"),("Employee expense","employee_expense"),
        ("Finance cost","finance_cost"),("Depreciation and amortisation","depreciation"),("Other expense","other_expense"),
        ("Total expense","total_expense"),("PBT — continuing","pbt_continuing"),("Tax","tax_expense"),
        ("PAT — continuing","pat_continuing"),("PAT — total","pat_total"),
    ))
    balance_sheet_rows = statement_rows((
        ("Property, plant and equipment","ppe"),("Capital work in progress","cwip"),("Inventory","inventory"),
        ("Trade receivables","trade_receivables"),("Cash","cash"),("Other bank balances","other_bank_balances"),
        ("Current assets","current_assets"),("Total assets","total_assets"),("Total equity","total_equity"),
        ("Current borrowings","current_borrowings"),("Non-current borrowings","non_current_borrowings"),
        ("Lease liabilities","lease_liabilities_total"),("Trade payables","trade_payables"),
        ("Current liabilities","current_liabilities"),("Total liabilities","total_liabilities"),
    ))
    cash_flow_rows = statement_rows((
        ("Cash from operations","cfo"),("Capital expenditure","capex"),("Investing cash flow","cfi"),
        ("Financing cash flow","cff"),("Dividends paid","dividends_paid"),("Closing cash","closing_cash"),
    ))

    segment_index = {}
    for row in segment_history:
        segment_index[(int(row.get("fiscal_year") or 0), str(row.get("segment_key")), str(row.get("metric_key")))] = row

    def segment_cell(year, segment_key, metric_key):
        row = segment_index.get((year, segment_key, metric_key)) or {}
        if row.get("value") is None or row.get("extraction_status") == "blocked":
            return "Withheld" if row.get("extraction_status") == "blocked" else "—"
        return f"{float(row.get('value')) / 100:,.1f}<small>p.{int(row.get('source_page') or 0)}</small>"

    segment_history_rows = "".join(
        f"<tr><th>{_esc(label)}</th>{''.join(f'<td>{segment_cell(year, segment_key, metric_key)}</td>' for year in history_years)}</tr>"
        for label, segment_key, metric_key in (
            ("Wire revenue", "wire", "revenue"),
            ("Wire result before finance/tax", "wire", "result"),
            ("Wire assets", "wire", "assets"),
            ("Wire liabilities", "wire", "liabilities"),
            ("Others revenue", "others", "revenue"),
            ("Others result", "others", "result"),
            ("India revenue", "india", "revenue"),
            ("Outside-India revenue", "outside_india", "revenue"),
        )
    )
    gap_rows = "".join(
        f"<tr><th>{_esc(str(row.get('metric_key') or '').replace('_',' '))}</th><td>{_esc(row.get('gap_status'))}</td><td>{_esc(row.get('reason'))}</td><td>{_esc(row.get('next_source'))}</td></tr>"
        for row in history_gaps
    )
    operating_kpi_rows = "".join(
        f"<tr><th>{_esc(row.get('kpi_name'))}</th><td>{_esc(row.get('period_end'))}</td>"
        f"<td>{_esc(row.get('value_text') if row.get('value_numeric') is None else row.get('value_numeric'))} {_esc(row.get('unit'))}</td>"
        f"<td>{_esc(row.get('description'))}</td><td><a href='{_esc(row.get('source_url'))}'>{_esc(row.get('source_title'))}</a></td></tr>"
        for row in operational_kpis
    ) or "<tr><td colspan='5'>Not available: no source-linked operating KPI history is captured.</td></tr>"
    industry_rows = "".join(
        f"<article><strong>{_esc(row.get('category')).replace('_',' ')}</strong><p>{_esc(row.get('conclusion'))}</p>"
        f"<small>{_esc(row.get('period_end'))} · {_esc(row.get('source_title'))} p.{_esc(row.get('source_page'))}</small></article>"
        for row in industry_observations
    ) or "<p class='missing'>No validated industry / competitive observations are available.</p>"
    market_share_rows = "".join(
        f"<tr><th>{_esc(row.get('market_name'))}</th><td>{_esc(row.get('product_or_service'))}</td><td>{_esc(row.get('geography'))}</td>"
        f"<td>{_esc(row.get('share_pct'))}%</td><td>{_esc(row.get('measurement_basis'))}</td></tr>"
        for row in market_shares
    ) or "<tr><td colspan='5'>Not available: no compatible primary-source TAM or market-share denominator has been validated.</td></tr>"
    peer_rows = "".join(
        f"<tr><th>{_esc(row.get('legal_name'))}</th><td>{_esc(row.get('primary_exchange'))}:{_esc(row.get('primary_symbol'))}</td>"
        f"<td>{_esc(row.get('membership_role'))}</td><td>{_esc(row.get('inclusion_reason'))}</td></tr>"
        for row in operating_peers
    ) or "<tr><td colspan='4'>Not available: compatible peer valuation and return data have not been validated.</td></tr>"

    valuation_range_rows = "".join(
        f"<article><span>{_esc(row.get('model_name'))}</span><div class='range'><i></i><b>₹{_esc(row.get('fair_value_low'))}</b><strong>₹{_esc(row.get('fair_value_base'))}</strong><b>₹{_esc(row.get('fair_value_high'))}</b></div><small>{_esc(row.get('status'))} · {_esc(row.get('model_type'))}</small></article>"
        for row in models if row.get('fair_value_base') is not None
    ) or "<p class='missing'>No source-backed valuation range is currently available.</p>"
    dcf_model = models_by_type.get("dcf") or {}
    reverse_dcf_model = models_by_type.get("reverse_dcf") or {}
    multiples_model = models_by_type.get("multiples") or {}
    monte_carlo_model = models_by_type.get("monte_carlo") or {}
    dcf_assumptions = dcf_model.get("assumptions") or {}
    reverse_assumptions = reverse_dcf_model.get("assumptions") or {}
    reverse_outputs = reverse_dcf_model.get("outputs") or {}
    monte_assumptions = monte_carlo_model.get("assumptions") or {}
    monte_outputs = monte_carlo_model.get("outputs") or {}
    normalized_fcf = _nested(dcf_assumptions, "financial_snapshot", "normalized_fcf_crore")
    latest_fcf = _nested(dcf_assumptions, "fcf_history", default=[])
    latest_fcf = latest_fcf[-1].get("fcf_crore") if latest_fcf and isinstance(latest_fcf[-1], dict) else None
    reverse_implied_growth = reverse_outputs.get("implied_annual_fcf_growth")
    reverse_discount = reverse_assumptions.get("discount_rate")
    reverse_terminal = reverse_assumptions.get("terminal_growth")
    reverse_years = reverse_assumptions.get("years")
    quote_as_of = _nested(dcf_assumptions, "current_price_source", "quote_ts", default="Not recorded")
    legacy_monte_method = monte_assumptions.get("method") or monte_outputs.get("method") or "Not recorded"
    legacy_monte_simulations = monte_assumptions.get("simulation_count")
    normalized_fcf_label = f"₹{float(normalized_fcf):,.1f}cr" if normalized_fcf is not None else "Not available"
    latest_fcf_label = f"₹{float(latest_fcf):,.1f}cr" if latest_fcf is not None else "Not available"
    reverse_growth_label = _pct(reverse_implied_growth, 1)
    reverse_discount_label = _pct(reverse_discount, 1)
    reverse_terminal_label = _pct(reverse_terminal, 1)
    dcf_range_label = (
        f"₹{float(dcf_model.get('fair_value_low')):,.0f} / ₹{float(dcf_model.get('fair_value_base')):,.0f} / ₹{float(dcf_model.get('fair_value_high')):,.0f}"
        if all(dcf_model.get(key) is not None for key in ("fair_value_low", "fair_value_base", "fair_value_high"))
        else "Not validated"
    )
    multiples_range_label = (
        f"₹{float(multiples_model.get('fair_value_low')):,.0f} / ₹{float(multiples_model.get('fair_value_base')):,.0f} / ₹{float(multiples_model.get('fair_value_high')):,.0f}"
        if all(multiples_model.get(key) is not None for key in ("fair_value_low", "fair_value_base", "fair_value_high"))
        else "Not validated"
    )

    if symbol == "USHAMART":
        header_summary = "Usha Martin is predominantly a wire-rope manufacturing and export franchise. FY2026 shows stronger margins, cash conversion and a move to net cash; valuation and governance conclusions remain pending human review."
        executive_summary = "Research conclusion: continue underwriting, not yet a buy decision. The positive change is operating leverage and cash conversion: revenue +6.2%, EBITDA +21.6%, margin +2.7pp, FCF ₹457.3 crore and net cash ₹96.3 crore. The key disconfirmers are unresolved governance review, unavailable segment capex/cash conversion, a geographic-revenue reconciliation exception and valuation assumptions that are not operator-reviewed."
        financial_story_text = "FY2026 revenue increased 6.2% to ₹3,691.1 crore; pre-exception EBITDA increased 21.6% to ₹774.0 crore and margin expanded from 18.3% to 21.0%. CFO rose to ₹655.3 crore and FCF to ₹457.3 crore. CFO / continuing PAT improved to 133.4%, and ₹76.8 crore net debt moved to ₹96.3 crore net cash. Values reconcile to the consolidated annual report and FY2025 comparative columns; they are not yet human-reviewed."
        segment_intro = "USHAMART reports Wire & Wire Ropes and Others on annual-report p.311. Business-segment revenue, result, assets and liabilities reconcile. Geographic revenue on p.311 does not reconcile to consolidated revenue and remains withheld. Segment capex and cash conversion are not disclosed."
        segment_rows = "<tr><th>Wire &amp; Wire Ropes</th><td>FY2026</td><td>Revenue / result before finance and tax</td><td>₹3,613.1cr / ₹650.4cr</td><td>Reconciles on p.311</td><td><a href='https://ushamartin.com/public/upload/investorrelations/Annual-Report-FY-2025-26.pdf'>Official annual report p.311</a></td></tr><tr><th>Others</th><td>FY2026</td><td>Revenue / result before finance and tax</td><td>₹78.0cr / (₹1.6cr)</td><td>Reconciles on p.311</td><td><a href='https://ushamartin.com/public/upload/investorrelations/Annual-Report-FY-2025-26.pdf'>Official annual report p.311</a></td></tr>"
        headline_grid = "<div><span>FY2026 revenue</span><strong>₹3,691cr</strong></div><div><span>EBITDA margin</span><strong>21.0%</strong></div><div><span>Free cash flow</span><strong>₹457cr</strong></div><div><span>Net cash</span><strong>₹96cr</strong></div>"
    else:
        first_year = history_years[0] if history_years else 0
        latest_year = history_years[-1] if history_years else 0
        first_revenue = history_value(first_year, "revenue")
        latest_revenue = history_value(latest_year, "revenue")
        latest_pat = history_value(latest_year, "pat_total")
        latest_cfo = history_value(latest_year, "cfo")
        latest_capex = abs(history_value(latest_year, "capex") or 0)
        latest_fcf_generic = (latest_cfo - latest_capex) if latest_cfo is not None else None
        latest_debt = (history_value(latest_year, "current_borrowings") or 0) + (history_value(latest_year, "non_current_borrowings") or 0)
        latest_cash = (history_value(latest_year, "cash") or 0) + (history_value(latest_year, "other_bank_balances") or 0)
        revenue_cagr = None
        if first_revenue and latest_revenue and latest_year > first_year:
            revenue_cagr = (latest_revenue / first_revenue) ** (1 / (latest_year - first_year)) - 1
        ratio_index = {(str(row.get("formula_key")), str(row.get("period_end"))[:4]): row for row in production_ratios}
        def latest_ratio(key):
            row = ratio_index.get((key, str(latest_year))) or {}
            return float(row.get("value")) if row.get("value") is not None else None
        ebitda_margin_generic = latest_ratio("ebitda_margin")
        cfo_pat_generic = latest_ratio("cfo_pat")
        roce_generic = latest_ratio("roce_proxy")
        header_summary = str(selected.get("thesis_summary") or "No persisted thesis conclusion.")
        executive_summary = str(selected.get("thesis_summary") or "No human-reviewed investment conclusion is recorded.")
        if history_years and all(value is not None for value in (latest_revenue, latest_pat, latest_cfo, latest_fcf_generic)):
            financial_story_text = (
                f"The validated consolidated history spans FY{first_year}–FY{latest_year}. Revenue reached ₹{latest_revenue/100:,.1f} crore"
                + (f", a {revenue_cagr*100:.1f}% CAGR" if revenue_cagr is not None else "")
                + f"; PAT was ₹{latest_pat/100:,.1f} crore, CFO ₹{latest_cfo/100:,.1f} crore and FCF ₹{latest_fcf_generic/100:,.1f} crore. "
                + (f"EBITDA margin was {ebitda_margin_generic:.1f}%, " if ebitda_margin_generic is not None else "")
                + (f"CFO/PAT {cfo_pat_generic:.1f}% and " if cfo_pat_generic is not None else "")
                + (f"the transparent ROCE proxy {roce_generic:.1f}%. " if roce_generic is not None else "")
                + "Every figure is linked to an official annual-report page and all balance-sheet, P&L and cash-flow checks passed. Values are deterministically validated, not yet human-reviewed."
            )
        else:
            financial_story_text = "A comparable validated multi-year financial history is not yet available. Missing periods remain explicit and no value is inferred or zero-filled."
        segment_intro = "Segment values appear only where disclosed; unsupported economics remain unavailable."
        headline_grid = (
            f"<div><span>FY{latest_year} revenue</span><strong>{'₹'+format(latest_revenue/100, ',.1f')+'cr' if latest_revenue is not None else 'Not available'}</strong></div>"
            f"<div><span>EBITDA margin</span><strong>{format(ebitda_margin_generic, '.1f')+'%' if ebitda_margin_generic is not None else 'Not available'}</strong></div>"
            f"<div><span>Free cash flow</span><strong>{'₹'+format(latest_fcf_generic/100, ',.1f')+'cr' if latest_fcf_generic is not None else 'Not available'}</strong></div>"
            f"<div><span>Net cash / (debt)</span><strong>{'₹'+format((latest_cash-latest_debt)/100, ',.1f')+'cr' if history_years else 'Not available'}</strong></div>"
        )
    usha_investor_sections = ""
    if symbol == "USHAMART":
        usha_investor_sections = """<style>.story-grid,.moat-grid,.method-bridge{display:grid;gap:14px;margin:20px 0}.story-grid,.moat-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.method-bridge{grid-template-columns:repeat(3,minmax(0,1fr))}.story-grid article,.moat-grid article,.method-bridge article{background:#fffdf8;border:1px solid #d8cebd;border-top:4px solid #9a6c23;padding:18px;break-inside:avoid}.story-grid strong,.moat-grid strong,.method-bridge strong{display:block;font:700 18px/1.2 Georgia,serif;margin:8px 0}.story-grid p,.moat-grid p,.method-bridge p{margin:8px 0}.story-grid small,.moat-grid small,.method-bridge small{color:#655f56}.method-bridge article{border-top-color:#172c3b}.method-bridge span{display:block;color:#9a6c23;font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase}.status{display:inline-block!important;padding:3px 7px;border-radius:999px;background:#eee6d8;color:#6b4a14!important;font:700 10px/1.2 ui-sans-serif,system-ui!important;letter-spacing:.05em;text-transform:uppercase}.status.unproven,.status.caution{background:#f2dfdc;color:#7c342f!important}.definition-note{background:#eee6d8;border-left:4px solid #9a6c23;padding:13px 16px}@media(max-width:700px){.story-grid,.moat-grid,.method-bridge{grid-template-columns:1fr}}@media print{.story-grid,.moat-grid{grid-template-columns:repeat(2,1fr)}.method-bridge{grid-template-columns:repeat(3,1fr)}.story-grid article,.moat-grid article,.method-bridge article{font-size:11px;padding:12px}}</style><section class='argument'><div><span class='kicker'>Investment argument</span><h2>Operating quality improved sharply; valuation still fails the proof test.</h2><p>FY2026 revenue grew 6.2%, EBITDA increased 21.6%, FCF reached ₹457.3 crore and the balance sheet moved to ₹96.3 crore net cash. The last stored read-only quote was ₹515.30 on 8 August 2026; the unreviewed DCF range of ₹58–175 and earnings-multiple range of ₹290–516 do not support a capital decision without refreshed price and operator-reviewed assumptions.</p></div><aside><strong>Decision</strong><p>Continue research. Avoid adding until valuation, capex returns and operating drivers are re-underwritten.</p></aside></section>
<section><h2>FY2026 financial and return bridge</h2><div class='grid six'><div><span>Revenue</span><strong>₹3,691cr</strong><small>+6.2%</small></div><div><span>Pre-exception EBITDA</span><strong>₹774cr</strong><small>21.0% margin</small></div><div><span>Continuing PAT</span><strong>₹491cr</strong><small>+20.9%</small></div><div><span>FCF</span><strong>₹457cr</strong><small>93.1% of PAT</small></div><div><span>ROCE</span><strong>21.79%</strong><small>financing-capital basis</small></div><div><span>ROIC</span><strong>16.74%</strong><small>NOPAT / avg capital</small></div></div><div class='bridge'><div><span>EBIT margin</span><b>17.81%</b><small>657.6 / 3,691.1</small></div><em>×</em><div><span>Capital turnover</span><b>1.22×</b><small>3,691.1 / 3,017.2</small></div><em>=</em><div><span>ROCE</span><b>21.79%</b><small>FY2026 calculated</small></div></div><p class='note'>Capital = equity + current and non-current borrowings − cash; average FY2025/FY2026 basis. Maintenance versus growth capex is not disclosed. Source: Annual Report pp.240–243.</p><p class='definition-note'><strong>Two EBITDA definitions are kept separate:</strong> ₹774cr / 21.0% is the report's deterministic pre-exception calculation from the audited statements. Management reports operating EBITDA of ₹705cr / 19.1% on p.18. The ₹69cr difference is not bridged in the current evidence, so neither definition is silently relabelled.</p></section>
<section><span class='kicker'>Story behind the numbers</span><h2>FY2026 was a cash-conversion year; the unresolved question is durability.</h2><div class='story-grid'><article><strong>1 · Modest sales, faster profit</strong><p>Revenue rose 6.2%, while the statement-derived pre-exception EBITDA rose 21.6% and continuing PAT rose 20.9%. That spread is consistent with operating leverage, but the reports do not provide a reconciled volume / price / mix bridge, so the exact cause is not asserted.</p><small>Annual Report pp.240–243; management operating-EBITDA definition on p.18.</small></article><article><strong>2 · Earnings converted to cash</strong><p>CFO reached ₹655.3cr versus continuing PAT of ₹491.2cr. After ₹198.1cr of capex, FCF was ₹457.3cr. This is stronger evidence than accounting profit alone, but one year does not prove a durable conversion rate.</p><small>Annual Report pp.242–243; FCF = CFO − capex.</small></article><article><strong>3 · Financing risk fell</strong><p>₹76.8cr of FY2025 net debt moved to ₹96.3cr of FY2026 net cash. The balance sheet can fund reinvestment more safely, but management's planned ₹200–250cr annual capex still needs an incremental-return test.</p><small>Annual Report pp.19, 22, 240–243.</small></article><article><strong>4 · Returns improved, proof remains incomplete</strong><p>ROCE decomposes to 17.81% EBIT margin × 1.22× capital turnover. The next proof is whether new capacity sustains margins and turnover rather than merely expanding the asset base.</p><small>Calculated from reconciled statement inputs; segment capex and cash flow are not disclosed.</small></article></div></section>
"""
        usha_investor_sections += f"""
<section><span class='kicker'>A · Thesis evolution</span><h2>From divestiture clean-up to cash-generative wire-rope reinvestment</h2><table><thead><tr><th>Phase</th><th>Evidence</th><th>Investor interpretation</th></tr></thead><tbody><tr><th>FY2020 scope break</th><td>Total PAT includes a material discontinued steel-business disposal gain; continuing PAT was negative.</td><td>Total and continuing earnings remain separate.</td></tr><tr><th>FY2021–FY2022 recovery</th><td>Continuing revenue recovered while financing cost declined.</td><td>Balance-sheet repair and operating normalization.</td></tr><tr><th>FY2023–FY2024 reinvestment</th><td>Capex increased and return margins inflected despite uneven revenue.</td><td>Returns must be judged across the investment cycle.</td></tr><tr><th>FY2025–FY2026 cash conversion</th><td>FY2026 CFO ₹655.3cr; cash exceeded borrowings.</td><td>Improved resilience, but valuation proof remains open.</td></tr></tbody></table></section>
<section><span class='kicker'>B · Growth and CAGR</span><h2>Ten-year historical financial model</h2><p>Consolidated, annual, INR crore unless stated. FY2020 total PAT is not comparable because of discontinued operations. EBITDA, EBIT, borrowings and FCF are deterministic calculations from cited source rows.</p><div class='scroll'><table class='history'><thead><tr><th>Metric</th>{history_head}</tr></thead><tbody>{historical_model_rows}</tbody></table></div><p class='missing'><strong>Volume / price / mix waterfall unavailable:</strong> annual reports do not provide compatible consolidated unit-volume, realized-price and mix inputs across FY2017–FY2026; FY2017–FY2018 remain explicitly non-comparable due to the legacy steel business.</p></section>
<section><span class='kicker'>C · Segment and geography economics</span><h2>Segment history with reconciliation</h2><div class='scroll'><table class='history'><thead><tr><th>Metric</th>{history_head}</tr></thead><tbody>{segment_history_rows}</tbody></table></div><p>Business-segment revenue, result, assets and liabilities reconcile to consolidated statements. FY2026 geographic revenue is withheld because the issuer table totals ₹95.4cr below consolidated revenue. Business-segment capex and cash flow are not disclosed.</p></section>
<section><span class='kicker'>Operating drivers, industry and peers</span><h2>Decision-relevant operating proof, not generic market labels</h2><h3>Operating KPI history</h3><div class='scroll'><table><thead><tr><th>KPI</th><th>Period</th><th>Value</th><th>Decision use</th><th>Evidence</th></tr></thead><tbody>{operating_kpi_rows}</tbody></table></div><h3>Industry and competitive evidence</h3><div class='observation-grid'>{industry_rows}</div><h3>Market share and TAM</h3><div class='scroll'><table><thead><tr><th>Market</th><th>Product</th><th>Geography</th><th>Share</th><th>Measurement basis</th></tr></thead><tbody>{market_share_rows}</tbody></table></div><h3>Scoped peer universe</h3><div class='scroll'><table><thead><tr><th>Company</th><th>Listing</th><th>Role</th><th>Inclusion rationale</th></tr></thead><tbody>{peer_rows}</tbody></table></div></section>
<section><span class='kicker'>D · Full financial statements</span><h2>Income statement, balance sheet, cash flow and capital allocation</h2><p>Consolidated, annual, INR crore. Each reported value links to its source page. FY2020 total PAT remains separate from continuing PAT because of the divested steel business.</p><h3>Income statement</h3><div class='scroll'><table class='history'><thead><tr><th>Metric</th>{history_head}</tr></thead><tbody>{income_statement_rows}</tbody></table></div><h3>Balance sheet</h3><div class='scroll'><table class='history'><thead><tr><th>Metric</th>{history_head}</tr></thead><tbody>{balance_sheet_rows}</tbody></table></div><h3>Cash flow and capital allocation</h3><div class='scroll'><table class='history'><thead><tr><th>Metric</th>{history_head}</tr></thead><tbody>{cash_flow_rows}</tbody></table></div></section>
<section><span class='kicker'>E · Ratio library and return drivers</span><h2>Profitability, returns, cash conversion, leverage and reinvestment</h2><p>The formula-linked annual ratio appendix covers FY2017–FY2026 where source inputs are comparable and exposes every input and source page. Gross margin, DIO, DPO and the full cash-conversion cycle are not calculated because material cost is not complete COGS. ROCE is decomposed into EBIT margin × capital turnover; ROIC uses NOPAT and average financing capital with explicit tax caveats.</p></section>
<section><span class='kicker'>F · Management, moat and governance</span><h2>Moat hypothesis: credible operating ingredients, not yet a proven durable advantage.</h2><p>A Buffett/Munger-style test asks whether the economics are understandable, repeat demand is real, customers are reluctant to switch, pricing power survives cycles, reinvestment earns high incremental returns, management allocates capital well and the purchase price provides a margin of safety. Current primary evidence supports parts of that chain, not the full conclusion.</p><div class='moat-grid'><article><span class='status supported'>Supported company claim</span><strong>Mission-critical replacement demand</strong><p>Management states that wire ropes are consumables replaced on safety-mandated cycles. That can create recurring demand after an installation win.</p><small><a href='https://ushamartin.com/public/upload/investorrelations/Annual-Report-FY-2025-26.pdf'>Annual Report p.19</a> · independent retention and replacement-frequency data are missing.</small></article><article><span class='status partial'>Partial evidence</span><strong>Qualification and process capability</strong><p>The company says selected high-end OceanMax orders moved from the UK plant to Ranchi after meeting customer requirements. This suggests qualification capability, but does not prove customer switching costs or price premiums.</p><small><a href='https://ushamartin.com/public/upload/investorrelations/Annual-Report-FY-2025-26.pdf'>Annual Report p.22</a></small></article><article><span class='status partial'>Partial evidence</span><strong>Scale and reinvestment runway</strong><p>Management reports 40,000 MT of added wire-and-rope capacity and plans approximately ₹200–250cr of annual capex. Scale can deepen capability; it can also dilute returns if utilization, mix and pricing lag.</p><small><a href='https://ushamartin.com/public/upload/investorrelations/Annual-Report-FY-2025-26.pdf'>Annual Report p.22</a> · incremental ROIC and segment capex are not disclosed.</small></article><article><span class='status unproven'>Unproven</span><strong>Pricing power</strong><p>The company describes a move from standard products to engineered, higher-performance solutions, but a reconciled volume / price / mix series and realized-price premium are absent.</p><small><a href='https://ushamartin.com/public/upload/investorrelations/Annual-Report-FY-2025-26.pdf'>Annual Report p.12</a></small></article><article><span class='status caution'>Counter-evidence</span><strong>Small global share</strong><p>Management explicitly says global market share is small and gives no numeric share. This may indicate runway, but it is not evidence of market power.</p><small><a href='https://ushamartin.com/public/upload/investorrelations/Annual-Report-FY-2025-26.pdf'>Annual Report p.18</a></small></article><article><span class='status unproven'>Decision gate</span><strong>Stewardship and margin of safety</strong><p>Net cash and stronger cash conversion improve resilience. Governance review, guidance delivery, compatible peers and a reviewed valuation are still incomplete, so the ownership test remains open.</p><small>No durable-moat score or clean-governance conclusion is assigned.</small></article></div><p class='definition-note'><strong>What would prove the compounder case:</strong> sustained high-end mix, repeat-customer evidence, realized pricing above input inflation, utilization of new capacity and incremental ROIC above an explicit user-reviewed hurdle. <strong>What breaks it:</strong> margin reversal, capital turnover decline, cash conversion deterioration, failed qualification, customer concentration or governance exceptions.</p></section>
<section><span class='kicker'>G · Valuation, catalysts, risks and decision</span><h2>One cash-flow basis, three questions; no method is allowed to hide the assumptions.</h2><div class='method-bridge'><article><span>1 · DCF: what normalized cash flow is worth</span><strong>{dcf_range_label}</strong><p>Bear / base / bull. The base starts from {normalized_fcf_label}, the median of FY2024–FY2026 positive CFO less capex, not the latest {latest_fcf_label}. That conservative normalization is the main reason the DCF sits far below the stored quote.</p><small>10-year scenarios: 3/8/12% FCF growth; 14/12/11% discount; 3/4/5% terminal growth. Complete but unreviewed.</small></article><article><span>2 · Reverse DCF: what the quote requires</span><strong>{reverse_growth_label} annual FCF growth</strong><p>At the stored ₹515.30 quote, the same normalized FCF and equity bridge require this constant growth rate for {reverse_years} years under a {reverse_discount_label} discount rate and {reverse_terminal_label} terminal growth.</p><small>Quote timestamp {_esc(quote_as_of)}. The quote is stale and the result is a market-implied hurdle, not a forecast.</small></article><article><span>3 · Monte Carlo: how uncertainty should be distributed</span><strong>Withheld pending method replacement</strong><p>The stored {int(legacy_monte_simulations or 0):,}-run module uses { _esc(legacy_monte_method) } with PAT, terminal multiples and simulated price paths. It is not comparable with the DCF and its stored path-to-terminal replay is not internally reliable.</p><small>The replacement must sample growth, discount rate, terminal growth and normalized FCF on the same DCF basis, preserve a fixed seed and publish percentiles and replay checks. A distribution is sensitivity analysis, not a separate fair-value truth.</small></article></div><div class='valuation-ranges'>{valuation_range_rows}</div><table><thead><tr><th>Method</th><th>Range / output</th><th>Question answered</th><th>Primary weakness</th><th>Decision use</th></tr></thead><tbody><tr><th>10-year DCF</th><td>{dcf_range_label}</td><td>What normalized cash flow supports</td><td>Long-duration growth and discount assumptions</td><td>Scenario underwrite only</td></tr><tr><th>Reverse DCF</th><td>{reverse_growth_label} implied annual FCF growth</td><td>What must be true at ₹515.30</td><td>Stale quote and constant-growth simplification</td><td>Expectation test</td></tr><tr><th>Earnings multiple</th><td>{multiples_range_label}</td><td>EPS sensitivity at 18× / 25× / 32×</td><td>No validated peer set or historical range</td><td>Cross-check only</td></tr><tr><th>Monte Carlo</th><td>Not accepted</td><td>Distribution of DCF outcomes</td><td>Legacy implementation mixes methods and fails replay</td><td>Withheld</td></tr></tbody></table><p><strong>Catalysts to monitor:</strong> capex conversion into segment returns, sustained FCF conversion and explicit operating guidance. <strong>Disconfirmers:</strong> margin reversal, weaker cash conversion, unreconciled disclosures or governance exceptions. <strong>Decision:</strong> continue research; no capital action is authorized.</p></section>
<section><span class='kicker'>Coverage debt</span><h2>Exact unavailable or blocked evidence</h2><table><thead><tr><th>Data point</th><th>Status</th><th>Reason</th><th>Next source</th></tr></thead><tbody>{gap_rows}</tbody></table></section>
"""

    risk_rows = "".join(
        f"<article class='risk'><strong>{_esc(row.get('severity'))} · {_esc(row.get('category'))}</strong><p>{_esc(row.get('conclusion'))}</p><a href='{_esc(row.get('source_url'))}'>Source: {_esc(row.get('source_title'))} · p.{_esc(row.get('source_page'))}</a></article>" for row in risks
    ) or "<p>No structured governance risk is captured; this is not evidence of clean governance.</p>"
    evolution_rows = "".join(
        f"<tr><td>{_esc(row.get('filed_at'))}</td><th>{_esc(row.get('title'))}</th><td>{_esc(row.get('event_type'))}</td><td>{_esc(row.get('extraction_status'))}</td><td><a href='{_esc(row.get('attachment_url') or row.get('source_url'))}'>Original</a></td></tr>" for row in filings
    ) or "<tr><td colspan='5'>No filing timeline is captured.</td></tr>"
    if symbol != "USHAMART":
        latest_year_label = f"FY{history_years[-1]}" if history_years else "Latest period unavailable"
        usha_investor_sections = f"""<style>.story-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:20px 0}}.story-grid article{{background:#fffdf8;border:1px solid #d8cebd;border-top:4px solid #9a6c23;padding:18px;break-inside:avoid}}.story-grid strong{{display:block;font:700 18px/1.2 Georgia,serif;margin:8px 0}}.story-grid small{{color:#655f56}}@media(max-width:700px){{.story-grid{{grid-template-columns:1fr}}}}</style>
<section class='argument'><div><span class='kicker'>Investment conclusion</span><h2>{_esc(executive_summary)}</h2><p>{_esc(financial_story_text)}</p></div><aside><strong>Decision boundary</strong><p>Research output only. A human-reviewed valuation and decision record are required before any capital action.</p></aside></section>
<section><span class='kicker'>A · Thesis evolution and numbers story</span><h2>{_esc(latest_year_label)} in the context of the full validated history</h2><p>{_esc(financial_story_text)}</p><div class='scroll'><table class='history'><thead><tr><th>Metric</th>{history_head}</tr></thead><tbody>{historical_model_rows}</tbody></table></div></section>
<section><span class='kicker'>B · Full financial model</span><h2>Income statement, balance sheet, cash flow and capital allocation</h2><p>Consolidated, annual, INR crore. Reported values preserve issuer sign and scope; derived FCF uses CFO minus the absolute capital-expenditure outflow.</p><h3>Income statement</h3><div class='scroll'><table class='history'><thead><tr><th>Metric</th>{history_head}</tr></thead><tbody>{income_statement_rows}</tbody></table></div><h3>Balance sheet</h3><div class='scroll'><table class='history'><thead><tr><th>Metric</th>{history_head}</tr></thead><tbody>{balance_sheet_rows}</tbody></table></div><h3>Cash flow and capital allocation</h3><div class='scroll'><table class='history'><thead><tr><th>Metric</th>{history_head}</tr></thead><tbody>{cash_flow_rows}</tbody></table></div></section>
<section><span class='kicker'>C · Business, industry and moat</span><h2>What is supported—and what still needs proof</h2><div class='section-summary-grid'>{section_rows}</div><h3>Operating KPI evidence</h3><div class='scroll'><table><thead><tr><th>KPI</th><th>Period</th><th>Value</th><th>Decision use</th><th>Evidence</th></tr></thead><tbody>{operating_kpi_rows}</tbody></table></div><h3>Industry observations</h3><div class='observation-grid'>{industry_rows}</div><h3>TAM and market share</h3><div class='scroll'><table><thead><tr><th>Market</th><th>Product</th><th>Geography</th><th>Share</th><th>Basis</th></tr></thead><tbody>{market_share_rows}</tbody></table></div><h3>Compatible peer universe</h3><div class='scroll'><table><thead><tr><th>Company</th><th>Listing</th><th>Role</th><th>Rationale</th></tr></thead><tbody>{peer_rows}</tbody></table></div></section>
<section><span class='kicker'>D · Ratio and return architecture</span><h2>Profitability, cash conversion, leverage, liquidity and capital efficiency</h2><p>Each calculated ratio below carries a versioned formula, accepted inputs and page locators. Unsupported ratios remain not computable.</p><div class='scroll'><table><thead><tr><th>Ratio</th><th>Period</th><th>Value</th><th>Formula</th><th>Inputs</th></tr></thead><tbody>{production_ratio_rows}</tbody></table></div></section>
<section><span class='kicker'>E · Valuation and expected return</span><h2>Model outputs remain separate from historical fact</h2><div class='valuation-ranges'>{valuation_range_rows}</div><p class='missing'>DCF, reverse DCF, multiples, historical ranges and Monte Carlo stay unavailable when a current price, share basis, normalized forecast inputs or reviewed assumptions are missing. No point estimate is invented.</p></section>
<section><span class='kicker'>F · Catalysts, risks and decision</span><h2>What can change the thesis</h2><div class='story-grid'><article><strong>Risk evidence</strong>{risk_rows}</article><article><strong>Latest filings and events</strong><div class='scroll'><table><thead><tr><th>Date</th><th>Event</th><th>Type</th><th>Status</th><th>Source</th></tr></thead><tbody>{evolution_rows}</tbody></table></div></article></div><p><strong>Decision:</strong> {_esc(selected.get('decision_status') or 'Research required')}. No broker, client or external write is authorized.</p></section>"""
    body = f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>{_esc(selected.get('legal_name') or selected.get('company_name'))} — Long-Term Thesis v{version}</title>
<style>:root{{--ink:#172c3b;--paper:#f5f0e6;--sheet:#fffdf8;--brass:#9a6c23;--risk:#8a3b35;--line:#d8cebd}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 ui-sans-serif,system-ui}}main{{max-width:1080px;margin:0 auto;padding:48px 32px}}header{{border-top:7px solid var(--ink);border-bottom:1px solid var(--line);padding:34px 0}}h1{{font:700 42px/1.05 Georgia,serif;margin:8px 0}}h2{{font:700 25px/1.15 Georgia,serif;margin-top:36px}}.kicker,.state{{color:var(--brass);font-weight:700;text-transform:uppercase;letter-spacing:.08em;font-size:12px}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin:26px 0}}.grid div{{background:var(--sheet);padding:18px}}.grid strong{{display:block;font-size:24px}}.grid.six{{grid-template-columns:repeat(6,1fr)}}.observation-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:18px 0}}.observation-grid article{{padding:16px;background:#fffdf8;border-top:3px solid var(--brass)}}.observation-grid strong{{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:#7a551a}}.observation-grid p{{margin:8px 0}}.valuation-ranges{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:20px 0}}.valuation-ranges article{{padding:16px;background:#fffdf8;border-top:3px solid var(--ink)}}.valuation-ranges span,.valuation-ranges small{{display:block;color:#655f56;font-size:11px}}.range{{display:grid;grid-template-columns:auto 1fr auto;gap:8px;align-items:center;margin:10px 0}}.range i{{height:4px;background:linear-gradient(90deg,#8a3b35,#9a6c23,#172c3b)}}.range strong{{font-size:21px}}.section-summary-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}.section-summary{{padding:15px;background:var(--sheet);border-top:3px solid var(--brass)}}.section-summary strong{{font:700 15px Georgia,serif}}.section-summary p{{margin:8px 0;font-size:12px}}.section-summary small{{font-size:11px;color:#655f56}}.argument{{display:grid;grid-template-columns:2fr 1fr;gap:28px;background:#fffdf8;border-left:6px solid var(--brass);padding:25px;margin:28px 0}}.argument h2{{margin:8px 0;font-size:31px}}.argument aside{{background:var(--ink);color:white;padding:22px}}.bridge{{display:grid;grid-template-columns:1fr auto 1fr auto 1fr;gap:12px;align-items:stretch;margin:20px 0}}.bridge div{{padding:18px;background:#fffdf8;border-top:3px solid var(--brass)}}.bridge b{{display:block;font:700 28px Georgia,serif;margin:8px 0}}.bridge em{{align-self:center;font-size:22px;color:var(--brass)}}.note{{font-size:12px;color:#655f56}}table{{width:100%;border-collapse:collapse;background:var(--sheet);font-size:13px}}th,td{{border:1px solid var(--line);padding:9px;text-align:left;vertical-align:top}}thead th{{background:var(--ink);color:white}}.missing{{color:var(--risk)}}code{{white-space:pre-wrap;font-size:11px}}a{{color:#6b4a14}}footer{{margin-top:50px;border-top:1px solid var(--line);padding-top:18px;color:#655f56}}@media(max-width:700px){{main{{padding:24px 14px}}h1{{font-size:32px}}.grid{{grid-template-columns:1fr 1fr}}.scroll{{overflow:auto}}}}@page{{size:A4;margin:14mm}}@media print{{body{{background:white}}main{{max-width:none;padding:0}}section{{break-inside:auto}}h2{{break-after:avoid}}table{{break-inside:auto}}tr{{break-inside:avoid}}a{{color:inherit;text-decoration:none}}}}</style></head>
<body><main><header><div class='kicker'>Long-Term Investment Thesis · version {version} · generated {_esc(generated_at)}</div><h1>{_esc(selected.get('legal_name') or selected.get('company_name'))}</h1><p>{_esc(selected.get('exchange'))}:{_esc(symbol)} · Research as of {_esc(as_of)} · Source cutoff {_esc(selected.get('updated_at'))}</p><p>{_esc(header_summary)}</p></header>
<div class='grid'>{headline_grid}</div>
<section><h2>Executive investment summary</h2><p>{_esc(executive_summary)}</p><p><strong>Decision ask:</strong> validate governance observations and operator-review valuation assumptions before any capital decision.</p></section>
{usha_investor_sections}
<section><h2>Appendix A · Segment source ledger</h2><p>{_esc(segment_intro)}</p><div class='scroll'><table><thead><tr><th>Segment</th><th>Period</th><th>Metric</th><th>Value</th><th>Reconciliation / locator</th><th>Evidence</th></tr></thead><tbody>{segment_rows}</tbody></table></div></section>
<section><h2>Appendix B · Ratio formulas, inputs and reconciliations</h2><p>{_esc(financial_story_text)}</p><div class='scroll'><table><thead><tr><th>Ratio</th><th>Period</th><th>Value</th><th>Formula</th><th>Inputs and page locators</th></tr></thead><tbody>{production_ratio_rows}</tbody></table></div><h3>Reconciliation and exceptions</h3><div class='scroll'><table><thead><tr><th>Check</th><th>Period</th><th>Status</th><th>Explanation</th><th>Pages</th></tr></thead><tbody>{validation_rows}</tbody></table></div></section>
<section><h2>Appendix C · Legacy normalized fact series</h2><p class='state'>{_esc(group.get('basis_label') or 'Basis unavailable')} · display unit {unit_label} · source quality {_esc(group.get('verification_status') or 'Missing')}</p><p>Historical facts preserve their reported sign. FCF uses CFO minus the absolute capital-expenditure outflow. CFO/PAT and net debt are derived only from consistent annual scope, currency and unit. Missing inputs render Not computable.</p><div class='scroll'><table><thead><tr><th>Year</th><th>Revenue</th><th>PAT</th><th>CFO</th><th>FCF</th><th>CFO/PAT</th><th>Net debt/(cash)</th><th>Verification</th></tr></thead><tbody>{financial_rows}</tbody></table></div></section>
<section><h2>Appendix D · Capital-efficiency method</h2><p>ROCE = EBIT margin × capital turnover. ROIC = NOPAT / average invested capital. Closing capital uses equity + interest-bearing borrowings − cash; average opening/closing capital is required. No WACC spread is shown without a user-reviewed hurdle.</p><div class='scroll'><table><thead><tr><th>Metric</th><th>Value</th><th>Formula</th><th>Exact missing inputs</th></tr></thead><tbody>{capital_rows}</tbody></table></div></section>
<section><h2>Appendix E · Management guidance ledger</h2><div class='scroll'><table><thead><tr><th>Metric</th><th>Target</th><th>Horizon / given</th><th>Actual</th><th>Status</th><th>Source</th></tr></thead><tbody>{guidance_rows}</tbody></table></div></section>
<section><h2>Appendix F · Risk evidence ledger</h2>{risk_rows}</section>
<section><h2>Appendix G · Research perspectives</h2><p>These are concise analyst perspectives from the research dossier; they remain separate from validated facts and the committee decision.</p><div class='section-summary-grid'>{section_rows}</div></section>
<section><h2>Appendix H · Valuation method detail</h2><p>Historical facts, management guidance, lawfully sourced external estimates and model scenarios remain separate. No point forecast is treated as certain. The stored Monte Carlo distribution is withheld because its methodology and replay are not human-validated.</p><div class='scroll'><table><thead><tr><th>Model</th><th>As of</th><th>Status</th><th>Estimate class</th><th>Bear</th><th>Base</th><th>Bull</th><th>Expected CAGR</th><th>Inputs, formula, horizon, uncertainty, sensitivity and validation</th></tr></thead><tbody>{valuation_rows}</tbody></table></div></section>
<section><h2>Appendix I · Filing and event timeline</h2><div class='scroll'><table><thead><tr><th>Date</th><th>Event</th><th>Type</th><th>Extraction</th><th>Source</th></tr></thead><tbody>{evolution_rows}</tbody></table></div></section>
<section><h2>Appendix J · Evidence coverage</h2><p>Covered {covered}/{len(matrix)} · pending review {pending} · missing {missing} · stale {stale} · source-count debt {debt}. Coverage is not investment readiness.</p></section>
<section><h2>Appendix K · Source-to-section audit</h2><div class='scroll'><table><thead><tr><th>Data point</th><th>Section</th><th>Coverage</th><th>Debt</th><th>Published</th><th>Citation records</th></tr></thead><tbody>{source_rows}</tbody></table></div></section>
<footer><strong>Decision gate:</strong> machine extraction and evidence coverage are not an investment conclusion. This report requires human review. It authorizes no broker, client, capital or external write. Artifact generated locally on Devarsh SSD.</footer></main></body></html>"""
    report_path.write_text(body, encoding="utf-8")
    pdf_path = report_root / f"{report_key}.pdf"
    chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    report_format = "html"
    primary_path = report_path
    if chrome.is_file():
        completed = subprocess.run([str(chrome), "--headless", "--no-sandbox", "--disable-gpu", f"--print-to-pdf={pdf_path}", report_path.as_uri()], capture_output=True, text=True, timeout=90, check=False)
        if completed.returncode == 0 and pdf_path.is_file() and pdf_path.stat().st_size > 10000:
            report_format = "pdf"
            primary_path = pdf_path
    digest = hashlib.sha256(primary_path.read_bytes()).hexdigest()
    coverage_snapshot = {"covered": covered, "total": len(matrix), "pending_review": pending, "missing": missing, "stale": stale, "source_count_debt": debt, "html_companion_path": str(report_path)}
    caveats = ["Machine-extracted financial facts are not human-reviewed unless explicitly labelled.", "Unsupported ratios and forecasts remain unavailable.", "Evidence coverage is distinct from evidence quality and decision readiness."]
    inserted = run_statement(f"""
        WITH inserted AS (
        INSERT INTO research.thesis_reports (
          report_key,holding_thesis_id,company_id,report_version,report_format,
          report_status,as_of_date,source_cutoff_at,artifact_path,artifact_hash,
          coverage_snapshot,assumptions,caveats,generated_by
        ) VALUES (
          {sql_literal(report_key)},{int(thesis_id)},{company_id or 'NULL'},{version},{sql_literal(report_format)},
          'generated',{sql_literal(as_of)},{sql_literal(selected.get('updated_at'))},
          {sql_literal(str(primary_path))},{sql_literal(digest)},
          {sql_jsonb(coverage_snapshot)},{sql_jsonb(["No forecast is generated without validated model inputs."])},
          {sql_jsonb(caveats)},{sql_literal(actor)}
        ) RETURNING id,report_key,report_version,report_status,as_of_date,artifact_path,artifact_hash,created_at
        ) SELECT coalesce(json_agg(row_to_json(inserted)), '[]'::json)::text FROM inserted
    """)
    return inserted[0] if inserted else {"report_key": report_key, "report_version": version, "artifact_path": str(primary_path), "artifact_hash": digest, "report_format": report_format}
