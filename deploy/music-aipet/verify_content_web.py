'''在候选容器或线上容器内验证三个工具的真实搜索及来源。'''
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.environ.get('CONTENT_SOURCE_DIR', '/srv/music'))
from content_tools import generate_content
from fastmcp import Client

TOPICS = [
    ('zodiac', '处女座今日运势', 'zodiac_fortune', 'zodiac'),
    ('metaphysics', '二十四节气中白露的传统文化寓意是什么？', 'metaphysics_analysis', 'question'),
    ('chat', '今天有哪些适合放松身心的科学方法？', 'daily_chat', 'topic'),
]

def check(kind, result, elapsed):
    evidence = result.get('search', {})
    row = dict(kind=kind, success=result.get('success'), error_code=result.get('error_code'),
               elapsed_seconds=round(elapsed, 2), search_model=evidence.get('model'),
               executed=evidence.get('executed'), query_count=evidence.get('query_count'),
               searched_at=evidence.get('searched_at'), sources=evidence.get('sources'),
               characters=len(result.get('content', '')))
    print(json.dumps(row, ensure_ascii=False), flush=True)
    assert result.get('success'), row
    assert evidence.get('executed') and evidence.get('query_count', 0) > 0
    assert evidence.get('sources') and evidence.get('model') == 'MiniMax-M3'
    assert datetime.fromisoformat(evidence['searched_at']).date() == datetime.now(timezone(timedelta(hours=8))).date()

async def main():
    if os.environ.get('VERIFY_VIA_MCP') == '1':
        async with Client('http://music-content-mcp:3061/mcp', timeout=130) as client:
            for kind, topic, tool, arg in TOPICS:
                started=time.monotonic()
                result=await client.call_tool(tool, {arg:topic}, timeout=130)
                data=result.data if isinstance(result.data, dict) else json.loads(result.content[0].text)
                check(kind,data,time.monotonic()-started)
    else:
        for kind, topic, _, _ in TOPICS:
            started=time.monotonic()
            check(kind,generate_content(kind,topic),time.monotonic()-started)
asyncio.run(main())
