'''六个陪伴工具：可信设备作用域、版本化策略、联网证据和业务状态。'''
import asyncio
import hashlib
import hmac
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode
from uuid import uuid4

from content_tools import CHAT_NEXT, generate_content, search_information, SearchFailure
from personality_policies import build_strategy

SLOTS = asyncio.Semaphore(2)
CACHE = OrderedDict()
CACHE_TTL = 180
SITUATIONS = {'normal', 'busy', 'tired', 'upset', 'conflict', 'celebrate'}


def failed(code):
    return dict(success=False, error_code=code,
                next_action='明确告知本次工具未完成，不编造检索、记忆、反馈或提醒结果。')


def trusted_scope(headers=None):
    if headers is None and os.environ.get('COMPANION_TRANSPORT') == 'cloud-stdio':
        headers = {
            'x-companion-token': os.environ.get('COMPANION_INTERNAL_TOKEN', ''),
            'x-companion-device': os.environ.get('COMPANION_CLOUD_DEVICE', ''),
            'x-companion-session': os.environ.get('COMPANION_CLOUD_SESSION', ''),
        }
    if headers is None:
        from fastmcp.server.dependencies import get_http_headers
        headers = get_http_headers()
    headers = {k.lower(): v for k, v in headers.items()}
    expected = os.environ.get('COMPANION_INTERNAL_TOKEN', '')
    actual = headers.get('x-companion-token', '')
    if not expected or not hmac.compare_digest(expected.encode(), actual.encode()):
        raise ValueError('untrusted_scope')
    device = headers.get('x-companion-device', '').strip().lower()
    session = headers.get('x-companion-session', '')
    if not re.fullmatch(r'[a-z0-9:_-]{1,128}', device) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,128}', session):
        raise ValueError('invalid_scope')
    return device, session


def backend(scope, path, method='GET', body=None):
    base = os.environ.get('COMPANION_BACKEND_URL', 'http://web-api:8000').rstrip('/')
    if base != 'http://web-api:8000':
        raise ValueError('invalid_backend_endpoint')
    url = base + '/api/internal/companion/devices/' + quote(scope[0], safe='') + path
    request = urllib.request.Request(url, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'X-Internal-Token': os.environ['COMPANION_INTERNAL_TOKEN'],
                 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=5) as response:
        raw = response.read(131073)
    if len(raw) > 131072:
        raise ValueError('backend_response_too_large')
    return json.loads(raw)


def snapshot_for(scope, query=''):
    return backend(scope, '/context?' + urlencode({'q': query[:200]}))


def cache_put(scope, topic, evidence):
    now = time.monotonic()
    for key in list(CACHE):
        if CACHE[key][0] <= now:
            del CACHE[key]
    while len(CACHE) >= 128:
        CACHE.popitem(last=False)
    key = uuid4().hex
    CACHE[key] = (now + CACHE_TTL, scope, topic.strip(), evidence)
    return key


def cache_get(key, scope, topic):
    item = CACHE.get(key)
    if not item or item[0] <= time.monotonic() or item[1] != scope or item[2] != topic.strip():
        raise ValueError('search_expired_or_scope_mismatch')
    return item[3]


def public_search(topic):
    if not isinstance(topic, str) or not topic.strip() or len(topic) > 6000:
        raise ValueError('invalid_topic')
    key = os.environ.get('MINIMAX_API_KEY', '')
    base = os.environ.get('MINIMAX_BASE_URL', 'https://api.minimax.cn/v1').rstrip('/')
    if not key or base not in ('https://api.minimax.cn/v1', 'https://api.minimaxi.com/v1', 'https://api.minimax.io/v1'):
        raise ValueError('search_not_configured')
    date = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    return search_information(base, key, 'chat', topic, date)


async def guarded(operation):
    try:
        scope = trusted_scope()
        if SLOTS.locked():
            return failed('busy')
        async with SLOTS:
            return await operation(scope)
    except urllib.error.HTTPError as error:
        return failed('backend_or_provider_http_' + str(error.code))
    except (urllib.error.URLError, TimeoutError, OSError):
        return failed('network_unavailable')
    except SearchFailure as error:
        return failed(str(error))
    except (ValueError, KeyError, TypeError):
        return failed('invalid_request_or_scope')


async def personal_content(kind, topic, context='', draft='', situation='normal', search_id=''):
    async def operation(scope):
        if situation not in SITUATIONS or len(context) > 2000 or len(draft) > 2000:
            raise ValueError('invalid_request')
        snapshot = await asyncio.to_thread(snapshot_for, scope, topic)
        strategy = build_strategy(snapshot, situation)
        evidence = cache_get(search_id, scope, topic) if search_id else None
        data = json.dumps(dict(pet=snapshot.get('pet'), memories=snapshot.get('memories'),
                               context=context), ensure_ascii=False)[:6000]
        result = await asyncio.to_thread(generate_content, kind, topic, data, draft, evidence, strategy)
        result['strategy'] = strategy
        result['search_reused'] = bool(search_id)
        return result
    result = await guarded(operation)
    if kind == 'chat' and not result.get('success'):
        result['next_action'] = CHAT_NEXT
    return result


