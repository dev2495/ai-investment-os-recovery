"""Bounded read model for the Long-Term Investment Thesis workspace."""

from __future__ import annotations

from datetime import datetime, timezone

from financial_quality import build_financial_quality
from valuation_workbench import build_valuation_workbench


def build_long_term_thesis_workspace(
    query,
    *,
    run_rows,
    run_map,
    sql_literal,
    runtime_root,
    vault_root,
):
    def bounded(name, default, minimum, maximum):
        try:
            raw = int(str(query.get(name, [str(default)])[0]).strip() or default)
        except (TypeError, ValueError):
            raw = default
        return max(minimum, min(maximum, raw))

    requested_id = bounded("thesis_id", 0, 0, 10_000_000)
    requested_symbol = str(query.get("symbol", [""])[0] or "").strip().upper()
    requested_exchange = str(query.get("exchange", [""])[0] or "").strip().upper()
    facts_page = bounded("facts_page", 1, 1, 10_000)
    evidence_page = bounded("evidence_page", 1, 1, 10_000)
    page_size = bounded("page_size", 12, 6, 24)
    requested_profile = str(query.get("profile", ["dashboard"])[0] or "dashboard").strip().lower()
    # The investor dashboard is the safe, bounded default.  The legacy explicit
    # ``workspace`` profile remains an operations alias for callers that have not
    # yet moved to ``operations``; an omitted or unknown profile never hydrates
    # the research control plane by accident.
    operations_profile = requested_profile in {"operations", "workspace"}
    dashboard_profile = not operations_profile
    workspace_profile = (
        "long_term_thesis_operations_v1"
        if operations_profile
        else "long_term_thesis_dashboard_v1"
    )
    facts_offset = (facts_page - 1) * page_size
    evidence_offset = (evidence_page - 1) * page_size

    # The investor dashboard needs the latest substantive Research Case pack,
    # but not its task graph, raw evidence ledger, blockers, or model runs. Keep
    # the projection inside the already-bounded thesis selector: one latest
    # relevant case and at most one latest version of 20 named sections.
    research_pack_projection = "case_pack.research_pack"
    research_pack_join = """
    LEFT JOIN LATERAL (
      SELECT latest_case.id AS research_case_id,
             latest_report.id AS report_id,
             latest_report.report_version,
             latest_report.report_status,
             latest_report.delivery_state,
             (
               SELECT jsonb_object_agg(
                 latest_section.section_key,
                 jsonb_build_object(
                   'title',latest_section.title,
                   'summary',latest_section.summary,
                   'status',latest_section.status,
                   'content',latest_section.content,
                   'citation_ids',latest_section.citation_ids,
                   'coverage_gaps',latest_section.coverage_gaps
                 ) ORDER BY latest_section.section_key
               )
               FROM (
                 SELECT DISTINCT ON (section.section_key)
                        section.id,section.section_key,section.title,section.summary,
                        section.status,section.content,section.citation_ids,
                        section.coverage_gaps,section.version,section.updated_at
                 FROM research.research_pack_sections section
                 WHERE section.research_case_id=latest_case.id
                 ORDER BY section.section_key,section.version DESC,
                          section.updated_at DESC,section.id DESC
                 LIMIT 20
               ) latest_section
             ) AS research_pack
      FROM research.research_cases latest_case
      LEFT JOIN LATERAL (
        SELECT report.id,report.report_version,report.report_status,
               coalesce(
                 report.coverage_snapshot->>'delivery_state',
                 CASE WHEN report.pdf_path IS NOT NULL THEN 'pdf_ready'
                      ELSE 'html_ready_pdf_retry' END
               ) AS delivery_state
        FROM research.research_case_reports report
        WHERE report.research_case_id=latest_case.id
          AND report.report_status<>'superseded'
        ORDER BY report.report_version DESC,report.id DESC
        LIMIT 1
      ) latest_report ON true
      WHERE (latest_case.holding_thesis_id=thesis.id OR latest_case.company_id=company.id)
        AND latest_case.status IN ('active','review','completed','blocked')
        AND EXISTS (
          SELECT 1 FROM research.research_pack_sections available_section
          WHERE available_section.research_case_id=latest_case.id
        )
      ORDER BY latest_case.updated_at DESC,latest_case.id DESC
      LIMIT 1
    ) case_pack ON true
    """

    if operations_profile:
        evidence_projection = "coalesce(evidence.coverage_count,0)"
        evidence_join = """
        LEFT JOIN LATERAL (
          SELECT count(*)::integer AS coverage_count
          FROM research.fundamental_evidence e WHERE e.company_id=company.id
        ) evidence ON true
        """
        thesis_order = "coalesce(evidence.coverage_count,0) DESC, thesis.updated_at DESC,thesis.id DESC"
    else:
        evidence_projection = "NULL::integer"
        evidence_join = ""
        thesis_order = "thesis.updated_at DESC,thesis.id DESC"

    requested_identity_order = ""
    if requested_symbol:
        requested_exchange_clause = (
            f" AND upper(thesis.exchange)={sql_literal(requested_exchange)}"
            if requested_exchange
            else ""
        )
        requested_identity_order = (
            "CASE WHEN upper(thesis.symbol)="
            f"{sql_literal(requested_symbol)}{requested_exchange_clause} "
            "THEN 0 ELSE 1 END,"
        )

    theses = run_rows(f"""
        SELECT thesis.id,thesis.symbol,thesis.exchange,thesis.company_name,
               thesis.thesis_title,thesis.thesis_status,thesis.decision_status,
               thesis.primary_owner_agent,thesis.thesis_summary,thesis.business_model,
               thesis.industry_structure,thesis.moat_score,thesis.management_score,
               thesis.governance_score,thesis.capital_allocation_score,
               thesis.financial_quality_score,thesis.valuation_status,
               thesis.base_case_fair_value,thesis.bear_case_fair_value,
               thesis.bull_case_fair_value,thesis.expected_cagr_pct,
               thesis.thesis_killers,thesis.exit_criteria,thesis.review_frequency,
               thesis.last_reviewed_at,thesis.next_review_due_at,
               thesis.thesis_note_path,thesis.metadata,thesis.updated_at,
               company.id AS research_company_id,company.company_key,
               company.legal_name,company.real_company_verified_at,
               control.position_count,control.client_count,control.clients,
               control.long_term_gross_exposure,control.checklist_count,
               control.checklist_complete_count,control.valuation_model_count,
               control.valuation_complete_count,
               {evidence_projection} AS evidence_count,
               dossier.dossier_id,dossier.dossier_version_id,
               dossier.version_number AS dossier_version_number,
               dossier.version_status AS dossier_version_status,
               dossier.research_as_of,dossier.source_cutoff_at,
               dossier.executive_conclusion,dossier.decision_summary,
               dossier.evidence_coverage,dossier.section_count,
               dossier.reviewed_section_count,dossier.specialist_count,
               dossier.updated_at AS dossier_updated_at,
               {research_pack_projection} AS research_pack,
               case_pack.research_case_id AS latest_research_case_id,
               case_pack.report_id AS latest_research_case_report_id,
               case_pack.report_version AS latest_research_case_report_version,
               case_pack.report_status AS latest_research_case_report_status,
               case_pack.delivery_state AS latest_research_case_report_delivery_state
        FROM portfolio.holding_theses thesis
        LEFT JOIN portfolio.v_long_term_thesis_control control ON control.id=thesis.id
        LEFT JOIN research.companies company
          ON upper(company.primary_symbol)=upper(thesis.symbol)
         AND upper(company.primary_exchange)=upper(thesis.exchange)
        {evidence_join}
        LEFT JOIN LATERAL (
          SELECT latest.* FROM research.v_latest_investment_dossiers latest
          WHERE latest.company_id=company.id
            AND (latest.holding_thesis_id=thesis.id OR latest.holding_thesis_id IS NULL)
          ORDER BY (latest.holding_thesis_id=thesis.id) DESC,
                   latest.updated_at DESC NULLS LAST LIMIT 1
        ) dossier ON true
        {research_pack_join}
        ORDER BY {requested_identity_order}
                 (company.id IS NOT NULL) DESC,
                 {thesis_order} LIMIT 50
    """)
    selected_by_id = next(
        (row for row in theses if int(row.get("id") or 0) == requested_id),
        None,
    )
    selected_by_symbol = next(
        (
            row
            for row in theses
            if requested_symbol
            and str(row.get("symbol") or "").strip().upper() == requested_symbol
            and (
                not requested_exchange
                or str(row.get("exchange") or "").strip().upper() == requested_exchange
            )
        ),
        None,
    )
    selected = selected_by_id or selected_by_symbol or (theses[0] if theses else None)
    privacy = {
        "scope": "local_private",
        "private_data_egress_allowed": False,
        "broker_write_allowed": False,
        "client_write_allowed": False,
        "external_write_allowed": False,
    }
    if selected is None:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "workspace_profile": workspace_profile,
            "theses": [],
            "selected_thesis": None,
            "issues": [{"status": "empty", "message": "No persisted holding thesis exists."}],
            "privacy": privacy,
        }

    thesis_id = int(selected.get("id") or 0)
    company_id = int(selected.get("research_company_id") or 0)
    dossier_version_id = int(selected.get("dossier_version_id") or 0)
    symbol = str(selected.get("symbol") or "").strip().upper()
    exchange = str(selected.get("exchange") or "NSE").strip().upper()
    symbol_sql = sql_literal(symbol)
    exchange_sql = sql_literal(exchange)
    company_clause = f"={company_id}" if company_id else "IS NULL"

    queries = {
        "coverage": f"""SELECT
          (SELECT count(*) FROM portfolio.holding_theses)::integer AS holding_theses,
          (SELECT count(*) FROM portfolio.holding_thesis_versions)::integer AS thesis_versions,
          (SELECT count(*) FROM portfolio.holding_valuation_models)::integer AS valuation_models,
          (SELECT count(*) FROM research.company_statement_facts)::integer AS normalized_statement_facts,
          (SELECT count(*) FROM research.company_statement_facts WHERE is_current)::integer AS current_statement_facts,
          (SELECT count(DISTINCT company_id) FROM research.company_statement_facts)::integer AS statement_companies,
          (SELECT count(*) FROM research.fundamental_evidence)::integer AS evidence_records,
          (SELECT count(DISTINCT company_id) FROM research.fundamental_evidence)::integer AS evidence_companies,
          (SELECT count(*) FROM research.fundamental_specialist_opinions)::integer AS specialist_opinions,
          (SELECT count(*) FROM research.watchlist_items)::integer AS watchlist_items,
          (SELECT count(*) FROM research.company_ir_sources WHERE status='active')::integer AS active_ir_sources,
          (SELECT count(*) FROM research.corporate_filings)::integer AS filings_registered,
          (SELECT count(*) FROM research.corporate_filings WHERE extraction_status='extracted')::integer AS filings_extracted,
          (SELECT count(*) FROM research.v_company_statement_facts_current WHERE company_id {company_clause})::integer AS selected_company_facts,
          (SELECT count(*) FROM research.fundamental_evidence WHERE company_id {company_clause})::integer AS selected_company_evidence,
          (SELECT count(*) FROM research.fundamental_specialist_opinions WHERE company_id {company_clause})::integer AS selected_company_opinions,
          (SELECT count(*) FROM research.corporate_filings WHERE upper(symbol)={symbol_sql})::integer AS selected_company_filings""",
        "thesis_versions": f"""SELECT id,version_number,note_path,change_type,thesis_status,
          decision_status,thesis_summary,business_model,industry_structure,score_snapshot,
          valuation_snapshot,thesis_killers,exit_criteria,evidence,created_by,created_at
          FROM portfolio.holding_thesis_versions WHERE holding_thesis_id={thesis_id}
          ORDER BY version_number DESC,id DESC LIMIT 24""",
        "dossier_sections": f"""SELECT section.id,section.section_key,section.section_order,
          section.section_title,section.section_status,section.content_markdown,
          section.primary_evidence_id,section.evidence_as_of,section.generated_by,
          section.reviewed_by,section.reviewed_at,section.updated_at,
          evidence.source_title,evidence.source_url,evidence.verification_status
          FROM research.investment_dossier_sections section
          LEFT JOIN research.fundamental_evidence evidence ON evidence.id=section.primary_evidence_id
          WHERE section.dossier_version_id={dossier_version_id or -1}
          ORDER BY section.section_order,section.id LIMIT 40""",
        "checklists": f"""SELECT id,checklist_key,checklist_name,status,score,findings,
          evidence,owner_agent,updated_at FROM portfolio.holding_thesis_checklists
          WHERE holding_thesis_id={thesis_id} ORDER BY checklist_key,id DESC LIMIT 40""",
        "valuation_models": f"""SELECT id,model_key,model_name,model_type,status,
          fair_value_low,fair_value_base,fair_value_high,expected_cagr_pct,assumptions,
          outputs,note_path,owner_agent,updated_at FROM portfolio.holding_valuation_models
          WHERE holding_thesis_id={thesis_id} ORDER BY updated_at DESC,model_key LIMIT 40""",
        "market_price_anchor": f"""WITH live_quotes AS (
            SELECT live.instrument_token AS id,'zerodha_live_quote_state'::text AS source_key,
              live.provider,live.provider_symbol,live.symbol,live.exchange,'INR'::text AS currency,
              live.last_price AS price,
              coalesce(live.exchange_timestamp,live.last_trade_timestamp,live.received_at) AS quote_ts,
              live.received_at,'primary_zerodha_live'::text AS source_class,1 AS source_priority,
              (instrument.instrument_token IS NOT NULL) AS approved_for_valuation,
              true AS provider_entitled,'zerodha_canonical'::text AS provider_entitlement_key,
              live.instrument_token,live.source_mode,live.broker_write_allowed,
              CASE WHEN instrument.instrument_token IS NOT NULL THEN 'verified_zerodha_instrument'
                   ELSE 'unmapped_zerodha_instrument' END AS mapping_status,
              CASE WHEN live.exchange_timestamp IS NOT NULL THEN 'exchange_timestamp'
                   WHEN live.last_trade_timestamp IS NOT NULL THEN 'last_trade_local_ist'
                   ELSE 'receipt_utc' END AS timestamp_basis,
              stream.connection_state AS stream_connection_state,
              stream.health_status AS stream_health_status,
              stream.last_heartbeat_at AS stream_last_heartbeat_at,
              stream.stream_heartbeat_age_seconds
            FROM market.live_quote_state live
            LEFT JOIN market.zerodha_instruments instrument
              ON instrument.instrument_token=live.instrument_token AND instrument.active
             AND upper(instrument.exchange)=upper(live.exchange)
             AND upper(instrument.trading_symbol)=upper(live.symbol)
            LEFT JOIN LATERAL (
              SELECT connection_state,health_status,last_heartbeat_at,
                CASE WHEN last_heartbeat_at IS NULL THEN NULL
                     ELSE greatest(0,extract(epoch FROM (now()-last_heartbeat_at))) END
                  AS stream_heartbeat_age_seconds
              FROM market.v_zerodha_stream_health LIMIT 1
            ) stream ON true
            WHERE upper(live.symbol)={symbol_sql} AND upper(live.exchange)={exchange_sql}
              AND lower(live.provider)='zerodha' AND live.last_price>0
          ), stored_quote_candidates AS (
            SELECT candidate.*
            FROM market.price_quotes candidate
            WHERE upper(candidate.symbol)={symbol_sql}
              AND upper(candidate.exchange)={exchange_sql}
              AND candidate.price>0
            ORDER BY CASE WHEN lower(candidate.provider)='zerodha' THEN 2 ELSE 3 END,
                     candidate.quote_ts DESC,candidate.id DESC
            LIMIT 16
          ), stored_quotes AS (
            SELECT quote.id,quote.source_key,quote.provider,quote.provider_symbol,
              quote.symbol,quote.exchange,quote.currency,quote.price,quote.quote_ts,
              quote.created_at AS received_at,
              CASE WHEN lower(quote.provider)='zerodha' THEN 'zerodha_stored_quote'
                   WHEN registry.source_key IS NOT NULL THEN 'entitled_secondary_quote'
                   ELSE 'unentitled_secondary_quote' END AS source_class,
              CASE WHEN lower(quote.provider)='zerodha' THEN 2 ELSE 3 END AS source_priority,
              CASE WHEN lower(quote.provider)='zerodha' THEN instrument.instrument_token IS NOT NULL
                   ELSE registry.source_key IS NOT NULL END AS approved_for_valuation,
              CASE WHEN lower(quote.provider)='zerodha' THEN true
                   ELSE registry.source_key IS NOT NULL END AS provider_entitled,
              CASE WHEN lower(quote.provider)='zerodha' THEN 'zerodha_canonical'
                   ELSE registry.source_key END AS provider_entitlement_key,
              instrument.instrument_token,'bounded_read_only_snapshot'::text AS source_mode,
              false AS broker_write_allowed,
              CASE WHEN lower(quote.provider)='zerodha' AND instrument.instrument_token IS NOT NULL
                     THEN 'verified_zerodha_instrument'
                   WHEN lower(quote.provider)='zerodha' THEN 'unmapped_zerodha_instrument'
                   ELSE 'exact_exchange_symbol' END AS mapping_status,
              coalesce(quote.raw_payload->>'ai_os_timestamp_basis','unknown') AS timestamp_basis,
              NULL::text AS stream_connection_state,
              NULL::text AS stream_health_status,
              NULL::timestamptz AS stream_last_heartbeat_at,
              NULL::numeric AS stream_heartbeat_age_seconds
            FROM stored_quote_candidates quote
            LEFT JOIN LATERAL (
              SELECT mapping.instrument_token FROM market.zerodha_instruments mapping
              WHERE mapping.active AND upper(mapping.exchange)=upper(quote.exchange)
                AND upper(mapping.trading_symbol)=upper(quote.symbol)
              ORDER BY mapping.last_seen_at DESC LIMIT 1
            ) instrument ON true
            LEFT JOIN core.data_source_registry registry
              ON registry.source_key=quote.source_key
             AND registry.status IN ('active','installed','mapped')
             AND lower(coalesce(registry.provider,''))=lower(quote.provider)
             AND coalesce(registry.metadata->>'valuation_price_entitled','false')='true'
          )
          SELECT * FROM (SELECT * FROM live_quotes UNION ALL SELECT * FROM stored_quotes) quotes
          ORDER BY source_priority,quote_ts DESC,id DESC LIMIT 16""",
        "market_holidays": f"""SELECT exchange,holiday_date,session_status,source_url
          FROM market.exchange_holidays
          WHERE upper(exchange)={exchange_sql}
            AND holiday_date BETWEEN current_date-14 AND current_date+14
          ORDER BY holiday_date""",
        "monte_carlo_runs": f"""SELECT id,run_key,run_status,horizon_years,
          simulation_count,start_price,starting_multiple,assumptions,input_snapshot,
          percentile_summary,probability_summary,warnings,evidence,note_path,
          created_by,created_at FROM portfolio.v_long_term_monte_carlo_runs
          WHERE holding_thesis_id={thesis_id} ORDER BY created_at DESC,id DESC LIMIT 12""",
        "research_updates": f"""SELECT id,update_kind,checklist_key,model_key,status,
          score,fair_value_low,fair_value_base,fair_value_high,expected_cagr_pct,
          findings,assumptions,outputs,evidence,source_summary,note_path,created_by,created_at
          FROM portfolio.holding_thesis_research_updates WHERE holding_thesis_id={thesis_id}
          ORDER BY created_at DESC,id DESC LIMIT 40""",
        "financial_facts": f"""SELECT fact_key,canonical_name,statement_type,fiscal_year,
          fiscal_period,period_start,period_end,statement_scope,value_numeric,value_text,currency,unit,scale_power,
          source_as_of_date,available_at,restatement_version,restatement_status,evidence_id,
          source_type,source_name,source_url,verification_status,source_locator
          FROM research.v_company_statement_facts_current WHERE company_id {company_clause}
          ORDER BY fiscal_year DESC,fact_key LIMIT {page_size} OFFSET {facts_offset}""",
        "financial_series": f"""SELECT fact_key,canonical_name,statement_type,fiscal_year,
          fiscal_period,period_start,period_end,statement_scope,value_numeric,value_text,currency,unit,scale_power,
          source_as_of_date,available_at,restatement_version,restatement_status,evidence_id,
          source_type,source_name,source_url,verification_status,source_locator
          FROM research.v_company_statement_facts_current WHERE company_id {company_clause}
          ORDER BY fiscal_year DESC,fact_key LIMIT 240""",
        "fundamental_evidence": f"""SELECT id,source_type,source_name,source_url,
          source_title,published_at,retrieved_at,source_as_of_date,page_start,page_end,
          section_reference,extraction_method,verification_status,verified_by,verified_at,
          source_locator FROM research.fundamental_evidence WHERE company_id {company_clause}
          ORDER BY coalesce(source_as_of_date,published_at::date,retrieved_at::date) DESC,id DESC
          LIMIT {page_size} OFFSET {evidence_offset}""",
        "specialist_opinions": f"""SELECT DISTINCT ON (opinion.specialist_key)
          opinion.id,opinion.specialist_key,opinion.agent_name,opinion.opinion_status,
          opinion.conclusion,opinion.score_low,opinion.score_base,opinion.score_high,
          opinion.confidence_pct,opinion.disconfirming_evidence,opinion.required_followups,
          opinion.evidence_id,opinion.opinion_as_of,opinion.reviewed_by,opinion.reviewed_at,
          opinion.review_rationale,opinion.created_at,opinion.updated_at,
          evidence.source_title,evidence.source_url,
          evidence.verification_status AS evidence_verification_status
          FROM research.fundamental_specialist_opinions opinion
          JOIN research.fundamental_evidence evidence ON evidence.id=opinion.evidence_id
          WHERE opinion.company_id {company_clause}
            AND (opinion.holding_thesis_id={thesis_id} OR opinion.holding_thesis_id IS NULL)
          ORDER BY opinion.specialist_key,opinion.opinion_as_of DESC,opinion.id DESC""",
        "governance_observations": f"""SELECT o.id,o.observation_key,o.category,
          o.observation_status,o.severity,o.conclusion,o.disclosed_value,o.disclosed_unit,
          o.period_end,o.source_page,o.verification_status,o.available_at,o.evidence_id,
          e.source_title,e.source_url FROM research.governance_forensic_observations o
          JOIN research.fundamental_evidence e ON e.id=o.evidence_id
          WHERE o.company_id {company_clause} AND o.verification_status NOT IN ('rejected','superseded')
          ORDER BY CASE o.severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
                   o.available_at DESC,o.id DESC LIMIT 40""",
        "filings": f"""SELECT id AS filing_id,source_name,exchange,symbol,company_name,
          filing_type,event_type,title,filed_at,source_url,attachment_url,extraction_status,
          pdf_page_count,pdf_extracted_at,created_at FROM research.corporate_filings
          WHERE upper(symbol)={symbol_sql} ORDER BY filed_at DESC NULLS LAST,id DESC
          LIMIT {page_size} OFFSET {evidence_offset}""",
        "news": f"""SELECT id,source_name,source_url,title,publisher,published_at,
          captured_at,symbols,topics,sentiment,relevance_score FROM market.news_items
          WHERE {symbol_sql}=ANY(symbols) ORDER BY coalesce(published_at,captured_at) DESC,id DESC
          LIMIT {page_size} OFFSET {evidence_offset}""",
        "ir_sources": f"""SELECT id,source_key,source_kind,source_url,document_label,status,
          verified_at,verified_by,last_collected_at,updated_at FROM research.company_ir_sources
          WHERE upper(symbol)={symbol_sql} AND upper(exchange)={exchange_sql}
          ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END,updated_at DESC LIMIT 40""",
        "source_matrix": f"""SELECT requirement_key,section_key,section_order,data_point_key,
          requirement_label,acceptable_source_kinds,minimum_source_count,max_age_days,
          extraction_required,minimum_validation,is_material,is_required,linked_source_count,
          covered_source_count,pending_review_count,stale_source_count,latest_captured_at,
          latest_publication_date,sources,coverage_status,coverage_debt
          FROM research.v_thesis_source_matrix WHERE company_id {company_clause}
          ORDER BY section_order,requirement_key LIMIT 60""",
        "source_pipeline": f"""SELECT source_item_id,symbol,company_name,source_kind,source_title,
          source_url,publication_date,effective_date,captured_at,capture_status,parser_status,
          validation_status,access_status,terms_status,robots_status,source_scope,materiality,
          change_kind,material_change,change_summary,section_hint,local_artifact_path,
          citation_locator,proposed_link_count,validated_link_count,next_gate
          FROM research.v_thesis_source_pipeline_queue WHERE company_id {company_clause}
          ORDER BY CASE next_gate WHEN 'parser_exception' THEN 1 WHEN 'source_review' THEN 2
            WHEN 'validate' THEN 3 WHEN 'review_links' THEN 4 ELSE 5 END,captured_at DESC
          LIMIT 24""",
        "cited_briefs": f"""SELECT id,brief_key,generated_at,generated_by,artifact_path,artifact_hash,
          covered_requirement_count,total_requirement_count,pending_review_count,
          missing_requirement_count,stale_requirement_count,source_item_count,brief_status,notes
          FROM research.thesis_cited_briefs WHERE company_id {company_clause}
          ORDER BY generated_at DESC,id DESC LIMIT 12""",
        "operational_kpis": f"""SELECT definition.kpi_key,definition.kpi_name,definition.description,
          definition.unit,definition.frequency,observation.period_start,observation.period_end,
          observation.value_numeric,observation.value_text,observation.source_as_of_date,
          observation.available_at,observation.source_locator,observation.metadata,
          evidence.source_title,evidence.source_url,evidence.verification_status
          FROM research.operational_kpi_observations observation
          JOIN research.operational_kpi_definitions definition ON definition.id=observation.kpi_definition_id
          JOIN research.fundamental_evidence evidence ON evidence.id=observation.evidence_id
          WHERE observation.company_id {company_clause}
          ORDER BY definition.kpi_key,observation.period_end LIMIT 240""",
        "industry_observations": f"""SELECT observation.id,observation.observation_key,
          observation.category,observation.conclusion,observation.value_numeric,observation.unit,
          observation.metric_availability,observation.period_end,observation.source_page,
          observation.source_excerpt,observation.verification_status,observation.available_at,
          observation.metadata,evidence.source_title,evidence.source_url
          FROM research.industry_competitive_observations observation
          JOIN research.fundamental_evidence evidence ON evidence.id=observation.evidence_id
          WHERE observation.company_id {company_clause}
            AND observation.verification_status NOT IN ('rejected','superseded')
          ORDER BY observation.period_end DESC,observation.category,observation.id DESC LIMIT 80""",
        "market_share_observations": f"""SELECT share.id,share.market_key,share.market_name,
          share.product_or_service,share.geography,share.channel,share.period_start,share.period_end,
          share.share_pct,share.numerator_value,share.denominator_value,share.measurement_basis,
          share.methodology,share.source_as_of_date,share.available_at,share.source_locator,
          evidence.source_title,evidence.source_url,evidence.verification_status
          FROM research.market_share_observations share
          JOIN research.fundamental_evidence evidence ON evidence.id=share.evidence_id
          WHERE share.company_id {company_clause}
          ORDER BY share.period_end DESC,share.market_key,share.geography LIMIT 80""",
        "operating_peers": f"""SELECT peer_set.peer_set_key,peer_set.peer_set_name,
          peer_set.methodology,peer_set.valid_from,peer_set.valid_to,membership.membership_role,
          membership.inclusion_reason,peer.id peer_company_id,peer.legal_name,peer.primary_symbol,
          peer.primary_exchange,peer.isin,evidence.source_title,evidence.source_url,
          evidence.verification_status
          FROM research.peer_sets peer_set
          JOIN research.peer_set_memberships membership ON membership.peer_set_id=peer_set.id
          JOIN research.companies peer ON peer.id=membership.peer_company_id
          JOIN research.fundamental_evidence evidence ON evidence.id=membership.evidence_id
          WHERE peer_set.subject_company_id {company_clause}
            AND (peer_set.valid_to IS NULL OR peer_set.valid_to>=current_date)
          ORDER BY peer_set.valid_from DESC,membership.membership_role,peer.legal_name LIMIT 40""",
        "management_guidance": f"""SELECT score.company_id,score.claim_id,score.claim_key,
          score.communication_type,score.communication_title,score.claim_date,
          score.speaker_name,score.speaker_role,score.claim_type,score.claim_text,
          score.metric_key,score.target_operator,score.target_value,score.target_unit,
          score.target_period_end,score.assessment_due_at,score.claim_status,
          score.outcome_date,score.outcome_status,score.actual_value,score.actual_unit,
          score.assessment,score.claim_evidence_id,score.outcome_evidence_id,
          evidence.source_url,evidence.source_title,evidence.verification_status,
          outcome.source_url outcome_source_url,outcome.source_title outcome_source_title,
          outcome.verification_status outcome_verification_status
          FROM research.v_management_claim_scorecard score
          LEFT JOIN research.fundamental_evidence evidence ON evidence.id=score.claim_evidence_id
          LEFT JOIN research.fundamental_evidence outcome ON outcome.id=score.outcome_evidence_id
          WHERE score.company_id {company_clause}
          ORDER BY score.claim_date DESC,score.claim_id DESC LIMIT 20""",
        "segment_facts": f"""SELECT segment.id segment_id,segment.segment_key,
          segment.segment_name,segment.segment_type,segment.parent_segment_id,
          fact.fiscal_year,fact.fiscal_period,fact.period_start,fact.period_end,
          definition.fact_key,definition.canonical_name,fact.value_numeric,
          fact.currency,fact.unit,fact.source_as_of_date,fact.available_at,
          fact.evidence_id,fact.source_locator,evidence.source_title,evidence.source_url,
          evidence.verification_status
          FROM research.company_segment_facts fact
          JOIN research.company_segments segment ON segment.id=fact.segment_id
          JOIN research.statement_fact_definitions definition ON definition.id=fact.fact_definition_id
          LEFT JOIN research.fundamental_evidence evidence ON evidence.id=fact.evidence_id
          WHERE fact.company_id {company_clause}
          ORDER BY segment.segment_name,fact.fiscal_year DESC,definition.fact_key LIMIT 160""",
        "research_cases": f"""SELECT id,case_key,request_text,entity_type,entity_key,
          resolution_status,company_id,holding_thesis_id,ticker,exchange,company_name,
          owner_agent,priority,horizon,mandate,status,work_plan,source_plan,budget,
          data_boundary,coverage_snapshot,exception_count,graph_run_id,cooldown_until,
          proposed_by,confirmed_by,started_at,completed_at,created_at,updated_at,
          lead_status,current_goal,workspace_path,iteration_count,decision_readiness,last_progress_at
          FROM research.research_cases
          WHERE holding_thesis_id={thesis_id} OR company_id {company_clause}
          ORDER BY (status IN ('proposed','active','collecting','review','blocked')) DESC,updated_at DESC,id DESC LIMIT 20""",
        "research_case_work_items": f"""SELECT id,research_case_id,work_key,parent_work_item_id,
          work_type,owner_agent,title,objective,status,priority,iteration,
          task_id,inbox_id,worker_run_id,model_decision_id,created_at,updated_at
          FROM research.research_case_work_items
          WHERE research_case_id IN (SELECT id FROM research.research_cases
            WHERE holding_thesis_id={thesis_id} OR company_id {company_clause})
          ORDER BY priority DESC,updated_at DESC,id LIMIT 80""",
        "financial_production_runs": f"""SELECT id,run_key,company_id,filing_id,parser_name,parser_version,statement_scope,currency,unit,source_sha256,source_url,source_path,status,started_at,completed_at,created_by,summary FROM research.financial_production_runs WHERE company_id {company_clause} ORDER BY completed_at DESC NULLS LAST,id DESC LIMIT 12""",
        "financial_history": f"""SELECT sf.fiscal_year,jsonb_agg(jsonb_build_object('id',sf.id,'production_run_id',sf.production_run_id,'fact_key',sf.fact_key,'fiscal_year',sf.fiscal_year,'period_end',sf.period_end,'statement_type',sf.statement_type,'statement_scope',sf.statement_scope,'value',sf.value,'currency',sf.currency,'unit',sf.unit,'source_page',sf.source_page,'reported_line',sf.reported_line,'extraction_status',sf.extraction_status,'source_url',run.source_url,'source_sha256',run.source_sha256,'run_key',run.run_key) ORDER BY sf.statement_type,sf.fact_key) facts FROM research.financial_source_facts sf JOIN research.financial_production_runs run ON run.id=sf.production_run_id WHERE sf.company_id {company_clause} AND sf.fiscal_year BETWEEN 2017 AND 2026 AND sf.extraction_status IN ('validated','human_reviewed') GROUP BY sf.fiscal_year ORDER BY sf.fiscal_year""",
        "financial_segment_history": f"""SELECT seg.id,seg.production_run_id,seg.fiscal_year,seg.period_end,seg.segment_type,seg.segment_key,seg.segment_name,seg.metric_key,seg.value,seg.currency,seg.unit,seg.source_page,seg.reported_line,seg.extraction_status,seg.exception_reason,run.source_url FROM research.financial_segment_facts seg JOIN research.financial_production_runs run ON run.id=seg.production_run_id WHERE seg.company_id {company_clause} AND seg.fiscal_year BETWEEN 2017 AND 2026 ORDER BY seg.fiscal_year,seg.segment_type,seg.segment_key,seg.metric_key LIMIT 480""",
        "financial_history_gaps": f"""SELECT id,section_key,metric_key,period_start,period_end,gap_status,reason,next_source FROM research.financial_history_gaps WHERE company_id {company_clause} ORDER BY section_key,metric_key LIMIT 80""",
        "financial_production_ratios": f"""SELECT rr.id,rr.production_run_id,fd.formula_key,fd.version formula_version,fd.label,fd.expression,fd.basis,fd.unit,rr.period_end,rr.statement_scope,rr.value,rr.calculation_status,rr.not_computable_reason,rr.caveats,jsonb_agg(jsonb_build_object('input_role',ri.input_role,'fact_id',sf.id,'fact_key',sf.fact_key,'value',sf.value,'unit',sf.unit,'source_page',sf.source_page,'reported_line',sf.reported_line,'status',sf.extraction_status) ORDER BY ri.input_role) inputs FROM research.financial_ratio_results rr JOIN research.financial_formula_definitions fd ON fd.id=rr.formula_definition_id LEFT JOIN research.financial_ratio_inputs ri ON ri.ratio_result_id=rr.id LEFT JOIN research.financial_source_facts sf ON sf.id=ri.fact_id WHERE rr.company_id {company_clause} GROUP BY rr.id,fd.id ORDER BY rr.period_end DESC,fd.label LIMIT 200""",
        "financial_validation_checks": f"""SELECT vc.id,vc.production_run_id,vc.check_key,vc.period_end,vc.check_type,vc.status,vc.left_value,vc.right_value,vc.tolerance,vc.explanation,vc.source_pages FROM research.financial_validation_checks vc JOIN research.financial_production_runs run ON run.id=vc.production_run_id WHERE run.company_id {company_clause} ORDER BY vc.period_end DESC,vc.check_key LIMIT 80""",
        "research_case_agents": f"""SELECT run.id,run.research_case_id,run.role_key,
          run.agent_name,run.skill_key,run.status,task.status task_status,
          node_run.status graph_status,node_run.error source_validation_error,
          worker.status worker_status,worker.output_note_path,
          run.graph_node_run_id,run.task_id,run.inbox_id,run.evidence,run.artifacts,
          run.disagreements,run.exceptions,run.created_at,run.updated_at
          FROM research.research_case_agent_runs run
          LEFT JOIN agent.tasks task ON task.id=run.task_id
          LEFT JOIN agent.graph_node_runs node_run ON node_run.id=run.graph_node_run_id
          LEFT JOIN agent.worker_runs worker ON worker.id=node_run.worker_run_id
          WHERE run.research_case_id IN (
            SELECT id FROM research.research_cases
            WHERE holding_thesis_id={thesis_id} OR company_id {company_clause}
          ) ORDER BY run.research_case_id DESC,run.role_key LIMIT 140""",
        "research_case_evidence": f"""SELECT id,research_case_id,evidence_id,source_item_id,
          source_kind,source_identifier,source_url,local_artifact_path,publication_date,
          effective_date,captured_at,parser_status,validation_status,citation_locator,
          created_by,created_at,updated_at FROM research.research_case_evidence
          WHERE research_case_id IN (
            SELECT id FROM research.research_cases
            WHERE holding_thesis_id={thesis_id} OR company_id {company_clause}
          ) ORDER BY captured_at DESC,id DESC LIMIT 80""",
        "research_case_events": f"""SELECT event.id,event.research_case_id,event.event_type,
          event.event_status,event.event_summary,event.actor,event.event_payload,event.occurred_at
          FROM research.research_case_events event
          WHERE event.research_case_id IN (
            SELECT id FROM research.research_cases
            WHERE holding_thesis_id={thesis_id} OR company_id {company_clause}
          ) ORDER BY event.occurred_at DESC,event.id DESC LIMIT 80""",
        "model_run_preflights": f"""SELECT id,preflight_key,research_case_id,status,
          public_only,private_data_egress_allowed,external_write_allowed,broker_write_allowed,
          source_count,document_count,cached_document_count,estimated_storage_bytes,
          estimated_duration_seconds,estimated_cost_usd,hard_max_cost_usd,
          exchange_rate_inr_per_usd,run_plan,data_boundary,block_reasons,approval_id,
          approval_expires_at,approved_by,approved_at,completed_at,created_at,updated_at
          FROM research.model_run_preflights
          WHERE request_kind='research_case' AND research_case_id IN (
            SELECT id FROM research.research_cases
            WHERE holding_thesis_id={thesis_id} OR company_id {company_clause}
          ) ORDER BY created_at DESC,id DESC LIMIT 30""",
        "research_case_model_runs": f"""SELECT research_case_id,role_key,agent_name,status,
          attempt,route_name,model_name,artifact_path,artifact_hash,output_summary,
          validation_result,cited_source_ids,actual_cost_usd,latency_ms,exception_detail,
          started_at,finished_at,updated_at
          FROM research.v_research_case_model_progress
          WHERE research_case_id IN (
            SELECT id FROM research.research_cases
            WHERE holding_thesis_id={thesis_id} OR company_id {company_clause}
          ) ORDER BY research_case_id DESC,updated_at DESC,role_key LIMIT 160""",
        "thesis_reports": f"""SELECT id,report_key,holding_thesis_id,company_id,
          report_version,report_format,report_status,as_of_date,source_cutoff_at,
          artifact_path,artifact_hash,coverage_snapshot,assumptions,caveats,
          generated_by,human_reviewed_by,human_reviewed_at,created_at
          FROM research.thesis_reports WHERE holding_thesis_id={thesis_id}
          ORDER BY report_version DESC,id DESC LIMIT 12""",
        "source_events": f"""SELECT id,source_item_id,event_type,event_summary,actor,event_payload,
          occurred_at FROM research.thesis_source_events WHERE company_id {company_clause}
          ORDER BY occurred_at DESC,id DESC LIMIT 24""",
        "watchlist": f"""SELECT id,watchlist_key,watchlist_name,purpose,symbol,exchange,
          company_name,item_type,status,priority,thesis,catalyst,invalidation,review_on,
          owner_agent,source_kind,source_ref,evidence,updated_at FROM research.v_watchlist_board
          WHERE upper(symbol)={symbol_sql} ORDER BY updated_at DESC,id DESC LIMIT 20""",
        "committee": f"""SELECT id,review_key,review_status,recommended_decision,
          decision_status,memo_status,memo_note_path,committee_members,evidence_summary,
          source_gaps,required_followups,proposed_action,approval_id,approval_status,
          approval_owner_agent,approval_risk_level,task_id,task_status,final_decision,
          decision_notes,live_execution_allowed,capital_action_allowed,decided_by,
          decided_at,created_by,created_at,updated_at FROM portfolio.v_long_term_committee_queue
          WHERE holding_thesis_id={thesis_id} ORDER BY created_at DESC,id DESC LIMIT 12""",
        "freshness": f"""SELECT
          (SELECT max(available_at) FROM research.v_company_statement_facts_current WHERE company_id {company_clause}) AS financials_at,
          (SELECT max(retrieved_at) FROM research.fundamental_evidence WHERE company_id {company_clause}) AS evidence_at,
          (SELECT max(filed_at) FROM research.corporate_filings WHERE upper(symbol)={symbol_sql}) AS filings_at,
          (SELECT max(coalesce(published_at,captured_at)) FROM market.news_items WHERE {symbol_sql}=ANY(symbols)) AS news_at,
          (SELECT max(opinion_as_of) FROM research.fundamental_specialist_opinions WHERE company_id {company_clause}) AS opinions_at,
          (SELECT max(updated_at) FROM portfolio.holding_valuation_models WHERE holding_thesis_id={thesis_id}) AS valuation_at""",
        "execution_control": """SELECT global_execution_locked,broker_execution_policy,
          paper_trading_allowed,live_broker_writes_allowed,lock_reason,updated_at
          FROM trading.v_execution_control_state LIMIT 1""",
    }
    if dashboard_profile:
        # Keep the front-stage investor read model bounded.  In particular, do
        # not execute case/task/evidence-ledger/model-run/source-pipeline queries
        # merely because an operations drawer exists in the client.
        queries["coverage"] = f"""SELECT
          (SELECT count(*) FROM research.v_company_statement_facts_current
            WHERE company_id {company_clause})::integer AS selected_company_facts,
          (SELECT count(*) FROM research.corporate_filings
            WHERE upper(symbol)={symbol_sql})::integer AS filings_registered,
          (SELECT count(*) FROM research.corporate_filings
            WHERE upper(symbol)={symbol_sql} AND extraction_status='extracted')::integer AS filings_extracted,
          (SELECT count(*) FROM research.corporate_filings
            WHERE upper(symbol)={symbol_sql})::integer AS selected_company_filings"""
        dashboard_keys = {
            "coverage", "valuation_models", "market_price_anchor", "market_holidays", "monte_carlo_runs",
            "thesis_versions", "dossier_sections", "management_guidance",
            "operating_peers", "segment_facts", "governance_observations",
            "filings", "news", "financial_facts", "financial_history", "financial_history_gaps",
            "financial_production_ratios", "financial_validation_checks",
            "thesis_reports", "watchlist", "committee", "execution_control",
        }
        queries = {key: value for key, value in queries.items() if key in dashboard_keys}

    issues = []
    # Financial Quality needs a bounded multi-year statement series. SQL limits remain
    # authoritative; this guard prevents truncating the 240-fact series to 40.
    data = run_map(queries, row_limit=240, batch_size=6, error_collector=issues)
    coverage = (data.get("coverage") or [{}])[0]
    if operations_profile:
        data["financial_quality"] = build_financial_quality(data.get("financial_series") or [])
    data["valuation_workbench"] = build_valuation_workbench(selected, data)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace_profile": workspace_profile,
        "runtime_root": str(runtime_root),
        "vault_root": str(vault_root),
        "privacy": privacy,
        "pagination": {
            "page_size": page_size,
            "facts_page": facts_page,
            "facts_total": int(coverage.get("selected_company_facts") or 0),
            "evidence_page": evidence_page if operations_profile else None,
            "evidence_total": int(coverage.get("selected_company_evidence") or 0) if operations_profile else None,
            "filings_total": int(coverage.get("selected_company_filings") or 0),
        },
        "theses": theses,
        "selected_thesis": selected,
        "issues": issues,
        **data,
    }
