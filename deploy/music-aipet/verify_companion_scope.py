'''可本地运行的可信头绑定回归。'''
import importlib.util
from pathlib import Path
from types import SimpleNamespace

source = Path(__file__).resolve().parents[2] / 'xiaozhi-esp32-server/main/xiaozhi-server/core/providers/tools/server_mcp'
spec = importlib.util.spec_from_file_location('scope', source / 'companion_scope.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
config = dict(url='http://example', headers={'x-companion-device': 'forged',
    'X-COMPANION-TOKEN': 'forged', 'ordinary': 'retained'})
conn = SimpleNamespace(device_id='AA:BB:CC:DD:EE:FF', session_id='real-session',
    config={'business_api': {'token': 'unit-secret'}})
result = module.bind_companion_scope('aipet_music_content', config, conn)
assert result['headers']['X-Companion-Device'] == 'aa:bb:cc:dd:ee:ff'
assert result['headers']['X-Companion-Token'] == 'unit-secret'
assert result['headers']['ordinary'] == 'retained'
assert 'x-companion-device' not in result['headers']
assert config['headers']['x-companion-device'] == 'forged'
assert module.bind_companion_scope('unrelated', config, conn) is config
manager = (source / 'mcp_manager.py').read_text(encoding='utf-8')
assert manager.count('ServerMCPClient(bind_companion_scope(') == 2
print('PASS: trusted connection identity, static forgery overridden, initial/reconnect bound')
