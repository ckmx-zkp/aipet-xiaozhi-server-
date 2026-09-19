<template>
  <div class="welcome device-management-page">
    <HeaderBar />

    <div class="main-wrapper">
      <!-- 顶部操作工具栏卡片 -->
      <div class="management-header-card">
        <div class="header-left-area">
          <button class="back-btn" @click="$router.push('/home')" title="返回智能体列表">
            <i class="el-icon-arrow-left"></i>
          </button>
          <div class="title-with-badge">
            <h2 class="page-title">{{ $t('device.management') }}</h2>
            <span class="device-count-badge">
              <i class="el-icon-cpu"></i>
              {{ filteredDeviceList.length }} 台设备
            </span>
          </div>
        </div>

        <div class="header-actions-area">
          <!-- 搜索输入框 -->
          <div class="search-wrap">
            <el-input
              :placeholder="$t('device.searchPlaceholder')"
              v-model="searchKeyword"
              class="modern-search-input"
              @keyup.enter.native="handleSearch"
              clearable
              @clear="handleSearch"
            >
              <i slot="suffix" class="el-icon-search search-icon" @click="handleSearch"></i>
            </el-input>
          </div>

          <!-- 批量操作与添加 -->
          <button class="action-btn primary-btn" @click="handleAddDevice">
            <i class="el-icon-plus"></i>
            <span>{{ $t('device.bindWithCode') }}</span>
          </button>

          <button class="action-btn secondary-btn" @click="handleManualAddDevice">
            <i class="el-icon-circle-plus-outline"></i>
            <span>{{ $t('device.manualAdd') }}</span>
          </button>

          <button
            v-if="selectedCount > 0"
            class="action-btn danger-btn"
            @click="deleteSelected"
          >
            <i class="el-icon-delete"></i>
            <span>{{ $t('device.unbind') }} ({{ selectedCount }})</span>
          </button>

          <!-- 视图模式切换 -->
          <div class="view-mode-toggle">
            <button
              class="toggle-btn"
              :class="{ 'is-active': viewMode === 'card' }"
              @click="viewMode = 'card'"
              title="卡片视图"
            >
              <i class="el-icon-menu"></i>
            </button>
            <button
              class="toggle-btn"
              :class="{ 'is-active': viewMode === 'table' }"
              @click="viewMode = 'table'"
              title="表格视图"
            >
              <i class="el-icon-s-grid"></i>
            </button>
          </div>
        </div>
      </div>

      <!-- 全选状态栏（卡片模式下便捷操作） -->
      <div class="batch-bar" v-if="filteredDeviceList.length > 0 && viewMode === 'card'">
        <el-checkbox
          :value="isCurrentPageAllSelected"
          @change="handleSelectAll"
          class="batch-checkbox"
        >
          {{ isCurrentPageAllSelected ? $t('common.deselectAll') : $t('common.selectAll') }}
        </el-checkbox>
        <span class="selected-hint" v-if="selectedCount > 0">
          已选中 <strong>{{ selectedCount }}</strong> 台设备
        </span>
      </div>

      <!-- 内容区域 -->
      <div class="content-scroll-container" v-loading="loading">
        <!-- 1. 卡片视图（默认推荐） -->
        <div v-if="viewMode === 'card'" class="device-cards-grid">
          <!-- 空状态 -->
          <div v-if="filteredDeviceList.length === 0 && !loading" class="empty-state">
            <div class="empty-icon"><i class="el-icon-cpu"></i></div>
            <p class="empty-title">暂无绑定设备</p>
            <p class="empty-desc">请点击上方“绑定新设备”根据设备端提示进行绑定</p>
            <button class="action-btn primary-btn" @click="handleAddDevice">
              <i class="el-icon-plus"></i> {{ $t('device.bindWithCode') }}
            </button>
          </div>

          <!-- 设备独立卡片列表 -->
          <div
            v-for="device in paginatedDeviceList"
            :key="device.device_id"
            class="device-item-card"
            :class="{ 'is-selected': device.selected }"
          >
            <!-- 卡片头部：选择框 + 图标 + 型号 + 状态灯 -->
            <div class="card-head">
              <div class="head-left">
                <el-checkbox v-model="device.selected" class="device-card-checkbox"></el-checkbox>
                <div class="device-board-avatar">
                  <i class="el-icon-cpu"></i>
                </div>
                <div class="device-name-wrap">
                  <el-tooltip :content="getFirmwareTypeName(device.model)" placement="top" effect="light">
                    <span class="device-model-name">{{ getFirmwareTypeName(device.model) }}</span>
                  </el-tooltip>
                  <span class="firmware-tag">
                    v{{ device.firmwareVersion || '1.0.0' }}
                  </span>
                </div>
              </div>

              <!-- 在线/离线状态指示 -->
              <div class="status-badge" :class="device.deviceStatus === 'online' ? 'online' : 'offline'">
                <span class="status-dot"></span>
                <span>{{ device.deviceStatus === 'online' ? $t('device.online') : $t('device.offline') }}</span>
              </div>
            </div>

            <!-- 卡片中间：详细参数区 -->
            <div class="card-body">
              <!-- 设备备注/别名 -->
              <div class="info-row remark-row">
                <span class="info-label">{{ $t('device.remark') }}:</span>
                <div class="remark-content">
                  <el-input
                    v-if="device.isEdit"
                    v-model="device.remark"
                    size="mini"
                    maxlength="64"
                    show-word-limit
                    @blur="onRemarkBlur(device)"
                    @keyup.enter.native="onRemarkEnter(device)"
                    ref="remarkInput"
                  />
                  <div v-else class="remark-display" @click="editRemark(device)">
                    <span class="remark-text">{{ device.remark || '点击设置设备昵称' }}</span>
                    <i class="el-icon-edit edit-icon"></i>
                  </div>
                </div>
              </div>

              <!-- MAC 地址 -->
              <div class="info-row">
                <span class="info-label">{{ $t('device.macAddress') }}:</span>
                <div class="mac-pill">
                  <MacAddressMask :macAddress="device.macAddress" />
                </div>
              </div>

              <!-- 自动升级 Switch -->
              <div class="info-row">
                <span class="info-label">{{ $t('device.autoUpdate') }}:</span>
                <div class="ota-switch-wrap">
                  <el-switch
                    v-model="device.otaSwitch"
                    active-color="#10b981"
                    inactive-color="#cbd5e1"
                    @change="handleOtaSwitchChange(device)"
                  />
                  <span class="switch-hint">{{ device.otaSwitch ? '已开启自动升级' : '已关闭' }}</span>
                </div>
              </div>

              <!-- 专属音色 -->
              <div class="info-row voice-row">
                <span class="info-label">音色:</span>
                <div class="voice-badge-wrap">
                  <span
                    class="voice-tag"
                    :class="device.ttsVoiceId ? 'custom' : 'inherit'"
                    :title="device.ttsVoiceId ? `专属音色: ${device.ttsVoiceName || device.ttsVoiceId}` : '跟随智能体默认音色'"
                  >
                    <i :class="device.ttsVoiceId ? 'el-icon-microphone' : 'el-icon-user'"></i>
                    {{ device.ttsVoiceId ? (device.ttsVoiceName || '专属音色') : '跟随智能体' }}
                  </span>
                  <button class="edit-voice-icon-btn" @click.stop="openVoiceDialog(device)" title="配置设备专属音色">
                    <i class="el-icon-setting"></i>
                  </button>
                </div>
              </div>

              <!-- 绑定时间与最后对话 -->
              <div class="time-meta-block">
                <div class="time-item" :title="`绑定时间: ${device.bindTime}`">
                  <i class="el-icon-date"></i>
                  <span>绑定: {{ device.bindTime || '-' }}</span>
                </div>
                <div class="time-item" :title="`最后对话: ${device.lastConversation}`">
                  <i class="el-icon-chat-dot-round"></i>
                  <span>最近: {{ device.lastConversation || '暂无对话' }}</span>
                </div>
              </div>
            </div>

            <!-- 卡片底部：操作按钮组 -->
            <div class="card-footer">
              <button
                class="card-pill-btn voice-btn"
                @click="openVoiceDialog(device)"
                title="设置设备专属音色或跟随智能体"
              >
                <i class="el-icon-headset"></i>
                <span>配置音色</span>
              </button>

              <button
                v-if="isGenerate(device)"
                class="card-pill-btn generate-theme-btn"
                @click="handleGenertor(device)"
              >
                <i class="el-icon-picture-outline"></i>
                <span>{{ $t('device.deviceThemeGeneration') }}</span>
              </button>

              <button
                class="card-pill-btn unbind-btn"
                @click="handleUnbind(device.device_id)"
              >
                <i class="el-icon-link"></i>
                <span>{{ $t('device.unbind') }}</span>
              </button>
            </div>
          </div>
        </div>

        <!-- 2. 表格视图（备用切换） -->
        <div v-else class="device-table-view">
          <CustomTable
            ref="deviceTable"
            :data="paginatedDeviceList"
            :columns="tableColumns"
            :loading="loading"
            :loading-text="$t('deviceManagement.loading')"
            :show-selection="true"
            :show-operations="true"
            :operations-label="$t('device.operation')"
            :total="filteredDeviceList.length"
            :current-page="currentPage"
            :page-size="pageSize"
            :page-size-options="pageSizeOptions"
            @size-change="handlePageSizeChange"
            @page-change="goToPage"
          >
            <template slot="model" slot-scope="scope">
              {{ getFirmwareTypeName(scope.row.model) }}
            </template>
            <template slot="macAddress" slot-scope="scope">
              <MacAddressMask :macAddress="scope.row.macAddress" />
            </template>
            <template slot="deviceStatus" slot-scope="scope">
              <el-tag v-if="scope.row.deviceStatus === 'online'" type="success">{{ $t('device.online') }}</el-tag>
              <el-tag v-else type="info">{{ $t('device.offline') }}</el-tag>
            </template>
            <template slot="remark" slot-scope="scope">
              <el-input v-show="scope.row.isEdit" v-model="scope.row.remark" size="mini" maxlength="64" show-word-limit
                @blur="onRemarkBlur(scope.row)" @keyup.enter.native="onRemarkEnter(scope.row)" />
              <span v-show="!scope.row.isEdit" class="remark-view">
                <i class="el-icon-edit" @click="scope.row.isEdit = true" style="cursor: pointer;"></i>
                <span @click="scope.row.isEdit = true">
                  {{ scope.row.remark || '-' }}
                </span>
              </span>
            </template>
            <template slot="otaSwitch" slot-scope="scope">
              <el-switch v-model="scope.row.otaSwitch" size="mini" active-color="#10b981" inactive-color="#cbd5e1"
                @change="handleOtaSwitchChange(scope.row)"></el-switch>
            </template>
            <template slot="ttsVoiceName" slot-scope="scope">
              <el-tag size="mini" :type="scope.row.ttsVoiceId ? 'primary' : 'info'">
                {{ scope.row.ttsVoiceId ? (scope.row.ttsVoiceName || '专属音色') : '跟随智能体' }}
              </el-tag>
            </template>
            <template slot="operations" slot-scope="scope">
              <el-button size="mini" type="text" @click="openVoiceDialog(scope.row)">
                配置音色
              </el-button>
              <el-button size="mini" type="text" @click="handleUnbind(scope.row.device_id)">
                {{ $t('device.unbind') }}
              </el-button>
              <el-button v-if="isGenerate(scope.row)" size="mini" type="text" @click="handleGenertor(scope.row)">
                {{ $t('device.deviceThemeGeneration') }}
              </el-button>
            </template>
          </CustomTable>
        </div>

        <!-- 卡片模式底部分页 -->
        <div class="pagination-footer" v-if="viewMode === 'card' && filteredDeviceList.length > 0">
          <el-pagination
            background
            layout="total, sizes, prev, pager, next"
            :current-page="currentPage"
            :page-size="pageSize"
            :page-sizes="pageSizeOptions"
            :total="filteredDeviceList.length"
            @size-change="handlePageSizeChange"
            @current-change="goToPage"
          />
        </div>
      </div>
    </div>

    <!-- 弹窗组件 -->
    <AddDeviceDialog :visible.sync="addDeviceDialogVisible" :agent-id="currentAgentId"
      @refresh="fetchBindDevices(currentAgentId || 'all')" />
    <ManualAddDeviceDialog :visible.sync="manualAddDeviceDialogVisible" :agent-id="currentAgentId"
      @refresh="fetchBindDevices(currentAgentId || 'all')" />
    <DeviceVoiceDialog :visible.sync="voiceDialogVisible" :device="currentVoiceDevice"
      @refresh="fetchBindDevices(currentAgentId || 'all')" />

    <el-footer>
      <version-footer />
    </el-footer>
  </div>
