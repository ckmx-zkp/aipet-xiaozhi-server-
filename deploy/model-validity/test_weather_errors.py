import ast, asyncio, unittest
from pathlib import Path
from unittest.mock import patch
import httpx, os

source=Path(os.environ['WEATHER_SOURCE']) if 'WEATHER_SOURCE' in os.environ else Path(__file__).resolve().parents[2]/'xiaozhi-esp32-server/main/xiaozhi-server/plugins_func/functions/get_weather.py'
tree=ast.parse(source.read_text(encoding='utf-8'))
selected=[n for n in tree.body if isinstance(n,(ast.ClassDef,ast.AsyncFunctionDef)) and n.name in {'WeatherServiceError','fetch_city_info'}]
ns={'httpx':httpx,'HEADERS':{}}
exec(compile(ast.Module(body=selected,type_ignores=[]),str(source),'exec'),ns)
class WeatherErrorsTest(unittest.TestCase):
 def request(self,status,payload):
  transport=httpx.MockTransport(lambda request:httpx.Response(status,json=payload))
  client=httpx.AsyncClient(transport=transport)
  with patch.object(httpx,'AsyncClient',return_value=client):
   return asyncio.run(ns['fetch_city_info']('北京','test','weather.example'))
 def test_auth_is_not_city_not_found(self):
  for code in (401,403):
   with self.assertRaisesRegex(ns['WeatherServiceError'],'鉴权失败'):self.request(code,{'error':{}})
 def test_limit_is_distinct(self):
  with self.assertRaisesRegex(ns['WeatherServiceError'],'额度或频率'):self.request(429,{})
 def test_real_unknown_city(self):
  self.assertIsNone(self.request(200,{'code':'404'}))
 def test_success(self):
  self.assertEqual(self.request(200,{'code':'200','location':[{'name':'北京'}]})['name'],'北京')
 def test_missing_credentials(self):
  with self.assertRaisesRegex(ns['WeatherServiceError'],'尚未配置'):asyncio.run(ns['fetch_city_info']('北京','',''))
if __name__=='__main__':unittest.main()
