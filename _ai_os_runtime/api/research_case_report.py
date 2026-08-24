"""Generate a versioned company Research Case HTML/PDF pack from durable sections."""
from __future__ import annotations
import hashlib, html, json, os, re, subprocess
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from atomic_report_renderer import find_chrome_browser, render_html_pdf
SSD=Path('/Volumes/Devarsh SSD'); ROOT=SSD/'AI OS Data'/'reports'/'company-research'
DOCKER='/Applications/Docker.app/Contents/Resources/bin/docker'
def q(v):return "NULL" if v is None else "'"+str(v).replace("'","''").replace('\x00','')+"'"
def j(v):return q(json.dumps(v,sort_keys=True,default=str))+"::jsonb"
def rows(sql):
 r=subprocess.run([DOCKER,'exec','-i','ai_os_postgres','psql','-q','-t','-A','-v','ON_ERROR_STOP=1','-U','ai_os','-d','ai_os'],input=f"SELECT coalesce(json_agg(row_to_json(q)),'[]'::json)::text FROM ({sql}) q;",text=True,capture_output=True)
 if r.returncode:raise RuntimeError(r.stderr.strip())
 return json.loads(r.stdout.strip() or '[]')
def statement(sql):
 r=subprocess.run([DOCKER,'exec','-i','ai_os_postgres','psql','-q','-t','-A','-v','ON_ERROR_STOP=1','-U','ai_os','-d','ai_os'],input=sql,text=True,capture_output=True)
 if r.returncode:raise RuntimeError(r.stderr.strip())
 return r.stdout.strip()
def h(v):return html.escape(str(v or ''))
def list_items(items,key):
 if not isinstance(items,list) or not items:return "<p class='gap'>Not established from the current approved packet.</p>"
 values=[]
 for item in items[:24]:
  if isinstance(item,dict):
   body=item.get(key) or item.get('point') or item.get('claim') or item.get('risk') or item.get('condition') or item.get('label') or json.dumps(item,default=str)
   cites=', '.join(str(x) for x in item.get('citation_ids',[])[:8])
  else:body=item;cites=''
  values.append(f"<li>{h(body)}{f'<small>{h(cites)}</small>' if cites else ''}</li>")
 return '<ul>'+''.join(values)+'</ul>'
def chrome():
 return find_chrome_browser()
def render_pdf(browser:Path,html_path:Path,pdf_path:Path,target:Path)->tuple[str|None,str|None]:
 result=render_html_pdf(browser,html_path,pdf_path,profile_root=target)
 return (result.get('pdf_hash'),None) if result.get('ok') else (None,str(result.get('error')))

ACCEPTED_SOURCE_STATES={'validated','human_reviewed','accepted','accepted_with_primary_corroboration'}
ACCEPTED_SECTION_STATES={'reviewed','complete'}
ACCEPTED_RATIO_STATES={'validated','human_reviewed'}

def _json_object(value:Any)->dict[str,Any]:
 if isinstance(value,dict):return value
 if isinstance(value,str):
  try:
   parsed=json.loads(value)
   return parsed if isinstance(parsed,dict) else {}
  except (TypeError,ValueError):return {}
 return {}

def _json_list(value:Any)->list[Any]:
 if isinstance(value,list):return value
 if isinstance(value,str):
  try:
   parsed=json.loads(value)
   return parsed if isinstance(parsed,list) else []
  except (TypeError,ValueError):return []
 return []

def _review_passed(review:dict[str,Any]|None)->bool:
 row=review or {};output=_json_object(row.get('output_summary'));validation=_json_object(row.get('validation_result'))
 return str(row.get('status') or '')=='completed' and output.get('review_decision')=='passed' and validation.get('valid') is True

