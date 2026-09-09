const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../../xiaozhi-esp32-server/main/manager-web/src/components/RestartVoiceServiceButton.vue'), 'utf8').split('<script>')[1].split('</script>')[0].replace(/import Api[^;]+;/, '').replace('export default', 'module.exports =');
function setup() {
  const calls = []; const messages = []; let release;
  const Api = {admin: {getWsServerList: (...args) => calls.push(['list', ...args]), sendWsServerAction: (...args) => calls.push(['restart', ...args])}};
  const ctx = {module: {exports: {}}, Api, setTimeout: fn => {release = fn; return 1;}, clearTimeout() {}};
  vm.runInNewContext(source, ctx);
  const component = ctx.module.exports; const instance = component.data();
  for (const [name, method] of Object.entries(component.methods)) instance[name] = method.bind(instance);
  instance.$message = Object.fromEntries(['success','error','warning'].map(kind => [kind, msg => messages.push(kind)]));
  return {instance, calls, messages, release: () => release()};
}
test('打开确认框只获取服务，不执行重启；单服务自动选择', () => {
 const {instance:i,calls} = setup(); i.openDialog(); i.openDialog(); assert.equal(calls.length,1);
 calls[0][2]({data:{code:0,data:['ws://voice']}}); assert.equal(i.visible,true); assert.equal(i.target,'ws://voice'); assert.equal(calls.length,1);
});
test('列表失败或无服务不显示确认框', () => {
 const {instance:i,calls} = setup(); i.openDialog(); calls[0][3](); assert.equal(i.busy,false); assert.equal(i.visible,false);
 i.openDialog(); calls[1][2]({data:{code:0,data:[]}}); assert.equal(i.visible,false);
});
test('非法目标及重复点击不发送；成功进入冷却期', () => {
 const s=setup(),i=s.instance; i.target='unlisted'; i.restart(); assert.equal(s.calls.length,0);
 i.servers=['ws://voice'];i.target=i.servers[0];i.restart();i.restart();assert.equal(s.calls.length,1);
 s.calls[0][2]({data:{code:0,data:true}});i.restart();assert.equal(s.calls.length,1);assert.equal(i.coolingDown,true);assert.equal(s.messages[0],'success');s.release();assert.equal(i.coolingDown,false);
});
test('网络错误不重试，也不显示重启成功', () => {
 const s=setup(),i=s.instance;i.servers=['ws://voice'];i.target=i.servers[0];i.restart();s.calls[0][3]();assert.equal(s.calls.length,1);assert.equal(s.messages[0],'warning');assert.equal(i.coolingDown,true);
});
test('服务返回false不能显示成功', () => {
 const s=setup(),i=s.instance;i.servers=['ws://voice'];i.target=i.servers[0];i.restart();s.calls[0][2]({data:{code:0,data:false}});assert.equal(s.messages[0],'error');
});
