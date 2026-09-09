"""在服务器本机读取模型清单，仅输出非敏感字段。"""
import json
import subprocess

def models():
    sql = "SELECT JSON_OBJECT('id',id,'modelType',model_type,'name',model_name,'enabled',is_enabled,'default',is_default,'config',config_json) FROM ai_model_config"
    result = subprocess.run(['docker', 'exec', '-i', 'xiaozhi-esp32-server-db', 'sh', '-c',
                             'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --default-character-set=utf8mb4 -uroot -N -B --raw xiaozhi_esp32_server'],
                            input=sql, text=True, capture_output=True, check=True)
    return [json.loads(line) for line in result.stdout.splitlines()]

if __name__ == '__main__':
    for model in models():
        config = model.pop('config') or {}
        if isinstance(config, str):
            config = json.loads(config)
        model['provider'] = config.get('type')
        model['fields'] = sorted(config)
        model['missingFields'] = [k for k, v in config.items() if v is None or v == '']
        print(json.dumps(model, ensure_ascii=False))