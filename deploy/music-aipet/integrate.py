from pathlib import Path
import json, shutil, subprocess
stage=Path('/opt/xiaozhi-music-stage-XHruglZa')
backup=stage/'integration-backup'
backup.mkdir(mode=0o700)
nginx=Path('/opt/ai-pet/ai-pet-app/nginx.conf')
settings=Path('/opt/xiaozhi-server/data/.mcp_server_settings.json')
shutil.copy2(nginx,backup/'nginx.conf')
old=nginx.read_text()
assert old.count('    location / {')==1
assert '/audio_ogg/' not in old
addition='''    location ^~ /audio_ogg/ {
        proxy_pass http://127.0.0.1:3060;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_read_timeout 600s;
        access_log off;
    }
    location ^~ /lyric/ {
        proxy_pass http://127.0.0.1:3060;
        access_log off;
    }

'''
config=json.loads(settings.read_text()) if settings.exists() else {}
if settings.exists():
    shutil.copy2(settings,backup/'mcp-settings.json')
else:
    (backup/'settings-was-absent').touch()
servers=config.setdefault('mcpServers',{})
assert 'aipet_music_content' not in servers
servers['aipet_music_content']={'url':'http://music-content-mcp:3061/mcp','transport':'streamable-http','timeout':60,'sse_read_timeout':120}
try:
    nginx.write_text(old.replace('    location / {',addition+'    location / {'))
    subprocess.run(['docker','exec','ai-pet-app-web','nginx','-t'],check=True)
    subprocess.run(['docker','exec','ai-pet-app-web','nginx','-s','reload'],check=True)
    settings.write_text(json.dumps(config,indent=2))
except Exception:
    nginx.write_text(old)
    subprocess.run(['docker','exec','ai-pet-app-web','nginx','-s','reload'])
    raise
print('Global MCP configured for all new sessions; signed audio proxy enabled; backup='+str(backup))
