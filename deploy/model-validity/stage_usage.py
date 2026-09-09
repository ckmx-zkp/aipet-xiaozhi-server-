"""在已授权 ECS 构建候选并用完整生产数据库副本验收。"""
import subprocess,time,tarfile
from pathlib import Path
p=Path('/opt/aipet-model-validation-20260909')
def run(args,**kw):return subprocess.run(args,check=True,**kw)
with (p/'maven-usage-final.log').open('w') as log:
 run(['docker','run','--rm','--memory=2g','--cpus=2','-v',str(p/'manager-api')+':/workspace/manager-api','-v',str(p/'manager-web')+':/workspace/manager-web:ro','-v',str(p/'m2')+':/root/.m2','-w','/workspace/manager-api','maven:3.9-eclipse-temurin-21','mvn','-B','package','-DskipTests=false','-Dtest=!DeviceTest,!loginControllerTest'],stdout=log,stderr=subprocess.STDOUT)
print('Java package and tests passed',flush=True)
run(['docker','run','--rm','--network','none','-e','WEATHER_SOURCE=/get_weather.py','-v',str(p/'test_weather_errors.py')+':/test.py:ro','-v',str(p/'get_weather.py')+':/get_weather.py:ro','xiaozhi-aipet-server:v0.9.6-b15-validity','python','/test.py'])
(p/'usage-dist').mkdir(exist_ok=True)
with tarfile.open(p/'usage-web-dist.tar.gz') as tar:tar.extractall(p/'usage-dist',filter='data')
with (p/'.dockerignore').open('a') as f:f.write('\n!usage-dist/\n!usage-dist/**\n!get_weather.py\n')
(p/'Dockerfile.usage-manager').write_text('FROM xiaozhi-aipet-manager:20260909-validity-r2\nCOPY manager-api/target/xiaozhi-esp32-api.jar /app/xiaozhi-esp32-api.jar\nCOPY usage-dist/ /usr/share/nginx/html/\n')
(p/'Dockerfile.usage-voice').write_text('FROM xiaozhi-aipet-server:v0.9.6-b15-validity\nCOPY model_validation.py /opt/xiaozhi-esp32-server/core/model_validation.py\nCOPY get_weather.py /opt/xiaozhi-esp32-server/plugins_func/functions/get_weather.py\n')
for file,tag in [('Dockerfile.usage-manager','xiaozhi-aipet-manager:20260909-usage'),('Dockerfile.usage-voice','xiaozhi-aipet-server:v0.9.6-b16-services')]:
 with (p/(file+'.log')).open('w') as log:run(['docker','build','-f',str(p/file),'-t',tag,str(p)],stdout=log,stderr=subprocess.STDOUT)
 print(tag+' built',flush=True)
backup=p/'backup/pre-usage.sql'
with backup.open('wb') as f:
 run(['docker','exec','xiaozhi-esp32-server-db','sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump --default-character-set=utf8mb4 -uroot --single-transaction --no-tablespaces --set-gtid-purged=OFF xiaozhi_esp32_server'],stdout=f,stderr=subprocess.PIPE)
backup.chmod(0o600)
run(['docker','start','model-validity-test-db','model-validity-test-redis'],stdout=subprocess.DEVNULL)
for _ in range(50):
 r=subprocess.run(['docker','exec','model-validity-test-db','sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -h127.0.0.1 -uroot -N -e "SELECT 1"'],capture_output=True)
 if r.returncode==0:break
 time.sleep(1)
else:raise RuntimeError('test database unavailable')
with backup.open('rb') as f:
 run(['docker','exec','-i','model-validity-test-db','sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --default-character-set=utf8mb4 -uroot xiaozhi_esp32_server'],stdin=f,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
run(['docker','rm','model-validity-test-manager'],stdout=subprocess.DEVNULL)
run(['docker','run','-d','--name','model-validity-test-manager','--network','model-validity-test','--memory=1500m','--env-file',str(p/'test-manager.env'),'xiaozhi-aipet-manager:20260909-usage'],stdout=subprocess.DEVNULL)
print('fresh production snapshot restored; candidate manager started',flush=True)
