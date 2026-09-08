'''本次跨服务发布：独立候选构建、临时数据库验收、备份和可回滚切换。'''
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

stage = Path(sys.argv[1]).resolve()
assert stage.parent == Path('/opt') and stage.name.startswith('aipet-companion-')
root = Path('/opt/xiaozhi-music-aipet')
be = Path('/opt/ai-pet/ai-pet-backend')
voice = Path('/opt/xiaozhi-server')
revision = sys.argv[3]
be_image = 'ai-pet-backend-release:' + revision
mcp_image = 'xiaozhi-music-aipet:20260908-companion'
voice_image = 'xiaozhi-aipet-server:v0.9.6-b14-companion'


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def inspect(name):
    return json.loads(subprocess.check_output(['docker', 'inspect', name]))[0]


def build(args, filename):
    with (stage / filename).open('w') as log:
        run(args, stdout=log, stderr=subprocess.STDOUT)
    print(filename + ': PASS', flush=True)


def prepare():
    backup = stage / 'backup'
    backup.mkdir(mode=0o700, exist_ok=False)
    for source, name in [(be / 'docker-compose.yml', 'backend-compose.yml'),
                         (root / 'compose.json', 'music-compose.json'),
                         (voice / 'docker-compose_all.yml', 'voice-compose.yml')]:
        shutil.copy2(source, backup / name)
    shutil.copytree(root / 'server', backup / 'music-server')
    (backup / 'images.json').write_text(json.dumps({name: inspect(name)['Image'] for name in
        ['ai-pet-backend-web-api-1', 'ai-pet-backend-memory-mcp-1',
         'ai-pet-backend-agent-worker-1', 'xiaozhi-esp32-server',
         'xiaozhi-music-aipet-music-content-mcp-1']}))
    run(['git', 'pull', '--ff-only'], cwd=be)
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=be).decode().strip() == revision
    build(['docker', 'build', '--build-arg', 'VCS_REF=' + revision, '-t', be_image, str(be)], 'backend-build.log')
    build(['docker', 'build', '-f', str(stage / 'Dockerfile.companion'), '-t', mcp_image, str(stage)], 'content-build.log')
    build(['docker', 'build', '-f', str(stage / 'Dockerfile.voice-companion'), '-t', voice_image, str(stage)], 'voice-build.log')


