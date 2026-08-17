"""Generate a versioned company Research Case HTML/PDF pack from durable sections."""
from __future__ import annotations
import hashlib, html, json, os, re, signal, subprocess, tempfile, time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
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
 for path in [Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),Path('/Applications/Chromium.app/Contents/MacOS/Chromium')]:
  if path.exists():return path
 return None
def render_pdf(browser:Path,html_path:Path,pdf_path:Path,target:Path)->tuple[str|None,str|None]:
 """Render to a temporary SSD file and accept it once stable; Chrome need not exit cleanly."""
 render_path=target/(pdf_path.stem+'.rendering.pdf')
 if render_path.exists():render_path.unlink()
 error=None
 with tempfile.TemporaryDirectory(dir=str(target)) as profile:
  command=[str(browser),'--headless=new','--no-sandbox','--disable-gpu','--disable-extensions',
   '--disable-background-networking','--no-first-run','--disable-dev-shm-usage',
   '--run-all-compositor-stages-before-draw','--virtual-time-budget=5000','--print-to-pdf-no-header',
   f'--user-data-dir={profile}',f'--print-to-pdf={render_path}',html_path.as_uri()]
  process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  deadline=time.monotonic()+60;last_size=-1;stable=0
  try:
   while time.monotonic()<deadline:
    if render_path.exists():
     size=render_path.stat().st_size
     stable=stable+1 if size>1024 and size==last_size else 0;last_size=size
     if stable>=4:break
    if process.poll() is not None and not render_path.exists():
     error=f'Chrome exited {process.returncode} before producing a PDF';break
    time.sleep(.25)
   else:error='PDF render did not produce a stable file within 60 seconds'
  finally:
   if process.poll() is None:
    try:os.killpg(process.pid,signal.SIGTERM)
    except ProcessLookupError:pass
    try:process.wait(timeout=3)
    except subprocess.TimeoutExpired:
     try:os.killpg(process.pid,signal.SIGKILL)
     except ProcessLookupError:pass
  if not error and render_path.exists() and render_path.stat().st_size>1024:
   os.replace(render_path,pdf_path)
   return hashlib.sha256(pdf_path.read_bytes()).hexdigest(),None
  if render_path.exists():render_path.unlink()
 return None,error or 'PDF renderer did not create a valid artifact'

def publish_case_workspace(case:dict[str,Any],sections:list[dict[str,Any]],report:dict[str,Any],generated_by:str)->int:
 """Project a completed agent pack into the thesis selector without implying human approval."""
 by_key={str(row.get('section_key')):row for row in sections}
 def summary(key:str)->str:
  row=by_key.get(key) or {};content=row.get('content') or {}
  return str(row.get('summary') or content.get('summary') or '').strip()
 thesis_summary=summary('investment_conclusion') or summary('committee_decision') or 'Research pack generated; human review remains required.'
 business=summary('business_segments') or None
 industry=' '.join(filter(None,[summary('industry_structure'),summary('moat_quality')])).strip() or None
 symbol=str(case.get('ticker') or '').upper();exchange=str(case.get('exchange') or 'NSE').upper();case_id=int(case['id'])
 metadata={'research_case_id':case_id,'company_id':case.get('company_id'),'report_id':report.get('id'),'report_version':report.get('report_version'),'publication_state':'research_complete_awaiting_human_review'}
 statement(f"""INSERT INTO portfolio.holding_theses
  (symbol,exchange,company_name,thesis_title,thesis_status,thesis_note_path,primary_owner_agent,
   investment_book_key,purpose_key,thesis_summary,business_model,industry_structure,review_frequency,
   next_review_due_at,decision_status,metadata,created_by,updated_by,updated_at)
 VALUES ({q(symbol)},{q(exchange)},{q(case.get('company_name'))},{q(str(case.get('company_name') or symbol)+' Long-Term Research')},
  'under_research',{q(report.get('html_path'))},{q(case.get('owner_agent') or 'Long-Term Portfolio Manager')},
  'long_term','research_case',{q(thesis_summary)},{q(business)},{q(industry)},'quarterly',now()+interval '14 days',
  'awaiting_human_review',{j(metadata)},{q(generated_by)},{q(generated_by)},now())
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
    THEN portfolio.holding_theses.decision_status ELSE 'awaiting_human_review' END,
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
  {j({'research_case_id':case_id,'report_id':report.get('id'),'html_hash':report.get('html_hash'),'pdf_hash':report.get('pdf_hash'),'human_review_required':True})},{q(generated_by)})
 ON CONFLICT (holding_thesis_id,version_number) DO UPDATE SET note_path=EXCLUDED.note_path,
  thesis_summary=EXCLUDED.thesis_summary,business_model=EXCLUDED.business_model,industry_structure=EXCLUDED.industry_structure,
  evidence=portfolio.holding_thesis_versions.evidence||EXCLUDED.evidence;
 UPDATE research.research_case_blockers SET status='resolved',resolved_at=now(),
  resolution={q('The durable HTML report was published and the PDF artifact was rendered on Devarsh SSD.' if report.get('pdf_path') else 'The durable HTML report was published; the PDF remains a bounded local render retry.')},
  system_action='Resolved automatically without rerunning paid research.',updated_at=now()
 WHERE research_case_id={case_id} AND blocker_key='research_pack_generation' AND status<>'resolved';""")
 return thesis_id
