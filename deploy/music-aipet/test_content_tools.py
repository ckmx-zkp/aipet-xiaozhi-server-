import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
here = Path(__file__).resolve().parent
sys.path.insert(0, str(here if (here / 'content_tools.py').exists() else here.parent))
from content_tools import CHAT_NEXT, FACT_NEXT, generate_content

def search_response():
    return {'stop_reason':'end_turn','content':[
        {'type':'server_tool_use','id':'search1','name':'web_search','input':{'query':'today'}},
        {'type':'web_search_tool_result','tool_use_id':'search1','content':[
            {'type':'web_search_result','title':'资料','url':'https://example.com/source'}]},
        {'type':'text','text':'已检索资料摘要，来源不一定发表于今天。'}]}

def answer(text='最终回答', reason='stop'):
    return {'choices':[{'message':{'content':text},'finish_reason':reason}]}

def encoded(data):
    return io.BytesIO(json.dumps(data).encode())

@patch.dict(os.environ, {'MINIMAX_API_KEY':'test-only','MINIMAX_BASE_URL':'https://api.minimax.cn/v1','MINIMAX_SEARCH_MODEL':'MiniMax-M3','ARK_API_KEY':'','ARK_BASE_URL':'','ARK_MODEL':''})
class ContentTests(unittest.TestCase):
    def test_fact_kinds_require_search_then_generation(self):
        for kind in ('zodiac','metaphysics'):
            with self.subTest(kind=kind), patch('urllib.request.urlopen', side_effect=[encoded(search_response()),encoded(answer('<think>隐藏</think>最终回答'))]) as call:
                result=generate_content(kind,'今日主题',context='背景',draft='草稿')
                self.assertTrue(result['success'])
                self.assertEqual(result['content'],'最终回答')
                self.assertTrue(result['search']['executed'])
                self.assertEqual(result['search']['sources'][0]['url'],'https://example.com/source')
                self.assertTrue(result['search']['searched_at'].endswith('+08:00'))
                self.assertEqual(call.call_count,2)
                req=call.call_args_list[0].args[0]
                self.assertTrue(req.full_url.endswith('/anthropic/v1/messages'))
                self.assertEqual(json.loads(req.data)['tools'][0]['type'],'web_search_20250305')
                self.assertIn('web_search',json.loads(req.data)['system'])
                second=json.loads(call.call_args_list[1].args[0].data)
                values=json.loads(second['messages'][1]['content'])
                self.assertEqual(values['draft'],'草稿')
                self.assertIn('summary',values['web_search'])
                self.assertIn(values['date_china'],json.loads(req.data)['messages'][0]['content'])

    def test_chat_skips_search_and_generates(self):
        with patch('urllib.request.urlopen', side_effect=[encoded(answer('<think>隐藏</think>讲个故事'))]) as call:
            result=generate_content('chat','讲个故事',context='背景',draft='草稿')
        self.assertTrue(result['success'])
        self.assertEqual(result['content'],'讲个故事')
        self.assertTrue(result['search']['skipped'])
        self.assertFalse(result['search']['executed'])
        self.assertEqual(call.call_count,1)
        req=call.call_args_list[0].args[0]
        self.assertTrue(req.full_url.endswith('/chat/completions'))
        body=json.loads(req.data)
        self.assertIn('娱乐陪聊',body['messages'][0]['content'])
        self.assertNotIn('web_search',json.loads(body['messages'][1]['content']))

    def test_chat_failure_tells_model_to_speak(self):
        with patch('urllib.request.urlopen',side_effect=HTTPError('url',429,'secret',{},None)):
            result=generate_content('chat','笑话')
        self.assertFalse(result['success'])
        self.assertEqual(result['error_code'],'rate_limited')
        self.assertEqual(result['next_action'],CHAT_NEXT)
        self.assertNotIn('secret',str(result))

    def assert_search_rejected(self,data,code):
        with patch('urllib.request.urlopen',side_effect=lambda *a,**k: encoded(data)) as call:
            result=generate_content('zodiac','天蝎座')
        self.assertEqual(result['error_code'],code)
        self.assertFalse(result['success'])
        self.assertEqual(result['next_action'],FACT_NEXT)
        self.assertEqual(call.call_count,2 if code == 'search_not_executed' else 1)

    def test_skipped_search_retries_once_then_generates(self):
        with patch('urllib.request.urlopen',side_effect=[encoded({'content':[]}),encoded(search_response()),encoded(answer())]) as call:
            result=generate_content('zodiac','天蝎座')
        self.assertTrue(result['success'])
        self.assertEqual(call.call_count,3)
        self.assertLessEqual(call.call_args_list[1].kwargs['timeout'],call.call_args_list[0].kwargs['timeout'])

    def test_model_claim_is_not_search(self):
        self.assert_search_rejected({'content':[{'type':'text','text':'我已联网'}]},'search_not_executed')

    def test_client_tool_call_is_not_server_search(self):
        data=search_response()
        data['content'][0]['type']='tool_use'
        self.assert_search_rejected(data,'search_not_executed')

    def test_unmatched_result_is_rejected(self):
        data=search_response()
        data['content'][1]['tool_use_id']='unrelated'
        self.assert_search_rejected(data,'search_no_sources')

    def test_tool_error_does_not_fallback(self):
        data=search_response()
        data['content'][1]['content']={'type':'web_search_tool_result_error','error_code':'unavailable'}
        self.assert_search_rejected(data,'search_no_sources')

    def test_unsafe_url_is_rejected(self):
        data=search_response()
        data['content'][1]['content'][0]['url']='javascript:alert(1)'
        self.assert_search_rejected(data,'search_no_sources')

    def test_search_summary_required(self):
        data=search_response()
        data['content'].pop()
        self.assert_search_rejected(data,'search_no_summary')

    def test_truncated_search_rejected(self):
        data=search_response()
        data['stop_reason']='max_tokens'
        self.assert_search_rejected(data,'search_incomplete')

    def test_search_network_failure_no_generation(self):
        with patch('urllib.request.urlopen',side_effect=TimeoutError) as call:
            result=generate_content('zodiac','天蝎座')
        self.assertEqual(result['error_code'],'search_timeout_or_network')
        self.assertEqual(result['next_action'],FACT_NEXT)
        self.assertEqual(call.call_count,1)

    def test_rate_limit_redacted(self):
        with patch('urllib.request.urlopen',side_effect=HTTPError('url',429,'secret',{},None)):
            result=generate_content('zodiac','天蝎座')
        self.assertEqual(result['error_code'],'rate_limited')
        self.assertEqual(result['next_action'],FACT_NEXT)
        self.assertNotIn('secret',str(result))

    def test_missing_key(self):
        with patch.dict(os.environ,{'MINIMAX_API_KEY':''}), patch('urllib.request.urlopen') as call:
            result=generate_content('chat','主题')
            self.assertEqual(result['error_code'],'not_configured')
            self.assertEqual(result['next_action'],CHAT_NEXT)
            call.assert_not_called()

    def test_input_limit(self):
        self.assertEqual(generate_content('chat','x'*6001)['error_code'],'input_too_long')

    def test_incomplete_thinking_not_spoken(self):
        with patch('urllib.request.urlopen',side_effect=[encoded(answer('<think>unfinished'))]):
            result=generate_content('chat','主题')
            self.assertFalse(result['success'])
            self.assertEqual(result['next_action'],CHAT_NEXT)

    def test_minimax_rate_limit_falls_back_to_ark(self):
        env={'ARK_API_KEY':'ark-test','ARK_BASE_URL':'https://ark.cn-beijing.volces.com/api/v3','ARK_MODEL':'deepseek-v4-flash-ga-260731'}
        with patch.dict(os.environ, env), patch('urllib.request.urlopen', side_effect=[HTTPError('url',429,'secret',{},None), encoded(answer('方舟笑话'))]) as call:
            result=generate_content('chat','笑话')
        self.assertTrue(result['success'])
        self.assertEqual(result['content'],'方舟笑话')
        self.assertEqual(result['model'],'deepseek-v4-flash-ga-260731')
        self.assertEqual(result['search']['fallback'],'ark')
        self.assertEqual(result['search']['provider'],'ark')
        self.assertEqual(call.call_count,2)
        self.assertTrue(call.call_args_list[1].args[0].full_url.endswith('/api/v3/chat/completions'))
        body=json.loads(call.call_args_list[1].args[0].data)
        self.assertEqual(body['thinking'],{'type':'disabled'})
        self.assertNotIn('secret',str(result))

    def test_ark_only_when_minimax_missing(self):
        env={'MINIMAX_API_KEY':'','ARK_API_KEY':'ark-test','ARK_BASE_URL':'https://ark.cn-beijing.volces.com/api/v3','ARK_MODEL':'deepseek-v4-flash-ga-260731'}
        with patch.dict(os.environ, env), patch('urllib.request.urlopen', side_effect=[encoded(answer('只走方舟'))]) as call:
            result=generate_content('chat','故事')
        self.assertTrue(result['success'])
        self.assertEqual(result['search']['provider'],'ark')
        self.assertEqual(call.call_count,1)

    def test_fact_search_unavailable_falls_back_without_claiming_search(self):
        env={'ARK_API_KEY':'ark-test','ARK_BASE_URL':'https://ark.cn-beijing.volces.com/api/v3','ARK_MODEL':'deepseek-v4-flash-ga-260731'}
        with patch.dict(os.environ, env), patch('urllib.request.urlopen', side_effect=[HTTPError('url',429,'secret',{},None), encoded(answer('未联网的娱乐运势'))]):
            result=generate_content('zodiac','天蝎座')
        self.assertTrue(result['success'])
        self.assertFalse(result['search']['executed'])
        self.assertEqual(result['search']['fallback'],'ark')
        self.assertIn('不要声称已经联网检索', result['next_action'])

    def test_generation_truncation_rejected(self):
        with patch('urllib.request.urlopen',side_effect=[encoded(answer(reason='length'))]):
            result=generate_content('chat','主题')
            self.assertEqual(result['error_code'],'generation_incomplete')
            self.assertEqual(result['next_action'],CHAT_NEXT)

if __name__ == '__main__':
    unittest.main()