def database_test():
    network = 'companion-test-' + stage.name
    run(['docker', 'network', 'create', '--internal', network], stdout=subprocess.DEVNULL)
    password = secrets.token_hex(24)
    env = dict(DATABASE_URL=f'postgresql+asyncpg://postgres:{password}@companion-test-db:5432/companion_test',
               JWT_SECRET_KEY=secrets.token_hex(32), INTERNAL_SERVICE_TOKEN=secrets.token_hex(32),
               COMPANION_ENABLED='true')
    testenv = stage / 'test.env'
    env['COMPANION_INTERNAL_TOKEN'] = env['INTERNAL_SERVICE_TOKEN']
    env['MUSIC_API_TOKEN'] = 'isolated-test-only'
    testenv.write_text('\n'.join(k + '=' + v for k, v in env.items()) + '\n')
    testenv.chmod(0o600)
    # 此数据库只含脚本生成的测试数据，无宿主端口，无生产卷。
    name = 'companion-test-db-' + stage.name
    api_name = 'companion-test-api-' + stage.name
    mcp_name = 'companion-test-mcp-' + stage.name
    db_env = dict(os.environ, POSTGRES_PASSWORD=password)
    try:
        run(['docker', 'run', '-d', '--name', name, '--network', network,
             '--network-alias', 'companion-test-db', '--tmpfs', '/var/lib/postgresql/data',
             '-e', 'POSTGRES_PASSWORD', '-e', 'POSTGRES_DB=companion_test', 'pgvector/pgvector:pg16'],
            env=db_env, stdout=subprocess.DEVNULL)
        for _ in range(30):
            if subprocess.run(['docker', 'exec', name, 'pg_isready', '-U', 'postgres'],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                break
            time.sleep(1)
        common = ['docker', 'run', '--rm', '--network', network, '--env-file', str(testenv),
                  '-v', str(be / 'scripts') + ':/checks:ro', be_image]
        build(common + ['alembic', 'upgrade', 'head'], 'test-migration.log')
        build(common + ['python', '/checks/verify_companion_db.py'], 'test-database.log')
        run(['docker', 'run', '-d', '--name', api_name, '--network', network,
             '--network-alias', 'web-api', '--env-file', str(testenv), be_image], stdout=subprocess.DEVNULL)
        run(['docker', 'run', '-d', '--name', mcp_name, '--network', network,
             '--env-file', str(testenv), '-v', str(stage / 'verify_companion_write.py') + ':/checks.py:ro',
             mcp_image], stdout=subprocess.DEVNULL)
        for attempt in range(15):
            with (stage / 'test-mcp-write.log').open('w') as log:
                result = subprocess.run(['docker', 'exec', mcp_name, 'python', '/checks.py'],
                                        stdout=log, stderr=subprocess.STDOUT)
            if result.returncode == 0:
                print('test-mcp-write.log: PASS', flush=True)
                break
            if attempt >= 14:
                raise RuntimeError('MCP write validation failed; see private staging log')
            time.sleep(1)
    finally:
        subprocess.run(['docker', 'rm', '-f', mcp_name, api_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL)
        subprocess.run(['docker', 'network', 'rm', network], stdout=subprocess.DEVNULL)


def activate_backend():
    # 新增表迁移先于应用切换；私有环境从当前运行容器读取，不打印。
    env = inspect('ai-pet-backend-web-api-1')['Config']['Env']
    private = stage / 'backend.env'
    private.write_text('\n'.join(env) + '\nCOMPANION_ENABLED=true\n')
    private.chmod(0o600)
    build(['docker', 'run', '--rm', '--network', 'ai-pet-backend_default', '--env-file', str(private),
           be_image, 'alembic', 'upgrade', 'head'], 'production-migration.log')
    import yaml
    compose = be / 'docker-compose.yml'
    config = yaml.safe_load(compose.read_text())
    for service in ('web-api', 'memory-mcp', 'agent-worker'):
        config['services'][service]['image'] = be_image
    config['services']['web-api']['environment']['COMPANION_ENABLED'] = 'true'
    compose.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
    compose.chmod(0o600)
    run(['docker', 'compose', 'up', '-d', '--no-build', '--no-deps',
         'web-api', 'memory-mcp', 'agent-worker'], cwd=be)
    print('Backend switched; original image IDs and compose are backed up.', flush=True)


def activate_tools():
    import yaml
    private_config = voice / 'data/.config.yaml'
    shutil.copy2(private_config, stage / 'backup/voice-config.yaml')
    voice_config = yaml.safe_load(private_config.read_text())
    voice_config['companion_tools_enabled'] = True
    private_config.write_text(yaml.safe_dump(voice_config, allow_unicode=True, sort_keys=False))
    private_config.chmod(0o600)
    # 仅复用现有业务内部令牌。私有文件不复制到Git、不输出。
    env = inspect('ai-pet-backend-web-api-1')['Config']['Env']
    token = next(v.split('=', 1)[1] for v in env if v.startswith('INTERNAL_SERVICE_TOKEN='))
    private = root / 'companion.env'
    private.write_text('COMPANION_INTERNAL_TOKEN=' + token + '\nCOMPANION_BACKEND_URL=http://web-api:8000\n')
    private.chmod(0o600)
    compose = root / 'compose.json'
    config = json.loads(compose.read_text())
    service = config['services']['music-content-mcp']
    service['image'] = mcp_image
    service.setdefault('env_file', []).append(str(private))
    service.setdefault('networks', []).append('backend-internal')
    config.setdefault('networks', {})['backend-internal'] = dict(external=True, name='ai-pet-backend_default')
    compose.write_text(json.dumps(config, indent=2))
    compose.chmod(0o600)
    shutil.copytree(stage / 'server', root / 'server', dirs_exist_ok=True)
    run(['docker', 'compose', '-f', str(compose), 'up', '-d', '--no-deps', 'music-content-mcp'], cwd=root)
    compose = voice / 'docker-compose_all.yml'
    config = yaml.safe_load(compose.read_text())
    config['services']['xiaozhi-esp32-server']['image'] = voice_image
    compose.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
    compose.chmod(0o600)
    run(['docker', 'compose', '-f', str(compose), 'up', '-d', '--no-deps', 'xiaozhi-esp32-server'], cwd=voice)
    print('MCP and voice switched; gateway unchanged.', flush=True)


def rollback():
    private_backup = stage / 'backup/voice-config.yaml'
    if private_backup.exists():
        shutil.copy2(private_backup, voice / 'data/.config.yaml')
    for source, target, services in [
        ('voice-compose.yml', voice / 'docker-compose_all.yml', ['xiaozhi-esp32-server']),
        ('music-compose.json', root / 'compose.json', ['music-content-mcp']),
        ('backend-compose.yml', be / 'docker-compose.yml', ['web-api', 'memory-mcp', 'agent-worker'])]:
        shutil.copy2(stage / 'backup' / source, target)
        run(['docker', 'compose', '-f', str(target), 'up', '-d', '--no-build', '--no-deps'] + services,
            cwd=target.parent)
    # 新增表保留，避免丢失已接受的约定；旧应用不使用此表。
    print('Services rolled back; additive table retained.')


actions = dict(prepare=prepare, database_test=database_test, activate_backend=activate_backend,
               activate_tools=activate_tools, rollback=rollback)
actions[sys.argv[2]]()