def assess_prepublication(case:dict[str,Any],sections:list[dict[str,Any]],evidence:list[dict[str,Any]],
 preflight:dict[str,Any]|None,review:dict[str,Any]|None,blockers:list[dict[str,Any]],
 financial_facts:list[dict[str,Any]],ratios:list[dict[str,Any]])->dict[str,Any]:
 """Deterministically label report content without granting a capital decision."""
 section_states={str(row.get('section_key')):str(row.get('status') or 'not_started') for row in sections}
 gap_count=sum(len(_json_list(row.get('coverage_gaps'))) for row in sections)
 accepted_sources=sum(1 for row in evidence if str(row.get('validation_status') or row.get('parser_status') or '').lower() in ACCEPTED_SOURCE_STATES)
 accepted_facts=sum(1 for row in financial_facts if str(row.get('extraction_status') or '').lower() in ACCEPTED_SOURCE_STATES)
 accepted_ratios=sum(1 for row in ratios if str(row.get('calculation_status') or '').lower() in ACCEPTED_RATIO_STATES and row.get('value') is not None)
 delivery_blocker_keys={'report_pdf_render','research_pack_generation'}
 high_blockers=[row for row in blockers if str(row.get('status') or '') in {'open','retrying'} and str(row.get('severity') or '') in {'high','critical'} and str(row.get('blocker_key') or '') not in delivery_blocker_keys]
 delivery_blockers=[row for row in blockers if str(row.get('status') or '') in {'open','retrying'} and str(row.get('blocker_key') or '') in delivery_blocker_keys]
 preflight_state=str((preflight or {}).get('status') or 'missing')
 preflight_ready=preflight_state in {'approved','completed'}
 review_passed=_review_passed(review)
 sections_ready=bool(section_states) and all(state in ACCEPTED_SECTION_STATES for state in section_states.values())
 accepted=all((preflight_ready,review_passed,sections_ready,not high_blockers,accepted_sources>0,accepted_facts>0,accepted_ratios>0,gap_count==0))
 evidence_debt=any((accepted_sources==0,accepted_facts==0,accepted_ratios==0,gap_count>0,bool(high_blockers),str((_json_object((review or {}).get('output_summary'))).get('review_decision') or '')=='needs_revision'))
 content_state='accepted' if accepted else 'evidence_debt' if evidence_debt else 'draft'
 stale=any(str(row.get('validation_status') or '').lower()=='stale' for row in evidence)
 freshness_state='stale' if stale else 'not_assessed' if evidence else 'unknown'
 caveats=[]
 if not sections_ready:caveats.append('One or more report sections remain draft, collecting, blocked or not started.')
 if not preflight_ready:caveats.append(f"Latest public-research preflight is {preflight_state}; it is not approved or completed.")
 if not review_passed:caveats.append('Latest independent review has not passed its deterministic output and validation contract.')
 if high_blockers:caveats.append(f"{len(high_blockers)} open high/critical blocker(s) prevent acceptance.")
 if accepted_sources==0:caveats.append('No case evidence is validated or human reviewed.')
 if accepted_facts==0:caveats.append('No financial source facts are validated or human reviewed.')
 if accepted_ratios==0:caveats.append('No numeric financial ratios are validated or human reviewed.')
 if gap_count:caveats.append(f'{gap_count} explicit section coverage gap(s) remain.')
 return {
  'content_state':content_state,
  'content_label':{'accepted':'Research Pack','draft':'Draft Research Pack','evidence_debt':'Evidence-Debt Research Pack'}[content_state],
  'decision_state':'awaiting_human_review' if accepted else 'research_required',
  'freshness_state':freshness_state,
  'human_review_required':True,
  'capital_action_allowed':False,
  'preflight_state':preflight_state,
  'independent_review_state':'passed' if review_passed else str((review or {}).get('status') or 'missing'),
  'section_states':section_states,'section_gap_count':gap_count,
  'accepted_source_count':accepted_sources,'validated_financial_fact_count':accepted_facts,
  'validated_ratio_count':accepted_ratios,'open_high_blocker_count':len(high_blockers),
  'open_delivery_blocker_count':len(delivery_blockers),'caveats':caveats,
 }

def _decimal_text(value:Any,places:int=2)->str:
 try:value_dec=Decimal(str(value))
 except (InvalidOperation,TypeError,ValueError):return 'Not available'
 rendered=f'{value_dec:,.{places}f}'
 return rendered.rstrip('0').rstrip('.') if '.' in rendered else rendered

def _display_value(value:Any,unit:Any)->tuple[str,str]:
 unit_text=str(unit or '').strip()
 if value is None:return ('Not computable','No numeric value was stored')
 if unit_text.lower()=='lakh':
  try:raw=Decimal(str(value))
  except (InvalidOperation,ValueError,TypeError):return ('Not computable','Stored numeric value is invalid')
  crore=raw/Decimal('100')
  return (f'₹{_decimal_text(crore)} crore',f'{_decimal_text(raw)} INR lakh ÷ 100')
 if unit_text=='INR/share':return (f'₹{_decimal_text(value)} per share','Reported INR/share')
 if unit_text.lower()=='percent':return (f'{_decimal_text(value)}%','Reported percent')
 if unit_text.lower() in {'ratio','multiple'}:return (f'{_decimal_text(value)}×',f'Reported {unit_text.lower()}')
 if unit_text.lower()=='days':return (f'{_decimal_text(value)} days','Reported days')
 safe_unit=h(unit_text)
 return (f'{_decimal_text(value)} {safe_unit}'.strip(),f'Reported {safe_unit or "unit not recorded"}')

def _source_link(source_url:Any,page:Any,label:str='Source')->str:
 raw_url=str(source_url or '').strip()
 public_url=raw_url if raw_url.lower().startswith(('https://','http://')) else ''
 suffix=f' · p.{h(page)}' if page else ''
 return f"<a href='{h(public_url)}' rel='noreferrer'>{h(label)}</a>{suffix}" if public_url else f'{h(label)} public URL unavailable{suffix}'

