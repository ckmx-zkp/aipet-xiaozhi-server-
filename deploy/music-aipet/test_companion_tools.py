'''策略覆盖、身份隔离与联网失败路径。'''
import asyncio
import copy
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

here = Path(__file__).resolve().parent
sys.path.insert(0, str(here if (here / 'companion_tools.py').exists() else here.parent))
import companion_tools as tools
from content_tools import CHAT_NEXT
from personality_policies import SIGN_PROFILES, MBTI_PROFILES, build_strategy


class CompanionTests(unittest.TestCase):
    def setUp(self):
        tools.CACHE.clear()

    def test_all_192_profiles_and_no_mutation(self):
        self.assertEqual(len(SIGN_PROFILES), 12)
        self.assertEqual(len(MBTI_PROFILES), 16)
        outputs = set()
        for sign in SIGN_PROFILES:
            for mbti in MBTI_PROFILES:
                source = dict(pet=dict(sun_sign=sign, mbti=mbti))
                original = copy.deepcopy(source)
                strategy = build_strategy(source)
                outputs.add((strategy['voice'], tuple(strategy['guidance'])))
                self.assertEqual(source, original)
        self.assertEqual(len(outputs), 192)

    def test_preference_wins_and_unknown_ignored(self):
        result = build_strategy(dict(owner=dict(mbti='INTJ'),
            approved_preferences=dict(reply_length='long', tone='invalid')), 'busy')
        self.assertEqual(result['reply_length'], 'long')
        self.assertEqual(result['question_frequency'], 'none')
        self.assertEqual(result['tone'], 'gentle')

    def test_untrusted_scope_rejected(self):
        with patch.dict(os.environ, {'COMPANION_INTERNAL_TOKEN': 'unit-secret'}):
            for headers in ({}, {'x-companion-token': 'forged'},
                {'x-companion-token': 'unit-secret', 'x-companion-device': '../other', 'x-companion-session': 's'}):
                with self.assertRaises(ValueError):
                    tools.trusted_scope(headers)
            self.assertEqual(tools.trusted_scope({'X-Companion-Token': 'unit-secret',
                'X-Companion-Device': 'AA:BB:CC', 'X-Companion-Session': 's'}), ('aa:bb:cc', 's'))

    def test_cache_device_session_topic_and_expiry(self):
        key = tools.cache_put(('device', 'session'), 'topic', {'executed': True})
        self.assertTrue(tools.cache_get(key, ('device', 'session'), 'topic')['executed'])
        for scope, topic in [(('other', 'session'), 'topic'), (('device', 'other'), 'topic'),
                             (('device', 'session'), 'different')]:
            with self.assertRaises(ValueError):
                tools.cache_get(key, scope, topic)
        with patch.object(tools.time, 'monotonic', return_value=float('inf')):
            with self.assertRaises(ValueError):
                tools.cache_get(key, ('device', 'session'), 'topic')

    def test_cache_bounded(self):
        for i in range(150):
            tools.cache_put(('d', 's'), str(i), {})
        self.assertEqual(len(tools.CACHE), 128)

    def test_reply_reuses_only_scoped_evidence(self):
        evidence = dict(executed=True, sources=[dict(url='https://example.org')], summary='test')
        key = tools.cache_put(('d', 's'), 'topic', evidence)
        with patch.object(tools, 'trusted_scope', return_value=('d', 's')), \
             patch.object(tools, 'snapshot_for', return_value={}), \
             patch.object(tools, 'generate_content', return_value={'success': True}) as generate:
            result = asyncio.run(tools.personal_content('chat', 'topic', search_id=key))
            self.assertTrue(result['search_reused'])
            self.assertIs(generate.call_args.args[4], evidence)
        with patch.object(tools, 'trusted_scope', return_value=('other', 's')), \
             patch.object(tools, 'snapshot_for', return_value={}), \
             patch.object(tools, 'generate_content') as generate:
            self.assertFalse(asyncio.run(tools.personal_content('chat', 'topic', search_id=key))['success'])
            generate.assert_not_called()

    def test_backend_failure_does_not_generate(self):
        with patch.object(tools, 'trusted_scope', return_value=('d', 's')), \
             patch.object(tools, 'snapshot_for', side_effect=TimeoutError), \
             patch.object(tools, 'generate_content') as generate:
            result = asyncio.run(tools.personal_content('chat', 'topic'))
            self.assertFalse(result['success'])
            self.assertEqual(result['next_action'], CHAT_NEXT)
            generate.assert_not_called()

    def test_chat_generation_failure_tells_model_to_speak(self):
        with patch.object(tools, 'trusted_scope', return_value=('d', 's')), \
             patch.object(tools, 'snapshot_for', return_value={}), \
             patch.object(tools, 'generate_content',
                          return_value={'success': False, 'error_code': 'rate_limited',
                                        'next_action': 'stale'}):
            result = asyncio.run(tools.personal_content('chat', '笑话'))
            self.assertFalse(result['success'])
            self.assertEqual(result['next_action'], CHAT_NEXT)

    def test_exact_six_registered_tools_and_no_identity_arguments(self):
        import inspect
        registered = {}
        class MCP:
            def tool(self):
                def register(func):
                    registered[func.__name__] = func
                    return func
                return register
        tools.register_companion_tools(MCP())
        self.assertEqual(set(registered), {'conversation_plan', 'context_search', 'companion_reply',
            'interaction_feedback', 'shared_activity', 'followup_plan'})
        for func in registered.values():
            self.assertFalse({'device_id', 'user_id', 'session_id', 'token'} & set(inspect.signature(func).parameters))


if __name__ == '__main__':
    unittest.main()
