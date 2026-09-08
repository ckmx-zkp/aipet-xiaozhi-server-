'''只在服务器执行：令牌从stdin读取到0600私有文件，代码和日志不保存令牌。'''
import json
import os
import shutil
import secrets
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

root = Path('/opt/xiaozhi-music-aipet')
stage = Path(sys.argv[1]).resolve()
assert stage.parent == Path('/opt') and stage.name.startswith('aipet-companion-')
if sys.argv[2] == 'secret':
    endpoint = sys.stdin.readline().strip()
    p = urlsplit(endpoint)
    assert p.scheme == 'wss' and p.hostname == 'api.xiaozhi.me' and p.path == '/mcp/' and parse_qs(p.query).get('token')
    target = root / 'cloud.env'
    assert not target.exists(), 'existing cloud config; inspect before replacing'
    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write('MCP_ENDPOINT=' + endpoint + '\n')
    print('Cloud endpoint saved privately; token not logged.')
elif sys.argv[2] == 'identity':
    target = root / 'cloud-account.json'
    assert not target.exists(), 'existing account file; inspect before replacing'
    credentials = dict(login_name='cyber_xiaozhi_2323485', password=secrets.token_urlsafe(32),
                       binding_id=secrets.token_urlsafe(24))
    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(credentials, f)
    subprocess.run(['docker', 'cp', str(stage / 'provision_cloud_identity.py'),
                    'ai-pet-backend-web-api-1:/tmp/provision_cloud_identity.py'], check=True)
    result = subprocess.run(['docker', 'exec', '-i', 'ai-pet-backend-web-api-1',
        'python', '/tmp/provision_cloud_identity.py'], input=json.dumps(credentials),
        text=True, capture_output=True, check=True)
    identity = json.loads(result.stdout)
    with target.open('w') as f:
        json.dump({**credentials, **identity}, f)
    state = json.loads(subprocess.check_output(['docker', 'inspect', 'ai-pet-backend-web-api-1']))[0]
    token = next(v.split('=', 1)[1] for v in state['Config']['Env'] if v.startswith('INTERNAL_SERVICE_TOKEN='))
    private = root / 'cloud.env'
    with private.open('a') as f:
        f.write('COMPANION_INTERNAL_TOKEN=' + token + '\nCOMPANION_CLOUD_DEVICE=' + identity['device_uid'] + '\n')
    print('Independent digital-twin identity created; credentials private; no pet data reused.')
elif sys.argv[2] == 'activate':
    config_path = root / 'compose.json'
    config = json.loads(config_path.read_text())
    assert 'cloud-mcp-bridge' not in config['services'], 'bridge already exists'
    shutil.copy2(config_path, stage / 'backup/pre-cloud-compose.json')
    service = dict(image='xiaozhi-music-aipet:20260908-cloud', restart='unless-stopped',
        command=['python', 'cloud_bridge.py'], env_file=['music.env', 'content.env', 'cloud.env'],
        networks=['xiaozhi', 'backend-internal'], read_only=True, tmpfs=['/tmp'],
        security_opt=['no-new-privileges:true'],
        logging=dict(driver='json-file', options={'max-size':'10m', 'max-file':'3'}))
    config['services']['cloud-mcp-bridge'] = service
    config_path.write_text(json.dumps(config, indent=2))
    subprocess.run(['docker', 'compose', '-f', str(config_path), 'up', '-d', '--no-deps', 'cloud-mcp-bridge'], cwd=root, check=True)
    print('Cloud bridge started with independent digital-twin identity.')
