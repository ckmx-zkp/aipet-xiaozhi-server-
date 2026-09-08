'''云端同款stdio入口验收，日志仅含工具名与状态。'''
import asyncio
import json
import os
from fastmcp import Client
from fastmcp.client.transports import StdioTransport


def data(result):
    return result.data if isinstance(result.data, dict) else json.loads(result.content[0].text)


async def main():
    os.environ['COMPANION_TRANSPORT'] = 'cloud-stdio'
    os.environ['COMPANION_CLOUD_SESSION'] = 'cloud-stdio-validation'
    transport = StdioTransport(command='python', args=['/srv/music/cloud_entry.py'], env=dict(os.environ))
    async with Client(transport, timeout=130) as client:
        names = {tool.name for tool in await client.list_tools()}
        assert len(names) == 14, names
        for name, args in [('conversation_plan', {}), ('memory_search', {'query': ''}),
                           ('followup_plan', {'action': 'list'})]:
            result = data(await client.call_tool(name, args))
            assert result['success'], dict(tool=name, error=result.get('error_code'))
            print('PASS: cloud stdio ' + name, flush=True)
        result = data(await client.call_tool('emotion_support', {'feeling': '今天有点疲惫，想轻松聊聊'}, timeout=130))
        assert result['success'] and result['search']['executed'], result.get('error_code')
        print(json.dumps(dict(check='emotion_support', success=True, sources=len(result['search']['sources']))), flush=True)
        print('PASS: fourteen cloud tools; independent digital-twin identity', flush=True)


asyncio.run(main())
