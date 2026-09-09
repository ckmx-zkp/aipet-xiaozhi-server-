<template>
  <div class="usage-page">
    <HeaderBar />
    <main>
      <div class="toolbar"><h2>续费提醒</h2><div><el-checkbox v-model="showInactive">包含未启用配置</el-checkbox><RestartVoiceServiceButton /><el-button :loading="loading" @click="load">刷新用量</el-button></div></div>
      <el-alert title="官方用量最多每分钟更新一次。额度重置时间不等于套餐到期日；到期日可手工填写，提前7天提醒。" type="info" :closable="false" show-icon />
      <el-alert v-if="warningCount" :title="`${warningCount} 个服务需要关注额度或续费日期`" type="warning" :closable="false" show-icon class="notice" />
      <el-alert title="天气检查记录（2026-09-09）：默认和风凭据返回401。请在智能体工具配置中填写自己的 API Host 和 API Key；此记录不是实时余额查询。" type="warning" :closable="false" show-icon class="notice" />
      <el-table :data="visibleServices" v-loading="loading" stripe class="service-table">
        <el-table-column label="服务 / 关联模型" min-width="230"><template slot-scope="s">
          <strong>{{ s.row.service }}</strong><div class="muted" v-if="s.row.resourceKind !== 'voice_clone'">{{ s.row.models.join('、') }}</div>
          <div v-if="s.row.resourceKind === 'voice_clone'" class="muted">已分配 {{ s.row.resourceCount }} 个音色 · <a href="#/voice-resource-management">管理音色资源</a></div>
          <div v-else class="muted">启用 {{ s.row.enabledCount }} · 有效 {{ s.row.validCount }} · 无效 {{ s.row.invalidCount }} · 待验证 {{ s.row.unknownCount }}</div>
        </template></el-table-column>
        <el-table-column label="用量与剩余额度" min-width="270"><template slot-scope="s">
          <el-tag size="small" :type="s.row.status === 'ok' ? 'success' : 'info'">{{ statusLabel(s.row.status) }}</el-tag>
          <div v-for="(item,index) in s.row.usage" :key="index" class="quota">
            <div>{{ item.label }} <strong v-if="item.remainingPercent != null">剩余 {{ item.remainingPercent }}%</strong></div>
            <el-progress v-if="item.remainingPercent != null" :percentage="Math.max(0,Math.min(100,item.remainingPercent))" :status="item.remainingPercent <= 20 ? 'exception' : 'success'" />
            <div v-if="item.cloneId" class="muted">剩余训练：{{ item.remainingTrainingTimes == null ? '未查询' : item.remainingTrainingTimes + ' 次' }} · 官方状态：{{ item.providerStatus == null ? '未查询' : item.providerStatus }}<br />最近查询：{{ item.quotaCheckedAt || '尚未查询' }}<br /><el-button type="text" size="mini" :loading="refreshingClone === item.cloneId" @click="refreshClone(item)">查询状态 / 次数</el-button></div>
            <div v-if="item.total != null" class="muted">已用 {{ item.used }} / 总额度 {{ item.total }}（供应商计数）</div>
            <div v-if="item.resetAt" class="muted">重置：{{ formatTime(item.resetAt) }}</div>
          </div>
          <p class="muted">{{ s.row.message }}</p>
          <div class="muted">查询时间：{{ formatTime(s.row.checkedAt) }}</div>
        </template></el-table-column>
        <el-table-column label="到期与续费提醒" min-width="245"><template slot-scope="s">
          <el-tag v-if="s.row.warning" type="warning">{{ s.row.reminder }}</el-tag>
          <div class="muted">人工套餐到期日</div>
          <el-date-picker v-model="s.row.renewalDate" type="date" value-format="yyyy-MM-dd" placeholder="未填写" size="small" style="width:160px" :disabled="saving === s.row.serviceKey" @change="save(s.row)" />
          <div v-if="s.row.consoleUrl" class="quota"><a :href="s.row.consoleUrl" target="_blank" rel="noopener noreferrer">打开供应商后台核对 / 续费</a></div>
        </template></el-table-column>
      </el-table>
    </main>
  </div>
</template>
<script>
import Api from '@/apis/api';
import HeaderBar from '@/components/HeaderBar.vue';
import RestartVoiceServiceButton from '@/components/RestartVoiceServiceButton.vue';
export default {
  components: {HeaderBar,RestartVoiceServiceButton},
  data(){return {services:[],loading:false,saving:null,showInactive:false,refreshingClone:null};},
  computed:{visibleServices(){return this.showInactive?this.services:this.services.filter(s=>s.enabledCount>0 || s.warning || s.alwaysVisible);},warningCount(){return this.services.filter(s=>s.warning).length;}},
  created(){this.load();},
  methods:{
    refreshClone(item){
      if(this.refreshingClone)return;this.refreshingClone=item.cloneId;
      Api.voiceClone.refreshStatus(item.cloneId,({data})=>{this.refreshingClone=null;if(data.code===0){Object.assign(item,data.data);this.$message.success('音色状态已更新');}else this.$message.error(data.msg || '查询失败');},()=>{this.refreshingClone=null;this.$message.error('音色状态未能刷新，请稍后重试');});
    },
    statusLabel(status){return {ok:'官方查询成功',manual:'需后台核对',unavailable:'查询暂不可用',not_applicable:'无账户账单'}[status] || status;},
    formatTime(value){return value ? new Date(Number(value)).toLocaleString('zh-CN',{hour12:false}) : '—';},
    load(){
      if(this.loading)return;this.loading=true;
      Api.model.getServiceUsage(({data})=>{this.loading=false;if(data.code===0)this.services=data.data;else this.$message.error(data.msg || '用量查询失败');},()=>{this.loading=false;this.$message.error('无法获取用量，请稍后重试');});
    },
    save(row){
      this.saving=row.serviceKey;
      Api.model.saveServiceReminder(row.serviceKey,{renewalDate:row.renewalDate || null},({data})=>{this.saving=null;if(data.code===0)this.$message.success('到期提醒已保存');else this.$message.error(data.msg || '保存失败');this.load();},()=>{this.saving=null;this.$message.error('保存失败');this.load();});
    }
  }
};
</script>
<style scoped>
.usage-page {min-height:100vh;background:#eff4ff;min-width:1000px;}
main {max-width:1500px;margin:auto;padding:28px;}
.toolbar,.toolbar>div {display:flex;align-items:center;justify-content:space-between;gap:12px;}
h2 {color:#25324b;}.notice {margin-top:12px;}.service-table {margin-top:20px;border-radius:12px;}
.muted {font-size:12px;color:#606b7b;line-height:1.7;white-space:normal;word-break:break-word;margin-top:6px;}
.quota {margin-top:12px;}a {color:#3378e8;}
</style>
