'''容器内为独立数字分身创建普通用户和虚拟设备，不复用任何宠物资料。'''
import asyncio
import json
import sys
from pwdlib import PasswordHash
from sqlalchemy import select
from pet_common.db import get_session_factory
from pet_common.models import User, Device, PersonaProfile, AuditLog


async def main():
    credentials = json.load(sys.stdin)
    async with get_session_factory()() as session:
        assert not await session.scalar(select(User).where(User.login_name == credentials['login_name']))
        assert not await session.scalar(select(Device).where(Device.device_uid == 'cloud-agent-2323485'))
        user = User(login_name=credentials['login_name'],
                    password_hash=PasswordHash.recommended().hash(credentials['password']), role='user')
        session.add(user)
        await session.flush()
        device = Device(user_id=user.id, device_uid='cloud-agent-2323485',
                        binding_id=credentials['binding_id'], name='赛博分身小智',
                        capabilities={'companion_kind': 'digital_twin', 'transport': 'cloud_mcp'})
        session.add(device)
        await session.flush()
        session.add(PersonaProfile(user_id=user.id, device_id=device.id,
            dossier=dict(identity='你是赛博分身小智，一个数字分身与对话伙伴，不是宠物。不冒充真人本人，不编造未提供的个人经历。',
                         background=[], roles=['数字分身', '聊天伙伴'], goals=['真诚交流', '尊重边界'],
                         evolution_rules=['明确偏好经用户批准后长期采用'], relationship='平等尊重的交流伙伴')))
        session.add(AuditLog(actor='service:cloud-provision', action='cloud_companion_created',
                            target_type='device', target_id=str(device.id), detail={'kind':'digital_twin'}))
        await session.commit()
        print(json.dumps(dict(user_id=user.id, device_id=device.id, device_uid=device.device_uid)))


asyncio.run(main())
