import json, subprocess
def run(args):
    return subprocess.check_output(args, text=True)
name='xiaozhi-esp32-server-db'
env=dict(x.split('=',1) for x in json.loads(run(['docker','inspect',name]))[0]['Config']['Env'] if '=' in x)
def query(sql):
    return run(['docker','exec','-e','MYSQL_PWD='+env['MYSQL_ROOT_PASSWORD'],name,'mysql','-uroot','--batch',env.get('MYSQL_DATABASE','xiaozhi_esp32_server'),'-e',sql])
print(query('SELECT d.mac_address,d.board,d.app_version,d.agent_id,a.agent_name,a.intent_model_id FROM ai_device d LEFT JOIN ai_agent a ON a.id=d.agent_id;'))
print(query('SELECT id,model_code FROM ai_model_config WHERE model_type=\'Intent\';'))
