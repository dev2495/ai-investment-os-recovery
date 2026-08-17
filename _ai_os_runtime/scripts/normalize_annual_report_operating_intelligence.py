#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

from collect_nse_bse_filings import run_psql_json, run_psql_text, sql_jsonb, sql_literal
from normalize_annual_report_financials import load_reports


PARSER_VERSION = "annual_report_operating_intelligence_v1"
PRODUCTION_TABLE = re.compile(
    r"PRODUCTION\s+VOLUME.*?Products\s+FY\s+(\d{4})-(\d{2})\s+FY\s+(\d{4})-(\d{2})"
    r".*?Wire\s+Ropes\s+([\d,]+)\s+([\d,]+)"
    r".*?Wire/Strands/LRPC\s+([\d,]+)\s+([\d,]+)"
    r".*?Conveyor\s+Cord\s+([\d,]+)\s+([\d,]+)",
    re.IGNORECASE | re.DOTALL,
)
CAPACITY_ADDITION = re.compile(
    r"augmenting\s+our\s+rope\s+and\s+wire\s+capacity\s+by\s+([\d,]+)\s*MT",
    re.IGNORECASE,
)
COMMISSIONED_SOLAR = re.compile(
    r"(?:completed\s+the\s+installation\s+of|completion\s+of\s+installation\s+of)\s+"
    r"([\d.]+)\s*MWp\s+of\s+on-site\s+solar\s+power\s+capacity",
    re.IGNORECASE,
)
SOLAR_PHASE_TARGET = re.compile(
    r"remaining\s+([\d.]+)\s*MWp\s+capacity\s+under\s+Phase\s+II\s+is\s+expected\s+to\s+be\s+"
    r"commissioned\s+during\s+FY\s+(\d{4})-(\d{2})",
    re.IGNORECASE,
)
SOLAR_INSTALLATION_IN_PROGRESS = re.compile(
    r"in\s+the\s+process\s+of\s+installing\s+a\s+([\d.]+)\s*MWp\s+rooftop\s+solar\s+PV\s+system",
    re.IGNORECASE,
)
ANNUAL_CAPEX_TARGET = re.compile(
    r"intend\s+to\s+invest\s+approximately\s+₹?\s*([\d,]+)[–-]([\d,]+)\s*Crore\s+annually",
    re.IGNORECASE,
)

KPI_DEFINITIONS = {
    "wire_ropes_production_mt": ("Wire ropes production", "Gross standalone production volume of wire ropes", "MT"),
    "wire_strands_lrpc_production_mt": (
        "Wire, strands and LRPC production",
        "Gross standalone production volume of wire, strands and LRPC",
        "MT",
    ),
    "conveyor_cord_production_mt": ("Conveyor cord production", "Gross standalone production volume of conveyor cord", "MT"),
    "rope_wire_capacity_added_mt": (
        "Rope and wire capacity added",
        "Capacity augmented over the period explicitly described by management",
        "MT",
    ),
    "onsite_solar_installed_mwp": (
        "On-site solar installed capacity",
        "Installed on-site solar power capacity explicitly reported as completed",
        "MWp",
    ),
}


def normalized_page_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def fiscal_year_end(full_year: int) -> dt.date:
    return dt.date(full_year, 3, 31)


def source_excerpt(text: str, match: re.Match[str], radius: int = 260) -> str:
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    return text[start:end].strip()