</template>

<script>
import Api from '@/apis/api';
import AddDeviceDialog from "@/components/AddDeviceDialog.vue";
import DeviceVoiceDialog from "@/components/DeviceVoiceDialog.vue";
import HeaderBar from "@/components/HeaderBar.vue";
import ManualAddDeviceDialog from "@/components/ManualAddDeviceDialog.vue";
import VersionFooter from "@/components/VersionFooter.vue";
import MacAddressMask from "@/components/MacAddressMask.vue";
import CustomButton from "@/components/CustomButton.vue";
import CustomTable from "@/components/CustomTable.vue";
import {
  compareTimestamps,
  formatCreateDate,
  formatTimestamp,
  hasTimestampValue,
  parseLegacyDate,
  parseTimestamp,
} from '@/utils/deviceTime.mjs';

export default {
  name: "DeviceManagementPage",
  components: {
    HeaderBar,
    AddDeviceDialog,
    DeviceVoiceDialog,
    ManualAddDeviceDialog,
    VersionFooter,
    MacAddressMask,
    CustomButton,
    CustomTable,
  },
  data() {
    return {
      viewMode: 'card', // 默认卡片视图
      addDeviceDialogVisible: false,
      manualAddDeviceDialogVisible: false,
      voiceDialogVisible: false,
      currentVoiceDevice: {},
      selectedDeviceId: '',
      searchKeyword: "",
      activeSearchKeyword: "",
      currentAgentId: this.$route.query.agentId || '',
      currentPage: 1,
      pageSize: 12, // 卡片网格更适合 12 / 24 数量
      pageSizeOptions: [12, 24, 48, 96],
      deviceList: [],
      loading: false,
      firmwareTypes: [],
      mqttServiceAvailable: false,
    };
  },
  computed: {
    filteredDeviceList() {
      const keyword = this.activeSearchKeyword.toLowerCase();
      if (!keyword) return this.deviceList;
      return this.deviceList.filter(device =>
        (device.model && device.model.toLowerCase().includes(keyword)) ||
        (device.macAddress && device.macAddress.toLowerCase().includes(keyword)) ||
        (device.remark && device.remark.toLowerCase().includes(keyword))
      );
    },
    paginatedDeviceList() {
      const start = (this.currentPage - 1) * this.pageSize;
      const end = start + this.pageSize;
      return this.filteredDeviceList.slice(start, end);
    },
    selectedCount() {
      return this.deviceList.filter(device => device.selected).length;
    },
    isCurrentPageAllSelected() {
      return this.paginatedDeviceList.length > 0 &&
        this.paginatedDeviceList.every(device => device.selected);
    },
    tableColumns() {
      const columns = [
        { prop: 'model', label: this.$t('device.model'), align: 'center' },
        { prop: 'firmwareVersion', label: this.$t('device.firmwareVersion'), align: 'center' },
        { prop: 'macAddress', label: this.$t('device.macAddress'), align: 'center' },
        { prop: 'bindTime', label: this.$t('device.bindTime'), align: 'center' },
        { prop: 'lastConversation', label: this.$t('device.lastConversation'), align: 'center' },
      ];
      if (this.mqttServiceAvailable) {
        columns.push({ prop: 'deviceStatus', label: this.$t('device.deviceStatus'), align: 'center' });
      }
      columns.push({ prop: 'ttsVoiceName', label: '生效音色', align: 'center' });
      columns.push({ prop: 'remark', label: this.$t('device.remark'), align: 'center' });
      columns.push({ prop: 'otaSwitch', label: this.$t('device.autoUpdate'), align: 'center' });
      return columns;
    },
  },
  mounted() {
    const agentId = this.$route.query.agentId;
    this.fetchBindDevices(agentId || 'all');
  },
  created() {
    this.getFirmwareTypes();
  },
  methods: {
    async getFirmwareTypes() {
      try {
        const res = await Api.dict.getDictDataByType('FIRMWARE_TYPE');
        this.firmwareTypes = res.data;
      } catch (error) {
        console.error(this.$t('device.getFirmwareTypeFailed') + ':', error);
      }
    },
    handlePageSizeChange(val) {
      this.pageSize = val;
      this.currentPage = 1;
    },
    handleSearch() {
      this.activeSearchKeyword = this.searchKeyword;
      this.currentPage = 1;
    },
    handleSelectAll(val) {
      const shouldSelect = typeof val === 'boolean' ? val : !this.isCurrentPageAllSelected;
      this.paginatedDeviceList.forEach(row => {
        row.selected = shouldSelect;
      });
    },
    editRemark(device) {
      device.isEdit = true;
      this.$nextTick(() => {
        if (this.$refs.remarkInput && this.$refs.remarkInput[0]) {
          this.$refs.remarkInput[0].focus();
        }
      });
    },
    deleteSelected() {
      const selectedDevices = this.deviceList.filter(device => device.selected);
      if (selectedDevices.length === 0) {
        this.$message.warning({
          message: this.$t('device.selectAtLeastOne'),
          showClose: true
        });
        return;
      }

      this.$confirm(this.$t('device.confirmBatchUnbind').replace('{count}', selectedDevices.length), this.$t('message.warning'), {
        confirmButtonText: this.$t('button.ok'),
        cancelButtonText: this.$t('button.cancel'),
        type: 'warning'
      }).then(() => {
        const deviceIds = selectedDevices.map(device => device.device_id);
        this.batchUnbindDevices(deviceIds);
      });
    },
    batchUnbindDevices(deviceIds) {
      const promises = deviceIds.map(id => {
        return new Promise((resolve, reject) => {
          Api.device.unbindDevice(id, ({ data }) => {
            if (data.code === 0) {
              resolve();
            } else {
              reject(data.msg || this.$t('device.bindFailed'));
            }
          });
        });
      });
      Promise.all(promises)
        .then(() => {
          this.$message.success({
            message: this.$t('device.batchUnbindSuccess').replace('{count}', deviceIds.length),
            showClose: true
          });
          this.fetchBindDevices(this.currentAgentId);
        })
        .catch(error => {
          this.$message.error({
            message: error || this.$t('device.batchUnbindError'),
            showClose: true
          });
        });
    },
    handleAddDevice() {
      this.addDeviceDialogVisible = true;
    },
    handleManualAddDevice() {
      this.manualAddDeviceDialogVisible = true;
    },
    submitRemark(row) {
      if (row._submitting) return;

      const text = (row.remark || '').trim();
      if (text.length > 64) {
        this.$message.warning(this.$t('device.remarkTooLong'));
        return;
      }
      if (text === row._originalRemark) {
        return;
      }

      row._submitting = true;
      this.updateDeviceInfo(row.device_id, { alias: text }, (ok, resp) => {
        if (ok) {
          row._originalRemark = text;
          this.$message.success(this.$t('device.remarkSaved'));
        } else {
          row.remark = row._originalRemark;
          this.$message.error(resp.msg || this.$t('device.remarkSaveFailed'));
        }
        row._submitting = false;
      });
    },
    onRemarkBlur(row) {
      row.isEdit = false;
      setTimeout(() => {
        this.submitRemark(row);
      }, 100);
    },
    onRemarkEnter(row) {
      row.isEdit = false;
      this.submitRemark(row);
    },
    handleUnbind(device_id) {
      this.$confirm(this.$t('device.confirmUnbind'), this.$t('message.warning'), {
        confirmButtonText: this.$t('button.ok'),
        cancelButtonText: this.$t('button.cancel'),
        type: 'warning'
      }).then(() => {
        Api.device.unbindDevice(device_id, ({ data }) => {
          if (data.code === 0) {
            this.$message.success({
              message: this.$t('device.unbindSuccess'),
              showClose: true
            });
            this.fetchBindDevices(this.$route.query.agentId);
          } else {
            this.$message.error({
              message: data.msg || this.$t('device.unbindFailed'),
              showClose: true
            });
          }
        });
      });
    },
    handleGenertor(row) {
      const pathname = window.location.pathname;
      const basePath = pathname.split('/').slice(0, -1).join('/');
      const url = `${window.location.origin}${basePath}/generator/?deviceId=${row.device_id}`;
      sessionStorage.setItem('devicePath', window.location.href);
      window.location.href = url;
    },
    openVoiceDialog(device) {
      this.currentVoiceDevice = device;
      this.voiceDialogVisible = true;
    },
    goToPage(page) {
      this.currentPage = page;
    },
    fetchBindDevices(agentId) {
      this.loading = true;
      Api.device.getAgentBindDevices(agentId, ({ data }) => {
        this.loading = false;
        if (data.code === 0) {
          this.deviceList = data.data.map(device => {
            const hasCreateDateTimestamp = hasTimestampValue(device.createDateTimestamp);
            const rawBindTime = hasCreateDateTimestamp
              ? parseTimestamp(device.createDateTimestamp)
              : parseLegacyDate(device.createDate);
            return {
              device_id: device.id,
              model: device.board,
              firmwareVersion: device.appVersion,
              macAddress: device.macAddress,
              bindTime: formatCreateDate(device.createDateTimestamp, device.createDate),
              lastConversation: formatTimestamp(device.lastConnectedAtTimestamp),
              remark: device.alias,
              _originalRemark: device.alias,
              isEdit: false,
              _submitting: false,
              otaSwitch: device.autoUpdate === 1,
              agentId: device.agentId,
              agentName: device.agentName,
              ttsModelId: device.ttsModelId,
              ttsVoiceId: device.ttsVoiceId,
              ttsVoiceName: device.ttsVoiceName,
              ttsVolume: device.ttsVolume,
              ttsRate: device.ttsRate,
              ttsPitch: device.ttsPitch,
              rawBindTime,
              selected: false,
              deviceStatus: 'offline'
            };
          }).sort((firstDevice, secondDevice) => compareTimestamps(
            firstDevice.rawBindTime,
            secondDevice.rawBindTime,
          ));
          this.activeSearchKeyword = "";
          this.searchKeyword = "";

          this.fetchDeviceStatus(agentId);
        } else {
          this.$message.error(data.msg || this.$t('device.getListFailed'));
        }
      });
    },
    fetchDeviceStatus(agentId) {
      this.loading = true;
      Api.device.getDeviceStatus(agentId, ({ data }) => {
        this.loading = false;
        if (data.code === 0) {
          try {
            const statusData = JSON.parse(data.data);
            if (statusData && typeof statusData === 'object') {
              this.mqttServiceAvailable = true;
              this.updateDeviceStatusFromResponse(statusData);
            } else {
              this.mqttServiceAvailable = false;
            }
          } catch (error) {
            this.mqttServiceAvailable = false;
          }
        } else {
          this.mqttServiceAvailable = false;
        }
      });
    },
    updateDeviceStatusFromResponse(deviceStatusMap) {
      this.deviceList.forEach(device => {
        const macAddress = device.macAddress ? device.macAddress.replace(/:/g, '_') : 'unknown';
        const groupId = device.model ? device.model.replace(/:/g, '_') : 'GID_default';
        const mqttClientId = `${groupId}@@@${macAddress}@@@${macAddress}`;

        if (deviceStatusMap[mqttClientId]) {
          const statusInfo = deviceStatusMap[mqttClientId];
          let isOnline = false;
          if (statusInfo.isAlive === true) {
            isOnline = true;
          } else if (statusInfo.isAlive === false) {
            isOnline = false;
          } else if (statusInfo.isAlive === null && statusInfo.exists === true) {
            isOnline = true;
          }
          device.deviceStatus = isOnline ? 'online' : 'offline';
        } else {
          device.deviceStatus = 'offline';
        }
      });
    },
    getFirmwareTypeName(type) {
      const firmwareType = this.firmwareTypes.find(item => item.key === type);
      return firmwareType ? firmwareType.name : (type || '通用 ESP32 设备');
    },
    updateDeviceInfo(device_id, payload, callback) {
      return Api.device.updateDeviceInfo(device_id, payload, ({ data }) => {
        callback(data.code === 0, data);
      });
    },
    handleOtaSwitchChange(row) {
      this.updateDeviceInfo(row.device_id, { autoUpdate: row.otaSwitch ? 1 : 0 }, (result, { msg }) => {
        if (result) {
          this.$message.success(row.otaSwitch ? this.$t('device.autoUpdateEnabled') : this.$t('device.autoUpdateDisabled'));
          return;
        }
        row.otaSwitch = !row.otaSwitch;
        this.$message.error(msg || this.$t('message.error'));
      });
    },
    isGenerate(row) {
      if (!row.firmwareVersion) return false;
      const version = row.firmwareVersion.replace(/\./g, '');
      return Number(version) >= 200;
    },
  }
};
</script>

