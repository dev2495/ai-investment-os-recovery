"""Deterministic followed-company delta monitor.

The monitor reads only already-authorized warehouse sources, persists durable
source-linked deltas, and queues local extraction for new official filings.
It never invokes a model or performs broker, client, or other external writes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


MATERIAL_TERMS = (
    "results", "earnings", "guidance", "order", "contract", "capacity", "acquisition",
    "merger", "demerger", "buyback", "dividend", "auditor", "resignation", "default",
    "fraud", "investigation", "rating", "pledge", "related party", "insolvency",
)
CRITICAL_TERMS = ("fraud", "default", "insolvency", "investigation", "auditor resignation")
RISK_TERMS = ("resignation", "auditor", "default", "fraud", "investigation", "pledge", "insolvency")


def _classification(title: str) -> tuple[str, str, str]:
    normalized = str(title or "").lower()
    if any(term in normalized for term in CRITICAL_TERMS):
        return "critical", "reunderwrite", "risk"
    if any(term in normalized for term in RISK_TERMS):
        return "high", "review", "risk"
    if any(term in normalized for term in MATERIAL_TERMS):
        return "high", "review", "catalyst"
    return "medium", "monitor", "monitor"


def run_company_research_monitor_once(
    *, run_rows, run_statement, sql_literal, sql_jsonb, limit: int = 80,
    min_interval_minutes: int = 15, force: bool = False,
) -> dict[str, Any]:
    raw_statement = run_statement
    def mutate(sql: str):
        clean = sql.strip().rstrip(";")
        wrapped = f"WITH mutation_rows AS ({clean}) SELECT coalesce(json_agg(row_to_json(mutation_rows)),'[]'::json)::text FROM mutation_rows"
        return raw_statement(wrapped)

    bounded_limit = max(1, min(250, int(limit)))
    interval_minutes = max(5, min(1440, int(min_interval_minutes)))
    if not force:
        recent = run_rows(f"""SELECT id,run_key,status,finished_at FROM research.company_research_monitor_runs
          WHERE status IN ('completed','partial') AND finished_at>=now()-({interval_minutes}||' minutes')::interval
          ORDER BY finished_at DESC,id DESC LIMIT 1""")
        if recent:
            return {"status":"idle","reason":"cooldown","min_interval_minutes":interval_minutes,
                    "last_run":recent[0],"model_calls":0,"private_data_egress_allowed":False,
                    "external_write_allowed":False,"broker_write_allowed":False}
    run_key = "company-research-monitor-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:8]
    followed = run_rows(
        f"""
        SELECT DISTINCT ON (upper(item.exchange),upper(item.symbol))
          item.id watchlist_item_id,item.exchange,item.symbol,item.company_name,item.metadata,
          case_row.id research_case_id,case_row.company_id,case_row.holding_thesis_id,
          case_row.status research_case_status
        FROM research.watchlist_items item
        JOIN research.watchlists list_row ON list_row.id=item.watchlist_id
          AND list_row.watchlist_key='company_research_following'
        LEFT JOIN LATERAL (
          SELECT case_value.id,case_value.company_id,case_value.holding_thesis_id,case_value.status,case_value.updated_at
          FROM research.research_cases case_value
          WHERE upper(coalesce(case_value.exchange,'NSE'))=upper(item.exchange)
            AND upper(case_value.ticker)=upper(item.symbol)
            AND case_value.status IN ('collecting','active','review','blocked','completed')
          ORDER BY case_value.updated_at DESC,case_value.id DESC LIMIT 1
        ) case_row ON true
        WHERE item.status='active'
          AND coalesce((item.metadata->>'monitoring_enabled')::boolean,
                       (item.metadata->>'automatic_collection')::boolean,true)=true
        ORDER BY upper(item.exchange),upper(item.symbol),item.updated_at DESC,item.id DESC
        LIMIT {bounded_limit}
        """
    )
    mutate(
        f"""
        INSERT INTO research.company_research_monitor_runs
          (run_key,status,followed_count,created_by,metadata)
        VALUES ({sql_literal(run_key)},'running',{len(followed)},'Company Research Monitor',
          {sql_jsonb({'bounded_limit': bounded_limit, 'model_calls': 0, 'private_data_egress_allowed': False,
                      'external_write_allowed': False, 'broker_write_allowed': False})})
        ON CONFLICT (run_key) DO NOTHING RETURNING id
        """
    )
    filing_updates = 0
    news_updates = 0
    case_updates = 0
    source_jobs_queued = 0
    errors: list[dict[str, str]] = []
    touched_cases: set[int] = set()

    for item in followed:
        try:
            watchlist_item_id = int(item["watchlist_item_id"])
            case_id = int(item.get("research_case_id") or 0)
            company_id = int(item.get("company_id") or 0)
            exchange = str(item.get("exchange") or "NSE").upper()
            symbol = str(item.get("symbol") or "").upper()
            company_name = str(item.get("company_name") or symbol)

            filings = run_rows(
                f"""
                SELECT filing.id,filing.title,filing.source_url,filing.local_path,
                       filing.extraction_status,coalesce(filing.filed_at,filing.created_at) effective_at,
                       filing.created_at captured_at,filing.content_hash
                FROM research.corporate_filings filing
                WHERE upper(filing.symbol)={sql_literal(symbol)}
                  AND upper(coalesce(filing.exchange,{sql_literal(exchange)}))={sql_literal(exchange)}
                  AND filing.source_url IS NOT NULL
                  AND coalesce(filing.filed_at,filing.created_at)>=now()-interval '45 days'
                ORDER BY coalesce(filing.filed_at,filing.created_at) DESC,filing.id DESC LIMIT 20
                """
            )
            for filing in filings:
                materiality, decision_impact, signal = _classification(str(filing.get("title") or "Official filing"))
                inserted = mutate(
                    f"""
                    INSERT INTO research.company_research_updates
                      (update_key,watchlist_item_id,research_case_id,company_id,exchange,symbol,company_name,
                       update_type,title,summary,source_kind,source_identifier,source_url,effective_at,captured_at,
                       materiality,confidence,decision_impact,evidence,metadata)
                    VALUES ('filing:'||{int(filing['id'])},{watchlist_item_id},{case_id or 'NULL'},{company_id or 'NULL'},
                      {sql_literal(exchange)},{sql_literal(symbol)},{sql_literal(company_name)},'filing',
                      {sql_literal(str(filing.get('title') or 'Official filing'))},
                      {sql_literal('New official filing captured; extraction status: '+str(filing.get('extraction_status') or 'pending')+'.')},
                      'corporate_filing',{sql_literal('research.corporate_filings:'+str(filing['id']))},
                      {sql_literal(filing.get('source_url'))},{sql_literal(str(filing.get('effective_at')))}::timestamptz,
                      {sql_literal(str(filing.get('captured_at') or filing.get('effective_at')))}::timestamptz,
                      {sql_literal(materiality)},0.99,{sql_literal(decision_impact)},
                      {sql_jsonb([{'table':'research.corporate_filings','id':filing['id'],'source_url':filing.get('source_url'),
                                   'content_hash':filing.get('content_hash')}])},
                      {sql_jsonb({'signal':signal,'extraction_status':filing.get('extraction_status'),
                                  'model_generated':False,'human_decision_required':decision_impact in {'review','reunderwrite'}})})
                    ON CONFLICT (update_key) DO NOTHING RETURNING id
                    """
                )
                if inserted:
                    filing_updates += 1
                    if case_id:
                        touched_cases.add(case_id)
                        if str(filing.get("extraction_status") or "") not in {"extracted", "validated", "human_reviewed"}:
                            queued = mutate(
                                f"""
                                INSERT INTO research.research_case_source_jobs
                                  (research_case_id,corporate_filing_id,job_kind,status,priority,source_url,artifact_path,created_by)
                                VALUES ({case_id},{int(filing['id'])},'extract_official_filing','queued',5,
                                  {sql_literal(filing.get('source_url'))},{sql_literal(filing.get('local_path'))},'Company Research Monitor')
                                ON CONFLICT (research_case_id,corporate_filing_id,job_kind) DO UPDATE SET
                                  status=CASE WHEN research.research_case_source_jobs.status IN ('completed','running')
                                    THEN research.research_case_source_jobs.status ELSE 'queued' END,
                                  priority=LEAST(research.research_case_source_jobs.priority,5),next_retry_at=NULL,
                                  source_url=EXCLUDED.source_url,artifact_path=EXCLUDED.artifact_path,updated_at=now()
                                RETURNING status
                                """
                            )
                            if queued and queued[0].get("status") == "queued":
                                source_jobs_queued += 1

            news_rows = run_rows(
                f"""
                SELECT news.id,news.title,news.source_url,news.source_name,news.publisher,
                       coalesce(news.published_at,news.captured_at) effective_at,news.captured_at,
                       news.relevance_score
                FROM market.news_items news
                WHERE {sql_literal(symbol)}=ANY(news.symbols)
                  AND news.source_url IS NOT NULL
                  AND coalesce(news.published_at,news.captured_at)>=now()-interval '14 days'
                ORDER BY coalesce(news.published_at,news.captured_at) DESC,news.id DESC LIMIT 12
                """
            )
            for news in news_rows:
                materiality, decision_impact, signal = _classification(str(news.get("title") or "Public news"))
                confidence = min(0.95, max(0.50, float(news.get("relevance_score") or 0.65)))
                inserted = mutate(
                    f"""
                    INSERT INTO research.company_research_updates
                      (update_key,watchlist_item_id,research_case_id,company_id,exchange,symbol,company_name,
                       update_type,title,summary,source_kind,source_identifier,source_url,effective_at,captured_at,
                       materiality,confidence,decision_impact,evidence,metadata)
                    VALUES ('news:'||{int(news['id'])},{watchlist_item_id},{case_id or 'NULL'},{company_id or 'NULL'},
                      {sql_literal(exchange)},{sql_literal(symbol)},{sql_literal(company_name)},'news',
                      {sql_literal(str(news.get('title') or 'Public news'))},
                      {sql_literal('Authorized public news captured for monitored review; no thesis change is inferred until reviewed.')},
                      'authorized_public_news',{sql_literal('market.news_items:'+str(news['id']))},
                      {sql_literal(news.get('source_url'))},{sql_literal(str(news.get('effective_at')))}::timestamptz,
                      {sql_literal(str(news.get('captured_at') or news.get('effective_at')))}::timestamptz,
                      {sql_literal(materiality)},{confidence:.4f},{sql_literal(decision_impact)},
                      {sql_jsonb([{'table':'market.news_items','id':news['id'],'source_url':news.get('source_url'),
                                   'source_name':news.get('source_name'),'publisher':news.get('publisher')}])},
                      {sql_jsonb({'signal':signal,'model_generated':False,'thesis_change_inferred':False,
                                  'human_decision_required':decision_impact in {'review','reunderwrite'}})})
                    ON CONFLICT (update_key) DO NOTHING RETURNING id
                    """
                )
                if inserted:
                    news_updates += 1

            if case_id:
                case_events = run_rows(
                    f"""
                    SELECT event.id,event.event_type,event.event_status,event.event_summary,event.occurred_at
                    FROM research.research_case_events event
                    WHERE event.research_case_id={case_id}
                      AND event.occurred_at>=now()-interval '30 days'
                      AND event.event_type NOT IN ('monitor_update','proposed')
                    ORDER BY event.occurred_at DESC,event.id DESC LIMIT 12
                    """
                )
                for event in case_events:
                    inserted = mutate(
                        f"""
                        INSERT INTO research.company_research_updates
                          (update_key,watchlist_item_id,research_case_id,company_id,exchange,symbol,company_name,
                           update_type,title,summary,source_kind,source_identifier,effective_at,materiality,
                           confidence,decision_impact,evidence,metadata)
                        VALUES ('case-event:'||{int(event['id'])},{watchlist_item_id},{case_id},{company_id or 'NULL'},
                          {sql_literal(exchange)},{sql_literal(symbol)},{sql_literal(company_name)},'case_event',
                          {sql_literal(str(event.get('event_type') or 'Research case update').replace('_',' ').title())},
                          {sql_literal(str(event.get('event_summary') or 'Research case status changed.'))},
                          'research_case_event',{sql_literal('research.research_case_events:'+str(event['id']))},
                          {sql_literal(str(event.get('occurred_at')))}::timestamptz,'medium',1.0,'monitor',
                          {sql_jsonb([{'table':'research.research_case_events','id':event['id']}])},
                          {sql_jsonb({'event_status':event.get('event_status'),'model_generated':False})})
                        ON CONFLICT (update_key) DO NOTHING RETURNING id
                        """
                    )
                    if inserted:
                        case_updates += 1
        except Exception as exc:  # one company cannot stop the bounded monitor pass
            errors.append({"symbol": str(item.get("symbol") or ""), "error": f"{type(exc).__name__}: {exc}"[:500]})

    for case_id in touched_cases:
        mutate(
            f"""
            UPDATE research.research_cases SET
              status=CASE WHEN status IN ('completed','review') THEN status ELSE 'collecting' END,
              lead_status=CASE WHEN status IN ('completed','review') THEN lead_status ELSE 'monitoring_update_extraction' END,
              current_goal=CASE WHEN status IN ('completed','review') THEN current_goal ELSE 'Extract new official monitored filings' END,
              last_progress_at=now(),updated_at=now()
            WHERE id={case_id} RETURNING id
            """
        )

    status = "partial" if errors else "completed"
    result_rows = mutate(
        f"""
        UPDATE research.company_research_monitor_runs SET status={sql_literal(status)},
          filing_updates={filing_updates},news_updates={news_updates},case_updates={case_updates},
          source_jobs_queued={source_jobs_queued},error_count={len(errors)},errors={sql_jsonb(errors)},finished_at=now()
        WHERE run_key={sql_literal(run_key)} RETURNING *
        """
    )
    result = result_rows[0] if result_rows else {"run_key": run_key, "status": status}
    result.update({
        "model_calls": 0,
        "private_data_egress_allowed": False,
        "external_write_allowed": False,
        "broker_write_allowed": False,
    })
    return result
