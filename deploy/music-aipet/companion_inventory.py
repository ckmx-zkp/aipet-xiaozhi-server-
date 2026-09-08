'''主机只读盘点，不输出令牌、用户姓名或记忆。'''
import json
import subprocess

code = '''
import asyncio, json
from sqlalchemy import select
from pet_common.models import Device
from pet_common.db import get_session_factory
async def main():
    async with get_session_factory()() as session:
        rows=(await session.scalars(select(Device))).all()
        print(json.dumps([dict(device_uid=r.device_uid,bound=r.user_id is not None) for r in rows]))
asyncio.run(main())
'''
print(subprocess.check_output(['docker', 'exec', 'ai-pet-backend-web-api-1', 'python', '-c', code]).decode())
for name in ['xiaozhi-esp32-server','xiaozhi-music-aipet-music-content-mcp-1']:
    state=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
    print(json.dumps(dict(name=name,image=state['Config']['Image'],running=state['State']['Running'],
                         networks=list(state['NetworkSettings']['Networks']))))