def load_financial_packet(company_id:Any)->tuple[list[dict[str,Any]],list[dict[str,Any]]]:
 cid=int(company_id or -1)
 facts=rows(f"""SELECT sf.id,sf.fact_key,sf.fiscal_year,sf.period_end,sf.statement_type,sf.statement_scope,
   sf.value,sf.currency,sf.unit,sf.source_page,sf.reported_line,sf.extraction_status,sf.issuer_restatement,
   run.source_url,run.source_sha256
  FROM research.financial_source_facts sf
  JOIN research.financial_production_runs run ON run.id=sf.production_run_id
  WHERE sf.company_id={cid} AND sf.extraction_status IN ('validated','human_reviewed')
  ORDER BY sf.fiscal_year,sf.statement_type,sf.fact_key,sf.id DESC LIMIT 800""")
 ratios=rows(f"""SELECT rr.id,fd.formula_key,fd.version formula_version,fd.label,fd.expression,fd.basis,fd.unit,
   rr.period_end,rr.statement_scope,rr.value,rr.calculation_status,rr.not_computable_reason,rr.caveats,
   jsonb_agg(jsonb_build_object('input_role',ri.input_role,'fact_id',sf.id,'fact_key',sf.fact_key,
    'fiscal_year',sf.fiscal_year,'value',sf.value,'unit',sf.unit,'source_page',sf.source_page,
    'reported_line',sf.reported_line,'source_url',source_run.source_url,'extraction_status',sf.extraction_status)
    ORDER BY ri.input_role) FILTER (WHERE sf.id IS NOT NULL) inputs
  FROM research.financial_ratio_results rr
  JOIN research.financial_formula_definitions fd ON fd.id=rr.formula_definition_id
  LEFT JOIN research.financial_ratio_inputs ri ON ri.ratio_result_id=rr.id
  LEFT JOIN research.financial_source_facts sf ON sf.id=ri.fact_id
  LEFT JOIN research.financial_production_runs source_run ON source_run.id=sf.production_run_id
  WHERE rr.company_id={cid} AND rr.calculation_status IN ('validated','human_reviewed','not_computable','blocked')
  GROUP BY rr.id,fd.id ORDER BY rr.period_end,fd.label LIMIT 300""")
 return facts,ratios

def render_financial_exhibits(facts:list[dict[str,Any]],ratios:list[dict[str,Any]])->tuple[str,dict[str,Any]]:
 status_rank={'human_reviewed':2,'validated':1};deduped={}
 for fact in facts:
  key=(str(fact.get('fact_key')),fact.get('fiscal_year'),str(fact.get('statement_scope')))
  current=deduped.get(key)
  if current is None or status_rank.get(str(fact.get('extraction_status')),0)>status_rank.get(str(current.get('extraction_status')),0):deduped[key]=fact
 accepted=sorted(deduped.values(),key=lambda row:(int(row.get('fiscal_year') or 0),str(row.get('statement_type')),str(row.get('fact_key'))))
 fact_rows=[]
 for fact in accepted:
  display,basis=_display_value(fact.get('value'),fact.get('unit'))
  restated=' · restated' if fact.get('issuer_restatement') else ''
  fact_rows.append(f"<tr><td>FY{h(fact.get('fiscal_year'))}<small>{h(fact.get('period_end'))}</small></td><td>{h(str(fact.get('fact_key') or '').replace('_',' ').title())}<small>{h(fact.get('statement_type'))}</small></td><td><strong>{display}</strong><small>{h(basis)}</small></td><td>{h(fact.get('statement_scope'))}{restated}</td><td>{h(fact.get('extraction_status')).replace('_',' ')}<small>{_source_link(fact.get('source_url'),fact.get('source_page'))}</small></td></tr>")
 years=sorted({int(row['fiscal_year']) for row in accepted if row.get('fiscal_year') is not None})
 missing_years=[]
 if years:missing_years=[year for year in range(years[0],years[-1]+1) if year not in years]
 fact_body=''.join(fact_rows) or "<tr><td colspan='5' class='gap'>No validated or human-reviewed financial_source_facts are available. Values are not inferred or zero-filled.</td></tr>"
 ratio_rows=[]
 for ratio in ratios:
  status=str(ratio.get('calculation_status') or '')
  display,basis=_display_value(ratio.get('value'),ratio.get('unit')) if status in ACCEPTED_RATIO_STATES else ('Not computable',str(ratio.get('not_computable_reason') or 'Calculation is blocked'))
  inputs=[]
  for item in _json_list(ratio.get('inputs')):
   if not isinstance(item,dict):continue
   input_value,input_basis=_display_value(item.get('value'),item.get('unit'))
   inputs.append(f"{h(item.get('input_role'))}: {input_value} ({h(input_basis)}; {_source_link(item.get('source_url'),item.get('source_page'))})")
  caveats='; '.join(str(item) for item in _json_list(ratio.get('caveats')))
  ratio_rows.append(f"<tr><td>{h(ratio.get('period_end'))}<small>{h(ratio.get('statement_scope'))}</small></td><td>{h(ratio.get('label'))}<small>{h(ratio.get('formula_key'))} v{h(ratio.get('formula_version'))}</small></td><td><strong>{display}</strong><small>{h(status).replace('_',' ')}</small></td><td>{h(ratio.get('expression'))}<small>{h(basis)}</small></td><td>{'<br>'.join(inputs) if inputs else 'No accepted input citations recorded'}{f'<small>{h(caveats)}</small>' if caveats else ''}</td></tr>")
 ratio_body=''.join(ratio_rows) or "<tr><td colspan='5' class='gap'>No validated, human-reviewed, or explicitly not-computable financial_ratio_results are available.</td></tr>"
 gaps=[]
 if missing_years:gaps.append('Missing fiscal years inside the available history: '+', '.join('FY'+str(year) for year in missing_years)+'.')
 if not accepted:gaps.append('No validated or human-reviewed financial history is available.')
 if not any(str(row.get('calculation_status')) in ACCEPTED_RATIO_STATES for row in ratios):gaps.append('No numeric ratio result has reached validated or human-reviewed status.')
 gap_html="<p class='gap'><strong>Deterministic coverage gaps:</strong> "+h(' '.join(gaps))+"</p>" if gaps else ''
 exhibit=f"""<section id='financial-history'><span class='kicker'>Deterministic financial exhibits</span><h2>Source-backed financial history</h2><p class='section-note'>Only validated or human-reviewed source facts are shown. INR lakh values are converted to INR crore by dividing by exactly 100; the reported value and conversion remain visible in every row.</p><div class='table-wrap'><table><thead><tr><th>Period</th><th>Reported metric</th><th>Value and basis</th><th>Scope</th><th>Verification and citation</th></tr></thead><tbody>{fact_body}</tbody></table></div>{gap_html}</section><section id='ratio-library'><span class='kicker'>Reproducible calculations</span><h2>Financial ratio library</h2><p class='section-note'>Numeric outputs require validated or human-reviewed calculation status. Formula, unit, scope, period and every stored input remain visible; blocked outputs remain “Not computable”.</p><div class='table-wrap'><table><thead><tr><th>Period</th><th>Ratio</th><th>Output</th><th>Formula and unit basis</th><th>Inputs and citations</th></tr></thead><tbody>{ratio_body}</tbody></table></div></section>"""
 return exhibit,{'financial_years':years,'financial_year_start':years[0] if years else None,'financial_year_end':years[-1] if years else None,'missing_financial_years':missing_years,'financial_fact_count':len(accepted),'ratio_row_count':len(ratios),'financial_gaps':gaps}

