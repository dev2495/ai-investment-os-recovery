import React from "react";
import { AlertTriangle, CheckCircle2, ExternalLink, FileUp, Play, Search, ShieldCheck } from "lucide-react";
import type { LiveRow } from "../../data/liveRow";
import { num, text } from "../../data/liveRow";
import { API_BASE_URL, post, uploadFile } from "../../data/client";
import { useApproveResearchModelPreflight, useProposeResearchCase, useStartResearchCase } from "../../data/actions";
import { Badge, Button } from "../../system/primitives";

function object(raw: unknown): LiveRow {
  return raw && typeof raw === "object" && !Array.isArray(raw) ? raw as LiveRow : {};
}

function list(raw: unknown): LiveRow[] {
  return Array.isArray(raw) ? raw.filter((row): row is LiveRow => Boolean(row && typeof row === "object")) : [];
}

function extractEntity(raw: string): string {
  const value = raw.trim().replace(/[“”"]/g, "");
  const match = value.match(/^(?:please\s+)?(?:(?:start|begin|launch|do)\s+)?(?:a\s+)?(?:long[- ]term\s+)?(?:company\s+)?research\s+(?:on|for|about)\s+(.+)$/i);
  return (match?.[1] || value).trim().replace(/[.?!]+$/, "");
}

function humanStatus(value: string): string {
  return value.replace(/_/g, " ");
}

export function ResearchCaseWorkspace({ selected, cases, agents, workItems, evidence, events, preflights = [], modelRuns = [], onRefresh }: {
  selected: LiveRow;
  cases: LiveRow[];
  agents: LiveRow[];
  workItems: LiveRow[];
  evidence: LiveRow[];
  events: LiveRow[];
  preflights?: LiveRow[];
  modelRuns?: LiveRow[];
  onRefresh: () => void;
}) {
  const propose = useProposeResearchCase();
  const start = useStartResearchCase();
  const approvePreflight = useApproveResearchModelPreflight();
  const [confirmed, setConfirmed] = React.useState(false);
  const [distinctConfirmed, setDistinctConfirmed] = React.useState(false);
  const [mandateCustom, setMandateCustom] = React.useState(false);
  const [resolvedCompanyId, setResolvedCompanyId] = React.useState<number | null>(null);
  const [notice, setNotice] = React.useState("");
  const [uploading, setUploading] = React.useState(false);
  const [uploadState, setUploadState] = React.useState("");
  const [form, setForm] = React.useState({ entity: "", priority: "medium", horizon: "3-5 years", mandate: "" });

  React.useEffect(() => {
    setConfirmed(false);
    setDistinctConfirmed(false);
    setMandateCustom(false);
    setResolvedCompanyId(null);
    setNotice("");
    setForm({ entity: "", priority: "medium", horizon: "3-5 years", mandate: "" });
    propose.reset();
  }, [selected]);

  const proposal = object(propose.data);
  const proposalMatches = list(proposal.matches);
  const mutationCase = object(proposal.research_case);
  const conflict = ["blocked_conflict", "open_case_conflict"].includes(text(proposal, "status"));
  const activeCase = mutationCase.id ? mutationCase : {};
  const caseId = num(activeCase, "id", 0);
  const caseAgents = agents.filter((row) => num(row, "research_case_id") === caseId);
  const caseWorkItems = workItems.filter((row) => num(row, "research_case_id") === caseId);
  const caseEvidence = evidence.filter((row) => num(row, "research_case_id") === caseId);
  const caseEvents = events.filter((row) => num(row, "research_case_id") === caseId);
  const proposalPreflight = object(proposal.model_preflight);
  const casePreflight = proposalPreflight.id
    ? proposalPreflight
    : preflights.filter((row) => num(row, "research_case_id") === caseId).sort((a, b) => num(b, "id") - num(a, "id"))[0] || {};
  const preflightId = num(casePreflight, "id");
  const estimatedUsd = num(casePreflight, "estimated_cost_usd");
  const hardMaxUsd = num(casePreflight, "hard_max_cost_usd");
  const exchangeRate = num(casePreflight, "exchange_rate_inr_per_usd", 87);
  const caseModelRuns = modelRuns.filter((row) => num(row, "research_case_id") === caseId);
  const caseStatus = text(activeCase, "status");
  const started = ["active", "collecting", "review", "blocked", "completed"].includes(caseStatus);
  const blocked = caseStatus === "blocked";
  const invalidLanes = caseAgents.filter((row) => ["needs_validation", "blocked"].includes(text(row, "status")));
  const workPlan = list(activeCase.work_plan);
  const sourcePlan = list(activeCase.source_plan);
  const displayedPlan = (workPlan.length ? workPlan : caseAgents).map((row) => {
    const durable = caseAgents.find((agent) => text(agent, "role_key") === text(row, "role_key"));
    return durable ? { ...row, ...durable } : row;
  });

  const roleNames: Record<string, string> = {
    company_business: "Business and company",
    filings: "Official filings",
    financials: "Financial statements",
    management: "Management and governance",
    industry_moat: "Industry and moat",
    valuation: "Valuation",
    bear_risk: "Bear case and risks",
    lead_synthesis: "Lead analyst synthesis",
    executive_summary: "Executive investment summary",
    independent_review: "Independent challenge",
    committee_review: "Committee decision brief",
  };

  function approveAndStart() {
    if (!caseId || !preflightId) return;
    const startNow = () => start.mutate({
      research_case_id: caseId,
      model_preflight_id: preflightId,
      operator_confirmed: true,
      actor: "Devarsh",
    }, {
      onSuccess: (data) => {
        const runtime = object(object(data).autonomous_runtime);
        setNotice(`Research Case #${num(object(object(data).research_case), "id", caseId)} started. ${num(runtime, "model_run_count", 11)} public-research roles are now durable.`);
        onRefresh();
        setConfirmed(false);
      },
    });
    if (text(casePreflight, "status") === "approved") startNow();
    else approvePreflight.mutate({ preflight_id: preflightId, operator_confirmed: true, actor: "Devarsh" }, { onSuccess: startNow });
  }

  function proposeCase(createDistinct = false) {
    const entity = extractEntity(form.entity);
    const entityKey = entity.toLowerCase();
    const selectedAliases = [text(selected, "symbol"), text(selected, "legal_name"), text(selected, "company_name")]
      .map((value) => value.trim().toLowerCase()).filter(Boolean);
    const selectedCompanyId = selectedAliases.includes(entityKey) ? num(selected, "research_company_id", 0) : 0;
    const baseMandate = form.mandate.trim() || `Build a source-backed long-term investment decision brief for ${entity}.`;
    const mandate = createDistinct
      ? `${baseMandate.replace(/\s+Distinct reassessment.*$/i, "")} Distinct reassessment as of ${new Date().toISOString().slice(0, 10)}.`
      : baseMandate;
    if (createDistinct) setForm((current) => ({ ...current, mandate }));
    setNotice("");
    setConfirmed(false);
    propose.mutate({
      request_text: form.entity,
      entity,
      company_id: resolvedCompanyId || selectedCompanyId || undefined,
      priority: form.priority as "low" | "medium" | "high" | "critical",
      horizon: form.horizon,
      mandate,
      create_distinct_confirmed: createDistinct,
      actor: "Devarsh",
    }, {
      onSuccess: (data) => {
        const response = object(data);
        const responseCase = object(response.research_case);
        if (text(response, "status") === "proposed") {
          setNotice(`Research Case #${num(responseCase, "id")} created. Confirm the company, boundary and cost below, then Start.`);
        } else {
          setNotice(text(response, "detail"));
        }
      },
    });
  }

  async function upload(file: File) {
    if (!caseId) return;
    setUploading(true);
    setUploadState("");
    try {
      const result = object(await uploadFile("/api/artifacts/local/upload", file, {
        file_name: file.name,
        title: `${text(activeCase, "ticker")} research case evidence - ${file.name}`,
        sensitivity: "private",
        suggested_destination: "research.research_case_evidence",
        actor: "Devarsh via Thesis Research Case",
      }));
      const ingestion = object(result.result);
      await post("/api/research/cases/evidence/link-upload", {
        research_case_id: caseId,
        local_artifact_path: text(ingestion, "stored_path"),
        source_identifier: text(ingestion, "ingestion_key", text(ingestion, "content_hash")),
        content_hash: text(ingestion, "content_hash"),
        parser_status: text(ingestion, "status", "registered"),
        citation_locator: { file_name: file.name, raw_artifact_id: ingestion.raw_artifact_id, local_ingestion_id: ingestion.id },
        actor: "Devarsh",
        operator_confirmed: true,
      });
      setUploadState("Uploaded to immutable SSD intake and linked for review.");
      onRefresh();
    } catch (error) {
      setUploadState(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  return <section className="ltw-research-case ltw-research-case--simple" id="research-case">
    <header className="ltw-research-launch__head">
      <div>
        <span>Start a new company underwrite</span>
        <h2>What company should Charlie research?</h2>
        <p>Use a company name, ticker, or a natural-language instruction. No model cost is incurred until you review and approve the plan.</p>
      </div>
    </header>

    <form className="ltw-research-launch" onSubmit={(event) => { event.preventDefault(); proposeCase(false); }}>
      <label className="ltw-research-launch__query">
        <Search size={19} aria-hidden="true" />
        <span className="sr-only">Company, ticker, or research instruction</span>
        <input
          autoComplete="off"
          placeholder="e.g. Start long-term research on Infosys"
          required
          value={form.entity}
          onChange={(event) => {
            const entity = event.target.value;
            setResolvedCompanyId(null);
            setDistinctConfirmed(false);
            setConfirmed(false);
            setNotice("");
            propose.reset();
            setForm((current) => ({
              ...current,
              entity,
              mandate: mandateCustom ? current.mandate : "",
            }));
          }}
        />
      </label>
      <Button disabled={propose.isPending} type="submit" variant="primary">
        {propose.isPending ? "Resolving company..." : "Review research plan"}
      </Button>
      <details className="ltw-research-launch__options">
        <summary>Adjust mandate, horizon or priority</summary>
        <div>
          <label><span>Priority</span><select value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value })}><option>low</option><option>medium</option><option>high</option><option>critical</option></select></label>
          <label><span>Horizon</span><select value={form.horizon} onChange={(event) => setForm({ ...form, horizon: event.target.value })}><option>1-3 years</option><option>3-5 years</option><option>5-10 years</option></select></label>
          <label className="wide"><span>Decision question</span><textarea rows={3} value={form.mandate} placeholder={`Build a source-backed long-term investment decision brief for ${extractEntity(form.entity) || "the company"}.`} onChange={(event) => { setMandateCustom(true); setForm({ ...form, mandate: event.target.value }); }} /></label>
        </div>
      </details>
    </form>

    {propose.isError ? <div className="ltw-case-error" role="alert"><AlertTriangle size={15} />{propose.error.message}</div> : null}
    {["needs_input", "needs_confirmation"].includes(text(proposal, "status")) ? <div className="ltw-case-resolve" role="status">
      <div><strong>{proposalMatches.length ? "Confirm the exact listed company" : "Company not verified yet"}</strong><p>{text(proposal, "detail")}</p></div>
      {proposalMatches.length ? <div>{proposalMatches.map((row) => <button key={num(row, "company_id")} type="button" onClick={() => {
        const ticker = text(row, "ticker");
        const companyName = text(row, "legal_name", text(row, "company_name"));
        setResolvedCompanyId(num(row, "company_id"));
        setNotice(`Selected ${text(row, "exchange")}:${ticker} - ${companyName}. Review the decision question, then review the plan again.`);
        propose.reset();
        setForm((current) => ({ ...current, entity: ticker, mandate: mandateCustom ? current.mandate : `Build a source-backed long-term investment decision brief for ${companyName}.` }));
      }}><strong>{text(row, "exchange")}:{text(row, "ticker")}</strong><span>{text(row, "legal_name", text(row, "company_name"))}</span></button>)}</div> : null}
    </div> : null}

    {notice ? <div className="ltw-case-active" role="status"><CheckCircle2 size={17} /><div><strong>{notice}</strong></div></div> : null}

    {conflict ? <div className="ltw-case-blocked" role="alert"><AlertTriangle size={18} /><div><strong>An existing case does not block a new mandate.</strong><p>{text(proposal, "detail")}</p><div className="ltw-case-actions"><label><input type="checkbox" checked={distinctConfirmed} onChange={(event) => setDistinctConfirmed(event.target.checked)} /> This is a distinct decision mandate.</label><Button disabled={!distinctConfirmed || propose.isPending} onClick={() => proposeCase(true)} size="sm" variant="primary">Create distinct case</Button></div></div></div> : null}

    {caseId ? <section className="ltw-case-confirm" aria-label={`Research Case ${caseId} confirmation`}>
      <header>
        <div><span>Verified company</span><h3>{text(activeCase, "company_name")}</h3><p>{text(activeCase, "exchange")}:{text(activeCase, "ticker")} · Research Case #{caseId}</p></div>
        <Badge tone={blocked ? "risk" : started ? "accent" : "warn"}>{humanStatus(caseStatus)}</Badge>
      </header>
      <p className="ltw-case-confirm__mandate">{text(activeCase, "mandate")}</p>
      <div className="ltw-case-confirm__facts">
        <div><span>Expected cost</span><strong>₹{(estimatedUsd * exchangeRate).toFixed(2)} / ${estimatedUsd.toFixed(3)}</strong><small>Hard stop ₹{(hardMaxUsd * exchangeRate).toFixed(2)} / ${hardMaxUsd.toFixed(3)}</small></div>
        <div><span>Research team</span><strong>11 roles</strong><small>Lead, specialists, summary, reviewer and committee</small></div>
        <div><span>Boundary</span><strong>Public sources only</strong><small>Private evidence remains on the SSD</small></div>
      </div>

      {!started ? <div className="ltw-case-start ltw-case-start--clear">
        <label><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /><span>I confirm the company, mandate and displayed maximum cost. No broker, client, capital or external write is authorized.</span></label>
        <Button disabled={!confirmed || !preflightId || start.isPending || approvePreflight.isPending} icon={Play} onClick={approveAndStart} variant="primary">{start.isPending || approvePreflight.isPending ? "Starting research..." : "Approve cost and start research"}</Button>
      </div> : blocked ? <div className="ltw-case-blocked"><AlertTriangle size={18} /><div><strong>This case needs source repair; other cases can still start.</strong><p>{invalidLanes.length || num(activeCase, "exception_count")} workstream(s) need qualified company evidence.</p></div></div> : <div className="ltw-case-active"><CheckCircle2 size={17} /><div><strong>Autonomous research is active</strong><p>{caseModelRuns.filter((row) => text(row, "status") === "completed").length}/{caseModelRuns.length || 11} roles completed. The final brief remains subject to independent and human review.</p></div></div>}

      {start.isError || approvePreflight.isError ? <div className="ltw-case-error" role="alert"><AlertTriangle size={15} />{start.error?.message || approvePreflight.error?.message}</div> : null}

      <details className="ltw-case-operations">
        <summary>Research plan, sources and workstream details</summary>
        <div className="ltw-case-operations__body">
          <div className="ltw-case-plan"><div><h4>Company research pack</h4>{caseWorkItems.map((row) => <article key={num(row, "id")}><span>{humanStatus(text(row, "work_type"))}</span><strong>{text(row, "title")}</strong><p>{text(row, "objective")}</p><Badge tone={text(row, "status") === "completed" ? "ok" : ["blocked", "waiting_input"].includes(text(row, "status")) ? "risk" : "default"}>{humanStatus(text(row, "status"))}</Badge></article>)}</div></div>
          <div className="ltw-case-plan"><div><h4>{started ? "Agent workstreams" : "Proposed workstreams"}</h4>{displayedPlan.map((row) => <article key={text(row, "role_key")}><span>{roleNames[text(row, "role_key")] || humanStatus(text(row, "role_key"))}</span><strong>{started ? humanStatus(text(row, "status", "waiting")) : "Planned"}</strong><p>{text(row, "objective", humanStatus(text(row, "skill_key")))}</p></article>)}</div><div><h4>Authorized source order</h4>{sourcePlan.map((row) => <article key={num(row, "rank")}><span>0{num(row, "rank")}</span><strong>{humanStatus(text(row, "kind"))}</strong><small>{text(row, "authorization")}</small></article>)}</div></div>
          <div className="ltw-case-coverage"><div><span>Collected</span><strong>{caseEvidence.length}</strong></div><div><span>Parsed</span><strong>{caseEvidence.filter((row) => ["parsed", "extracted", "validated"].includes(text(row, "parser_status"))).length}</strong></div><div><span>Validated</span><strong>{caseEvidence.filter((row) => ["validated", "human_reviewed"].includes(text(row, "validation_status"))).length}</strong></div><div><span>Exceptions</span><strong>{num(activeCase, "exception_count")}</strong></div></div>
          <div className="ltw-case-upload"><FileUp size={18} /><div><strong>Add first-party evidence</strong><p>Stored immutably on the external SSD and never accepted as a current fact without review.</p><small>{uploadState}</small></div><label className="ltw-upload-button">{uploading ? "Uploading..." : "Choose evidence"}<input disabled={uploading} type="file" accept=".pdf,.docx,.txt,.md,.json,.png,.jpg,.jpeg,.webp,.csv,.xlsx" onChange={(event) => { const file = event.target.files?.[0]; if (file) void upload(file); event.target.value = ""; }} /></label></div>
          {caseEvidence.length ? <div className="ltw-case-evidence">{caseEvidence.map((row) => <article key={num(row, "id")}><div><strong>{text(row, "source_identifier")}</strong><p>{humanStatus(text(row, "source_kind"))} · published {text(row, "publication_date", "not recorded")}</p></div><span>{humanStatus(text(row, "parser_status"))} / {humanStatus(text(row, "validation_status"))}</span>{text(row, "source_url") ? <a href={text(row, "source_url")} target="_blank" rel="noreferrer">Source <ExternalLink size={12} /></a> : null}</article>)}</div> : null}
          {caseEvents.length ? <div className="ltw-case-audit"><h4>Audit history</h4>{caseEvents.slice(0, 8).map((row) => <article key={num(row, "id")}><div><strong>{humanStatus(text(row, "event_type"))}</strong><p>{text(row, "event_summary")}</p></div><time>{text(row, "occurred_at")}</time></article>)}</div> : null}
          <div className="ltw-case-gate"><ShieldCheck size={17} /><div><strong>Human-reviewed decision remains gated</strong><p>Claims, calculations, citations, disagreement and exceptions must pass review before an investment conclusion is accepted.</p></div></div>
        </div>
      </details>
    </section> : null}

    <details className="ltw-existing-cases">
      <summary>Existing research cases <span>{cases.length}</span></summary>
      <div>{cases.map((row) => <article key={num(row, "id")}><div><strong>{text(row, "company_name")}</strong><span>{text(row, "exchange")}:{text(row, "ticker")} · Case #{num(row, "id")}</span></div><p>{text(row, "mandate")}</p><Badge tone={text(row, "status") === "blocked" ? "risk" : "default"}>{humanStatus(text(row, "status"))}</Badge></article>)}</div>
    </details>
  </section>;
}

export function reportViewUrl(reportId: number): string {
  return `${API_BASE_URL}/api/research/thesis-reports/${reportId}/view`;
}
