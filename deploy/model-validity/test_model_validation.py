import importlib.util
from pathlib import Path
import unittest
p=Path(__file__).parents[2]/"xiaozhi-esp32-server/main/xiaozhi-server/core/model_validation.py"
spec=importlib.util.spec_from_file_location("validation",p)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_blank_and_placeholder_keys_rejected(self):
  for key in ("", "  ", "你的密钥", "your_api_key", "xxxx"):
   with self.assertRaises(m.ProbeFailure): m.preflight("llm",{"type":"openai","api_key":key})
 def test_optional_proxy_does_not_invalidate(self):
  m.preflight("llm",{"type":"openai","api_key":"test-key","http_proxy":""})
 def test_transient_failure_does_not_claim_expiry_or_leak(self):
  r=m.classify(RuntimeError("https://example/?token=private-secret"))
  self.assertEqual(r['status'],'unknown'); self.assertNotIn('private-secret',r['reason'])
 def test_auth_and_quota_are_invalid(self):
  for text in ('unauthorized token=secret', 'insufficient quota secret'):
   r=m.classify(RuntimeError(text)); self.assertEqual(r['status'],'invalid'); self.assertNotIn('secret',r['reason'])
 def test_fixture_is_synthetic_pcm(self):
  import wave
  with wave.open(str(p.with_name('model_validation_sample.wav')),'rb') as f:
   self.assertEqual((f.getnchannels(),f.getsampwidth(),f.getframerate()),(1,2,16000))
   self.assertGreater(f.getnframes(),1000)
class VisionTests(unittest.IsolatedAsyncioTestCase):
 async def check_answer(self, answer):
  from unittest.mock import patch
  from types import SimpleNamespace
  class Client:
   def __init__(self, **kwargs):self.chat=SimpleNamespace(completions=self)
   async def __aenter__(self):return self
   async def __aexit__(self,*args):pass
   async def create(self, **kwargs):return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=answer))])
  with patch.dict('sys.modules',{'openai':SimpleNamespace(AsyncOpenAI=Client)}), patch.object(m.secrets,'SystemRandom') as random:
   random.return_value.sample.return_value=['blue','yellow']
   return await m.probe('vllm',{'type':'openai','model_name':'test','base_url':'https://example.invalid/v1','api_key':'test'})
 async def test_correct_pixels_required(self):
  self.assertIn('识别正确',await self.check_answer('Blue, yellow'))
 async def test_text_or_reasoning_is_not_visual_success(self):
  for answer in ['I cannot see images','Red, green','<think>blue,yellow</think>']:
   with self.assertRaises(m.ProbeFailure):await self.check_answer(answer)
if __name__=='__main__': unittest.main()