def publish_case_workspace(case:dict[str,Any],sections:list[dict[str,Any]],report:dict[str,Any],generated_by:str,
 assessment:dict[str,Any]|None=None)->int:
 """Project an honestly labelled pack into the thesis selector."""
 assessment=assessment or {'content_state':'draft','decision_state':'research_required','freshness_state':'unknown'}
 by_key={str(row.get('section_key')):row for row in sections}
 def summary(key:str)->str:
  row=by_key.get(key) or {};content=row.get('content') or {}
  return str(row.get('summary') or content.get('summary') or '').strip()
 thesis_summary=summary('investment_conclusion') or summary('committee_decision') or 'Draft research pack available; evidence and human review gates remain.'
 business=summary('business_segments') or None
 industry=' '.join(filter(None,[summary('industry_structure'),summary('moat_quality')])).strip() or None
 symbol=str(case.get('ticker') or '').upper();exchange=str(case.get('exchange') or 'NSE').upper();case_id=int(case['id'])
 publication_state={'accepted':'research_pack_awaiting_human_review','draft':'draft_research_pack_available','evidence_debt':'evidence_debt_pack_available'}.get(str(assessment.get('content_state')),'draft_research_pack_available')
 decision_status=str(assessment.get('decision_state') or 'research_required')
 metadata={'research_case_id':case_id,'company_id':case.get('company_id'),'report_id':report.get('id'),'report_version':report.get('report_version'),'publication_state':publication_state,'content_state':assessment.get('content_state'),'delivery_state':assessment.get('delivery_state'),'freshness_state':assessment.get('freshness_state')}
 statement(f"""INSERT INTO portfolio.holding_theses
  (symbol,exchange,company_name,thesis_title,thesis_status,thesis_note_path,primary_owner_agent,
   investment_book_key,purpose_key,thesis_summary,business_model,industry_structure,review_frequency,
   next_review_due_at,decision_status,metadata,created_by,updated_by,updated_at)
 VALUES ({q(symbol)},{q(exchange)},{q(case.get('company_name'))},{q(str(case.get('company_name') or symbol)+' Long-Term Research')},
  'under_research',{q(report.get('html_path'))},{q(case.get('owner_agent') or 'Long-Term Portfolio Manager')},
  'long_term','research_case',{q(thesis_summary)},{q(business)},{q(industry)},'quarterly',now()+interval '14 days',
  {q(decision_status)},{j(metadata)},{q(generated_by)},{q(generated_by)},now())
 ON CONFLICT (symbol,exchange) DO UPDATE SET
  company_name=EXCLUDED.company_name,thesis_title=EXCLUDED.thesis_title,
  thesis_version=CASE WHEN portfolio.holding_theses.metadata->>'research_case_id'={q(str(case_id))}
    THEN portfolio.holding_theses.thesis_version ELSE portfolio.holding_theses.thesis_version+1 END,
  thesis_status=CASE WHEN portfolio.holding_theses.thesis_status IN ('approved','human_reviewed','active')
    THEN portfolio.holding_theses.thesis_status ELSE 'under_research' END,
  thesis_note_path=EXCLUDED.thesis_note_path,thesis_summary=EXCLUDED.thesis_summary,
  business_model=coalesce(EXCLUDED.business_model,portfolio.holding_theses.business_model),
  industry_structure=coalesce(EXCLUDED.industry_structure,portfolio.holding_theses.industry_structure),
  decision_status=CASE WHEN portfolio.holding_theses.decision_status IN ('approved','rejected')
    THEN portfolio.holding_theses.decision_status ELSE EXCLUDED.decision_status END,
  metadata=portfolio.holding_theses.metadata||EXCLUDED.metadata,updated_by=EXCLUDED.updated_by,updated_at=now();""")
 published=rows(f"SELECT id,thesis_version,thesis_status,decision_status FROM portfolio.holding_theses WHERE symbol={q(symbol)} AND exchange={q(exchange)} LIMIT 1")
 if not published:raise RuntimeError('research case publication returned no thesis')
 thesis=published[0];thesis_id=int(thesis['id']);version=int(thesis['thesis_version'])
 statement(f"""UPDATE research.research_cases SET holding_thesis_id={thesis_id},workspace_path={q(report.get('html_path'))},
   last_progress_at=now(),updated_at=now() WHERE id={case_id};
 INSERT INTO portfolio.holding_thesis_versions
  (holding_thesis_id,symbol,exchange,version_number,note_path,change_type,thesis_status,decision_status,
   thesis_summary,business_model,industry_structure,evidence,created_by)
 VALUES ({thesis_id},{q(symbol)},{q(exchange)},{version},{q(report.get('html_path'))},'research_case_published',
  {q(thesis.get('thesis_status'))},{q(thesis.get('decision_status'))},{q(thesis_summary)},{q(business)},{q(industry)},
  {j({'research_case_id':case_id,'report_id':report.get('id'),'html_hash':report.get('html_hash'),'pdf_hash':report.get('pdf_hash'),'human_review_required':True,'content_state':assessment.get('content_state'),'delivery_state':assessment.get('delivery_state'),'freshness_state':assessment.get('freshness_state')})},{q(generated_by)})
 ON CONFLICT (holding_thesis_id,version_number) DO UPDATE SET note_path=EXCLUDED.note_path,
  thesis_summary=EXCLUDED.thesis_summary,business_model=EXCLUDED.business_model,industry_structure=EXCLUDED.industry_structure,
  evidence=portfolio.holding_thesis_versions.evidence||EXCLUDED.evidence;
 UPDATE research.research_case_blockers SET status='resolved',resolved_at=now(),
  resolution={q(('The honestly labelled '+str(assessment.get('content_state'))+' HTML report was published and its PDF was rendered on external SSD.') if report.get('pdf_path') else ('The honestly labelled '+str(assessment.get('content_state'))+' HTML report was published; PDF delivery remains a bounded local retry.'))},
  system_action='Resolved automatically without rerunning paid research.',updated_at=now()
 WHERE research_case_id={case_id} AND blocker_key='research_pack_generation' AND status<>'resolved';""")
 return thesis_id
