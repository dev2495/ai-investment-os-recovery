from __future__ import annotations

import hashlib
import json
from typing import Any, Callable


QueryFn = Callable[[str], list[dict[str, Any]]]
StatementFn = Callable[[str], list[dict[str, Any]]]

TERMINAL_RUN_STATES = {"completed", "failed", "cancelled"}
TERMINAL_NODE_STATES = {"completed", "skipped", "failed", "cancelled"}
ACTIVE_NODE_STATES = {"ready", "queued", "running", "waiting_approval", "waiting_input"}


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("\x00", "").replace("'", "''") + "'"


def sql_jsonb(value: object) -> str:
    return f"{sql_literal(json.dumps({} if value is None else value, separators=(',', ':'), default=str))}::jsonb"


def bounded_int(value: object, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError) as exc:
        raise ValueError("value must be an integer") from exc
    return max(minimum, min(maximum, parsed))


def _one(rows: list[dict[str, Any]], message: str) -> dict[str, Any]:
    if not rows:
        raise ValueError(message)
    return rows[0]


def _path_value(payload: object, path: str) -> object:
    current = payload
    for segment in [part for part in path.split(".") if part]:
        if isinstance(current, dict):
            current = current.get(segment)
        elif isinstance(current, list) and segment.isdigit():
            index = int(segment)
            current = current[index] if 0 <= index < len(current) else None
        else:
            return None
    return current


