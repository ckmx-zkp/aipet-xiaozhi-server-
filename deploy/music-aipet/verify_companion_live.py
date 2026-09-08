'''容器内真实MCP验证：不写真实用户的记忆与约定，不输出私人内容。'''
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, '/srv/music')
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


def data(result):
    return result.data if isinstance(result.data, dict) else json.loads(result.content[0].text)


async def main():
    url = os.environ.get('VERIFY_MCP_URL', 'http://music-content-mcp:3061/mcp')
    headers = {'X-Companion-Token': os.environ['COMPANION_INTERNAL_TOKEN'],
               'X-Companion-Device': os.environ['COMPANION_TEST_DEVICE'],
               'X-Companion-Session': 'companion-release-validation'}
    async with Client(StreamableHttpTransport(url, headers=headers), timeout=130) as client:
        names = {tool.name for tool in await client.list_tools()}
        assert len(names) == 10, names
        assert {'conversation_plan', 'context_search', 'companion_reply', 'interaction_feedback',
                'shared_activity', 'followup_plan', 'daily_chat', 'zodiac_fortune',
                'metaphysics_analysis', 'search_netease_music'} == names
        plan = data(await client.call_tool('conversation_plan', {'situation': 'busy'}))
        assert plan['success'], plan
        print(json.dumps(dict(check='plan', success=True, version=plan['strategy']['version'])), flush=True)
        listing = data(await client.call_tool('followup_plan', {'action': 'list'}))
        assert listing['success'], listing
        # 非法写请求必须失败且不得生成持久记录。
        invalid = data(await client.call_tool('interaction_feedback',
            {'preference': 'invalid', 'value': 'invalid', 'evidence': 'validation'}))
        assert not invalid['success']
        topic = '白露节气有哪些传统习俗'
        started = time.monotonic()
        search = data(await client.call_tool('context_search', {'topic': topic}, timeout=130))
        assert search['success'], search
        assert search['search']['executed'] and search['search']['sources']
        reply = data(await client.call_tool('companion_reply',
            {'topic': topic, 'search_id': search['search_id'], 'situation': 'busy'}, timeout=130))
        assert reply['success'] and reply['search_reused'], reply
        assert reply['search']['searched_at'] == search['search']['searched_at']
        print(json.dumps(dict(check='search_and_reply', success=True, reused=True,
            elapsed=round(time.monotonic()-started, 2), sources=len(reply['search']['sources']),
            characters=len(reply['content'])), ensure_ascii=False), flush=True)
        calls = [
            ('shared_activity', dict(activity='quiz', topic='白露节气趣味问答')),
            ('daily_chat', dict(topic='适合午休的轻松活动')),
            ('zodiac_fortune', dict(zodiac='处女座')),
            ('metaphysics_analysis', dict(question='白露节气在传统文化中的寓意')),
        ]
        for name, args in calls:
            started = time.monotonic()
            result = data(await client.call_tool(name, args, timeout=130))
            assert result['success'], dict(tool=name, error=result.get('error_code'))
            assert result['search']['executed'] and result['search']['sources']
            assert result['strategy']['version'] == plan['strategy']['version']
            print(json.dumps(dict(check=name, success=True, elapsed=round(time.monotonic()-started, 2),
                sources=len(result['search']['sources']), characters=len(result['content']))), flush=True)
    async with Client(url, timeout=15) as client:
        assert not data(await client.call_tool('conversation_plan', {}))['success']
    headers['X-Companion-Session'] = 'another-session'
    async with Client(StreamableHttpTransport(url, headers=headers), timeout=15) as client:
        result = data(await client.call_tool('companion_reply', {'topic': topic, 'search_id': search['search_id']}))
        assert not result['success']
    print('PASS: ten tools, real search/reuse, no-auth rejection, cross-session rejection', flush=True)


asyncio.run(main())
