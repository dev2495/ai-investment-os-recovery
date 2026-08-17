#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from extract_governance_forensics import load_source, normalized_page, source_excerpt
from extract_long_term_source_document import ensure_pdf_runtime, run_psql_json, sql_jsonb, sql_literal


RULES: tuple[dict[str, Any], ...] = (
    {"key": "global_market_share_small", "category": "market_share", "pattern": r"our global market share is small", "availability": "not_disclosed", "conclusion": "Management explicitly states that global market share is small but does not disclose a numeric share."},
    {"key": "rope_wire_capacity_added_40000_mt", "category": "capacity", "pattern": r"augmenting our rope and wire capacity by 40,?000 MT", "availability": "quantified", "value": 40000, "unit": "MT", "conclusion": "The company reports adding 40,000 MT of rope and wire capacity."},
    {"key": "value_chain_upgrade", "category": "value_chain", "pattern": r"moving from being a producer of standard products to a provider of engineered, high-performance solutions", "availability": "qualitative_only", "conclusion": "Management describes a shift from standard products toward engineered, higher-performance solutions."},
    {"key": "end_market_demand_drivers", "category": "end_market_demand", "pattern": r"infrastructure investment is lifting demand across cranes, ports and piling.{0,500}urbanisation.{0,300}elevator ropes", "availability": "qualitative_only", "conclusion": "The report links demand to infrastructure, ports, offshore energy, mining and urban elevator applications."},
    {"key": "safety_replacement_cycle", "category": "replacement_cycle", "pattern": r"every rope is a consumable replaced on a safety-mandated cycle", "availability": "qualitative_only", "conclusion": "Management states that wire ropes are consumables replaced on safety-mandated cycles."},
)


def extract_industry_observations_from_pages(pages: list[str], period_end: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rule in RULES:
        for page_number, raw in enumerate(pages, start=1):
            text = normalized_page(raw)
            match = re.search(rule["pattern"], text, re.IGNORECASE | re.DOTALL)
            if not match:
                continue
            rows.append({
                "observation_key": rule["key"], "category": rule["category"],
                "conclusion": rule["conclusion"], "value_numeric": rule.get("value"),
                "unit": rule.get("unit"), "metric_availability": rule["availability"],
                "period_end": period_end, "source_page": page_number,
                "source_excerpt": source_excerpt(text, match), "extraction_method": "deterministic_pattern",
                "verification_status": "machine_extracted", "metadata": {"pattern": rule["pattern"]},
            })
            break
    return rows


def persist(source: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("no industry observations matched")
    values = []
    for row in rows:
        values.append("(" + ",".join((str(int(source["company_id"])),str(int(source["evidence_id"])),
          sql_literal(row["observation_key"]),sql_literal(row["category"]),sql_literal(row["conclusion"]),
          str(row["value_numeric"]) if row["value_numeric"] is not None else "NULL",sql_literal(row["unit"]),
          sql_literal(row["metric_availability"]),sql_literal(row["period_end"])+"::date",str(row["source_page"]),
          sql_literal(row["source_excerpt"]),sql_literal(row["extraction_method"]),sql_literal(row["verification_status"]),
          sql_literal(source["available_at"])+"::timestamptz",sql_jsonb(row["metadata"])))+")")
    result=run_psql_json(f"""
      WITH incoming(company_id,evidence_id,observation_key,category,conclusion,value_numeric,unit,
        metric_availability,period_end,source_page,source_excerpt,extraction_method,verification_status,
        available_at,metadata) AS (VALUES {','.join(values)}), upserted AS (
        INSERT INTO research.industry_competitive_observations (company_id,evidence_id,observation_key,
          category,conclusion,value_numeric,unit,metric_availability,period_end,source_page,source_excerpt,
          extraction_method,verification_status,available_at,metadata) SELECT * FROM incoming
        ON CONFLICT (company_id,evidence_id,observation_key,period_end) DO UPDATE SET
          category=EXCLUDED.category,conclusion=EXCLUDED.conclusion,value_numeric=EXCLUDED.value_numeric,
          unit=EXCLUDED.unit,metric_availability=EXCLUDED.metric_availability,source_page=EXCLUDED.source_page,
          source_excerpt=EXCLUDED.source_excerpt,verification_status=EXCLUDED.verification_status,
          available_at=EXCLUDED.available_at,metadata=EXCLUDED.metadata,updated_at=now()
        RETURNING observation_key,category,value_numeric,unit,metric_availability,source_page
      ) SELECT json_build_object('written',count(*),'observations',json_agg(row_to_json(upserted) ORDER BY category))::text FROM upserted
    """)
    if not isinstance(result,dict): raise RuntimeError("industry persistence returned invalid result")
    return result


def main() -> int:
    parser=argparse.ArgumentParser(description="Extract primary-source industry and competitive observations.")
    parser.add_argument("--source-document-id",type=int,required=True); parser.add_argument("--evidence-id",type=int,required=True)
    parser.add_argument("--period-end",required=True); parser.add_argument("--persist",action="store_true")
    args=parser.parse_args(); ensure_pdf_runtime(); from pypdf import PdfReader  # type: ignore
    source=load_source(args.source_document_id,args.evidence_id); reader=PdfReader(str(Path(source["local_pdf_path"])))
    rows=extract_industry_observations_from_pages([page.extract_text() or "" for page in reader.pages],args.period_end)
    database=persist(source,rows) if args.persist else {"written":0}
    print(json.dumps({"ok":True,"symbol":source["symbol"],"observations":rows,"database":database,
      "numeric_market_share_fabricated":False,"capital_action_allowed":False,"broker_write_allowed":False},indent=2,sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