def condition_matches(edge: dict[str, Any], run: dict[str, Any], node_run: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    condition_type = str(edge.get("condition_type") or "always")
    condition = edge.get("condition") if isinstance(edge.get("condition"), dict) else {}
    state = run.get("working_state") if isinstance(run.get("working_state"), dict) else {}
    output = node_run.get("output_payload") if isinstance(node_run.get("output_payload"), dict) else {}

    if condition_type == "always":
        return True, {"condition_type": condition_type}
    if condition_type == "state_present":
        value = _path_value(state, str(condition.get("path") or ""))
        return value not in (None, "", [], {}), {"condition_type": condition_type, "observed": value}
    if condition_type == "state_equals":
        value = _path_value(state, str(condition.get("path") or ""))
        expected = condition.get("equals")
        return value == expected, {"condition_type": condition_type, "observed": value, "expected": expected}
    if condition_type == "node_output_equals":
        value = _path_value(output, str(condition.get("path") or ""))
        expected = condition.get("equals")
        return value == expected, {"condition_type": condition_type, "observed": value, "expected": expected}
    if condition_type == "node_output_not_equals":
        value = _path_value(output, str(condition.get("path") or ""))
        expected = condition.get("equals")
        return value != expected, {"condition_type": condition_type, "observed": value, "expected": expected}
    if condition_type in {"approved", "rejected"}:
        observed = str(node_run.get("approval_status") or output.get("decision") or "").lower()
        expected = "approved" if condition_type == "approved" else "rejected"
        return observed == expected, {"condition_type": condition_type, "observed": observed, "expected": expected}
    return False, {"condition_type": condition_type, "error": "unsupported_condition"}


def build_snapshot(query: QueryFn, *, run_id: int | None = None) -> dict[str, Any]:
    run_filter = f"WHERE graph_run_id={int(run_id)}" if run_id is not None else ""
    node_filter = f"WHERE graph_run_id={int(run_id)}" if run_id is not None else ""
    edge_filter = f"WHERE graph_run_id={int(run_id)}" if run_id is not None else ""
    event_filter = f"WHERE graph_run_id={int(run_id)}" if run_id is not None else ""
    checkpoint_filter = f"WHERE graph_run_id={int(run_id)}" if run_id is not None else ""
    return {
        "graphs": query("SELECT * FROM agent.v_graph_catalog ORDER BY graph_family,graph_name"),
        "nodes": query(
            """
            SELECT node.id AS graph_node_id,version.graph_key,version.version,
                   node.node_key,node.node_name,node.node_type,node.owner_agent,
                   node.skill_key,node.autonomy_level,node.approval_required,
                   node.retry_limit,node.timeout_seconds,node.configuration,
                   node.output_contract,node.on_error,node.ui_position
            FROM agent.graph_nodes node
            JOIN agent.graph_versions version ON version.id=node.graph_version_id
            JOIN agent.graph_definitions definition
              ON definition.graph_key=version.graph_key
             AND definition.active_version=version.version
            ORDER BY version.graph_key,node.id
            """
        ),
        "edges": query(
            """
            SELECT edge.id AS graph_edge_id,version.graph_key,version.version,
                   edge.from_node_key,edge.to_node_key,edge.edge_kind,
                   edge.condition_type,edge.condition,edge.priority,edge.enabled,edge.label
            FROM agent.graph_edges edge
            JOIN agent.graph_versions version ON version.id=edge.graph_version_id
            JOIN agent.graph_definitions definition
              ON definition.graph_key=version.graph_key
             AND definition.active_version=version.version
            ORDER BY version.graph_key,edge.priority,edge.id
            """
        ),
        "runs": query(
            f"SELECT * FROM agent.v_graph_run_status {run_filter} ORDER BY created_at DESC,graph_run_id DESC LIMIT 80"
        ),
        "node_runs": query(
            f"SELECT * FROM agent.v_graph_node_run_detail {node_filter} ORDER BY created_at,graph_node_run_id LIMIT 500"
        ),
        "edge_runs": query(
            f"SELECT * FROM agent.v_graph_edge_run_detail {edge_filter} ORDER BY created_at,graph_edge_run_id LIMIT 500"
        ),
        "checkpoints": query(
            f"""
            SELECT id,graph_run_id,graph_node_run_id,checkpoint_kind,resume_token,
                   state_snapshot,evidence_snapshot,created_by,created_at
            FROM agent.graph_checkpoints {checkpoint_filter}
            ORDER BY created_at DESC,id DESC LIMIT 120
            """
        ),
        "events": query(
            f"""
            SELECT id,graph_run_id,graph_node_run_id,event_type,severity,actor,
                   event_payload,occurred_at
            FROM agent.graph_events {event_filter}
            ORDER BY occurred_at DESC,id DESC LIMIT 300
            """
        ),
        "autonomy": query("SELECT * FROM agent.v_autonomy_control_board ORDER BY policy_key"),
        "autonomy_evidence": query(
            """
            SELECT evidence.id,policy.policy_key,evidence.graph_run_id,
                   evidence.graph_node_run_id,evidence.action_class,evidence.decision,
                   evidence.rationale,evidence.evidence,evidence.decided_by,evidence.created_at
            FROM agent.autonomy_evidence evidence
            LEFT JOIN agent.autonomy_policies policy ON policy.id=evidence.policy_id
            ORDER BY evidence.created_at DESC,evidence.id DESC LIMIT 160
            """
        ),
        "attention": query("SELECT * FROM agent.v_graph_attention_queue ORDER BY created_at DESC LIMIT 160"),
        "change_requests": query(
            """
            SELECT request.*,base.version AS base_version,applied.version AS applied_version,
                   approval.status AS approval_status
            FROM agent.graph_change_requests request
            LEFT JOIN agent.graph_versions base ON base.id=request.base_version_id
            LEFT JOIN agent.graph_versions applied ON applied.id=request.applied_version_id
            LEFT JOIN agent.approvals approval ON approval.id=request.approval_id
            ORDER BY request.created_at DESC,request.id DESC LIMIT 120
            """
        ),
        "corrections": query(
            "SELECT * FROM agent.correction_ledger ORDER BY created_at DESC,id DESC LIMIT 160"
        ),
        "waiting": query(
            "SELECT * FROM agent.waiting_on_principal ORDER BY created_at DESC,id DESC LIMIT 160"
        ),
    }


def start_graph_run(query: QueryFn, statement: StatementFn, payload: dict[str, Any]) -> dict[str, Any]:
    graph_key = str(payload.get("graph_key") or payload.get("graphKey") or "").strip()
    if not graph_key:
        raise ValueError("graph_key is required")
    actor = str(payload.get("actor") or payload.get("triggered_by") or "Charlie Munger").strip()
    trigger_type = str(payload.get("trigger_type") or payload.get("triggerType") or "manual").strip()
    input_payload = payload.get("input_payload") or payload.get("inputPayload") or {}
    if not isinstance(input_payload, dict):
        raise ValueError("input_payload must be an object")
    graph = _one(
        query(f"SELECT * FROM agent.v_graph_catalog WHERE graph_key={sql_literal(graph_key)} LIMIT 1"),
        f"active graph not found: {graph_key}",
    )
    if graph.get("status") != "active" or graph.get("version_status") != "active":
        raise ValueError(f"graph is not active and validated: {graph_key}")
    validation = graph.get("validation_result") if isinstance(graph.get("validation_result"), dict) else {}
    if not validation.get("valid"):
        raise ValueError(f"graph validation is not current: {graph_key}")

    contract_rows = query(
        f"SELECT input_contract FROM agent.graph_definitions WHERE graph_key={sql_literal(graph_key)} LIMIT 1"
    )
    contract = contract_rows[0].get("input_contract") if contract_rows else {}
    required = contract.get("required", []) if isinstance(contract, dict) else []
    missing = [str(key) for key in required if input_payload.get(str(key)) in (None, "", [], {})]
    if missing:
        raise ValueError("missing required graph inputs: " + ", ".join(missing))

    idempotency_key = str(payload.get("idempotency_key") or payload.get("idempotencyKey") or "").strip()
    correlation_key = str(payload.get("correlation_key") or payload.get("correlationKey") or "").strip()
    subject_type = str(payload.get("subject_type") or payload.get("subjectType") or "").strip()
    subject_ref = str(payload.get("subject_ref") or payload.get("subjectRef") or "").strip()

    rows = statement(
        f"""
        WITH selected AS (
            SELECT version.id AS graph_version_id,node.id AS start_node_id
            FROM agent.graph_definitions definition
            JOIN agent.graph_versions version
              ON version.graph_key=definition.graph_key
             AND version.version=definition.active_version
             AND version.status='active'
            JOIN agent.graph_nodes node
              ON node.graph_version_id=version.id AND node.node_type='start'
            WHERE definition.graph_key={sql_literal(graph_key)} AND definition.status='active'
            LIMIT 1
        ), existing AS (
            SELECT id FROM agent.graph_runs
            WHERE {sql_literal(idempotency_key)} <> ''
              AND idempotency_key={sql_literal(idempotency_key)}
            LIMIT 1
        ), inserted_run AS (
            INSERT INTO agent.graph_runs (
                graph_key,graph_version_id,trigger_type,triggered_by,run_status,
                idempotency_key,correlation_key,subject_type,subject_ref,
                input_payload,working_state,started_at
            )
            SELECT {sql_literal(graph_key)},selected.graph_version_id,
                   {sql_literal(trigger_type)},{sql_literal(actor)},'running',
                   nullif({sql_literal(idempotency_key)},''),nullif({sql_literal(correlation_key)},''),
                   nullif({sql_literal(subject_type)},''),nullif({sql_literal(subject_ref)},''),
                   {sql_jsonb(input_payload)},jsonb_build_object('input',{sql_jsonb(input_payload)}),now()
            FROM selected
            WHERE NOT EXISTS (SELECT 1 FROM existing)
            RETURNING id,graph_version_id
        ), selected_run AS (
            SELECT inserted_run.id,inserted_run.graph_version_id FROM inserted_run
            UNION ALL
            SELECT run.id,run.graph_version_id
            FROM agent.graph_runs run JOIN existing ON existing.id=run.id
            LIMIT 1
        ), start_node AS (
            SELECT node.id,selected_run.id AS graph_run_id
            FROM selected_run
            JOIN agent.graph_nodes node
              ON node.graph_version_id=selected_run.graph_version_id AND node.node_type='start'
            LIMIT 1
        ), inserted_node AS (
            INSERT INTO agent.graph_node_runs (
                graph_run_id,graph_node_id,attempt,status,input_payload
            )
            SELECT start_node.graph_run_id,start_node.id,1,'ready',{sql_jsonb(input_payload)}
            FROM start_node
            ON CONFLICT (graph_run_id,graph_node_id,attempt) DO NOTHING
            RETURNING id,graph_run_id
        ), event_insert AS (
            INSERT INTO agent.graph_events (
                graph_run_id,graph_node_run_id,event_type,severity,actor,event_payload
            )
            SELECT selected_run.id,inserted_node.id,'graph_started','info',{sql_literal(actor)},
                   jsonb_build_object('graph_key',{sql_literal(graph_key)},'trigger_type',{sql_literal(trigger_type)})
            FROM selected_run LEFT JOIN inserted_node ON inserted_node.graph_run_id=selected_run.id
            WHERE EXISTS (SELECT 1 FROM inserted_run)
            RETURNING id
        )
        SELECT jsonb_build_array(jsonb_build_object(
            'graph_run_id',selected_run.id,
            'created',EXISTS(SELECT 1 FROM inserted_run),
            'graph_key',{sql_literal(graph_key)},
            'run_status',(SELECT run_status FROM agent.graph_runs WHERE id=selected_run.id)
        ))::TEXT
        FROM selected_run
        """
    )
    return _one(rows, "graph run could not be created")


def _fetch_run(query: QueryFn, run_id: int) -> dict[str, Any]:
    return _one(
        query(f"SELECT * FROM agent.v_graph_run_status WHERE graph_run_id={int(run_id)} LIMIT 1"),
        f"graph run not found: {run_id}",
    )


def _fetch_node_runs(query: QueryFn, run_id: int) -> list[dict[str, Any]]:
    return query(
        f"SELECT * FROM agent.v_graph_node_run_detail WHERE graph_run_id={int(run_id)} ORDER BY created_at,graph_node_run_id"
    )


def _record_autonomy_decision(
    query: QueryFn,
    statement: StatementFn,
    run: dict[str, Any],
    node_run: dict[str, Any],
    actor: str,
) -> str:
    level = str(node_run.get("autonomy_level") or "draft_only")
    if level == "prohibited":
        decision = "deny"
        rationale = "The node is prohibited by the active graph version."
    elif level == "human_approval" or node_run.get("approval_required"):
        decision = "requires_approval"
        rationale = "The node is explicitly human-gated."
    else:
        decision = "allow"
        rationale = "The node may create bounded internal work under the active version; downstream capital and external actions remain gated."
    policy_key = "global_default_draft"
    configuration = node_run.get("configuration") if isinstance(node_run.get("configuration"), dict) else {}
    approval_type = str(configuration.get("approval_type") or "")
    if approval_type in {"investment_decision", "strategy_promotion"}:
        policy_key = "capital_action_gate"
    if node_run.get("node_type") == "tool_task" and "cloud" in str(node_run.get("skill_key") or ""):
        policy_key = "paid_cloud_gate"
    statement(
        f"""
        WITH policy AS (
            SELECT id FROM agent.autonomy_policies WHERE policy_key={sql_literal(policy_key)} LIMIT 1
        ), inserted AS (
            INSERT INTO agent.autonomy_evidence (
                policy_id,graph_run_id,graph_node_run_id,action_class,decision,
                rationale,evidence,decided_by
            )
            SELECT policy.id,{int(run['graph_run_id'])},{int(node_run['graph_node_run_id'])},
                   {sql_literal(str(node_run.get('node_type') or 'node'))},
                   {sql_literal(decision)},{sql_literal(rationale)},
                   jsonb_build_array(jsonb_build_object(
                       'graph_key',{sql_literal(str(run.get('graph_key') or ''))},
                       'node_key',{sql_literal(str(node_run.get('node_key') or ''))},
                       'autonomy_level',{sql_literal(level)},
                       'broker_writes_allowed',false
                   )),{sql_literal(actor)}
            FROM policy
            RETURNING id
        )
        SELECT jsonb_build_array(jsonb_build_object('id',id))::TEXT FROM inserted
        """
    )
    return decision


def _complete_node(
    query: QueryFn,
    statement: StatementFn,
    run: dict[str, Any],
    node_run: dict[str, Any],
    actor: str,
    output: dict[str, Any] | None = None,
    evidence: list[dict[str, Any]] | None = None,
) -> None:
    node_run_id = int(node_run["graph_node_run_id"])
    output_payload = output or {}
    evidence_payload = evidence or []
    statement(
        f"""
        WITH updated AS (
            UPDATE agent.graph_node_runs
            SET status='completed',output_payload={sql_jsonb(output_payload)},
                evidence=coalesce(evidence,'[]'::jsonb) || {sql_jsonb(evidence_payload)},
                started_at=coalesce(started_at,now()),finished_at=now(),updated_at=now()
            WHERE id={node_run_id} AND status NOT IN ('completed','skipped','failed','cancelled')
            RETURNING id,graph_run_id
        ), run_update AS (
            UPDATE agent.graph_runs run
            SET working_state=working_state || jsonb_build_object(
                    {sql_literal(str(node_run.get('node_key') or node_run_id))},
                    {sql_jsonb(output_payload)}
                ),
                run_status=CASE WHEN run_status IN ('waiting_approval','waiting_input') THEN 'running' ELSE run_status END,
                updated_at=now()
            FROM updated WHERE run.id=updated.graph_run_id
            RETURNING run.id
        ), event_insert AS (
            INSERT INTO agent.graph_events (
                graph_run_id,graph_node_run_id,event_type,severity,actor,event_payload
            )
            SELECT updated.graph_run_id,updated.id,'node_completed','info',{sql_literal(actor)},
                   jsonb_build_object('node_key',{sql_literal(str(node_run.get('node_key') or ''))},
                                      'node_type',{sql_literal(str(node_run.get('node_type') or ''))})
            FROM updated RETURNING id
        )
        SELECT jsonb_build_array(jsonb_build_object('completed',EXISTS(SELECT 1 FROM updated)))::TEXT
        """
    )
    _activate_successors(query, statement, _fetch_run(query, int(run["graph_run_id"])), node_run_id, actor)


def _fail_node(
    statement: StatementFn,
    run_id: int,
    node_run: dict[str, Any],
    actor: str,
    error: dict[str, Any],
) -> None:
    node_run_id = int(node_run["graph_node_run_id"])
    on_error = str(node_run.get("on_error") or "pause")
    run_status = "failed" if on_error == "fail" else "paused"
    node_status = "failed" if run_status == "failed" else "waiting_input"
    statement(
        f"""
        WITH updated AS (
            UPDATE agent.graph_node_runs
            SET status={sql_literal(node_status)},error={sql_jsonb(error)},
                finished_at=CASE WHEN {sql_literal(node_status)}='failed' THEN now() ELSE finished_at END,
                updated_at=now()
            WHERE id={node_run_id} RETURNING id,graph_run_id
        ), run_update AS (
            UPDATE agent.graph_runs run
            SET run_status={sql_literal(run_status)},failure={sql_jsonb(error)},updated_at=now(),
                finished_at=CASE WHEN {sql_literal(run_status)}='failed' THEN now() ELSE finished_at END
            FROM updated WHERE run.id=updated.graph_run_id RETURNING run.id
        ), correction AS (
            INSERT INTO agent.correction_ledger (
                source_kind,source_ref,graph_run_id,graph_node_run_id,correction_type,
                severity,observed_state,corrective_action,status,owner_agent
            )
            SELECT 'graph_node',updated.id::TEXT,updated.graph_run_id,updated.id,
                   'node_failure','high',{sql_jsonb(error)},
                   'Inspect the bounded failure evidence, repair the dependency or graph version, and verify before resuming.',
                   'open',coalesce({sql_literal(str(node_run.get('owner_agent') or ''))},'Jarvis')
            FROM updated RETURNING id
        ), event_insert AS (
            INSERT INTO agent.graph_events (
                graph_run_id,graph_node_run_id,event_type,severity,actor,event_payload
            )
            SELECT updated.graph_run_id,updated.id,'node_failed','error',{sql_literal(actor)},{sql_jsonb(error)}
            FROM updated RETURNING id
        )
        SELECT jsonb_build_array(jsonb_build_object('failed',EXISTS(SELECT 1 FROM updated)))::TEXT
        """
    )


def _activate_successors(
    query: QueryFn,
    statement: StatementFn,
    run: dict[str, Any],
    source_node_run_id: int,
    actor: str,
) -> None:
    source_node = _one(
        query(f"SELECT * FROM agent.v_graph_node_run_detail WHERE graph_node_run_id={int(source_node_run_id)} LIMIT 1"),
        f"source node run not found: {source_node_run_id}",
    )
    edges = query(
        f"""
        SELECT edge.*,target.id AS target_node_id,target.node_type AS target_node_type,
               target.configuration AS target_configuration
        FROM agent.graph_edges edge
        JOIN agent.graph_nodes target
          ON target.graph_version_id=edge.graph_version_id
         AND target.node_key=edge.to_node_key
        WHERE edge.graph_version_id={int(run['graph_version_id'])}
          AND edge.from_node_key={sql_literal(str(source_node.get('node_key') or ''))}
          AND edge.enabled=true
          AND edge.edge_kind IN ('success','conditional','loop')
        ORDER BY edge.priority,edge.id
        """
    )
    for edge in edges:
        matched, condition_result = condition_matches(edge, run, source_node)
        edge_id = int(edge["id"])
        if not matched:
            statement(
                f"""
                WITH inserted AS (
                    INSERT INTO agent.graph_edge_runs (
                        graph_run_id,graph_edge_id,source_node_run_id,condition_result,status
                    ) VALUES ({int(run['graph_run_id'])},{edge_id},{int(source_node_run_id)},
                              {sql_jsonb(condition_result)},'suppressed')
                    ON CONFLICT (graph_run_id,graph_edge_id,source_node_run_id) DO NOTHING
                    RETURNING id
                )
                SELECT jsonb_build_array(jsonb_build_object('suppressed',EXISTS(SELECT 1 FROM inserted)))::TEXT
                """
            )
            continue

        attempt = 1
        if edge.get("edge_kind") == "loop":
            traversals = query(
                f"SELECT count(*)::INTEGER AS count FROM agent.graph_edge_runs WHERE graph_run_id={int(run['graph_run_id'])} AND graph_edge_id={edge_id} AND status='traversed'"
            )
            attempt = int((traversals[0] if traversals else {}).get("count") or 0) + 1
            max_iterations = bounded_int((edge.get("condition") or {}).get("max_iterations"), default=1, minimum=1, maximum=50)
            if attempt > max_iterations:
                continue
        initial_status = "blocked" if edge.get("target_node_type") == "join" else "ready"
        rows = statement(
            f"""
            WITH target_insert AS (
                INSERT INTO agent.graph_node_runs (
                    graph_run_id,graph_node_id,attempt,status,input_payload
                ) VALUES (
                    {int(run['graph_run_id'])},{int(edge['target_node_id'])},{attempt},
                    {sql_literal(initial_status)},
                    jsonb_build_object('from_node_run_id',{int(source_node_run_id)},
                                       'graph_input',{sql_jsonb(run.get('input_payload') or {})})
                )
                ON CONFLICT (graph_run_id,graph_node_id,attempt) DO NOTHING
                RETURNING id
            ), target_row AS (
                SELECT id FROM target_insert
                UNION ALL
                SELECT id FROM agent.graph_node_runs
                WHERE graph_run_id={int(run['graph_run_id'])}
                  AND graph_node_id={int(edge['target_node_id'])}
                  AND attempt={attempt}
                LIMIT 1
            ), edge_insert AS (
                INSERT INTO agent.graph_edge_runs (
                    graph_run_id,graph_edge_id,source_node_run_id,target_node_run_id,
                    traversal,condition_result,status
                )
                SELECT {int(run['graph_run_id'])},{edge_id},{int(source_node_run_id)},
                       target_row.id,{attempt},{sql_jsonb(condition_result)},'traversed'
                FROM target_row
                ON CONFLICT (graph_run_id,graph_edge_id,source_node_run_id) DO NOTHING
                RETURNING id,target_node_run_id
            ), event_insert AS (
                INSERT INTO agent.graph_events (
                    graph_run_id,graph_node_run_id,event_type,severity,actor,event_payload
                )
                SELECT {int(run['graph_run_id'])},target_row.id,'edge_traversed','debug',
                       {sql_literal(actor)},jsonb_build_object(
                           'edge_id',{edge_id},'from_node_key',{sql_literal(str(edge.get('from_node_key') or ''))},
                           'to_node_key',{sql_literal(str(edge.get('to_node_key') or ''))},'attempt',{attempt}
                       )
                FROM target_row WHERE EXISTS (SELECT 1 FROM edge_insert)
                RETURNING id
            )
            SELECT jsonb_build_array(jsonb_build_object(
                'target_node_run_id',(SELECT id FROM target_row),
                'traversed',EXISTS(SELECT 1 FROM edge_insert)
            ))::TEXT
            """
        )
        target_run_id = int((rows[0] if rows else {}).get("target_node_run_id") or 0)
        if target_run_id and edge.get("target_node_type") == "join":
            _refresh_join(query, statement, int(run["graph_run_id"]), target_run_id)


def _refresh_join(query: QueryFn, statement: StatementFn, run_id: int, node_run_id: int) -> None:
    rows = query(
        f"""
        SELECT detail.graph_version_id,detail.graph_node_id,detail.configuration,
               (SELECT count(*) FROM agent.graph_edges edge
                WHERE edge.graph_version_id=detail.graph_version_id
                  AND edge.to_node_key=detail.node_key AND edge.enabled=true
                  AND edge.edge_kind IN ('success','conditional','loop'))::INTEGER AS incoming_count,
               (SELECT count(*) FROM agent.graph_edge_runs edge_run
                WHERE edge_run.graph_run_id=detail.graph_run_id
                  AND edge_run.target_node_run_id=detail.graph_node_run_id
                  AND edge_run.status='traversed')::INTEGER AS traversed_count
        FROM (
            SELECT node_run.graph_run_id,node_run.id AS graph_node_run_id,
                   node.graph_version_id,node.id AS graph_node_id,node.node_key,node.configuration
            FROM agent.graph_node_runs node_run
            JOIN agent.graph_nodes node ON node.id=node_run.graph_node_id
            WHERE node_run.id={int(node_run_id)} AND node.node_type='join'
        ) detail
        """
    )
    if not rows:
        return
    row = rows[0]
    configuration = row.get("configuration") if isinstance(row.get("configuration"), dict) else {}
    join_mode = str(configuration.get("join") or "all_success")
    incoming = int(row.get("incoming_count") or 0)
    traversed = int(row.get("traversed_count") or 0)
    ready = traversed >= 1 if join_mode in {"any", "any_success"} else incoming > 0 and traversed >= incoming
    if ready:
        statement(
            f"""
            WITH updated AS (
                UPDATE agent.graph_node_runs SET status='ready',updated_at=now()
                WHERE id={int(node_run_id)} AND status='blocked' RETURNING id
            )
            SELECT jsonb_build_array(jsonb_build_object('ready',EXISTS(SELECT 1 FROM updated)))::TEXT
            """
        )


def _dispatch_task_node(
    query: QueryFn,
    statement: StatementFn,
    run: dict[str, Any],
    node_run: dict[str, Any],
    actor: str,
) -> None:
    node_run_id = int(node_run["graph_node_run_id"])
    if node_run.get("task_id"):
        return
    owner = str(node_run.get("owner_agent") or "Jarvis")
    skill_key = str(node_run.get("skill_key") or "route_user_request")
    configuration = node_run.get("configuration") if isinstance(node_run.get("configuration"), dict) else {}
    source_qualified_worker_required = configuration.get("source_qualified_worker_required") is True
    dispatch_status = "needs_review" if source_qualified_worker_required else "queued"
    priority = str(configuration.get("priority") or "medium").lower()
    if priority not in {"low", "normal", "medium", "high", "critical"}:
        priority = "medium"
    objective = str(configuration.get("objective") or "").strip() or (
        f"Complete `{node_run.get('node_name')}` in graph `{run.get('graph_name')}`. "
        "Use only the graph input and verified warehouse evidence, attach source lineage, "
        "state missing evidence, and return a bounded internal result. Do not place orders, "
        "change capital, send external messages, or bypass approvals."
    )
    metadata = {
        "graph_run_id": int(run["graph_run_id"]),
        "graph_node_run_id": node_run_id,
        "graph_key": run.get("graph_key"),
        "node_key": node_run.get("node_key"),
        "skill_key": skill_key,
        "input_payload": run.get("input_payload") or {},
        "source_qualified_worker_required": source_qualified_worker_required,
    }
    rows = statement(
        f"""
        WITH selected AS (
            SELECT node_run.id,node_run.graph_run_id,node.node_name,node.node_key,
                   node.owner_agent,node.skill_key
            FROM agent.graph_node_runs node_run
            JOIN agent.graph_nodes node ON node.id=node_run.graph_node_id
            WHERE node_run.id={node_run_id} AND node_run.status='ready'
            FOR UPDATE
        ), task_insert AS (
            INSERT INTO agent.tasks (
                title,objective,owner_agent,status,priority,approval_required,
                source_kind,source_ref,output_format,evidence
            )
            SELECT selected.node_name,{sql_literal(objective)},selected.owner_agent,
                   {sql_literal(dispatch_status)},{sql_literal(priority)},{str(source_qualified_worker_required).lower()},'agent_message',selected.id::TEXT,
                   'graph_node_result',jsonb_build_array(jsonb_build_object(
                       'source_table','agent.graph_node_runs','graph_run_id',selected.graph_run_id,
                       'graph_node_run_id',selected.id,'node_key',selected.node_key,
                       'skill_key',selected.skill_key,'graph_input',{sql_jsonb(run.get('input_payload') or {})}
                   ))
            FROM selected RETURNING id,title,objective,owner_agent
        ), inbox_insert AS (
            INSERT INTO agent.inbox_items (
                task_id,title,owner_agent,status,priority,recommended_action,evidence,target_workspace
            )
            SELECT task.id,task.title,task.owner_agent,{sql_literal(dispatch_status)},{sql_literal(priority)},
                   {sql_literal('Assign a source-qualified worker and complete the graph node with company-scoped citations; generic task receipts do not satisfy this lane.' if source_qualified_worker_required else 'Complete the graph node with evidence; stop and report if a required source or permission is missing.')},
                   jsonb_build_array(jsonb_build_object(
                       'source_table','agent.graph_node_runs','graph_node_run_id',{node_run_id}
                   )),coalesce(nullif(profile.department,''),'command')
            FROM task_insert task LEFT JOIN agent.profiles profile ON profile.agent_name=task.owner_agent
            RETURNING id,task_id
        ), message_insert AS (
            INSERT INTO agent.agent_messages (
                thread_key,from_agent,to_agent,subject,body,priority,status,
                related_task_id,related_skill_key,metadata,processing_status,
                processed_at,generated_task_id,generated_inbox_id
            )
            SELECT 'graph-' || {int(run['graph_run_id'])}::TEXT,
                   CASE WHEN EXISTS (SELECT 1 FROM agent.profiles WHERE agent_name={sql_literal(actor)} AND status='active')
                        THEN {sql_literal(actor)} ELSE 'Charlie Munger' END,
                   task.owner_agent,task.title,task.objective,{sql_literal(priority)},
                   {sql_literal('needs_review' if source_qualified_worker_required else 'routed_to_task')},task.id,{sql_literal(skill_key)},{sql_jsonb(metadata)},
                   {sql_literal('needs_review' if source_qualified_worker_required else 'routed_to_task')},now(),task.id,inbox.id
            FROM task_insert task JOIN inbox_insert inbox ON inbox.task_id=task.id
            RETURNING id,generated_task_id,generated_inbox_id
        ), node_update AS (
            UPDATE agent.graph_node_runs node_run
            SET status={sql_literal('waiting_approval' if source_qualified_worker_required else 'queued')},task_id=message.generated_task_id,message_id=message.id,
                started_at=coalesce(started_at,now()),updated_at=now()
            FROM message_insert message WHERE node_run.id={node_run_id}
            RETURNING node_run.id,node_run.graph_run_id,node_run.task_id,node_run.message_id
        ), event_insert AS (
            INSERT INTO agent.graph_events (
                graph_run_id,graph_node_run_id,event_type,severity,actor,event_payload
            )
            SELECT node_update.graph_run_id,node_update.id,{sql_literal('source_worker_assignment_required' if source_qualified_worker_required else 'node_dispatched')},{sql_literal('warning' if source_qualified_worker_required else 'info')},
                   {sql_literal(actor)},jsonb_build_object(
                       'task_id',node_update.task_id,'message_id',node_update.message_id,
                       'owner_agent',{sql_literal(owner)},'skill_key',{sql_literal(skill_key)},
                       'source_qualified_worker_required',{str(source_qualified_worker_required).lower()}
                   )
            FROM node_update RETURNING id
        )
        SELECT jsonb_build_array(jsonb_build_object(
            'node_run_id',node_update.id,'task_id',node_update.task_id,
            'message_id',node_update.message_id,
            'source_qualified_worker_required',{str(source_qualified_worker_required).lower()}
        ))::TEXT FROM node_update
        """
    )
    if not rows:
        raise RuntimeError(f"graph node could not be dispatched: {node_run_id}")


def _dispatch_committee_node(
    statement: StatementFn,
    run: dict[str, Any],
    node_run: dict[str, Any],
    actor: str,
) -> None:
    if node_run.get("committee_packet_id"):
        return
    configuration = node_run.get("configuration") if isinstance(node_run.get("configuration"), dict) else {}
    committee_key = str(configuration.get("committee_key") or "").strip()
    if not committee_key:
        raise ValueError(f"committee_key is required for graph node: {node_run.get('node_key')}")
    rows = statement(
        f"""
        SELECT jsonb_build_array(agent.open_graph_committee_packet(
            {int(run['graph_run_id'])},
            {int(node_run['graph_node_run_id'])},
            {sql_literal(committee_key)},
            {sql_literal(actor)}
        ))::TEXT
        """
    )
    if not rows:
        raise RuntimeError(
            f"committee packet could not be opened for graph node: {node_run.get('graph_node_run_id')}"
        )


def _dispatch_approval_node(
    query: QueryFn,
    statement: StatementFn,
    run: dict[str, Any],
    node_run: dict[str, Any],
    actor: str,
) -> None:
    if node_run.get("approval_id"):
        return
    node_run_id = int(node_run["graph_node_run_id"])
    configuration = node_run.get("configuration") if isinstance(node_run.get("configuration"), dict) else {}
    approval_type = str(configuration.get("approval_type") or "graph_decision")
    title = str(node_run.get("node_name") or "Graph decision")
    owner = str(node_run.get("owner_agent") or "Charlie Munger")
    working_state = run.get("working_state") if isinstance(run.get("working_state"), dict) else {}
    committee_packet_id = None
    for state_value in working_state.values():
        if isinstance(state_value, dict) and state_value.get("committee_packet_id"):
            committee_packet_id = int(state_value["committee_packet_id"])
    decision_options = ["approve", "reject"]
    committee_context: dict[str, Any] = {}
    if committee_packet_id:
        packets = query(
            f"""
            SELECT id,committee_key,committee_name,packet_status,decision_options,
                   committee_recommendation,dissent_summary,conditions
            FROM agent.v_committee_packet_control
            WHERE id={committee_packet_id}
            LIMIT 1
            """
        )
        if packets:
            committee_context = packets[0]
            options = committee_context.get("decision_options")
            if isinstance(options, list) and options:
                decision_options = [str(option) for option in options]
    wait_options = [
        {"key": option, "label": option.replace("_", " ").title()}
        for option in decision_options
    ]
    question = str(
        configuration.get("decision_question") or configuration.get("question")
        or f"Approve or reject `{title}` after reviewing the linked graph evidence."
    )
    rows = statement(
        f"""
        WITH selected AS (
            SELECT id,graph_run_id FROM agent.graph_node_runs
            WHERE id={node_run_id} AND status='ready' FOR UPDATE
        ), task_insert AS (
            INSERT INTO agent.tasks (
                title,objective,owner_agent,status,priority,approval_required,
                source_kind,source_ref,output_format,evidence
            )
            SELECT {sql_literal(title)},{sql_literal(question)},{sql_literal(owner)},
                   'needs_review','high',true,'graph_approval',selected.id::TEXT,
                   'human_decision',jsonb_build_array(jsonb_build_object(
                       'source_table','agent.graph_node_runs','graph_run_id',selected.graph_run_id,
                       'graph_node_run_id',selected.id,'broker_writes_allowed',false
                   ))
            FROM selected RETURNING id
        ), approval_insert AS (
            INSERT INTO agent.approvals (
                task_id,approval_type,title,owner_agent,risk_level,status,requested_action,rationale
            )
            SELECT task.id,{sql_literal(approval_type)},{sql_literal(title)},
                   {sql_literal(owner)},'high','pending',jsonb_build_object(
                       'graph_run_id',{int(run['graph_run_id'])},'graph_node_run_id',{node_run_id},
                       'configuration',{sql_jsonb(configuration)},
                       'committee_packet_id',{committee_packet_id if committee_packet_id else 'NULL'},
                       'committee_context',{sql_jsonb(committee_context)},
                       'decision_options',{sql_jsonb(decision_options)},
                       'broker_order_allowed',false
                   ),{sql_literal(question)}
            FROM task_insert task RETURNING id,task_id
        ), inbox_insert AS (
            INSERT INTO agent.inbox_items (
                task_id,title,owner_agent,status,priority,recommended_action,evidence,target_workspace
            )
            SELECT approval.task_id,{sql_literal(title)},{sql_literal(owner)},'needs_review','high',
                   {sql_literal(question)},jsonb_build_array(jsonb_build_object(
                       'source_table','agent.approvals','approval_id',approval.id
                   )),'command'
            FROM approval_insert approval RETURNING id
        ), waiting_insert AS (
            INSERT INTO agent.waiting_on_principal (
                graph_run_id,graph_node_run_id,request_type,title,question,options,
                default_action,status,approval_id,requested_by
            )
            SELECT selected.graph_run_id,selected.id,'approval',{sql_literal(title)},
                   {sql_literal(question)},{sql_jsonb(wait_options)},
                   'reject','open',approval.id,{sql_literal(actor)}
            FROM selected JOIN approval_insert approval ON true
            RETURNING id,approval_id
        ), node_update AS (
            UPDATE agent.graph_node_runs node_run
            SET status='waiting_approval',task_id=approval.task_id,approval_id=approval.id,
                started_at=coalesce(started_at,now()),updated_at=now()
            FROM approval_insert approval WHERE node_run.id={node_run_id}
            RETURNING node_run.id,node_run.graph_run_id,node_run.approval_id
        ), run_update AS (
            UPDATE agent.graph_runs run SET run_status='waiting_approval',
                pending_decision=jsonb_build_object(
                    'graph_node_run_id',{node_run_id},'approval_id',node_update.approval_id,
                    'title',{sql_literal(title)}
                ),updated_at=now()
            FROM node_update WHERE run.id=node_update.graph_run_id RETURNING run.id
        ), event_insert AS (
            INSERT INTO agent.graph_events (
                graph_run_id,graph_node_run_id,event_type,severity,actor,event_payload
            )
            SELECT node_update.graph_run_id,node_update.id,'approval_requested','risk',
                   {sql_literal(actor)},jsonb_build_object('approval_id',node_update.approval_id)
            FROM node_update RETURNING id
        )
        SELECT jsonb_build_array(jsonb_build_object(
            'approval_id',node_update.approval_id,'waiting',true
        ))::TEXT FROM node_update
        """
    )
    if not rows:
        raise RuntimeError(f"approval node could not be dispatched: {node_run_id}")



def _source_qualified_worker_validation(
    run: dict[str, Any],
    worker: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Reject transport receipts that do not carry case-scoped, cited research evidence."""
    input_payload = run.get("input_payload") if isinstance(run.get("input_payload"), dict) else {}
    expected_case_id = int(input_payload.get("research_case_id") or 0)
    expected_company_id = int(input_payload.get("company_id") or 0)
    expected_ticker = str(input_payload.get("ticker") or "").strip().upper()
    evidence = worker.get("evidence") if isinstance(worker.get("evidence"), list) else []
    reasons: list[str] = []
    qualified = []
    for item in evidence:
        if not isinstance(item, dict):
            continue
        item_case_id = int(item.get("research_case_id") or 0)
        item_company_id = int(item.get("company_id") or 0)
        item_ticker = str(item.get("ticker") or item.get("symbol") or "").strip().upper()
        case_match = bool(expected_case_id and item_case_id == expected_case_id)
        company_match = bool(expected_company_id and item_company_id == expected_company_id)
        ticker_match = bool(expected_ticker and item_ticker == expected_ticker)
        identity_match = case_match and (not expected_company_id or company_match) and (not expected_ticker or not item_ticker or ticker_match)
        has_source = bool(item.get("source_url") or item.get("local_artifact_path") or item.get("source_identifier"))
        has_locator = bool(item.get("citation_locator") or item.get("source_locator"))
        validation_status = str(item.get("validation_status") or "").lower()
        validated = validation_status in {"machine_validated", "human_validated", "validated", "human_reviewed"}
        if identity_match and has_source and has_locator and validated:
            qualified.append(item)
    note_path = str(worker.get("output_note_path") or "")
    ssd_backed_path = note_path.startswith("/Volumes/Devarsh SSD/") or note_path.startswith("ai memory/")
    if not ssd_backed_path:
        reasons.append("artifact is not stored under the external-SSD vault")
    if not qualified:
        reasons.append("no company-scoped cited evidence passed case, source, locator and validation checks")
    if not str(worker.get("output_summary") or "").strip():
        reasons.append("research artifact summary is empty")
    return not reasons, reasons

def _sync_external_nodes(
    query: QueryFn,
    statement: StatementFn,
    run: dict[str, Any],
    actor: str,
) -> bool:
    progressed = False
    for node_run in _fetch_node_runs(query, int(run["graph_run_id"])):
        status = str(node_run.get("status") or "")
        if status == "waiting_approval" and node_run.get("approval_id"):
            requested_action = (
                node_run.get("approval_requested_action")
                if isinstance(node_run.get("approval_requested_action"), dict)
                else {}
            )
            approval_status = str(node_run.get("approval_status") or "").lower()
            if approval_status == "approved":
                statement(
                    f"""
                    WITH updated AS (
                        UPDATE agent.waiting_on_principal SET status='approved',resolved_by={sql_literal(actor)},
                            resolved_at=now(),resolution=jsonb_build_object('approval_status','approved'),updated_at=now()
                        WHERE graph_node_run_id={int(node_run['graph_node_run_id'])} AND status='open'
                        RETURNING id
                    )
                    SELECT jsonb_build_array(jsonb_build_object('resolved',count(*)))::TEXT FROM updated
                    """
                )
                _complete_node(query, statement, run, node_run, actor, {
                    "decision": requested_action.get("selected_decision") or "approved",
                    "approval_id": node_run.get("approval_id"),
                    "committee_packet_id": requested_action.get("committee_packet_id"),
                    "rationale": requested_action.get("decision_rationale"),
                })
                progressed = True
            elif approval_status in {"rejected", "cancelled", "denied"}:
                _fail_node(statement, int(run["graph_run_id"]), node_run, actor, {
                    "kind": "approval_rejected", "approval_id": node_run.get("approval_id"), "status": approval_status,
                })
                progressed = True
        elif status in {"queued", "running"} and node_run.get("node_type") == "committee":
            packet_status = str(node_run.get("committee_packet_status") or "").lower()
            if packet_status in {"awaiting_human", "closed"}:
                output = {
                    "committee_packet_id": node_run.get("committee_packet_id"),
                    "packet_status": packet_status,
                    "session_status": node_run.get("committee_session_status"),
                    "committee_recommendation": node_run.get("committee_recommendation"),
                    "human_final_decision": node_run.get("human_final_decision"),
                    "decision_options": node_run.get("committee_decision_options") or [],
                    "sealed_positions": True,
                }
                evidence = [{
                    "source_table": "agent.committee_packets",
                    "id": node_run.get("committee_packet_id"),
                    "committee_recommendation": node_run.get("committee_recommendation"),
                }]
                _complete_node(query, statement, run, node_run, actor, output, evidence)
                progressed = True
            elif packet_status == "cancelled":
                _fail_node(statement, int(run["graph_run_id"]), node_run, actor, {
                    "kind": "committee_cancelled",
                    "committee_packet_id": node_run.get("committee_packet_id"),
                })
                progressed = True
        elif status in {"queued", "running", "waiting_approval"} and node_run.get("task_id"):
            task_status = str(node_run.get("task_status") or "").lower()
            if task_status == "in_progress" and status != "running":
                statement(
                    f"""
                    WITH updated AS (
                        UPDATE agent.graph_node_runs SET status='running',updated_at=now()
                        WHERE id={int(node_run['graph_node_run_id'])} AND status='queued' RETURNING id
                    ) SELECT jsonb_build_array(jsonb_build_object('running',EXISTS(SELECT 1 FROM updated)))::TEXT
                    """
                )
                progressed = True
            elif task_status == "completed":
                worker_rows = query(
                    f"""
                    SELECT id,status,output_summary,output_note_path,evidence,finished_at
                    FROM agent.worker_runs WHERE task_id={int(node_run['task_id'])}
                    ORDER BY created_at DESC,id DESC LIMIT 1
                    """
                )
                worker = worker_rows[0] if worker_rows else {}
                if worker.get("id"):
                    statement(
                        f"""
                        WITH updated AS (
                            UPDATE agent.graph_node_runs SET worker_run_id={int(worker['id'])},updated_at=now()
                            WHERE id={int(node_run['graph_node_run_id'])} RETURNING id
                        ) SELECT jsonb_build_array(jsonb_build_object('updated',EXISTS(SELECT 1 FROM updated)))::TEXT
                        """
                    )
                output = {
                    "task_id": node_run.get("task_id"),
                    "task_status": task_status,
                    "worker_run_id": worker.get("id"),
                    "summary": worker.get("output_summary"),
                    "output_note_path": worker.get("output_note_path") or node_run.get("output_note_path"),
                }
                evidence = worker.get("evidence") if isinstance(worker.get("evidence"), list) else []
                configuration = node_run.get("configuration") if isinstance(node_run.get("configuration"), dict) else {}
                source_qualification_required = (
                    configuration.get("source_qualified_worker_required") is True
                    or str(run.get("graph_key") or "") == "company_research_case"
                )
                if source_qualification_required:
                    valid, reasons = _source_qualified_worker_validation(run, worker)
                    if not valid:
                        statement(
                            f"""
                            WITH task_update AS (
                                UPDATE agent.tasks SET status='needs_review',approval_required=true,updated_at=now()
                                WHERE id={int(node_run['task_id'])} RETURNING id
                            ), inbox_update AS (
                                UPDATE agent.inbox_items SET status='needs_review',
                                    recommended_action='Source validation blocked. Assign a source-qualified worker; generic task receipts do not satisfy this research lane.',
                                    updated_at=now()
                                WHERE task_id={int(node_run['task_id'])} RETURNING id
                            ), node_update AS (
                                UPDATE agent.graph_node_runs SET status='waiting_approval',
                                    worker_run_id={int(worker['id']) if worker.get('id') else 'NULL'},
                                    error=jsonb_build_object('kind','source_validation_blocked','reasons',{sql_jsonb(reasons)}),
                                    updated_at=now()
                                WHERE id={int(node_run['graph_node_run_id'])} RETURNING id,graph_run_id
                            ), graph_event AS (
                                INSERT INTO agent.graph_events (
                                    graph_run_id,graph_node_run_id,event_type,severity,actor,event_payload
                                ) SELECT graph_run_id,id,'source_validation_blocked','warning',{sql_literal(actor)},
                                         jsonb_build_object('task_id',{int(node_run['task_id'])},'reasons',{sql_jsonb(reasons)})
                                FROM node_update RETURNING id
                            )
                            SELECT jsonb_build_array(jsonb_build_object(
                                'blocked',EXISTS(SELECT 1 FROM node_update)
                            ))::TEXT
                            """
                        )
                        if str(run.get("graph_key") or "") == "company_research_case":
                            research_case_id = int((run.get("input_payload") or {}).get("research_case_id") or 0)
                            if research_case_id:
                                statement(
                                    f"""
                                    WITH agent_update AS (
                                        UPDATE research.research_case_agent_runs
                                        SET status='needs_validation',
                                            exceptions=jsonb_build_array(jsonb_build_object(
                                                'kind','source_validation_blocked',
                                                'summary','Generic task completion did not provide company-scoped, cited, validated research evidence.',
                                                'reasons',{sql_jsonb(reasons)},
                                                'task_id',{int(node_run['task_id'])},
                                                'worker_run_id',{int(worker['id']) if worker.get('id') else 'NULL'}
                                            )),updated_at=now()
                                        WHERE research_case_id={research_case_id}
                                          AND graph_node_run_id={int(node_run['graph_node_run_id'])}
                                        RETURNING id
                                    ), case_update AS (
                                        UPDATE research.research_cases SET status='blocked',
                                            exception_count=(
                                                SELECT count(*) FROM research.research_case_agent_runs
                                                WHERE research_case_id={research_case_id}
                                                  AND jsonb_array_length(exceptions)>0
                                            ),updated_at=now()
                                        WHERE id={research_case_id} RETURNING id
                                    ), case_event AS (
                                        INSERT INTO research.research_case_events (
                                            research_case_id,event_type,event_status,event_summary,actor,event_payload
                                        ) SELECT {research_case_id},'source_validation_blocked','blocked',
                                                 'A specialist lane produced a transport receipt without case-qualified cited evidence.',
                                                 {sql_literal(actor)},jsonb_build_object(
                                                     'graph_run_id',{int(run['graph_run_id'])},
                                                     'graph_node_run_id',{int(node_run['graph_node_run_id'])},
                                                     'task_id',{int(node_run['task_id'])},
                                                     'reasons',{sql_jsonb(reasons)}
                                                 )
                                        WHERE EXISTS (SELECT 1 FROM agent_update)
                                        RETURNING id
                                    )
                                    SELECT jsonb_build_array(jsonb_build_object(
                                        'case_blocked',EXISTS(SELECT 1 FROM case_update)
                                    ))::TEXT
                                    """
                                )
                        progressed = True
                        continue
                _complete_node(query, statement, run, node_run, actor, output, evidence)
                progressed = True
            elif task_status in {"blocked", "failed", "cancelled"}:
                _fail_node(statement, int(run["graph_run_id"]), node_run, actor, {
                    "kind": "worker_task_failed", "task_id": node_run.get("task_id"), "task_status": task_status,
                })
                progressed = True
    return progressed


def _create_checkpoint(statement: StatementFn, run: dict[str, Any], node_run: dict[str, Any], actor: str) -> dict[str, Any]:
    configuration = node_run.get("configuration") if isinstance(node_run.get("configuration"), dict) else {}
    rows = statement(
        f"""
        WITH inserted AS (
            INSERT INTO agent.graph_checkpoints (
                graph_run_id,graph_node_run_id,checkpoint_kind,state_snapshot,
                evidence_snapshot,created_by
            ) VALUES (
                {int(run['graph_run_id'])},{int(node_run['graph_node_run_id'])},
                {sql_literal(str(configuration.get('checkpoint_kind') or 'durable'))},
                jsonb_build_object('working_state',{sql_jsonb(run.get('working_state') or {})},
                                   'input_payload',{sql_jsonb(run.get('input_payload') or {})},
                                   'captured_at',now()),'[]'::jsonb,{sql_literal(actor)}
            ) RETURNING id,resume_token,checkpoint_kind,created_at
        ) SELECT jsonb_build_array(row_to_json(inserted))::TEXT FROM inserted
        """
    )
    return _one(rows, "checkpoint could not be created")


def _finalize_if_complete(query: QueryFn, statement: StatementFn, run_id: int, actor: str) -> None:
    state = _fetch_run(query, run_id)
    nodes = _fetch_node_runs(query, run_id)
    if any(str(node.get("status")) == "failed" for node in nodes):
        statement(
            f"""
            WITH updated AS (
                UPDATE agent.graph_runs SET run_status='failed',finished_at=coalesce(finished_at,now()),updated_at=now()
                WHERE id={run_id} AND run_status NOT IN ('failed','cancelled','completed') RETURNING id
            ) SELECT jsonb_build_array(jsonb_build_object('failed',EXISTS(SELECT 1 FROM updated)))::TEXT
            """
        )
        return
    end_completed = any(node.get("node_type") == "end" and node.get("status") == "completed" for node in nodes)
    active = any(str(node.get("status")) in ACTIVE_NODE_STATES for node in nodes)
    blocked = any(str(node.get("status")) == "blocked" for node in nodes)
    if end_completed and not active and not blocked:
        statement(
            f"""
            WITH updated AS (
                UPDATE agent.graph_runs SET run_status='completed',finished_at=now(),
                    pending_decision='{{}}'::jsonb,updated_at=now()
                WHERE id={run_id} AND run_status NOT IN ('completed','failed','cancelled')
                RETURNING id,output_payload
            ), event_insert AS (
                INSERT INTO agent.graph_events (
                    graph_run_id,event_type,severity,actor,event_payload
                ) SELECT id,'graph_completed','info',{sql_literal(actor)},
                         jsonb_build_object('output_payload',output_payload)
                FROM updated RETURNING id
            ) SELECT jsonb_build_array(jsonb_build_object('completed',EXISTS(SELECT 1 FROM updated)))::TEXT
            """
        )
    elif not active and not blocked and state.get("run_status") == "running":
        statement(
            f"""
            WITH updated AS (
                UPDATE agent.graph_runs SET run_status='failed',finished_at=now(),
                    failure=jsonb_build_object('kind','stalled_graph','message','No runnable nodes and no completed end node.'),
                    updated_at=now() WHERE id={run_id} RETURNING id
            ) SELECT jsonb_build_array(jsonb_build_object('failed',EXISTS(SELECT 1 FROM updated)))::TEXT
            """
        )


def advance_graph_run(query: QueryFn, statement: StatementFn, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        run_id = int(payload.get("graph_run_id") or payload.get("graphRunId") or payload.get("run_id") or payload.get("id"))
    except (TypeError, ValueError) as exc:
        raise ValueError("graph_run_id is required and must be an integer") from exc
    actor = str(payload.get("actor") or "Jarvis").strip() or "Jarvis"
    max_steps = bounded_int(payload.get("max_steps") or payload.get("maxSteps"), default=20, minimum=1, maximum=100)
    processed = 0

    for _ in range(max_steps):
        run = _fetch_run(query, run_id)
        if str(run.get("run_status")) in TERMINAL_RUN_STATES or str(run.get("run_status")) == "paused":
            break
        progressed = _sync_external_nodes(query, statement, run, actor)
        run = _fetch_run(query, run_id)
        if str(run.get("run_status")) in TERMINAL_RUN_STATES or str(run.get("run_status")) in {"paused", "waiting_approval", "waiting_input"}:
            if not progressed:
                break
        ready_nodes = [node for node in _fetch_node_runs(query, run_id) if node.get("status") == "ready"]
        if not ready_nodes:
            if progressed:
                processed += 1
                continue
            break
        node_run = ready_nodes[0]
        decision = _record_autonomy_decision(query, statement, run, node_run, actor)
        if decision == "deny":
            _fail_node(statement, run_id, node_run, actor, {
                "kind": "autonomy_denied", "node_key": node_run.get("node_key"),
            })
            processed += 1
            continue
        node_type = str(node_run.get("node_type") or "")
        if node_type in {"start", "join", "router"}:
            _complete_node(query, statement, run, node_run, actor, {"status": "completed"})
        elif node_type == "checkpoint":
            checkpoint = _create_checkpoint(statement, run, node_run, actor)
            _complete_node(query, statement, run, node_run, actor, {"checkpoint": checkpoint})
        elif node_type == "end":
            _complete_node(query, statement, run, node_run, actor, {"status": "complete"})
            _finalize_if_complete(query, statement, run_id, actor)
        elif node_type == "approval_gate":
            _dispatch_approval_node(query, statement, run, node_run, actor)
        elif node_type == "committee":
            _dispatch_committee_node(statement, run, node_run, actor)
        elif node_type in {"agent_task", "tool_task"}:
            _dispatch_task_node(query, statement, run, node_run, actor)
        else:
            _fail_node(statement, run_id, node_run, actor, {
                "kind": "unsupported_node_type", "node_type": node_type,
            })
        processed += 1

    _finalize_if_complete(query, statement, run_id, actor)
    result = _fetch_run(query, run_id)
    result["processed_steps"] = processed
    result["attention"] = query(
        f"SELECT * FROM agent.v_graph_attention_queue WHERE graph_run_id={run_id} ORDER BY created_at DESC"
    )
    return result


def pause_graph_run(query: QueryFn, statement: StatementFn, payload: dict[str, Any]) -> dict[str, Any]:
    run_id = bounded_int(payload.get("graph_run_id") or payload.get("run_id") or payload.get("id"), default=0, minimum=1, maximum=2_147_483_647)
    actor = str(payload.get("actor") or "Devarsh").strip()
    reason = str(payload.get("reason") or "Paused by operator").strip()
    rows = statement(
        f"""
        WITH updated AS (
            UPDATE agent.graph_runs SET run_status='paused',
                pending_decision=jsonb_build_object('pause_reason',{sql_literal(reason)},'paused_by',{sql_literal(actor)}),
                updated_at=now()
            WHERE id={run_id} AND run_status NOT IN ('completed','failed','cancelled') RETURNING id
        ), event_insert AS (
            INSERT INTO agent.graph_events (graph_run_id,event_type,severity,actor,event_payload)
            SELECT id,'graph_paused','warning',{sql_literal(actor)},jsonb_build_object('reason',{sql_literal(reason)})
            FROM updated RETURNING id
        ) SELECT jsonb_build_array(jsonb_build_object('paused',EXISTS(SELECT 1 FROM updated)))::TEXT
        """
    )
    if not rows or not rows[0].get("paused"):
        raise ValueError("graph run cannot be paused")
    return _fetch_run(query, run_id)


def resume_graph_run(query: QueryFn, statement: StatementFn, payload: dict[str, Any]) -> dict[str, Any]:
    run_id = bounded_int(payload.get("graph_run_id") or payload.get("run_id") or payload.get("id"), default=0, minimum=1, maximum=2_147_483_647)
    actor = str(payload.get("actor") or "Devarsh").strip()
    rows = statement(
        f"""
        WITH blockers AS (
            SELECT count(*)::INTEGER AS count FROM agent.waiting_on_principal
            WHERE graph_run_id={run_id} AND status='open'
        ), updated AS (
            UPDATE agent.graph_runs SET run_status='running',pending_decision='{{}}'::jsonb,updated_at=now()
            WHERE id={run_id} AND run_status='paused'
              AND (SELECT count FROM blockers)=0 RETURNING id
        ), node_update AS (
            UPDATE agent.graph_node_runs node_run SET status='ready',updated_at=now()
            FROM updated WHERE node_run.graph_run_id=updated.id AND node_run.status='waiting_input'
            RETURNING node_run.id
        ), event_insert AS (
            INSERT INTO agent.graph_events (graph_run_id,event_type,severity,actor,event_payload)
            SELECT id,'graph_resumed','info',{sql_literal(actor)},'{{}}'::jsonb FROM updated RETURNING id
        ) SELECT jsonb_build_array(jsonb_build_object(
            'resumed',EXISTS(SELECT 1 FROM updated),'open_blockers',(SELECT count FROM blockers)
        ))::TEXT
        """
    )
    if not rows or not rows[0].get("resumed"):
        blockers = (rows[0] if rows else {}).get("open_blockers")
        raise ValueError(f"graph run cannot resume; open blockers: {blockers or 0}")
    return advance_graph_run(query, statement, {"graph_run_id": run_id, "actor": actor})


def cancel_graph_run(query: QueryFn, statement: StatementFn, payload: dict[str, Any]) -> dict[str, Any]:
    run_id = bounded_int(payload.get("graph_run_id") or payload.get("run_id") or payload.get("id"), default=0, minimum=1, maximum=2_147_483_647)
    actor = str(payload.get("actor") or "Devarsh").strip()
    reason = str(payload.get("reason") or "Cancelled by operator").strip()
    rows = statement(
        f"""
        WITH updated AS (
            UPDATE agent.graph_runs SET run_status='cancelled',finished_at=now(),
                failure=jsonb_build_object('kind','operator_cancelled','reason',{sql_literal(reason)}),updated_at=now()
            WHERE id={run_id} AND run_status NOT IN ('completed','failed','cancelled') RETURNING id
        ), approval_update AS (
            UPDATE agent.approvals approval SET status='cancelled',decided_by={sql_literal(actor)},
                decided_at=now(),rationale=concat_ws(E'\n',nullif(approval.rationale,''),
                    'Cancelled with graph run: ' || {sql_literal(reason)})
            FROM agent.graph_node_runs node_run, updated
            WHERE node_run.graph_run_id=updated.id
              AND node_run.approval_id=approval.id
              AND approval.status='pending'
            RETURNING approval.id
        ), node_update AS (
            UPDATE agent.graph_node_runs node_run SET status='cancelled',finished_at=now(),updated_at=now()
            FROM updated WHERE node_run.graph_run_id=updated.id
              AND node_run.status NOT IN ('completed','failed','cancelled','skipped') RETURNING node_run.id
        ), waiting_update AS (
            UPDATE agent.waiting_on_principal wait SET status='cancelled',resolved_by={sql_literal(actor)},
                resolved_at=now(),resolution=jsonb_build_object('reason',{sql_literal(reason)}),updated_at=now()
            FROM updated WHERE wait.graph_run_id=updated.id AND wait.status='open' RETURNING wait.id
        ), event_insert AS (
            INSERT INTO agent.graph_events (graph_run_id,event_type,severity,actor,event_payload)
            SELECT id,'graph_cancelled','warning',{sql_literal(actor)},jsonb_build_object('reason',{sql_literal(reason)})
            FROM updated RETURNING id
        ) SELECT jsonb_build_array(jsonb_build_object('cancelled',EXISTS(SELECT 1 FROM updated)))::TEXT
        """
    )
    if not rows or not rows[0].get("cancelled"):
        raise ValueError("graph run cannot be cancelled")
    return _fetch_run(query, run_id)


def resolve_principal_wait(query: QueryFn, statement: StatementFn, payload: dict[str, Any]) -> dict[str, Any]:
    wait_id = bounded_int(payload.get("wait_id") or payload.get("waitId") or payload.get("id"), default=0, minimum=1, maximum=2_147_483_647)
    actor = str(payload.get("actor") or "Devarsh").strip()
    resolution = payload.get("resolution") or {}
    if not isinstance(resolution, dict):
        raise ValueError("resolution must be an object")
    wait = _one(query(f"SELECT * FROM agent.waiting_on_principal WHERE id={wait_id} LIMIT 1"), "principal wait not found")
    if wait.get("status") != "open":
        return wait
    if wait.get("request_type") == "approval":
        raise ValueError("approval waits must be resolved through the approval decision endpoint")
    rows = statement(
        f"""
        WITH updated AS (
            UPDATE agent.waiting_on_principal SET status='answered',resolved_by={sql_literal(actor)},
                resolved_at=now(),resolution={sql_jsonb(resolution)},updated_at=now()
            WHERE id={wait_id} AND status='open' RETURNING graph_run_id,graph_node_run_id
        ), run_update AS (
            UPDATE agent.graph_runs run SET run_status='running',
                working_state=working_state || jsonb_build_object('principal_resolution',{sql_jsonb(resolution)}),
                pending_decision='{{}}'::jsonb,updated_at=now()
            FROM updated WHERE run.id=updated.graph_run_id RETURNING run.id
        ), node_update AS (
            UPDATE agent.graph_node_runs node_run SET status='ready',
                input_payload=input_payload || jsonb_build_object('principal_resolution',{sql_jsonb(resolution)}),updated_at=now()
            FROM updated WHERE node_run.id=updated.graph_node_run_id AND node_run.status='waiting_input'
            RETURNING node_run.id
        ) SELECT jsonb_build_array(jsonb_build_object('resolved',EXISTS(SELECT 1 FROM updated),
                    'graph_run_id',(SELECT graph_run_id FROM updated)))::TEXT
        """
    )
    if not rows or not rows[0].get("resolved"):
        raise ValueError("principal wait could not be resolved")
    return advance_graph_run(query, statement, {"graph_run_id": rows[0]["graph_run_id"], "actor": actor})


def request_graph_change(query: QueryFn, statement: StatementFn, payload: dict[str, Any]) -> dict[str, Any]:
    graph_key = str(payload.get("graph_key") or payload.get("graphKey") or "").strip()
    title = str(payload.get("title") or "").strip()
    rationale = str(payload.get("rationale") or "").strip()
    actor = str(payload.get("actor") or payload.get("requested_by") or "Charlie Munger").strip()
    proposed_patch = payload.get("proposed_patch") or payload.get("proposedPatch") or {}
    safety_impact = payload.get("safety_impact") or payload.get("safetyImpact") or {}
    if not graph_key or not title or not rationale:
        raise ValueError("graph_key, title, and rationale are required")
    if not isinstance(proposed_patch, dict) or not isinstance(safety_impact, dict):
        raise ValueError("proposed_patch and safety_impact must be objects")
    _one(query(f"SELECT graph_key FROM agent.graph_definitions WHERE graph_key={sql_literal(graph_key)}"), "graph not found")
    rows = statement(
        f"""
        WITH base AS (
            SELECT version.id FROM agent.graph_definitions definition
            JOIN agent.graph_versions version
              ON version.graph_key=definition.graph_key AND version.version=definition.active_version
            WHERE definition.graph_key={sql_literal(graph_key)} LIMIT 1
        ), task_insert AS (
            INSERT INTO agent.tasks (
                title,objective,owner_agent,status,priority,approval_required,
                source_kind,source_ref,output_format,evidence
            ) VALUES (
                {sql_literal(title)},{sql_literal(rationale)},'CTO Agent','needs_review','high',true,
                'graph_change',{sql_literal(graph_key)},'graph_change_review',
                jsonb_build_array(jsonb_build_object('graph_key',{sql_literal(graph_key)},
                                                     'proposed_patch',{sql_jsonb(proposed_patch)},
                                                     'safety_impact',{sql_jsonb(safety_impact)}))
            ) RETURNING id
        ), approval_insert AS (
            INSERT INTO agent.approvals (
                task_id,approval_type,title,owner_agent,risk_level,status,requested_action,rationale
            ) SELECT task.id,'graph_change',{sql_literal(title)},'CTO Agent','high','pending',
                     jsonb_build_object('graph_key',{sql_literal(graph_key)},
                                        'proposed_patch',{sql_jsonb(proposed_patch)},
                                        'safety_impact',{sql_jsonb(safety_impact)},
                                        'direct_activation_allowed',false),{sql_literal(rationale)}
              FROM task_insert task RETURNING id,task_id
        ), request_insert AS (
            INSERT INTO agent.graph_change_requests (
                graph_key,base_version_id,requested_by,title,rationale,proposed_patch,
                safety_impact,status,approval_id
            ) SELECT {sql_literal(graph_key)},base.id,{sql_literal(actor)},{sql_literal(title)},
                     {sql_literal(rationale)},{sql_jsonb(proposed_patch)},{sql_jsonb(safety_impact)},
                     'pending',approval.id
              FROM base JOIN approval_insert approval ON true
            RETURNING *
        ) SELECT jsonb_build_array(row_to_json(request_insert))::TEXT FROM request_insert
        """
    )
    return _one(rows, "graph change request could not be created")


def record_correction(query: QueryFn, statement: StatementFn, payload: dict[str, Any]) -> dict[str, Any]:
    source_kind = str(payload.get("source_kind") or payload.get("sourceKind") or "operator_observation").strip()
    source_ref = str(payload.get("source_ref") or payload.get("sourceRef") or "").strip()
    correction_type = str(payload.get("correction_type") or payload.get("correctionType") or "outcome_mismatch").strip()
    corrective_action = str(payload.get("corrective_action") or payload.get("correctiveAction") or "").strip()
    owner = str(payload.get("owner_agent") or payload.get("ownerAgent") or "Model Risk Agent").strip()
    actor = str(payload.get("actor") or "Devarsh").strip()
    severity = str(payload.get("severity") or "medium").lower()
    if severity not in {"low", "medium", "high", "critical"}:
        raise ValueError("severity must be low, medium, high, or critical")
    if not corrective_action:
        raise ValueError("corrective_action is required")
    graph_run_id = payload.get("graph_run_id") or payload.get("graphRunId")
    graph_node_run_id = payload.get("graph_node_run_id") or payload.get("graphNodeRunId")
    run_sql = str(int(graph_run_id)) if graph_run_id not in (None, "") else "NULL"
    node_sql = str(int(graph_node_run_id)) if graph_node_run_id not in (None, "") else "NULL"
    expected = payload.get("expected_state") or payload.get("expectedState") or {}
    observed = payload.get("observed_state") or payload.get("observedState") or {}
    prevention = payload.get("prevention_change") or payload.get("preventionChange") or {}
    root_cause = str(payload.get("root_cause") or payload.get("rootCause") or "").strip()
    rows = statement(
        f"""
        WITH task_insert AS (
            INSERT INTO agent.tasks (
                title,objective,owner_agent,status,priority,approval_required,
                source_kind,source_ref,output_format,evidence
            ) VALUES (
                'Correction review: ' || {sql_literal(correction_type)},
                {sql_literal(corrective_action)},{sql_literal(owner)},'queued',
                {sql_literal('high' if severity in {'high','critical'} else 'medium')},false,
                'graph_correction',nullif({sql_literal(source_ref)},''),'correction_review',
                jsonb_build_array(jsonb_build_object('expected_state',{sql_jsonb(expected)},
                                                     'observed_state',{sql_jsonb(observed)},
                                                     'recorded_by',{sql_literal(actor)}))
            ) RETURNING id
        ), correction_insert AS (
            INSERT INTO agent.correction_ledger (
                source_kind,source_ref,graph_run_id,graph_node_run_id,correction_type,
                severity,expected_state,observed_state,root_cause,corrective_action,
                prevention_change,status,owner_agent,task_id
            ) SELECT {sql_literal(source_kind)},nullif({sql_literal(source_ref)},''),
                     {run_sql},{node_sql},{sql_literal(correction_type)},{sql_literal(severity)},
                     {sql_jsonb(expected)},{sql_jsonb(observed)},nullif({sql_literal(root_cause)},''),
                     {sql_literal(corrective_action)},{sql_jsonb(prevention)},'open',
                     {sql_literal(owner)},task.id
              FROM task_insert task RETURNING *
        ) SELECT jsonb_build_array(row_to_json(correction_insert))::TEXT FROM correction_insert
        """
    )
    return _one(rows, "correction could not be recorded")


def idempotency_key(graph_key: str, subject_ref: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{graph_key}|{subject_ref}|{canonical}".encode("utf-8")).hexdigest()
