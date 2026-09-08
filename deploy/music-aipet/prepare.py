from pathlib import Path
import shutil, json
stage = Path('/opt/xiaozhi-music-stage-XHruglZa')
root = Path('/opt/xiaozhi-music-aipet')
assert not root.exists(), 'Existing deployment; abort'
root.mkdir(mode=0o700)
for name in ('server', 'Dockerfile', 'http_entry.py'):
    src = stage / name
    if src.is_dir():
        shutil.copytree(src, root / name)
    else:
        shutil.copy2(src, root / name)
def read_env(path):
    result = {}
    for line in path.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            result[k.strip()] = v.strip().strip(chr(34)).strip(chr(39))
    return result
music = read_env(stage / 'music.env')
content = read_env(stage / 'content.env')
assert 'MUSIC_U=' in music.get('NETEASE_COOKIE', '')
assert content.get('MINIMAX_API_KEY')
music.update(MUSIC_BIND_HOST='0.0.0.0', MUSIC_BIND_PORT='3060', MUSIC_PUBLIC_BASE_URL='http://39.107.143.71:8081', MUSIC_DEVICE_BASE_URL='http://39.107.143.71:8081', MUSIC_FFMPEG_PATH='/usr/bin/ffmpeg', MUSIC_GATEWAY_URL='http://music-gateway:3060')
for name, data in [('music.env', music), ('content.env', content)]:
    path = root / name
    path.write_text(''.join(f'{k}={v}\n' for k,v in data.items()))
    path.chmod(0o600)
base = dict(image='xiaozhi-music-aipet:20260908', restart='unless-stopped', networks=['xiaozhi'], read_only=True, tmpfs=['/tmp'], security_opt=['no-new-privileges:true'], logging=dict(driver='json-file', options={'max-size':'10m','max-file':'3'}))
gateway = dict(base, build='.', command=['python','music_gateway.py'], env_file=['music.env'], ports=['127.0.0.1:3060:3060'])
mcp = dict(base, env_file=['music.env','content.env'], depends_on=['music-gateway'])
compose = dict(services={'music-gateway':gateway,'music-content-mcp':mcp}, networks={'xiaozhi':dict(external=True,name='xiaozhi-server_default')})
(root/'compose.json').write_text(json.dumps(compose,indent=2))
print('Prepared; credentials private; MCP internal only')
