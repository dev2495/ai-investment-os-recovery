#!/usr/bin/env python3
"""Bounded GET and MCP overview smoke; never calls a mutation tool."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

PATHS = ('/api/v1/doctor', '/api/v1/routines', '/api/v1/model-fabric')
READ_TOOLS = ('ai_os_doctor_overview', 'ai_os_routine_overview', 'ai_os_model_fabric_overview')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    proofs = []
    for path in PATHS:
        with urllib.request.urlopen('http://127.0.0.1:8765'+path, timeout=25) as response:
            data = json.load(response)
            proofs.append({'transport':'api','path':path,'http':response.status,
                'available':data.get('available'), 'broker_write_allowed':data.get('broker_write_allowed')})
    requests = [{'jsonrpc':'2.0','id':0,'method':'tools/list'}]
    requests.extend({'jsonrpc':'2.0','id':i+1,'method':'tools/call',
        'params':{'name':name,'arguments':{}}} for i,name in enumerate(READ_TOOLS))
    process = subprocess.run([sys.executable,str(args.repo/'_ai_os_runtime/mcp_server/ai_os_mcp_server.py')],
        input='\n'.join(json.dumps(request) for request in requests)+'\n',
        text=True,capture_output=True,timeout=100,check=True)
    replies = {reply['id']:reply for reply in map(json.loads,process.stdout.splitlines())}
    registered = {tool['name'] for tool in replies[0]['result']['tools']}
    for i,name in enumerate(READ_TOOLS):
        reply = replies[i+1]
        result = reply.get('result',{})
        available = None
        for block in result.get('content',[]):
            if block.get('type') == 'text':
                try:
                    available = json.loads(block['text']).get('available')
                except (ValueError,AttributeError):
                    pass
        proofs.append({'transport':'mcp','tool':name,'registered':name in registered,
            'error':bool(reply.get('error') or result.get('isError')),'available':available})
    ok = all(p.get('available') is True and not p.get('error') for p in proofs)
    print(json.dumps({'ok':ok,'proofs':proofs,'mutations':0,'model_calls':0,'broker_calls':0},indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