def register_companion_tools(mcp):
    @mcp.tool()
    async def conversation_plan(situation: str = 'normal') -> dict:
        '''读取当前设备主人、宠物、关系与已批准偏好，组合12星座和16MBTI专属版本化沟通策略。情境normal/busy/tired/upset/conflict/celebrate。不生成外部事实。'''
        async def operation(scope):
            if situation not in SITUATIONS:
                raise ValueError('invalid_situation')
            snapshot = await asyncio.to_thread(snapshot_for, scope)
            return dict(success=True, strategy=build_strategy(snapshot, situation))
        return await guarded(operation)

    @mcp.tool()
    async def context_search(topic: str) -> dict:
        '''检索当前主人相关记忆并通过MiniMax实际联网检索公开主题。请只传公开搜索主题，不传姓名、联系方式或私密原文。返回search_id，同一设备同一会话同一topic在180秒内可供companion_reply复用。'''
        async def operation(scope):
            snapshot = await asyncio.to_thread(snapshot_for, scope, topic)
            evidence = await asyncio.to_thread(public_search, topic)
            key = cache_put(scope, topic, evidence)
            return dict(success=True, search_id=key, expires_in=CACHE_TTL,
                        search=evidence, memories=snapshot.get('memories', []),
                        strategy=build_strategy(snapshot))
        return await guarded(operation)

    @mcp.tool()
    async def companion_reply(topic: str, context: str = '', situation: str = 'normal', search_id: str = '') -> dict:
        '''人格化陪伴回复：按当前主人与宠物的真实档案、关系、批准偏好及情境生成。必经MiniMax真实联网；可复用context_search相同topic的search_id。拒绝伪造记忆、诊断或排他关系。'''
        return await personal_content('chat', topic, context, situation=situation, search_id=search_id)

    @mcp.tool()
    async def interaction_feedback(preference: str, value: str, evidence: str) -> dict:
        '''仅用户明确表达偏好时记录候选记忆，用户在App批准后才影响长期策略。preference/value：reply_length short|medium|long；support_style listen|advice|balanced；question_frequency none|one；tone gentle|direct|playful。不凭星座推断偏好。'''
        async def operation(scope):
            result = await asyncio.to_thread(backend, scope, '/feedback', 'POST',
                dict(preference=preference, value=value, evidence=evidence))
            return dict(success=True, **result)
        return await guarded(operation)

    @mcp.tool()
    async def shared_activity(activity: str, topic: str = '', situation: str = 'normal') -> dict:
        '''联网设计一个轻量共同活动：story故事、quiz趣味问答、reflection日常回顾、relax休息、music音乐话题。返回可直接开始的第一步，不声称已播放音乐、控制硬件或完成活动。'''
        if activity not in {'story', 'quiz', 'reflection', 'relax', 'music'}:
            return failed('unsupported_activity')
        result = await personal_content('chat', topic or activity,
            '设计共同活动' + activity + '，先给一个短小步骤并等待用户回应。不作医疗建议，不宣称控制硬件。',
            situation=situation)
        result['activity'] = activity
        result['state'] = 'proposed' if result.get('success') else 'failed'
        return result

    @mcp.tool()
    async def followup_plan(action: str, topic: str = '', due_at: str = '', item_id: str = '', request_id: str = '', status: str = 'pending', offset: int = 0) -> dict:
        '''管理用户明确同意的约定。action=create/list/complete/cancel；create需要topic与含时区due_at（未来90天内），可给稳定request_id。list每页20条。只在到期后的合适会话中关心，08到21点；不能保证离线板子定时唤醒。取消/完成需item_id。'''
        async def operation(scope):
            if action == 'create':
                key = request_id or hashlib.sha256((scope[1] + topic + due_at).encode()).hexdigest()
                result = await asyncio.to_thread(backend, scope, '/followups', 'POST',
                    dict(request_id=key, topic=topic, due_at=due_at))
            elif action == 'list':
                if status not in {'pending', 'completed', 'cancelled'} or offset < 0:
                    raise ValueError('invalid_pagination')
                result = await asyncio.to_thread(backend, scope,
                    '/followups?' + urlencode(dict(status=status, limit=20, offset=offset)))
            elif action in {'complete', 'cancel'} and re.fullmatch(r'[a-zA-Z0-9-]{1,64}', item_id):
                result = await asyncio.to_thread(backend, scope, '/followups/' + item_id, 'PATCH',
                    dict(status='completed' if action == 'complete' else 'cancelled'))
            else:
                raise ValueError('invalid_action')
            return dict(success=True, result=result, delivery='next_suitable_session')
        return await guarded(operation)