def generate_research_case_report(case_id:int,generated_by:str='Research Report Builder')->dict[str,Any]:
 if not SSD.is_mount() or not os.access(str(SSD/'AI OS Data'),os.W_OK):raise RuntimeError('external SSD is not mounted and writable; no fallback')
 case_rows=rows(f"SELECT * FROM research.research_cases WHERE id={int(case_id)} LIMIT 1")
 if not case_rows:raise RuntimeError('research case was not found')
 case=case_rows[0]
 sections=rows(f"SELECT * FROM research.research_pack_sections WHERE research_case_id={int(case_id)} AND version=1 ORDER BY id")
 evidence=rows(f"SELECT id,source_kind,source_url,publication_date,captured_at,parser_status,validation_status,citation_locator FROM research.research_case_evidence WHERE research_case_id={int(case_id)} ORDER BY publication_date DESC NULLS LAST,id DESC")
 preflight_rows=rows(f"SELECT id,status,source_count,document_count,completed_at,updated_at FROM research.model_run_preflights WHERE research_case_id={int(case_id)} AND request_kind='research_case' ORDER BY id DESC LIMIT 1")
 review_rows=rows(f"SELECT id,status,iteration,attempt,output_summary,validation_result,finished_at FROM research.research_case_model_runs WHERE research_case_id={int(case_id)} AND role_key='independent_review' ORDER BY iteration DESC,attempt DESC,id DESC LIMIT 1")
 blockers=rows(f"SELECT id,blocker_key,stage_key,title,detail,status,severity,updated_at FROM research.research_case_blockers WHERE research_case_id={int(case_id)} AND status IN ('open','retrying') ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,id")
 financial_facts,ratios=load_financial_packet(case.get('company_id'))
 assessment=assess_prepublication(case,sections,evidence,preflight_rows[0] if preflight_rows else None,review_rows[0] if review_rows else None,blockers,financial_facts,ratios)
 financial_html,financial_snapshot=render_financial_exhibits(financial_facts,ratios)
 versions=rows(f"SELECT coalesce(max(report_version),0)+1 version FROM research.research_case_reports WHERE research_case_id={int(case_id)}")
 version=int(versions[0]['version']);slug=re.sub(r'[^A-Za-z0-9._-]+','-',str(case.get('ticker') or case.get('company_name') or case_id)).strip('-').lower();target=ROOT/slug;target.mkdir(parents=True,exist_ok=True)
 asof=date.today().isoformat();base=f"research-case-{case_id}-v{version}-{asof}";html_path=target/(base+'.html');pdf_path=target/(base+'.pdf')
 section_html=[];toc=[]
 for section in sections:
  content=_json_object(section.get('content'));gaps=_json_list(section.get('coverage_gaps'));section_key=str(section.get('section_key') or 'section')
  section_status=str(section.get('status') or 'not_started');title=str(section.get('title') or section_key.replace('_',' ').title())
  toc.append(f"<a href='#{h(section_key)}'>{h(title)}</a>")
  status_caveat='Independent/human review recorded for this section.' if section_status in ACCEPTED_SECTION_STATES else f"Agent-authored {section_status.replace('_',' ')}; not accepted fact or investment conclusion."
  detail_html=''
  if content.get('calculations') or content.get('assumptions'):
   detail_html='<details><summary>Calculations and assumptions</summary>'+list_items(content.get('calculations'),'label')+list_items(content.get('assumptions'),'assumption')+'</details>'
  gap_html="<p class='gap'><strong>Exact coverage debt:</strong> "+h('; '.join(str(item) for item in gaps[:12]))+"</p>" if gaps else ''
  section_html.append(f"<section id='{h(section_key)}'><div style='break-inside:avoid;page-break-inside:avoid'><span class='kicker'>{h(title)}</span><h2>{h(content.get('summary') or section.get('summary') or title)}</h2><p class='section-note'>{h(status_caveat)}</p></div><div class='cols'><div><h3>Evidence-linked findings</h3>{list_items(content.get('analysis') or content.get('facts'),'point')}</div><div><h3>Decision implications and disconfirmers</h3>{list_items(content.get('risks') or content.get('disconfirmers'),'risk')}</div></div>{detail_html}{gap_html}</section>")
 source_rows=[]
 for e in evidence:
  link=_source_link(e.get('source_url'),(_json_object(e.get('citation_locator'))).get('page'),'Open source') if e.get('source_url') else 'Source URL unavailable; durable local evidence remains private'
  source_rows.append(f"<tr><td>{h(e['id'])}</td><td>{h(e['source_kind'])}</td><td>{h(e.get('publication_date') or e.get('captured_at'))}</td><td>{h(e.get('parser_status'))}</td><td>{h(e.get('validation_status'))}</td><td>{link}</td></tr>")
 sources=''.join(source_rows) or "<tr><td colspan='6' class='gap'>No case evidence has been linked. This report cannot be accepted.</td></tr>"
 caveat_items=''.join(f'<li>{h(item)}</li>' for item in assessment.get('caveats') or []) or '<li>No deterministic prepublication caveat was recorded.</li>'
 blocker_items=''.join(f"<li><strong>{h(row.get('title'))}</strong> — {h(row.get('detail'))}</li>" for row in blockers) or '<li>No open runtime blocker was recorded at generation time.</li>'
 document=f"""<!doctype html><html><head><meta charset='utf-8'><link rel='icon' href='data:,'><title>{h(case['company_name'])} · {h(assessment['content_label'])}</title><style>
 @page{{size:A4;margin:14mm}}*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:#f5f0e7;color:#1d2d3d;font:14px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif}}main{{max-width:1120px;margin:auto;background:#fffdf9;box-shadow:0 14px 42px rgba(29,45,61,.08)}}header{{padding:44px 48px 34px;background:#eee3d2;border-top:7px solid #355577;border-bottom:1px solid #d7c9b5}}.kicker{{display:block;break-after:avoid;page-break-after:avoid;color:#986524;text-transform:uppercase;letter-spacing:.12em;font-size:10px;font-weight:800}}h1,h2{{font-family:Georgia,serif;color:#1c2c42}}h1{{font-size:40px;line-height:1.08;margin:8px 0 12px}}h2{{font-size:24px;line-height:1.25;margin:7px 0 14px}}h3{{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#7d5728;margin-top:0}}section{{padding:30px 48px;border-bottom:1px solid #e2d8ca}}section h2,section h3,thead{{break-after:avoid;page-break-after:avoid}}p,li,tr{{orphans:3;widows:3}}tr{{break-inside:avoid}}.meta,.cols{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}.meta div{{padding:12px 0;border-top:1px solid #d2c3af}}.status-strip{{margin-top:22px;padding:16px 18px;background:#fff9ef;border-left:5px solid #a76e27}}.status-strip strong{{display:block;font-family:Georgia,serif;font-size:19px}}.toc{{display:flex;flex-wrap:wrap;gap:8px 18px;padding:18px 48px;background:#f9f5ee;border-bottom:1px solid #e2d8ca}}.toc a{{font-weight:650}}.section-note{{break-before:avoid;page-break-before:avoid}}.section-note,small{{display:block;color:#6f746f;font-size:11px}}ul{{padding-left:20px}}li{{margin:0 0 9px}}li small{{margin-top:2px}}.gap{{padding:11px 13px;background:#f6efe5;color:#5f574d;border-left:3px solid #bd8b4c}}.table-wrap{{overflow-x:auto;border:1px solid #ded5c8}}table{{width:100%;border-collapse:collapse;font-size:10.5px}}th,td{{padding:8px;border-bottom:1px solid #ded5c8;text-align:left;vertical-align:top}}th{{background:#f3ede3;color:#34475a;text-transform:uppercase;letter-spacing:.04em;font-size:9px}}td strong{{white-space:nowrap}}a{{color:#315f83;text-decoration-thickness:1px}}details{{margin-top:18px;padding:12px 14px;background:#faf6ef}}footer{{padding:24px 48px;color:#6f756f;font-size:11px;background:#f5f0e7}}@media print{{body{{background:white}}main{{box-shadow:none}}.table-wrap{{overflow:visible}}a{{color:#1d2d3d;text-decoration:none}}}}@media(max-width:700px){{header,section,footer,.toc{{padding-left:20px;padding-right:20px}}h1{{font-size:31px}}.meta,.cols{{grid-template-columns:1fr}}table{{min-width:760px}}}}
 </style></head><body><main><header><span class='kicker'>{h(assessment['content_label'])} · Version {version}</span><h1>{h(case['company_name'])} · {h(case.get('exchange'))}:{h(case.get('ticker'))}</h1><p>{h(case['mandate'])}</p><div class='meta'><div><strong>Report as of</strong><br>{asof}</div><div><strong>Content assessment</strong><br>{h(assessment['content_state']).replace('_',' ')}</div><div><strong>Freshness assessment</strong><br>{h(assessment['freshness_state']).replace('_',' ')}</div><div><strong>Decision authority</strong><br>{h(assessment['decision_state']).replace('_',' ')} · no capital action</div></div><div class='status-strip'><span class='kicker'>Prepublication assessment</span><strong>{h(assessment['content_label'])}</strong><ul>{caveat_items}</ul></div></header><nav class='toc' aria-label='Report sections'><a href='#financial-history'>Financial history</a><a href='#ratio-library'>Ratio library</a>{''.join(toc)}<a href='#prepublication'>Method and blockers</a><a href='#sources'>Source appendix</a></nav>{financial_html}{''.join(section_html)}<section id='prepublication'><span class='kicker'>Method and acceptance gates</span><h2>What prevents or permits publication</h2><div class='cols'><div><h3>Deterministic assessment</h3><ul>{caveat_items}</ul></div><div><h3>Open blockers at generation</h3><ul>{blocker_items}</ul></div></div></section><section id='sources'><span class='kicker'>Appendix</span><h2>Source register</h2><p class='section-note'>Source links are public URLs only. Private local paths are deliberately omitted from the report and PDF.</p><div class='table-wrap'><table><thead><tr><th>ID</th><th>Type</th><th>Date</th><th>Parser</th><th>Validation</th><th>Link</th></tr></thead><tbody>{sources}</tbody></table></div></section><footer>Generated locally from durable Research Case records on external SSD. Agent prose remains subject to the section status and deterministic gates shown above. Historical user research requires fresh primary corroboration. No broker, client, capital or external write is authorized.</footer></main></body></html>"""
 html_path.write_text(document,encoding='utf-8');html_hash=hashlib.sha256(document.encode()).hexdigest();pdf_hash=None;pdf_error=None;browser=chrome()
 if browser:
  pdf_hash,pdf_error=render_pdf(browser,html_path,pdf_path,target)
  if not pdf_hash:
   first_error=pdf_error
   pdf_hash,pdf_error=render_pdf(browser,html_path,pdf_path,target)
   if not pdf_hash:pdf_error=f'PDF retry did not complete; HTML is ready. First attempt: {first_error}; retry: {pdf_error}'
 else:pdf_error='No local Chromium renderer is installed; HTML is ready'
 assessment['delivery_state']='pdf_ready' if pdf_hash else 'html_ready_pdf_retry'
 coverage_snapshot={**assessment,**financial_snapshot,'section_count':len(sections),'source_count':len(evidence),'pdf_error':pdf_error}
 report_status='generated'
 statement(f"""INSERT INTO research.research_case_reports
  (research_case_id,report_version,report_status,as_of_date,source_cutoff_at,html_path,html_hash,pdf_path,pdf_hash,section_count,citation_count,coverage_snapshot,generated_by)
 VALUES ({case_id},{version},{q(report_status)},{q(asof)}::date,now(),{q(str(html_path))},{q(html_hash)},
  {q(str(pdf_path)) if pdf_hash else 'NULL'},{q(pdf_hash)},{len(sections)},{len(evidence)},
  {j(coverage_snapshot)},{q(generated_by)})
 ON CONFLICT (research_case_id,report_version) DO UPDATE SET report_status=EXCLUDED.report_status,
  as_of_date=EXCLUDED.as_of_date,source_cutoff_at=EXCLUDED.source_cutoff_at,html_path=EXCLUDED.html_path,
  html_hash=EXCLUDED.html_hash,pdf_path=EXCLUDED.pdf_path,pdf_hash=EXCLUDED.pdf_hash,section_count=EXCLUDED.section_count,
  citation_count=EXCLUDED.citation_count,coverage_snapshot=EXCLUDED.coverage_snapshot,generated_by=EXCLUDED.generated_by;""")
 if pdf_hash:
  statement(f"""UPDATE research.research_case_blockers SET status='resolved',resolved_at=now(),
    resolution='A clean local Chrome session rendered the PDF; the HTML report remained available throughout.',
    system_action='Resolved automatically without rerunning paid analysis.',user_action=NULL,updated_at=now()
    WHERE research_case_id={case_id} AND blocker_key='report_pdf_render' AND status<>'resolved';""")
 else:
  statement(f"""INSERT INTO research.research_case_blockers
    (research_case_id,blocker_key,stage_key,title,detail,system_action,user_action,status,severity,retry_count,next_retry_at,metadata)
    VALUES ({case_id},'report_pdf_render','report','PDF is being retried; the HTML report is ready',
      'The local PDF renderer did not finish two clean bounded attempts. Research sections and the HTML report are preserved.',
      'The stack will retry PDF rendering from a clean local browser session without rerunning paid research.',
      'Open the HTML report now; use Repair only if the PDF is still unavailable after the next retry.',
      'retrying','medium',2,now()+interval '15 minutes',
      {j({'technical_detail':pdf_error,'html_path':str(html_path),'paid_research_rerun_required':False})})
    ON CONFLICT (research_case_id,blocker_key) DO UPDATE SET title=EXCLUDED.title,detail=EXCLUDED.detail,
      system_action=EXCLUDED.system_action,user_action=EXCLUDED.user_action,status='retrying',severity=EXCLUDED.severity,
      retry_count=research.research_case_blockers.retry_count+1,next_retry_at=EXCLUDED.next_retry_at,
      metadata=EXCLUDED.metadata,resolved_at=NULL,resolution=NULL,updated_at=now();""")
 persisted=rows(f"SELECT id,report_version,report_status,html_path,html_hash,pdf_path,pdf_hash FROM research.research_case_reports WHERE research_case_id={case_id} AND report_version={version} LIMIT 1")
 if not persisted:raise RuntimeError('research case report persistence returned no row')
 report=persisted[0];thesis_id=publish_case_workspace(case,sections,report,generated_by,assessment)
 return {'ok':True,'research_case_id':case_id,'holding_thesis_id':thesis_id,'report_id':int(report['id']),
  'report_version':version,'report_status':report_status,'content_state':assessment['content_state'],
  'delivery_state':assessment['delivery_state'],'freshness_state':assessment['freshness_state'],
  'decision_state':assessment['decision_state'],'html_path':str(html_path),'html_hash':html_hash,
  'pdf_path':str(pdf_path) if pdf_hash else None,'pdf_hash':pdf_hash,'pdf_error':pdf_error,
  'section_count':len(sections),'citation_count':len(evidence)}

