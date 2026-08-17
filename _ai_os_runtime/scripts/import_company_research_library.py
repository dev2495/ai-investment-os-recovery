#!/usr/bin/env python3
"""Import user-supplied company research into the SSD-only governed library.

Artifacts are historical analyst inputs, never accepted current facts. Originals
are copied by the operator before this script runs; this script only reads the SSD
copy, hashes it, extracts searchable text locally, and maps verified company rows.
"""
from __future__ import annotations
import argparse, hashlib, html, json, mimetypes, re, subprocess
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path('/Volumes/Devarsh SSD/AI OS Data/imports/company_research_benchmarks/2026-08-15')
EXTRACTED=ROOT/'_extracted'
ALIASES={
 'aaron_industries':('Aaron Industries','AARON'),'anantraj':('Anant Raj','ANANTRAJ'),
 'equitas_sfb':('Equitas Small Finance Bank','EQUITASBNK'),'sjs_enterprises':('SJS Enterprises','SJS'),
 'shivalik_bimetal':('Shivalik Bimetal Controls','SBCL'),'pds_limited':('PDS Limited','PDSL'),
 'inoxindia':('INOX India','INOXINDIA'),'inox_india':('INOX India','INOXINDIA'),
 'advent_hotels':('Advent Hotels International','ADVENTHTL'),'unicommerce':('Unicommerce eSolutions','UNIECOM'),
 'jai_balaji':('Jai Balaji Industries','JAIBALAJI'),'jaibalaji':('Jai Balaji Industries','JAIBALAJI'),
 'emmvee':('Emmvee Photovoltaic Power','EMMVEE'),'atlantaelectricals':('Atlanta Electricals','ATLANTAELEC'),
 'atlanta_electricals':('Atlanta Electricals','ATLANTAELEC'),'pinelabs':('Pine Labs','PINELABS'),
 'pine_labs':('Pine Labs','PINELABS'),'simca':('Simca Advertising','SIMCA'),
}
class TextHTML(HTMLParser):
 def __init__(self): super().__init__(); self.parts=[]
 def handle_data(self,data):
  value=' '.join(data.split())
  if value:self.parts.append(value)
def q(v): return "NULL" if v is None else "'"+str(v).replace("'","''").replace('\x00','')+"'"
def j(v): return q(json.dumps(v,sort_keys=True,default=str))+"::jsonb"
def sql(text):
 c=['/Applications/Docker.app/Contents/Resources/bin/docker','exec','-i','ai_os_postgres','psql','-q','-t','-A','-v','ON_ERROR_STOP=1','-U','ai_os','-d','ai_os']
 r=subprocess.run(c,input=text,text=True,capture_output=True)
 if r.returncode: raise RuntimeError(r.stderr.strip())
 return r.stdout.strip()
def key_for(path): return re.sub(r'[^a-z0-9]+','_',path.stem.lower()).strip('_')
def entity(path):
 key=key_for(path)
 for alias,(label,symbol) in ALIASES.items():
  if alias in key:return label,symbol
 if 'copper' in key:return 'Copper commodity',None
 if 'pyrolysis' in key:return 'Pyrolysis project',None
 if 'network_intelligence' in key:return 'Network Intelligence Evolution',None
 return path.stem.replace('_',' '),None
def kind(path):
 n=path.name.lower()
 if path.suffix.lower()=='.xlsx':return 'financial_model'
 if path.suffix.lower()=='.html':return 'interactive_dashboard'
 if path.suffix.lower()=='.md':return 'research_note'
 if 'commodity' in n or 'pyrolysis' in n:return 'sector_report'
 if path.suffix.lower()=='.pdf':return 'research_report'
 return 'other'
def extract(path):
 suffix=path.suffix.lower()
 if suffix=='.html':
  parser=TextHTML();parser.feed(path.read_text(errors='ignore'));return '\n'.join(parser.parts)
 if suffix=='.md':return path.read_text(errors='ignore')
 if suffix=='.pdf':
  try:
   from pypdf import PdfReader
  except ImportError:return ''
  values=[]
  for index,page in enumerate(PdfReader(str(path)).pages):
   values.append(f'\n--- PDF PAGE {index+1} ---\n'+(page.extract_text() or ''))
  return ''.join(values)
 return ''
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',default=str(ROOT));ap.add_argument('--actor',default='Research Librarian');args=ap.parse_args()
 root=Path(args.root); EXTRACTED.mkdir(parents=True,exist_ok=True)
 company_rows=json.loads(sql("SELECT coalesce(json_agg(json_build_object('id',id,'symbol',primary_symbol)),'[]'::json)::text FROM research.companies;") or '[]')
 by_symbol={str(r['symbol']).upper():int(r['id']) for r in company_rows if r.get('symbol')}
 counts={'seen':0,'imported':0,'matched':0,'pending':0,'parsed':0,'unsupported':0}
 for path in sorted(p for p in root.rglob('*') if p.is_file() and '_extracted' not in p.parts):
  counts['seen']+=1; data=path.read_bytes(); digest=hashlib.sha256(data).hexdigest(); label,symbol=entity(path); company_id=by_symbol.get(symbol or '')
  extracted=extract(path); text_path=None; parser_status='not_supported'
  if extracted.strip():
   target=EXTRACTED/(digest[:16]+'.txt');target.write_text(extracted);text_path=str(target);parser_status='parsed';counts['parsed']+=1
  else:counts['unsupported']+=1
  match_status='matched' if company_id else ('not_applicable' if symbol is None else 'pending')
  counts['matched' if company_id else 'pending']+=1
  collection='cowork_research' if '/cowork/' in str(path) else 'codex_outputs'
  mime=mimetypes.guess_type(path.name)[0] or 'application/octet-stream'; artifact_key='user-research-'+hashlib.sha256((digest+'|'+path.name).encode()).hexdigest()[:24]
  title=path.stem.replace('_',' ')
  payload={'relative_path':str(path.relative_to(root)),'symbol_hint':symbol,'private_data_egress_allowed':False,'accepted_current_fact':False,'fresh_primary_corroboration_required':True}
  out=sql(f"""INSERT INTO research.imported_company_research_artifacts
    (artifact_key,company_id,company_label,symbol_hint,artifact_kind,original_filename,local_artifact_path,extracted_text_path,content_hash,mime_type,source_collection,source_posture,entity_match_status,parser_status,review_status,title,metadata,imported_by)
    VALUES ({q(artifact_key)},{company_id if company_id else 'NULL'},{q(label)},{q(symbol)},{q(kind(path))},{q(path.name)},{q(str(path))},{q(text_path)},{q(digest)},{q(mime)},{q(collection)},'historical_user_supplied_research',{q(match_status)},{q(parser_status)},'needs_fresh_corroboration',{q(title)},{j(payload)},{q(args.actor)})
    ON CONFLICT (content_hash,original_filename) DO UPDATE SET company_id=EXCLUDED.company_id,company_label=EXCLUDED.company_label,symbol_hint=EXCLUDED.symbol_hint,
      local_artifact_path=EXCLUDED.local_artifact_path,extracted_text_path=EXCLUDED.extracted_text_path,entity_match_status=EXCLUDED.entity_match_status,
      parser_status=EXCLUDED.parser_status,metadata=EXCLUDED.metadata,updated_at=now() RETURNING id;""")
  if out:counts['imported']+=1
 print(json.dumps({'ok':True,'root':str(root),'storage':'external_ssd_only','source_posture':'historical_user_supplied_research','counts':counts},indent=2))
if __name__=='__main__':main()