def extract_report(path: Path, fiscal_year: int) -> dict[str, Any]:
    from pypdf import PdfReader  # type: ignore

    pages = [(number, normalized_page_text(page.extract_text() or "")) for number, page in enumerate(PdfReader(str(path)).pages, 1)]
    observations: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    communication_pages: list[tuple[int, str]] = []

    for page_number, text in pages:
        table = PRODUCTION_TABLE.search(text)
        if table:
            current_year = int(table.group(1)) + 1
            prior_year = int(table.group(3)) + 1
            values = [int(value.replace(",", "")) for value in table.groups()[4:]]
            for key, current, prior in (
                ("wire_ropes_production_mt", values[0], values[1]),
                ("wire_strands_lrpc_production_mt", values[2], values[3]),
                ("conveyor_cord_production_mt", values[4], values[5]),
            ):
                for year, value in ((current_year, current), (prior_year, prior)):
                    observations.append({
                        "kpi_key": key,
                        "period_end": fiscal_year_end(year).isoformat(),
                        "value_numeric": value,
                        "page_number": page_number,
                        "reported_text": source_excerpt(text, table, 420),
                        "measurement_scope": "standalone",
                    })

        capacity = CAPACITY_ADDITION.search(text)
        if capacity:
            observations.append({
                "kpi_key": "rope_wire_capacity_added_mt",
                "period_end": fiscal_year_end(fiscal_year).isoformat(),
                "value_numeric": int(capacity.group(1).replace(",", "")),
                "page_number": page_number,
                "reported_text": source_excerpt(text, capacity),
                "measurement_scope": "three_year_capacity_program",
            })

        solar = COMMISSIONED_SOLAR.search(text)
        if solar:
            observations.append({
                "kpi_key": "onsite_solar_installed_mwp",
                "period_end": fiscal_year_end(fiscal_year).isoformat(),
                "value_numeric": float(solar.group(1)),
                "page_number": page_number,
                "reported_text": source_excerpt(text, solar),
                "measurement_scope": "ranchi_phase_1",
            })

        solar_target = SOLAR_PHASE_TARGET.search(text)
        if solar_target:
            target_year = int(solar_target.group(2)) + 1
            claims.append({
                "claim_key": "solar_phase_2_commissioning",
                "claim_type": "capacity_commitment",
                "claim_text": source_excerpt(text, solar_target),
                "normalized_claim": "Commission remaining Phase II on-site solar capacity by the stated fiscal year end.",
                "metric_key": "onsite_solar_phase_2_commissioned_mwp",
                "target_operator": "gte",
                "target_value": float(solar_target.group(1)),
                "target_unit": "MWp",
                "target_period_end": fiscal_year_end(target_year).isoformat(),
                "page_number": page_number,
            })

        solar_installation = SOLAR_INSTALLATION_IN_PROGRESS.search(text)
        if solar_installation:
            claims.append({
                "claim_key": "rooftop_solar_installation",
                "claim_type": "capacity_commitment",
                "claim_text": source_excerpt(text, solar_installation),
                "normalized_claim": "Complete the reported rooftop solar installation program.",
                "metric_key": "onsite_solar_installed_mwp",
                "target_operator": "gte",
                "target_value": float(solar_installation.group(1)),
                "target_unit": "MWp",
                "target_period_end": fiscal_year_end(fiscal_year + 1).isoformat(),
                "page_number": page_number,
            })

        capex = ANNUAL_CAPEX_TARGET.search(text)
        if capex:
            claims.append({
                "claim_key": "annual_growth_capex_lower_bound",
                "claim_type": "capital_allocation_commitment",
                "claim_text": source_excerpt(text, capex),
                "normalized_claim": "Invest within the stated annual capacity-expansion capex range.",
                "metric_key": "annual_growth_capex_inr_crore",
                "target_operator": "gte",
                "target_value": int(capex.group(1).replace(",", "")),
                "target_unit": "INR crore; stated upper bound " + capex.group(2).replace(",", ""),
                "target_period_end": fiscal_year_end(fiscal_year + 1).isoformat(),
                "page_number": page_number,
            })

        lower = text.lower()
        if "the year in perspective" in lower or ("dear shareholders" in lower and "profit after tax" in lower):
            communication_pages.append((page_number, text))
        elif communication_pages and page_number == communication_pages[-1][0] + 1 and len(communication_pages) < 3:
            communication_pages.append((page_number, text))

    deduped: dict[tuple[str, str, float], dict[str, Any]] = {}
    for row in observations:
        deduped[(row["kpi_key"], row["period_end"], float(row["value_numeric"]))] = row
    return {
        "observations": list(deduped.values()),
        "claims": claims,
        "communication": {
            "page_start": communication_pages[0][0],
            "page_end": communication_pages[-1][0],
            "body_text": "\n\n".join(text for _, text in communication_pages)[:30000],
        } if communication_pages else None,
    }