def retry_research_case_report_pdf(report_id:int,generated_by:str='Research Report Retry')->dict[str,Any]:
 persisted=rows(f"""SELECT report.id,report.research_case_id,report.report_version,report.html_path,
  report.html_hash,report.coverage_snapshot FROM research.research_case_reports report
  WHERE report.id={int(report_id)} LIMIT 1""")
 if not persisted:return {'status':'missing_report','report_id':int(report_id)}
 report=persisted[0];case_id=int(report['research_case_id']);html_path=Path(str(report.get('html_path') or ''))
 pdf_path=html_path.with_suffix('.pdf');browser=chrome()
 result=render_html_pdf(browser,html_path,pdf_path,profile_root=html_path.parent) if browser else {'ok':False,'error':'No local Chromium renderer is installed; HTML is ready'}
 if result.get('ok'):
  statement(f"""UPDATE research.research_case_reports SET report_status='generated',
    pdf_path={q(result['pdf_path'])},pdf_hash={q(result['pdf_hash'])},generated_by={q(generated_by)},
    coverage_snapshot=coalesce(coverage_snapshot,'{{}}'::jsonb)||{j({'delivery_state':'pdf_ready','pdf_retry_same_report_row':True,'pdf_error':None})}
    WHERE id={int(report_id)};
   UPDATE research.research_case_blockers SET status='resolved',resolved_at=now(),
    resolution='The existing HTML report was rendered atomically to PDF from a clean local Chrome profile.',
    system_action='Resolved on the same report row without rerunning paid research.',user_action=NULL,
    next_retry_at=NULL,updated_at=now() WHERE research_case_id={case_id}
    AND blocker_key='report_pdf_render' AND status<>'resolved';""")
  return {'status':'report_retry_completed','ok':True,'research_case_id':case_id,'report_id':int(report_id),
   'report_version':int(report['report_version']),'html_path':str(html_path),**result}
 error=str(result.get('error') or 'PDF renderer did not create a valid artifact')
 statement(f"""UPDATE research.research_case_reports SET report_status='generated',generated_by={q(generated_by)},
   coverage_snapshot=coalesce(coverage_snapshot,'{{}}'::jsonb)||{j({'delivery_state':'html_ready_pdf_retry','pdf_retry_same_report_row':True,'pdf_error':error})}
   WHERE id={int(report_id)};
  UPDATE research.research_case_blockers SET status='retrying',retry_count=retry_count+1,
   next_retry_at=CASE WHEN retry_count+1<4 THEN now()+interval '15 minutes' ELSE NULL END,
   metadata=coalesce(metadata,'{{}}'::jsonb)||{j({'technical_detail':error,'report_id':int(report_id),'paid_research_rerun_required':False})},
   updated_at=now() WHERE research_case_id={case_id} AND blocker_key='report_pdf_render';""")
 return {'status':'report_retry_wait','ok':False,'research_case_id':case_id,'report_id':int(report_id),
  'report_version':int(report['report_version']),'html_path':str(html_path),'pdf_error':error}

