'''只对独立测试数据库中的虚构设备执行MCP写入验收。'''
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


def data(result):
    return result.data if isinstance(result.data, dict) else json.loads(result.content[0].text)


async def main():
    assert '@companion-test-db:' in os.environ['DATABASE_URL']
    headers = {'X-Companion-Token': os.environ['COMPANION_INTERNAL_TOKEN'],
               'X-Companion-Device': 'companion-test-device', 'X-Companion-Session': 'write-test'}
    async with Client(StreamableHttpTransport('http://127.0.0.1:3061/mcp', headers=headers)) as client:
        result = data(await client.call_tool('interaction_feedback',
            dict(preference='tone', value='gentle', evidence='请温柔一些')))
        assert result['success'] and result['status'] == 'candidate', result
        assert result['approval_required']
        args = dict(action='create', topic='一起分享读书感想',
            due_at=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(), request_id='mcp-write-test')
        result = data(await client.call_tool('followup_plan', args))
        assert result['success'], result
        item = result['result']['id']
        duplicate = data(await client.call_tool('followup_plan', args))
        assert duplicate['result']['id'] == item
        result = data(await client.call_tool('followup_plan', dict(action='list')))
        assert item in {r['id'] for r in result['result']}
        result = data(await client.call_tool('followup_plan', dict(action='cancel', item_id=item)))
        assert result['success'] and result['result']['status'] == 'cancelled'
        result = data(await client.call_tool('followup_plan', dict(action='complete', item_id=item)))
        assert not result['success']
    print('PASS: real MCP feedback candidate, create/retry/list/cancel and terminal conflict')


asyncio.run(main())
