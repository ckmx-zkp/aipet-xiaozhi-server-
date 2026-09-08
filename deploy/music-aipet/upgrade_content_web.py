'''候选验证通过后，备份并只更新全局内容 MCP 容器。'''
import json
import shutil
import subprocess
import sys
from pathlib import Path
stage=Path('/opt/xiaozhi-content-web-jt7IE3Bs')
root=Path('/opt/xiaozhi-music-aipet')
backup=stage/'backup'
new_image='xiaozhi-music-aipet:20260908-web'
compose=root/'compose.json'
content=root/'server/content_tools.py'
def run(args, **kw):
    return subprocess.run(args,check=True,**kw)
if sys.argv[1:] == ['prepare']:
    backup.mkdir(mode=0o700)
    shutil.copy2(compose,backup/'compose.json')
    shutil.copy2(content,backup/'content_tools.py')
    shutil.copy2(root/'server/tests/test_content_tools.py',backup/'test_content_tools.py')
    compile((stage/'code/content_tools.py').read_text(),str(content),'exec')
    shutil.copy2(stage/'code/content_tools.py',content)
    shutil.copy2(stage/'code/test_content_tools.py',root/'server/tests/test_content_tools.py')
    with (stage/'build.log').open('w') as log:
        run(['docker','build','-t',new_image,str(root)],stdout=log,stderr=subprocess.STDOUT)
    print('Image built; live service unchanged')
elif sys.argv[1:] == ['activate']:
    config=json.loads(compose.read_text())
    config['services']['music-content-mcp']['image']=new_image
    compose.write_text(json.dumps(config,indent=2))
    try:
        run(['docker','compose','-f',str(compose),'up','-d','--no-deps','music-content-mcp'],cwd=root)
    except Exception:
        shutil.copy2(backup/'compose.json',compose)
        run(['docker','compose','-f',str(compose),'up','-d','--no-deps','music-content-mcp'],cwd=root)
        raise
    print('Content MCP upgraded; music gateway unchanged')
elif sys.argv[1:] == ['rollback']:
    shutil.copy2(backup/'compose.json',compose)
    shutil.copy2(backup/'content_tools.py',content)
    shutil.copy2(backup/'test_content_tools.py',root/'server/tests/test_content_tools.py')
    run(['docker','compose','-f',str(compose),'up','-d','--no-deps','music-content-mcp'],cwd=root)
    print('Rolled back to pre-upgrade deployment')
else:
    raise SystemExit('Usage: prepare | activate | rollback')