def retry_pending_research_case_report()->dict[str,Any]:
 candidates=rows("""SELECT blocker.research_case_id,blocker.retry_count,report.id report_id
  FROM research.research_case_blockers blocker
  JOIN research.research_cases case_row ON case_row.id=blocker.research_case_id
  JOIN LATERAL (SELECT id FROM research.research_case_reports report
    WHERE report.research_case_id=blocker.research_case_id ORDER BY report_version DESC,id DESC LIMIT 1) report ON true
  WHERE blocker.blocker_key='report_pdf_render' AND blocker.status='retrying'
    AND blocker.next_retry_at<=now() AND blocker.retry_count<4
    AND case_row.status IN ('review','completed','blocked')
  ORDER BY blocker.next_retry_at,blocker.id LIMIT 1""")
 if not candidates:
  statement("""UPDATE research.research_case_blockers SET status='open',
    title='HTML report is ready; PDF needs browser repair',
    detail='Four clean local PDF render attempts did not complete. The source-backed HTML report remains available.',
    system_action='Automatic PDF retries stopped without rerunning paid research.',
    user_action='Open the HTML report or approve a scoped report-render repair.',next_retry_at=NULL,updated_at=now()
    WHERE blocker_key='report_pdf_render' AND status='retrying' AND retry_count>=4;""")
  return {'status':'idle'}
 return retry_research_case_report_pdf(int(candidates[0]['report_id']))
