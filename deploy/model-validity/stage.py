"""独立镜像及生产数据库副本验收；用户2026-09-09明确授权完整复制。"""
import json, secrets, subprocess, time
from pathlib import Path
stage=Path('/opt/aipet-model-validation-20260909')
def run(args,**kwargs): return subprocess.run(args,check=True,**kwargs)
def inspect(name): return json.loads(subprocess.check_output(['docker','inspect',name]))[0]
def build(file,tag):
 with (stage/(file+'.log')).open('w') as log:
  run(['docker','build','-f',str(stage/file),'-t',tag,str(stage)],stdout=log,stderr=subprocess.STDOUT)
 print(tag+': built',flush=True)
if __name__=='__main__':
 (stage/'Dockerfile.manager').write_text('FROM '+inspect('xiaozhi-esp32-server-web')['Config']['Image']+'\nCOPY manager-api/target/xiaozhi-esp32-api.jar /app/xiaozhi-esp32-api.jar\nCOPY dist/ /usr/share/nginx/html/\n')
 (stage/'Dockerfile.voice').write_text('FROM '+inspect('xiaozhi-esp32-server')['Config']['Image']+'\nCOPY model_validation.py /opt/xiaozhi-esp32-server/core/model_validation.py\nCOPY model_validation_handler.py /opt/xiaozhi-esp32-server/core/api/model_validation_handler.py\nCOPY http_server.py /opt/xiaozhi-esp32-server/core/http_server.py\nCOPY sample/model_validation_sample.wav /opt/xiaozhi-esp32-server/core/model_validation_sample.wav\n')
 (stage/'.dockerignore').write_text('*\n!Dockerfile.*\n!manager-api/\nmanager-api/*\n!manager-api/target/\nmanager-api/target/*\n!manager-api/target/xiaozhi-esp32-api.jar\n!dist/\n!dist/**\n!model_validation.py\n!model_validation_handler.py\n!http_server.py\n!sample/\n!sample/model_validation_sample.wav\n')
 build('Dockerfile.manager','xiaozhi-aipet-manager:20260909-validity')
 build('Dockerfile.voice','xiaozhi-aipet-server:v0.9.6-b15-validity')
 backup=stage/'backup'; backup.mkdir(mode=0o700,exist_ok=True)
 import shutil
 shutil.copy2('/opt/xiaozhi-server/docker-compose_all.yml',backup/'compose.yml')
 (backup/'images.json').write_text(json.dumps({n:inspect(n)['Image'] for n in ['xiaozhi-esp32-server-web','xiaozhi-esp32-server']}))
 # 完整快照仅保存在服务器0700目录，SQL文件0600，绝不下载到工作区。
 with (backup/'database.sql').open('wb') as out:
  run(['docker','exec','xiaozhi-esp32-server-db','sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump --default-character-set=utf8mb4 -uroot --single-transaction --no-tablespaces --set-gtid-purged=OFF xiaozhi_esp32_server'],stdout=out,stderr=subprocess.PIPE)
 (backup/'database.sql').chmod(0o600)
 print('production snapshot saved privately',flush=True)
 run(['docker','network','create','--internal','model-validity-test'],stdout=subprocess.DEVNULL)
 password=secrets.token_hex(24)
 env=stage/'test-db.env'; env.write_text('MYSQL_ROOT_PASSWORD='+password+'\nMYSQL_DATABASE=xiaozhi_esp32_server\n'); env.chmod(0o600)
 run(['docker','run','-d','--name','model-validity-test-db','--network','model-validity-test','--env-file',str(env),'--memory=1500m','--tmpfs','/var/lib/mysql','mysql:latest'],stdout=subprocess.DEVNULL)
 for _ in range(50):
  r=subprocess.run(['docker','exec','model-validity-test-db','sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -h127.0.0.1 -uroot -N -e "SELECT 1"'],capture_output=True)
  if r.returncode==0: break
  time.sleep(1)
 with (backup/'database.sql').open('rb') as source:
  run(['docker','exec','-i','model-validity-test-db','sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --default-character-set=utf8mb4 -uroot xiaozhi_esp32_server'],stdin=source,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 print('snapshot restored into isolated test database',flush=True)
 run(['docker','run','-d','--name','model-validity-test-redis','--network','model-validity-test','--memory=128m','redis:8.0'],stdout=subprocess.DEVNULL)
 envs=dict(SPRING_DATASOURCE_DRUID_URL='jdbc:mysql://model-validity-test-db:3306/xiaozhi_esp32_server?useUnicode=true&characterEncoding=UTF-8&serverTimezone=UTC&nullCatalogMeansCurrent=true',SPRING_DATASOURCE_DRUID_USERNAME='root',SPRING_DATASOURCE_DRUID_PASSWORD=password,SPRING_DATA_REDIS_HOST='model-validity-test-redis',SPRING_DATA_REDIS_PASSWORD='',SPRING_DATA_REDIS_PORT='6379',MODEL_VALIDATION_URL='http://model-validity-test-probe:8003/internal/models/validate')
 env=stage/'test-manager.env'; env.write_text('\n'.join(k+'='+v for k,v in envs.items())+'\n');env.chmod(0o600)
 run(['docker','run','-d','--name','model-validity-test-manager','--network','model-validity-test','--memory=1500m','--env-file',str(env),'-p','127.0.0.1:18022:8002','xiaozhi-aipet-manager:20260909-validity'],stdout=subprocess.DEVNULL)
 print('candidate started on loopback 18022; production snapshot in isolated test database; production unchanged',flush=True)
