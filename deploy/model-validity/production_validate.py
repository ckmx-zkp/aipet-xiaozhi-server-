"""线上逐项检测当前配置，使用现有管理员会话，不输出令牌。"""
import json,subprocess,urllib.request,urllib.error,collections,sys
from pathlib import Path
stage=Path('/opt/aipet-model-validation-20260909')
def sql(q):
 r=subprocess.run(['docker','exec','-i','xiaozhi-esp32-server-db','sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --default-character-set=utf8mb4 -uroot -N -B --raw xiaozhi_esp32_server'],input=q,text=True,capture_output=True,check=True)
 return r.stdout.strip()
def api(path,method='GET'):
 req=urllib.request.Request('http://127.0.0.1:8002/xiaozhi'+path,method=method,headers={'Authorization':'Bearer '+token})
 try: r=urllib.request.urlopen(req,timeout=40)
 except urllib.error.HTTPError as e: r=e
 return json.loads(r.read())
if __name__=='__main__':
 token=sql('SELECT t.token FROM sys_user_token t JOIN sys_user u ON u.id=t.user_id WHERE u.super_admin=1 AND t.expire_date>NOW() ORDER BY t.expire_date DESC LIMIT 1')
 if not token: raise RuntimeError('No active administrator session')
 ids=sql("SELECT id FROM ai_model_config ORDER BY CASE WHEN model_type='LLM' THEN 0 ELSE 1 END,model_type,id").splitlines()
 results=json.loads((stage/'production-results.json').read_text()) if "--resume" in sys.argv else []
 completed={x["id"] for x in results}
 for mid in ids:
  if mid in completed: continue
  r=api('/models/'+mid+'/validate','POST')
  if r.get('code')!=0:
   print(json.dumps({'id':mid,'error':r.get('msg','failed')},ensure_ascii=False),flush=True)
   raise RuntimeError('validation failed; previous rows retained')
  d=r['data'];row={k:d.get(k) for k in ['id','modelType','modelName','validityStatus','validityReason','validityCheckedAt','isEnabled','isDefault']}
  results.append(row)
  (stage/'production-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
  print(json.dumps(row,ensure_ascii=False),flush=True)
 print('COUNTS '+json.dumps(dict(collections.Counter(x['validityStatus'] for x in results))))
 print('invalid_enabled='+sql("SELECT COUNT(*) FROM ai_model_config WHERE validity_status<>'valid' AND (is_enabled=1 OR is_default=1)"))
 invalid=next(x['id'] for x in results if x['validityStatus']=='invalid')
 assert api('/models/enable/'+invalid+'/1','PUT').get('code')!=0
 assert api('/models/default/'+invalid,'PUT').get('code')!=0
 print('PASS production invalid enable/default guard')
