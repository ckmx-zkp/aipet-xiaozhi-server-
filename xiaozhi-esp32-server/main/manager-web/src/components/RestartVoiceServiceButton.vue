<template>
  <div v-if="$store.state.userInfo && $store.state.userInfo.superAdmin" class="restart-service">
    <el-button type="warning" plain icon="el-icon-refresh-right" :disabled="busy || coolingDown" @click="openDialog">
      {{ coolingDown ? '请等待服务重连' : '重启语音服务' }}
    </el-button>
    <el-dialog title="重启语音服务" :visible.sync="visible" width="460px" append-to-body :close-on-click-modal="false" :show-close="!busy">
      <el-alert title="设备语音连接会短暂断开，重连后使用最新配置。" type="warning" :closable="false" show-icon />
      <el-select v-model="target" placeholder="请选择语音服务" :disabled="busy" style="width: 100%; margin-top: 20px">
        <el-option v-for="address in servers" :key="address" :label="address" :value="address" />
      </el-select>
      <span slot="footer">
        <el-button :disabled="busy" @click="visible = false">取消</el-button>
        <el-button type="warning" :loading="busy" :disabled="!target || coolingDown" @click="restart">确认重启</el-button>
      </span>
    </el-dialog>
  </div>
</template>
<script>
import Api from '@/apis/api';
export default {
  data() { return { visible: false, busy: false, coolingDown: false, target: '', servers: [], cooldownTimer: null }; },
  beforeDestroy() { clearTimeout(this.cooldownTimer); },
  methods: {
    openDialog() {
      if (this.busy || this.coolingDown) return;
      this.busy = true;
      Api.admin.getWsServerList({}, ({ data }) => {
        this.busy = false;
        if (data.code !== 0) { this.$message.error(data.msg || '无法获取服务列表'); return; }
        this.servers = [...new Set((data.data || []).filter(address => typeof address === 'string' && address.trim()))];
        this.target = this.servers.length === 1 ? this.servers[0] : '';
        if (!this.servers.length) { this.$message.warning('尚未配置语音服务'); return; }
        this.visible = true;
      }, () => { this.busy = false; this.$message.error('无法获取服务列表，请稍后重试'); });
    },
    restart() {
      if (this.busy || this.coolingDown || !this.servers.includes(this.target)) return;
      this.busy = true;
      Api.admin.sendWsServerAction({ targetWs: this.target, action: 'restart' }, ({ data }) => {
        this.finishRequest();
        if (data.code !== 0 || data.data !== true) { this.$message.error(data.msg || '服务未确认接受重启指令，请检查服务状态'); return; }
        this.$message.success({ message: '重启指令已接受，请等待设备重新连接。', duration: 6000 });
      }, () => {
        this.finishRequest();
        this.$message.warning({ message: '重启结果尚未确认，请先检查设备是否重连，避免重复操作。', duration: 8000 });
      });
    },
    finishRequest() {
      this.busy = false;
      this.visible = false;
      this.coolingDown = true;
      this.cooldownTimer = setTimeout(() => { this.coolingDown = false; }, 30000);
    },
  },
};
</script>
<style scoped>
.restart-service { margin-right: 12px; }
</style>
