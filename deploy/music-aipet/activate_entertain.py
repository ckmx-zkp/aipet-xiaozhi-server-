'''Backup, build, and switch content MCP plus voice hint. No backend/gateway restart.'''
import json
import shutil
import subprocess
from pathlib import Path

root = Path('/opt/xiaozhi-music-aipet')
voice = Path('/opt/xiaozhi-server')
stage = Path('/opt/aipet-entertain-20260920')
mcp_image = 'xiaozhi-music-aipet:20260920-entertain'
voice_image = 'xiaozhi-aipet-server:v0.9.6-b16-entertain'


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    action = Path(__file__).name
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'prepare':
        stage.mkdir(mode=0o700, exist_ok=True)
        backup = stage / 'backup'
        backup.mkdir(mode=0o700, exist_ok=True)
        shutil.copy2(root / 'compose.json', backup / 'compose.json')
        shutil.copy2(root / 'server/content_tools.py', backup / 'content_tools.py')
        shutil.copy2(root / 'server/companion_tools.py', backup / 'companion_tools.py')
        shutil.copy2(voice / 'docker-compose_all.yml', backup / 'voice-compose.yml')
        shutil.copy2(stage / 'content_tools.py', root / 'server/content_tools.py')
        shutil.copy2(stage / 'companion_tools.py', root / 'server/companion_tools.py')
        (root / 'server/tests').mkdir(exist_ok=True)
        shutil.copy2(stage / 'test_content_tools.py', root / 'server/tests/test_content_tools.py')
        shutil.copy2(stage / 'test_companion_tools.py', root / 'server/tests/test_companion_tools.py')
        with (stage / 'mcp-build.log').open('w') as log:
            run(['docker', 'build', '-f', str(stage / 'Dockerfile.entertain'),
                 '-t', mcp_image, str(stage)], stdout=log, stderr=subprocess.STDOUT)
        with (stage / 'voice-build.log').open('w') as log:
            run(['docker', 'build', '-f', str(stage / 'Dockerfile.voice-entertain'),
                 '-t', voice_image, str(stage)], stdout=log, stderr=subprocess.STDOUT)
        print('images built; live unchanged')
    elif cmd == 'activate':
        compose = json.loads((root / 'compose.json').read_text())
        compose['services']['music-content-mcp']['image'] = mcp_image
        (root / 'compose.json').write_text(json.dumps(compose, indent=2))
        run(['docker', 'compose', '-f', str(root / 'compose.json'), 'up', '-d', '--no-deps',
             'music-content-mcp'], cwd=root)
        voice_compose = voice / 'docker-compose_all.yml'
        text = voice_compose.read_text()
        text = text.replace('xiaozhi-aipet-server:v0.9.6-b16-services-r2', voice_image)
        if voice_image not in text:
            raise SystemExit('voice compose image token not found')
        voice_compose.write_text(text)
        run(['docker', 'compose', '-f', str(voice_compose), 'up', '-d', '--no-deps',
             'xiaozhi-esp32-server'], cwd=voice)
        print('activated')
    elif cmd == 'rollback':
        backup = stage / 'backup'
        shutil.copy2(backup / 'compose.json', root / 'compose.json')
        shutil.copy2(backup / 'content_tools.py', root / 'server/content_tools.py')
        shutil.copy2(backup / 'companion_tools.py', root / 'server/companion_tools.py')
        shutil.copy2(backup / 'voice-compose.yml', voice / 'docker-compose_all.yml')
        run(['docker', 'compose', '-f', str(root / 'compose.json'), 'up', '-d', '--no-deps',
             'music-content-mcp'], cwd=root)
        run(['docker', 'compose', '-f', str(voice / 'docker-compose_all.yml'), 'up', '-d', '--no-deps',
             'xiaozhi-esp32-server'], cwd=voice)
        print('rolled back')
    else:
        raise SystemExit('Usage: prepare | activate | rollback')


if __name__ == '__main__':
    main()
