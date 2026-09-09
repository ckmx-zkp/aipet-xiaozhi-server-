"""用户明确授权后，仅更新管理台和语音服务镜像。"""
import json,re,subprocess
from pathlib import Path
p=Path('/opt/xiaozhi-server/docker-compose_all.yml')
s=p.read_text()
images={'xiaozhi-esp32-server':'xiaozhi-aipet-server:v0.9.6-b15-validity','xiaozhi-esp32-server-web':'xiaozhi-aipet-manager:20260909-validity-r2'}
c=json.loads(subprocess.check_output(['docker','compose','-f',str(p),'config','--format','json'],stderr=subprocess.DEVNULL))
for service,image in images.items():
 old=c['services'][service]['image']
 pattern=r'(?m)^(\s*image:\s*)'+re.escape(old)+r'\s*$'
 s,n=re.subn(pattern,lambda m:m.group(1)+image,s)
 if n!=1: raise RuntimeError('image replacement not unique: '+service)
backup=Path('/opt/aipet-model-validation-20260909/backup/pre-rollout-compose.yml')
if not backup.exists(): backup.write_text(p.read_text());backup.chmod(0o600)
p.write_text(s)
r=subprocess.run(['docker','compose','-f',str(p),'up','-d','--no-deps',*images],capture_output=True,text=True)
if r.returncode: raise RuntimeError('compose rollout failed; inspect deployment state')
print('manager and voice updated; other services unchanged')
