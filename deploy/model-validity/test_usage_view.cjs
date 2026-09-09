const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');const path = require('node:path');const vm = require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../../xiaozhi-esp32-server/main/manager-web/src/views/ServiceUsage.vue'),'utf8').split('<script>')[1].split('</script>')[0].replace(/import [^;]+;/g,'').replace('export default','module.exports =');
const ctx={module:{exports:{}},HeaderBar:{},RestartVoiceServiceButton:{},Api:{}};vm.runInNewContext(source,ctx);const component=ctx.module.exports;
test('Java字符串时间戳可以显示日期',()=>{const text=component.methods.formatTime('1788955200000');assert.ok(!text.includes('Invalid'));assert.match(text,/2026/);});
test('默认只展示在用服务或需要提醒的服务，允许看全部',()=>{const state={showInactive:false,services:[{enabledCount:1},{enabledCount:0},{enabledCount:0,warning:true}]};assert.equal(component.computed.visibleServices.call(state).length,2);state.showInactive=true;assert.equal(component.computed.visibleServices.call(state).length,3);});
