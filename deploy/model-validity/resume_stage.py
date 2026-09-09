import json, subprocess
from pathlib import Path
stage=Path('/opt/aipet-model-validation-20260909')
def run(args,**kwargs): return subprocess.run(args,check=True,**kwargs)
password=dict(line.split('=',1) for line in (stage/'test-db.env').read_text().splitlines())['MYSQL_ROOT_PASSWORD']
backup=stage/'backup'
with (backup/'database.sql').open('rb') as source:
 run(['docker','exec','-i','model-validity-test-db','sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --default-character-set=utf8mb4 -uroot xiaozhi_esp32_server'],stdin=source,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
print('snapshot restored into isolated test database',flush=True)
run(['docker','run','-d','--name','model-validity-test-redis','--network','model-validity-test','--memory=128m','redis:8.0'],stdout=subprocess.DEVNULL)
envs=dict(SPRING_DATASOURCE_DRUID_URL='jdbc:mysql://model-validity-test-db:3306/xiaozhi_esp32_server?useUnicode=true&characterEncoding=UTF-8&serverTimezone=UTC&nullCatalogMeansCurrent=true',SPRING_DATASOURCE_DRUID_USERNAME='root',SPRING_DATASOURCE_DRUID_PASSWORD=password,SPRING_DATA_REDIS_HOST='model-validity-test-redis',SPRING_DATA_REDIS_PASSWORD='',SPRING_DATA_REDIS_PORT='6379',MODEL_VALIDATION_URL='http://model-validity-test-probe:8003/internal/models/validate')
env=stage/'test-manager.env'; env.write_text('\n'.join(k+'='+v for k,v in envs.items())+'\n');env.chmod(0o600)
run(['docker','run','-d','--name','model-validity-test-manager','--network','model-validity-test','--memory=1500m','--env-file',str(env),'-p','127.0.0.1:18022:8002','xiaozhi-aipet-manager:20260909-validity'],stdout=subprocess.DEVNULL)
print('candidate started on loopback 18022; production snapshot in isolated test database; production unchanged',flush=True)
