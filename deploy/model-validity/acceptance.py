"""只在隔离数据库执行 API 验收，不输出凭证及用户数据。"""
import json, secrets, subprocess, urllib.request, urllib.error
from pathlib import Path
stage=Path('/opt/aipet-model-validation-20260909')
def sql(query):
 r=subprocess.run(['docker','exec','-i','model-validity-test-db','sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --default-character-set=utf8mb4 -uroot -N -B --raw xiaozhi_esp32_server'],input=query,text=True,capture_output=True)
 if r.returncode: raise RuntimeError('test SQL failed')
 return r.stdout.strip()
def api(path,method='GET',body=None,token=None):
 req=urllib.request.Request('http://'+json.loads(subprocess.check_output(['docker','inspect','model-validity-test-manager']))[0]['NetworkSettings']['Networks']['model-validity-test']['IPAddress']+':8002/xiaozhi'+path,data=None if body is None else json.dumps(body).encode(),method=method,headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+token} if token else {})})
 try: response=urllib.request.urlopen(req,timeout=40)
 except urllib.error.HTTPError as e: response=e
 return json.loads(response.read())
def check(ok,label):
 if not ok: raise AssertionError(label)
 print('PASS '+label,flush=True)
if __name__=='__main__':
 secret=sql("SELECT param_value FROM sys_params WHERE param_code='server.secret'")
 env=stage/'test-probe.env'; env.write_text('TEST_SECRET='+secret+'\n');env.chmod(0o600)
 code="import os; from aiohttp import web; from core.api.model_validation_handler import ModelValidationHandler; app=web.Application(); app.router.add_post('/internal/models/validate',ModelValidationHandler({'server':{'auth_key':os.environ['TEST_SECRET']}}).handle_post); web.run_app(app,port=8003)"
 if subprocess.run(['docker','inspect','model-validity-test-probe'],capture_output=True).returncode:
  subprocess.run(['docker','run','-d','--name','model-validity-test-probe','--network','model-validity-test','--memory=1500m','--cpus=1','--env-file',str(env),'xiaozhi-aipet-server:v0.9.6-b15-validity','python','-c',code],check=True,stdout=subprocess.DEVNULL)
 uid=sql('SELECT id FROM sys_user WHERE super_admin=1 LIMIT 1')
 token=secrets.token_hex(24); tid=str(secrets.randbelow(10**15))
 sql("DELETE FROM sys_user_token WHERE user_id='%s'"%uid)
 sql("INSERT INTO sys_user_token(id,user_id,token,expire_date,update_date,create_date) VALUES ('%s','%s','%s',DATE_ADD(NOW(),INTERVAL 1 HOUR),NOW(),NOW())"%(tid,uid,token))
 try:
  check(api('/models/VAD_SileroVAD/validate','POST').get('code')!=0,'unauthenticated rejected')
  r=api('/models/list?modelType=VAD&page=1&limit=100',token=token)
  check(r.get('code')==0 and 'validityStatus' in r['data']['list'][0],'list validity fields')
  sql("UPDATE ai_model_config SET validity_status='unknown',is_enabled=0,is_default=0 WHERE id='VAD_SileroVAD'")
  check(api('/models/enable/VAD_SileroVAD/1','PUT',token=token).get('code')!=0,'unknown enable rejected')
  check(api('/models/default/VAD_SileroVAD','PUT',token=token).get('code')!=0,'unknown default rejected')
  r=api('/models/VAD_SileroVAD/validate','POST',token=token)
  check(r.get('code')==0 and r['data']['validityStatus']=='valid','real VAD probe round trip')
  check(not r['data'].get('configJson'),'validation response excludes credentials')
  check(api('/models/enable/VAD_SileroVAD/1','PUT',token=token).get('code')==0,'valid enable allowed')
  check(api('/models/default/VAD_SileroVAD','PUT',token=token).get('code')==0,'valid default allowed')
  missing=sql("SELECT id FROM ai_model_config WHERE model_type='LLM' AND id NOT IN ('LLM_MiniMaxM25','LLM_ChatGLMLLM','LLM_KimiK27','LLM_QianfanCodingLLM') LIMIT 1")
  r=api('/models/'+missing+'/validate','POST',token=token)
  check(r.get('code')==0 and r['data']['validityStatus']=='invalid' and r['data']['isEnabled']==0,'missing credentials invalid and disabled')
  check(api('/models/enable/'+missing+'/1','PUT',token=token).get('code')!=0,'invalid enable rejected')
  r=api('/models/TTS_FishSpeech/validate','POST',token=token)
  check(r.get('code')==0 and r['data']['validityStatus']=='invalid','explicit JSON null snapshot round trip')
  row=api('/models/VAD_SileroVAD',token=token)['data']
  row['modelName']=row['modelName']+' acceptance'
  provider=sql("SELECT provider_code FROM ai_model_provider WHERE model_type='VAD' LIMIT 1")
  route='/models/VAD/'+provider+'/VAD_SileroVAD'
  r=api(route,'PUT',row,token)
  check(r.get('code')==0 and r['data']['validityStatus']=='valid','name edit preserves validity')
  row['configJson']['acceptance_revision']=secrets.token_hex(8)
  r=api(route,'PUT',row,token)
  check(r.get('code')==0 and r['data']['validityStatus']=='unknown' and r['data']['isEnabled']==0 and r['data']['isDefault']==0,'config edit invalidates and disables')
  normal=sql('SELECT id FROM sys_user WHERE super_admin=0 LIMIT 1')
  if normal:
   sql("UPDATE sys_user_token SET user_id='%s' WHERE id='%s'"%(normal,tid))
   check(api('/models/VAD_SileroVAD/validate','POST',token=token).get('code')!=0,'normal user cannot validate')
 finally: sql("DELETE FROM sys_user_token WHERE id='%s'"%tid)