<style lang="scss" scoped>
.device-management-page {
  min-width: 900px;
  min-height: 100vh;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f8fafc;
  overflow: hidden;
}

.main-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 16px 24px 20px;
  max-width: 1440px;
  width: 100%;
  margin: 0 auto;
  box-sizing: border-box;
  overflow: hidden;
}

/* 顶部操作条卡片 */
.management-header-card {
  background: #ffffff;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 16px -2px rgba(15, 23, 42, 0.04);
  padding: 14px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
  flex-shrink: 0;
  gap: 16px;
}

.header-left-area {
  display: flex;
  align-items: center;
  gap: 12px;

  .back-btn {
    width: 34px;
    height: 34px;
    border-radius: 10px;
    border: 1px solid #e2e8f0;
    background: #ffffff;
    color: #64748b;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    transition: all 0.2s;

    &:hover {
      background: #f1f5f9;
      color: #1e293b;
      border-color: #cbd5e1;
    }
  }

  .title-with-badge {
    display: flex;
    align-items: center;
    gap: 10px;

    .page-title {
      font-size: 18px;
      font-weight: 700;
      color: #1e293b;
      margin: 0;
    }

    .device-count-badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 9px;
      border-radius: 20px;
      background: #eff6ff;
      color: #3b82f6;
      font-size: 12px;
      font-weight: 600;
    }
  }
}