def persist(company_id: int, reports: list[dict[str, Any]], results: list[dict[str, Any]], actor: str) -> dict[str, int]:
    report_by_id = {int(row["filing_id"]): row for row in reports}
    definition_ids: dict[str, int] = {}
    definition_valid_from = {
        key: min(
            observation["period_end"]
            for result in results
            for observation in result["observations"]
            if observation["kpi_key"] == key
        )
        for key in {
            observation["kpi_key"]
            for result in results
            for observation in result["observations"]
        }
    }
    counts = {"communications": 0, "claims": 0, "kpi_definitions": 0, "kpi_observations": 0}

    for result in results:
        report = report_by_id[int(result["filing_id"])]
        fy = int(result["fiscal_year"])
        evidence_id = int(report["evidence_id"])
        communication = result.get("communication")
        communication_id: int | None = None
        if communication:
            communication_key = f"company-{company_id}-annual-report-message-fy{fy}"
            rows = run_psql_json(
                f"""
                WITH upserted AS (
                  INSERT INTO research.management_communications (
                    company_id,communication_key,communication_type,title,communication_date,
                    fiscal_year,fiscal_period,body_text,transcript_status,evidence_id,source_locator
                  ) VALUES (
                    {company_id},{sql_literal(communication_key)},'annual_report_message',
                    {sql_literal(f'Annual report management message FY{fy}')},{sql_literal(fiscal_year_end(fy).isoformat())}::date,
                    {fy},'FY',{sql_literal(communication['body_text'])},'extracted',{evidence_id},
                    {sql_jsonb({'filing_id': result['filing_id'], 'page_start': communication['page_start'], 'page_end': communication['page_end'], 'parser_version': PARSER_VERSION, 'review_status': 'machine_extracted_unreviewed'})}
                  ) ON CONFLICT (communication_key) DO UPDATE SET
                    body_text=EXCLUDED.body_text,transcript_status='extracted',evidence_id=EXCLUDED.evidence_id,
                    source_locator=EXCLUDED.source_locator,updated_at=now()
                  RETURNING id
                ) SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
                """
            )
            communication_id = int(rows[0]["id"])
            counts["communications"] += 1

        for claim in result["claims"]:
            if communication_id is None:
                continue
            claim_key = f"company-{company_id}-fy{fy}-{claim['claim_key']}"
            run_psql_text(
                f"""
                INSERT INTO research.management_claims (
                  company_id,communication_id,claim_key,claim_date,claim_type,claim_text,normalized_claim,
                  metric_key,target_operator,target_value,target_unit,target_period_end,assessment_due_at,
                  claim_status,evidence_id,source_locator
                ) VALUES (
                  {company_id},{communication_id},{sql_literal(claim_key)},{sql_literal(fiscal_year_end(fy).isoformat())}::date,
                  {sql_literal(claim['claim_type'])},{sql_literal(claim['claim_text'])},{sql_literal(claim['normalized_claim'])},
                  {sql_literal(claim['metric_key'])},{sql_literal(claim['target_operator'])},{claim['target_value']},
                  {sql_literal(claim['target_unit'])},{sql_literal(claim['target_period_end'])}::date,
                  {sql_literal(claim['target_period_end'])}::date,'open',{evidence_id},
                  {sql_jsonb({'filing_id': result['filing_id'], 'page_number': claim['page_number'], 'parser_version': PARSER_VERSION, 'review_status': 'machine_extracted_unreviewed'})}
                ) ON CONFLICT (claim_key) DO UPDATE SET
                  claim_text=EXCLUDED.claim_text,normalized_claim=EXCLUDED.normalized_claim,
                  target_value=EXCLUDED.target_value,target_unit=EXCLUDED.target_unit,
                  target_period_end=EXCLUDED.target_period_end,assessment_due_at=EXCLUDED.assessment_due_at,
                  evidence_id=EXCLUDED.evidence_id,source_locator=EXCLUDED.source_locator,updated_at=now();
                """
            )
            counts["claims"] += 1

        for observation in result["observations"]:
            key = observation["kpi_key"]
            valid_from = definition_valid_from[key]
            definition_id = definition_ids.get(key)
            if definition_id is None:
                name, description, unit = KPI_DEFINITIONS[key]
                rows = run_psql_json(
                    f"""
                    WITH upserted AS (
                      INSERT INTO research.operational_kpi_definitions (
                        company_id,kpi_key,kpi_name,description,unit,value_type,frequency,
                        aggregation_method,definition_valid_from,evidence_id,metadata
                      ) VALUES (
                        {company_id},{sql_literal(key)},{sql_literal(name)},{sql_literal(description)},
                        {sql_literal(unit)},'numeric','annual','reported',{sql_literal(valid_from)}::date,{evidence_id},
                        {sql_jsonb({'parser_version': PARSER_VERSION, 'review_status': 'machine_extracted_unreviewed', 'actor': actor, 'broker_write_allowed': False})}
                      ) ON CONFLICT (company_id,kpi_key,definition_valid_from) DO UPDATE SET
                        kpi_name=EXCLUDED.kpi_name,description=EXCLUDED.description,evidence_id=EXCLUDED.evidence_id,
                        metadata=EXCLUDED.metadata,updated_at=now()
                      RETURNING id
                    ) SELECT coalesce(json_agg(row_to_json(upserted)), '[]'::json)::text FROM upserted
                    """
                )
                definition_id = int(rows[0]["id"])
                definition_ids[key] = definition_id
                counts["kpi_definitions"] += 1
            run_psql_text(
                f"""
                INSERT INTO research.operational_kpi_observations (
                  company_id,kpi_definition_id,period_end,value_numeric,source_as_of_date,available_at,
                  evidence_id,source_locator,metadata
                ) VALUES (
                  {company_id},{definition_id},{sql_literal(observation['period_end'])}::date,{observation['value_numeric']},
                  {sql_literal(fiscal_year_end(fy).isoformat())}::date,{sql_literal(str(report['retrieved_at']))}::timestamptz,
                  {evidence_id},{sql_jsonb({'filing_id': result['filing_id'], 'page_number': observation['page_number'], 'reported_text': observation['reported_text']})},
                  {sql_jsonb({'parser_version': PARSER_VERSION, 'measurement_scope': observation['measurement_scope'], 'review_status': 'machine_extracted_unreviewed', 'source_document_sha256': report['content_hash'], 'actor': actor, 'broker_write_allowed': False})}
                ) ON CONFLICT (kpi_definition_id,period_end,evidence_id) DO UPDATE SET
                  value_numeric=EXCLUDED.value_numeric,available_at=EXCLUDED.available_at,
                  source_locator=EXCLUDED.source_locator,metadata=EXCLUDED.metadata;
                """
            )
            counts["kpi_observations"] += 1
    counts["claim_outcomes"] = reconcile_claim_outcomes(company_id, actor)
    return counts