def generate_research_case_report(case_id:int,generated_by:str='Research Report Builder')->dict[str,Any]:
 if not SSD.is_mount() or not os.access(str(SSD/'AI OS Data'),os.W_OK):raise RuntimeError('external SSD is not mounted and writable; no fallback')
 case=rows(f"SELECT * FROM research.research_cases WHERE id={int(case_id)}")[0]
 sections=rows(f"SELECT * FROM research.research_pack_sections WHERE research_case_id={int(case_id)} AND version=1 ORDER BY id")
 evidence=rows(f"SELECT id,source_kind,source_url,publication_date,captured_at,parser_status,validation_status,citation_locator FROM research.research_case_evidence WHERE research_case_id={int(case_id)} ORDER BY publication_date DESC NULLS LAST,id DESC")
 versions=rows(f"SELECT coalesce(max(report_version),0)+1 version FROM research.research_case_reports WHERE research_case_id={int(case_id)}")
 version=int(versions[0]['version']); slug=re.sub(r'[^A-Za-z0-9._-]+','-',str(case.get('ticker') or case.get('company_name') or case_id)).strip('-').lower(); target=ROOT/slug;target.mkdir(parents=True,exist_ok=True)
 asof=date.today().isoformat(); base=f"research-case-{case_id}-v{version}-{asof}"; html_path=target/(base+'.html');pdf_path=target/(base+'.pdf')
 section_html=[]
 for section in sections:
  content=section.get('content') or {}; gaps=section.get('coverage_gaps') or []
  section_html.append(f"<section id='{h(section['section_key'])}'><span class='kicker'>{h(section['title'])}</span><h2>{h(content.get('summary') or section.get('summary') or section['title'])}</h2><div class='cols'><div><h3>Evidence-backed findings</h3>{list_items(content.get('analysis') or content.get('facts'),'point')}</div><div><h3>Decision implications</h3>{list_items(content.get('risks') or content.get('disconfirmers'),'risk')}</div></div>{'<details><summary>Calculations and assumptions</summary>'+list_items(content.get('calculations'),'label')+list_items(content.get('assumptions'),'assumption')+'</details>' if content.get('calculations') or content.get('assumptions') else ''}{'<p class=gap><strong>Coverage debt:</strong> '+h('; '.join(str(x) for x in gaps[:12]))+'</p>' if gaps else ''}</section>")
 source_rows=[]
 for e in evidence:
  link=("<a href='"+h(e.get('source_url'))+"'>Open source</a>") if e.get('source_url') else 'Local SSD artifact'
  source_rows.append(f"<tr><td>{h(e['id'])}</td><td>{h(e['source_kind'])}</td><td>{h(e.get('publication_date') or e.get('captured_at'))}</td><td>{h(e.get('validation_status') or e.get('parser_status'))}</td><td>{link}</td></tr>")
 sources=''.join(source_rows)
 document=f"""<!doctype html><html><head><meta charset='utf-8'><link rel='icon' href='data:,'><title>{h(case['company_name'])} Research Pack</title><style>@page{{size:A4;margin:16mm}}*{{box-sizing:border-box}}body{{margin:0;background:#f7f3eb;color:#1d2d3d;font:14px/1.55 Arial,sans-serif}}main{{max-width:1120px;margin:auto;background:#fffdf9}}header{{padding:44px 48px;background:#eee3d2;border-bottom:1px solid #d7c9b5}}.kicker{{color:#986524;text-transform:uppercase;letter-spacing:.12em;font-size:10px;font-weight:800}}h1,h2{{font-family:Georgia,serif}}h1{{font-size:40px;margin:8px 0}}h2{{font-size:24px;line-height:1.25;margin:7px 0 18px}}h3{{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#8c622d}}section{{padding:30px 48px;border-bottom:1px solid #e2d8ca;break-inside:avoid}}.meta,.cols{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}.meta div{{padding:12px 0;border-top:1px solid #d2c3af}}ul{{padding-left:20px}}li{{margin:0 0 9px}}li small{{display:block;color:#8a837a}}.gap{{padding:11px 13px;background:#f6efe5;color:#6b6258}}table{{width:100%;border-collapse:collapse;font-size:11px}}th,td{{padding:8px;border-bottom:1px solid #ded5c8;text-align:left;vertical-align:top}}a{{color:#315f83}}footer{{padding:24px 48px;color:#6f756f;font-size:11px}}@media(max-width:700px){{header,section,footer{{padding-left:20px;padding-right:20px}}.meta,.cols{{grid-template-columns:1fr}}}}</style></head><body><main><header><span class='kicker'>Complete Company Research Pack · Version {version}</span><h1>{h(case['company_name'])} · {h(case.get('exchange'))}:{h(case.get('ticker'))}</h1><p>{h(case['mandate'])}</p><div class='meta'><div><strong>As of</strong><br>{asof}</div><div><strong>Research state</strong><br>{h(case['decision_readiness']).replace('_',' ')}</div><div><strong>Source coverage</strong><br>{len(evidence)} linked sources</div><div><strong>Authority</strong><br>Human decision required; no trading authority</div></div></header>{''.join(section_html)}<section><span class='kicker'>Appendix</span><h2>Source register</h2><table><thead><tr><th>ID</th><th>Type</th><th>Date</th><th>Review state</th><th>Link</th></tr></thead><tbody>{sources}</tbody></table></section><footer>Generated locally from durable Research Case sections on Devarsh SSD. Historical user research is reference material and requires fresh primary corroboration. No broker, client, capital or external write is authorized.</footer></main></body></html>"""
 html_path.write_text(document);html_hash=hashlib.sha256(document.encode()).hexdigest();pdf_hash=None;pdf_error=None;browser=chrome()
 if browser:pdf_hash,pdf_error=render_pdf(browser,html_path,pdf_path,target)
 else:pdf_error='No local Chromium renderer is installed'
 report_status='generated' if pdf_hash else 'needs_revision'
 statement(f"""INSERT INTO research.research_case_reports
  (research_case_id,report_version,report_status,as_of_date,source_cutoff_at,html_path,html_hash,pdf_path,pdf_hash,section_count,citation_count,coverage_snapshot,generated_by)
 VALUES ({case_id},{version},{q(report_status)},{q(asof)}::date,now(),{q(str(html_path))},{q(html_hash)},
  {q(str(pdf_path)) if pdf_hash else 'NULL'},{q(pdf_hash)},{len(sections)},{len(evidence)},
  {j({'section_count':len(sections),'source_count':len(evidence),'human_review_required':True,'pdf_error':pdf_error})},{q(generated_by)})
 ON CONFLICT (research_case_id,report_version) DO UPDATE SET report_status=EXCLUDED.report_status,
  as_of_date=EXCLUDED.as_of_date,source_cutoff_at=EXCLUDED.source_cutoff_at,html_path=EXCLUDED.html_path,
  html_hash=EXCLUDED.html_hash,pdf_path=EXCLUDED.pdf_path,pdf_hash=EXCLUDED.pdf_hash,section_count=EXCLUDED.section_count,
  citation_count=EXCLUDED.citation_count,coverage_snapshot=EXCLUDED.coverage_snapshot,generated_by=EXCLUDED.generated_by;""")
 persisted=rows(f"SELECT id,report_version,report_status,html_path,html_hash,pdf_path,pdf_hash FROM research.research_case_reports WHERE research_case_id={case_id} AND report_version={version} LIMIT 1")
 if not persisted:raise RuntimeError('research case report persistence returned no row')
 report=persisted[0];thesis_id=publish_case_workspace(case,sections,report,generated_by)
 return {'ok':True,'research_case_id':case_id,'holding_thesis_id':thesis_id,'report_id':int(report['id']),
  'report_version':version,'report_status':report_status,'html_path':str(html_path),'html_hash':html_hash,
  'pdf_path':str(pdf_path) if pdf_hash else None,'pdf_hash':pdf_hash,'pdf_error':pdf_error,
  'section_count':len(sections),'citation_count':len(evidence)}