.header-actions-area {
  display: flex;
  align-items: center;
  gap: 10px;
}

.search-wrap {
  width: 220px;
}

.modern-search-input {
  &::v-deep .el-input__inner {
    border-radius: 20px;
    border: 1px solid #e2e8f0;
    height: 36px;
    line-height: 36px;
    padding-left: 14px;
    color: #1e293b;
    transition: all 0.2s;

    &:focus {
      border-color: #4e75ff;
      box-shadow: 0 0 0 3px rgba(78, 117, 255, 0.12);
    }
  }

  .search-icon {
    font-size: 15px;
    color: #94a3b8;
    cursor: pointer;
    line-height: 36px;
    &:hover {
      color: #4e75ff;
    }
  }
}

.action-btn {
  border: none;
  border-radius: 20px;
  padding: 7px 16px;
  font-size: 13px;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  transition: all 0.22s ease;

  &.primary-btn {
    background: linear-gradient(135deg, #4e75ff 0%, #3b82f6 100%);
    color: #ffffff;
    box-shadow: 0 2px 8px rgba(78, 117, 255, 0.25);

    &:hover {
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(78, 117, 255, 0.35);
    }
  }

  &.secondary-btn {
    background: #eff6ff;
    color: #3b82f6;

    &:hover {
      background: #dbeafe;
      color: #1d4ed8;
    }
  }

  &.danger-btn {
    background: #fef2f2;
    color: #ef4444;

    &:hover {
      background: #fee2e2;
    }
  }
}

/* 视图切换 */
.view-mode-toggle {
  display: flex;
  background: #f1f5f9;
  padding: 3px;
  border-radius: 10px;
  gap: 2px;

  .toggle-btn {
    border: none;
    background: transparent;
    color: #64748b;
    width: 30px;
    height: 30px;
    border-radius: 7px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 15px;
    transition: all 0.2s;

    &:hover {
      color: #1e293b;
    }

    &.is-active {
      background: #ffffff;
      color: #4e75ff;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
    }
  }
}

/* 批量全选工具条 */
.batch-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 4px 10px;

  .selected-hint {
    font-size: 12px;
    color: #64748b;
    strong {
      color: #4e75ff;
    }
  }
}