def outcome_status(target_value: float, actual_value: float) -> str:
    if actual_value >= target_value:
        return "met"
    if actual_value > 0:
        return "partially_met"
    return "missed"


def reconcile_claim_outcomes(company_id: int, actor: str) -> int:
    candidates = run_psql_json(
        f"""
        SELECT coalesce(json_agg(row_to_json(candidate)), '[]'::json)::text
        FROM (
          SELECT claim.id AS claim_id,claim.claim_key,claim.target_value,claim.target_unit,
                 claim.target_period_end,observation.period_end AS outcome_date,
                 observation.value_numeric AS actual_value,observation.evidence_id
          FROM research.management_claims claim
          JOIN research.operational_kpi_definitions definition
            ON definition.company_id=claim.company_id AND definition.kpi_key=claim.metric_key
          JOIN LATERAL (
            SELECT item.*
            FROM research.operational_kpi_observations item
            WHERE item.kpi_definition_id=definition.id
              AND item.period_end>=claim.target_period_end
            ORDER BY item.period_end,item.id
            LIMIT 1
          ) observation ON true
          WHERE claim.company_id={company_id}
            AND claim.target_operator='gte'
            AND claim.target_value IS NOT NULL
            AND claim.target_period_end IS NOT NULL
            AND NOT EXISTS (
              SELECT 1 FROM research.management_claim_outcomes existing
              WHERE existing.claim_id=claim.id AND existing.outcome_date=observation.period_end
                AND existing.evidence_id=observation.evidence_id
            )
        ) candidate
        """
    )
    for candidate in candidates:
        target = float(candidate["target_value"])
        actual = float(candidate["actual_value"])
        status = outcome_status(target, actual)
        assessment = (
            f"Deterministic point-in-time assessment: observed {actual:g} {candidate['target_unit']} "
            f"against a target of at least {target:g} {candidate['target_unit']} by "
            f"{candidate['target_period_end']}; status {status}. Human review remains required."
        )
        run_psql_text(
            f"""
            INSERT INTO research.management_claim_outcomes (
              claim_id,outcome_date,outcome_status,actual_value,actual_unit,assessment,
              attribution_notes,evidence_id,assessed_by
            ) VALUES (
              {int(candidate['claim_id'])},{sql_literal(candidate['outcome_date'])}::date,{sql_literal(status)},
              {actual},{sql_literal(candidate['target_unit'])},{sql_literal(assessment)},
              'Machine-reconciled against a later source-linked operating KPI; human review required.',
              {int(candidate['evidence_id'])},{sql_literal(actor)}
            ) ON CONFLICT (claim_id,outcome_date,evidence_id) DO NOTHING;
            UPDATE research.management_claims SET claim_status={sql_literal(status)},updated_at=now()
            WHERE id={int(candidate['claim_id'])};
            """
        )
    return len(candidates)


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize source-linked operating intelligence from company annual reports.")
    parser.add_argument("--company-id", type=int, required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--exchange", default="NSE")
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--actor", default="Fundamental Data Engineer")
    args = parser.parse_args()

    reports = load_reports(args.symbol.upper(), args.exchange.upper(), args.limit)
    results: list[dict[str, Any]] = []
    for report in reports:
        path = Path(report["local_path"])
        if not path.is_file():
            continue
        extracted = extract_report(path, int(report["fiscal_year"]))
        extracted.update({"filing_id": int(report["filing_id"]), "fiscal_year": int(report["fiscal_year"])})
        results.append(extracted)
    payload: dict[str, Any] = {
        "company_id": args.company_id,
        "symbol": args.symbol.upper(),
        "reports_scanned": len(results),
        "communications_found": sum(1 for row in results if row["communication"]),
        "claims_found": sum(len(row["claims"]) for row in results),
        "observations_found": sum(len(row["observations"]) for row in results),
        "parser_version": PARSER_VERSION,
        "persisted": False,
    }
    if args.persist:
        payload["write_counts"] = persist(args.company_id, reports, results, args.actor)
        payload["persisted"] = True
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
