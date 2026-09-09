"""完整数据库副本上的续费提醒与权限验收。"""
import secrets,json,datetime
from acceptance import sql,api,check
uid=sql('SELECT id FROM sys_user WHERE super_admin=1 LIMIT 1');token=secrets.token_hex(24);tid=str(secrets.randbelow(10**15))
sql("DELETE FROM sys_user_token WHERE user_id='%s'"%uid)
sql("INSERT INTO sys_user_token(id,user_id,token,expire_date,update_date,create_date) VALUES ('%s','%s','%s',DATE_ADD(NOW(),INTERVAL 1 HOUR),NOW(),NOW())"%(tid,uid,token))
try:
 check(api('/models/usage').get('code')!=0,'usage requires authentication')
 r=api('/models/usage',token=token);check(r.get('code')==0,'usage list returns')
 rows=r['data'];check(sum(len(x['models']) for x in rows)==int(sql('SELECT COUNT(*) FROM ai_model_config')),'all model configurations covered')
 mini=next(x for x in rows if x['service']=='MiniMax')
 check(len(mini['models'])>=2,'same MiniMax credential grouped')
 check(mini['status'] in ('ok','unavailable'),'isolated network unavailability handled')
 serialized=json.dumps(rows)
 configs=sql('SELECT config_json FROM ai_model_config').splitlines()
 for raw in configs:
  if not raw or raw=='NULL':continue
  for k,v in json.loads(raw).items():
   if k in ['api_key','access_token','api_password','secret_key'] and isinstance(v,str) and len(v)>16:assert v not in serialized
 check(True,'response excludes credentials')
 key=mini['serviceKey']
 r=api('/models/usage/reminder/'+key,'PUT',{'renewalDate':'2026-09-10'},token)
 check(r.get('code')==0,'save manual expiration')
 row=next(x for x in api('/models/usage',token=token)['data'] if x['serviceKey']==key)
 check(row['renewalDate']=='2026-09-10' and row['warning'],'expiration warning persisted')
 check(api('/models/usage/reminder/'+key,'PUT',{'renewalDate':'bad'},token).get('code')!=0,'invalid date rejected')
 check(api('/models/usage/reminder/not-a-service','PUT',{'renewalDate':None},token).get('code')!=0,'unknown service rejected')
 check(api('/models/usage/reminder/'+key,'PUT',{'renewalDate':None},token).get('code')==0,'clear manual expiration')
 sql("UPDATE sys_user SET super_admin=0 WHERE id='%s'"%uid)
 normal=secrets.token_hex(24);sql("UPDATE sys_user_token SET token='%s' WHERE id='%s'"%(normal,tid))
 check(api('/models/usage',token=normal).get('code')!=0,'normal user usage rejected')
 check(api('/models/usage/reminder/'+key,'PUT',{'renewalDate':None},normal).get('code')!=0,'normal user reminder write rejected')
 check(api('/admin/server/emit-action','POST',{'targetWs':'ws://invalid','action':'restart'},normal).get('code')!=0,'normal user restart rejected')
finally:
 sql("UPDATE sys_user SET super_admin=1 WHERE id='%s'"%uid)
 sql("DELETE FROM sys_user_token WHERE id='%s'"%tid)