/* 滚动容器 */
.content-scroll-container {
  flex: 1;
  overflow-y: auto;
  padding-right: 4px;
  display: flex;
  flex-direction: column;

  &::-webkit-scrollbar {
    width: 6px;
  }
  &::-webkit-scrollbar-thumb {
    background: #cbd5e1;
    border-radius: 6px;
  }
}

/* 1. 设备独立卡片网格 */
.device-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 18px;
  padding-bottom: 20px;
}

.device-item-card {
  background: #ffffff;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 16px -2px rgba(15, 23, 42, 0.04), 0 2px 6px -1px rgba(15, 23, 42, 0.02);
  padding: 18px 20px 14px;
  display: flex;
  flex-direction: column;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;

  &:hover {
    transform: translateY(-3px);
    box-shadow: 0 12px 28px -4px rgba(78, 117, 255, 0.12), 0 4px 10px -2px rgba(78, 117, 255, 0.05);
    border-color: rgba(78, 117, 255, 0.35);
  }

  &.is-selected {
    border-color: #4e75ff;
    background: #fcfdff;
    box-shadow: 0 0 0 2px rgba(78, 117, 255, 0.2);
  }
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.head-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;

  .device-card-checkbox {
    margin-right: 2px;
  }

  .device-board-avatar {
    width: 38px;
    height: 38px;
    border-radius: 10px;
    background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
    color: #3b82f6;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    flex-shrink: 0;
  }

  .device-name-wrap {
    display: flex;
    flex-direction: column;
    min-width: 0;

    .device-model-name {
      font-size: 15px;
      font-weight: 700;
      color: #1e293b;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .firmware-tag {
      font-size: 11px;
      color: #64748b;
      font-weight: 500;
    }
  }
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;

  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
  }

  &.online {
    background: #ecfdf5;
    color: #10b981;
    .status-dot {
      background: #10b981;
      box-shadow: 0 0 6px #10b981;
    }
  }

  &.offline {
    background: #f1f5f9;
    color: #94a3b8;
    .status-dot {
      background: #cbd5e1;
    }
  }
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 14px;
}

