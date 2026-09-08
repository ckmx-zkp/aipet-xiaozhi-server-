'''在语音容器内验证真实原生客户端、四块实体板作用域和重连；不执行硬件动作。'''
import asyncio
import json
from types import SimpleNamespace

from config.config_loader import load_config
from core.providers.tools.server_mcp.mcp_manager import ServerMCPManager
from core.providers.tools.server_mcp.companion_scope import COMPANION_HINT

DEVICES = ['8c:fd:49:0c:a8:78', '8c:fd:49:0c:b2:44', '90:e5:b1:a8:ed:80', 'b4:3a:45:f3:9b:70']


async def main():
    config = await load_config()
    assert config.get('companion_tools_enabled') is True
    assert config.get('business_api', {}).get('token')
    from core.connection import ConnectionHandler
    messages = []
    conn = SimpleNamespace(config=config, dialogue=SimpleNamespace(update_system_message=messages.append))
    ConnectionHandler.change_system_prompt(conn, 'test')
    assert COMPANION_HINT in conn.prompt
    ConnectionHandler.change_system_prompt(conn, conn.prompt)
    assert conn.prompt.count(COMPANION_HINT) == 1
    print('PASS: production config and system prompt enabled', flush=True)
    for index, device in enumerate(DEVICES):
        conn = SimpleNamespace(config=config, device_id=device,
            session_id='companion-native-validation-' + str(index), func_handler=None)
        manager = ServerMCPManager(conn)
        await manager._init_server('aipet_music_content', manager.load_config()['aipet_music_content'])
        try:
            assert len(manager.get_all_tools()) == 10
            result = await manager.execute_tool('conversation_plan', {'situation': 'normal'})
            assert json.loads(result.content[0].text)['success']
            if index == 0:
                await manager.clients['aipet_music_content'].cleanup()
                result = await manager.execute_tool('conversation_plan', {'situation': 'busy'})
                assert json.loads(result.content[0].text)['success']
            print('PASS: native MCP scope ' + device, flush=True)
        finally:
            await manager.cleanup_all()


asyncio.run(main())