.info-row {
  display: flex;
  align-items: center;
  font-size: 12px;

  .info-label {
    width: 64px;
    color: #64748b;
    flex-shrink: 0;
  }

  .remark-content {
    flex: 1;
    min-width: 0;

    .remark-display {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
      padding: 2px 6px;
      border-radius: 6px;
      transition: background 0.15s;

      &:hover {
        background: #f1f5f9;
        .edit-icon {
          color: #4e75ff;
        }
      }

      .remark-text {
        color: #334155;
        font-weight: 500;
        max-width: 200px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .edit-icon {
        color: #94a3b8;
        font-size: 12px;
      }
    }
  }

  .mac-pill {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    padding: 2px 8px;
    border-radius: 6px;
    font-family: monospace;
    font-size: 11px;
    color: #475569;
  }

  .ota-switch-wrap {
    display: flex;
    align-items: center;
    gap: 8px;

    .switch-hint {
      font-size: 11px;
      color: #64748b;
    }
  }
}

.time-meta-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 10px;
  background: #f8fafc;
  border-radius: 8px;
  font-size: 11px;
  color: #64748b;

  .time-item {
    display: flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;

    i {
      color: #94a3b8;
    }
  }
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 10px;
  border-top: 1px solid #f1f5f9;

  .card-pill-btn {
    border: none;
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    cursor: pointer;
    transition: all 0.2s;

    &.voice-btn {
      background: #f0fdf4;
      color: #16a34a;
      border: 1px solid #bbf7d0;

      &:hover {
        background: #dcfce7;
        color: #15803d;
      }
    }

    &.generate-theme-btn {
      background: #eff6ff;
      color: #3b82f6;

      &:hover {
        background: #dbeafe;
        color: #1d4ed8;
      }
    }

    &.unbind-btn {
      background: #f8fafc;
      color: #64748b;

      &:hover {
        background: #fee2e2;
        color: #ef4444;
      }
    }
  }
}

.voice-row {
  .voice-badge-wrap {
    display: inline-flex;
    align-items: center;
    gap: 6px;

    .voice-tag {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 8px;
      border-radius: 12px;
      font-size: 11px;
      font-weight: 500;

      &.custom {
        background: #eff6ff;
        color: #2563eb;
        border: 1px solid #bfdbfe;
      }

      &.inherit {
        background: #f1f5f9;
        color: #64748b;
        border: 1px solid #e2e8f0;
      }
    }

    .edit-voice-icon-btn {
      border: none;
      background: transparent;
      color: #94a3b8;
      cursor: pointer;
      padding: 2px 4px;
      font-size: 13px;
      border-radius: 4px;
      transition: all 0.2s;

      &:hover {
        color: #3b82f6;
        background: #eff6ff;
      }
    }
  }
}

/* 2. 表格视图 */
.device-table-view {
  background: #ffffff;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  padding: 16px;
}

/* 分页 */
.pagination-footer {
  display: flex;
  justify-content: flex-end;
  padding: 12px 0 24px;
}

/* 空状态 */
.empty-state {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  background: #ffffff;
  border-radius: 16px;
  border: 1px dashed #cbd5e1;

  .empty-icon {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    background: #eff6ff;
    color: #3b82f6;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 28px;
    margin-bottom: 14px;
  }

  .empty-title {
    font-size: 16px;
    font-weight: 700;
    color: #1e293b;
    margin: 0 0 6px 0;
  }

  .empty-desc {
    font-size: 13px;
    color: #64748b;
    margin: 0 0 16px 0;
  }
}
</style>
