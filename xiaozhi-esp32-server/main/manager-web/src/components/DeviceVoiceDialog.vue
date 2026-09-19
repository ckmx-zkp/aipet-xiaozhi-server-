<template>
  <CustomDialog
    :visible.sync="localVisible"
    :title="dialogTitle"
    width="680px"
    :confirm-loading="submitting"
    confirm-text="保存配置"
    cancel-text="取消"
    @confirm="handleConfirm"
    @cancel="handleCancel"
    @close="handleClose"
  >
    <div class="device-voice-config-container">
      <!-- 顶部设备与智能体信息简报 -->
      <div class="device-brief-card">
        <div class="brief-icon">
          <i class="el-icon-headset"></i>
        </div>
        <div class="brief-info">
          <div class="brief-row">
            <span class="device-alias">{{ device.remark || device.model || '未命名设备' }}</span>
            <span class="device-mac" v-if="device.macAddress">MAC: {{ device.macAddress }}</span>
          </div>
          <div class="brief-agent">
            <i class="el-icon-user"></i>
            <span>所属智能体: <strong>{{ device.agentName || '默认智能体' }}</strong></span>
            <span class="current-voice-hint" v-if="device.ttsVoiceName">
              (当前生效音色: {{ device.ttsVoiceName }})
            </span>
          </div>
        </div>
      </div>

      <!-- 模式选择卡片 -->
      <div class="section-title">音色配置模式</div>
      <div class="mode-selector-grid">
        <div
          class="mode-card"
          :class="{ 'is-active': voiceMode === 'inherit' }"
          @click="voiceMode = 'inherit'"
        >
          <div class="mode-radio-icon">
            <i :class="voiceMode === 'inherit' ? 'el-icon-circle-check' : 'el-icon-circle-close'"></i>
          </div>
          <div class="mode-content">
            <div class="mode-title">跟随所属智能体配置</div>
            <div class="mode-desc">设备自动继承智能体设置的默认 TTS 语音引擎与音色，随智能体全局变化。</div>
          </div>
        </div>

        <div
          class="mode-card"
          :class="{ 'is-active': voiceMode === 'custom' }"
          @click="voiceMode = 'custom'"
        >
          <div class="mode-radio-icon">
            <i :class="voiceMode === 'custom' ? 'el-icon-circle-check' : 'el-icon-circle-close'"></i>
          </div>
          <div class="mode-content">
            <div class="mode-title">独立配置专属音色</div>
            <div class="mode-desc">为本台硬件设备指定独立的语音与语速参数，不受其他设备或智能体默认音色影响。</div>
          </div>
        </div>
      </div>

      <!-- 自定义配置表单区 -->
      <transition name="el-fade-in-linear">
        <div v-show="voiceMode === 'custom'" class="custom-voice-section">
          <!-- TTS 引擎选择与火山快捷导入 -->
          <div class="form-item-group">
            <div class="form-label-row">
              <span class="form-label">TTS 语音引擎</span>
              <button
                v-if="isHuoshanModel"
                class="quick-import-btn"
                :disabled="importingHuoshan"
                @click="handleImportHuoshan"
              >
                <i :class="importingHuoshan ? 'el-icon-loading' : 'el-icon-download'"></i>
                <span>{{ importingHuoshan ? '正在导入...' : '一键同步火山官方音色库' }}</span>
              </button>
            </div>
            <el-select
              v-model="form.ttsModelId"
              placeholder="请选择 TTS 语音引擎"
              class="full-width-select"
              :loading="loadingModels"
              @change="handleTtsModelChange"
            >
              <el-option
                v-for="model in ttsModelOptions"
                :key="model.value"
                :label="model.label"
                :value="model.value"
              />
            </el-select>
          </div>

          <!-- 音色选择与试听播放 -->
          <div class="form-item-group">
            <div class="form-label-row">
              <span class="form-label">专属音色选择</span>
              <span class="voice-count-hint" v-if="voiceOptions.length > 0">
                (已加载 {{ voiceOptions.length }} 种音色)
              </span>
            </div>

            <div class="voice-select-row">
              <el-select
                v-model="form.ttsVoiceId"
                placeholder="请选择或搜索音色 (支持拼音/中文筛选)"
                filterable
                class="voice-select-inner"
                :loading="loadingVoices"
                @change="handleVoiceSelect"
              >
                <el-option
                  v-for="voice in voiceOptions"
                  :key="voice.value"
                  :label="voice.label"
                  :value="voice.value"
                >
                  <div class="voice-option-item">
                    <div class="voice-option-text">
                      <span class="voice-name">{{ voice.label }}</span>
                      <span v-if="voice.languages" class="voice-lang-tag">{{ voice.languages }}</span>
                      <span v-if="voice.isSeed2" class="voice-seed-tag">Seed 2.0</span>
                    </div>
                    <button
                      v-if="voice.voiceDemo"
                      class="voice-preview-btn"
                      :class="{ 'is-playing': playingVoiceId === voice.value }"
                      @click.stop="togglePlayVoice(voice)"
                      title="试听音色"
                    >
                      <i :class="playingVoiceId === voice.value ? 'el-icon-video-pause' : 'el-icon-video-play'"></i>
                      <span>{{ playingVoiceId === voice.value ? '暂停' : '试听' }}</span>
                    </button>
                  </div>
                </el-option>
              </el-select>

              <!-- 当前选中音色的快捷试听按钮 -->
              <el-button
                class="test-listen-btn"
                :disabled="!selectedVoiceDemoUrl"
                :type="isPlayingSelectedVoice ? 'warning' : 'primary'"
                plain
                @click="togglePlaySelected"
              >
                <i :class="isPlayingSelectedVoice ? 'el-icon-video-pause' : 'el-icon-video-play'"></i>
                <span>{{ isPlayingSelectedVoice ? '停止试听' : '试听选中音色' }}</span>
              </el-button>
            </div>
          </div>

          <!-- 语音参数微调：音量、语速、音调 -->
          <div class="sliders-card">
            <div class="slider-item">
              <div class="slider-header">
                <span class="slider-label">语速调整 (Speed)</span>
                <span class="slider-val">{{ form.ttsRate > 0 ? `+${form.ttsRate}` : form.ttsRate }}%</span>
              </div>
              <el-slider
                v-model="form.ttsRate"
                :min="-100"
                :max="100"
                :step="5"
                :format-tooltip="val => (val > 0 ? `+${val}%` : `${val}%`)"
              />
              <div class="slider-scale-hint">
                <span>-100% 极慢</span>
                <span>0% 正常</span>
                <span>+100% 极快</span>
              </div>
            </div>

            <div class="slider-item">
              <div class="slider-header">
                <span class="slider-label">音量调整 (Volume)</span>
                <span class="slider-val">{{ form.ttsVolume > 0 ? `+${form.ttsVolume}` : form.ttsVolume }}%</span>
              </div>
              <el-slider
                v-model="form.ttsVolume"
                :min="-100"
                :max="100"
                :step="5"
                :format-tooltip="val => (val > 0 ? `+${val}%` : `${val}%`)"
              />
              <div class="slider-scale-hint">
                <span>-100% 极轻</span>
                <span>0% 正常</span>
                <span>+100% 洪亮</span>
              </div>
            </div>

            <div class="slider-item">
              <div class="slider-header">
                <span class="slider-label">音调微调 (Pitch)</span>
                <span class="slider-val">{{ form.ttsPitch > 0 ? `+${form.ttsPitch}` : form.ttsPitch }}%</span>
              </div>
              <el-slider
                v-model="form.ttsPitch"
                :min="-100"
                :max="100"
                :step="5"
                :format-tooltip="val => (val > 0 ? `+${val}%` : `${val}%`)"
              />
              <div class="slider-scale-hint">
                <span>-100% 低沉</span>
                <span>0% 正常</span>
                <span>+100% 高亢</span>
              </div>
            </div>
          </div>
        </div>
      </transition>
    </div>
  </CustomDialog>
</template>

<script>
import Api from '@/apis/api';
import CustomDialog from './CustomDialog.vue';

export default {
  name: 'DeviceVoiceDialog',
  components: {
    CustomDialog,
  },
  props: {
    visible: {
      type: Boolean,
      default: false,
    },
    device: {
      type: Object,
      default: () => ({}),
    },
  },
  data() {
    return {
      localVisible: this.visible,
      voiceMode: 'inherit', // 'inherit' | 'custom'
      ttsModelOptions: [],
      voiceOptions: [],
      loadingModels: false,
      loadingVoices: false,
      importingHuoshan: false,
      submitting: false,
      audioPlayer: null,
      playingVoiceId: null,
      form: {
        ttsModelId: '',
        ttsVoiceId: '',
        ttsVolume: 0,
        ttsRate: 0,
        ttsPitch: 0,
      },
    };
  },
  computed: {
    dialogTitle() {
      return `配置设备音色 - ${this.device.remark || this.device.model || '硬件设备'}`;
    },
    isHuoshanModel() {
      const selected = this.ttsModelOptions.find(m => m.value === this.form.ttsModelId);
      if (!selected) return true;
      const name = (selected.label || '').toLowerCase();
      return name.includes('火山') || name.includes('huoshan') || name.includes('doubao');
    },
    selectedVoiceDemoUrl() {
      const v = this.voiceOptions.find(item => item.value === this.form.ttsVoiceId);
      return v ? v.voiceDemo : '';
    },
    isPlayingSelectedVoice() {
      return this.playingVoiceId && this.playingVoiceId === this.form.ttsVoiceId;
    },
  },
  watch: {
    visible(val) {
      this.localVisible = val;
      if (val) {
        this.initDialogData();
      } else {
        this.stopAudio();
      }
    },
  },
  beforeDestroy() {
    this.stopAudio();
  },
  methods: {
    initDialogData() {
      this.stopAudio();
      const dev = this.device || {};
      const hasCustomVoice = Boolean(dev.ttsVoiceId);

      this.voiceMode = hasCustomVoice ? 'custom' : 'inherit';
      this.form = {
        ttsModelId: dev.ttsModelId || '',
        ttsVoiceId: dev.ttsVoiceId || '',
        ttsVolume: typeof dev.ttsVolume === 'number' ? dev.ttsVolume : 0,
        ttsRate: typeof dev.ttsRate === 'number' ? dev.ttsRate : 0,
        ttsPitch: typeof dev.ttsPitch === 'number' ? dev.ttsPitch : 0,
      };

      this.loadTtsModels();
    },

    loadTtsModels() {
      this.loadingModels = true;
      Api.model.getModelNames('TTS', '', ({ data }) => {
        this.loadingModels = false;
        if (data.code === 0 && Array.isArray(data.data)) {
          this.ttsModelOptions = data.data.map(item => ({
            value: item.id,
            label: item.modelName,
          }));

          // 如果没有选定模型，优先选火山 TTS 模型，否则默认选第一个
          if (!this.form.ttsModelId && this.ttsModelOptions.length > 0) {
            const huoshan = this.ttsModelOptions.find(m =>
              m.label.includes('火山') || m.label.toLowerCase().includes('huoshan')
            );
            this.form.ttsModelId = huoshan ? huoshan.value : this.ttsModelOptions[0].value;
          }

          if (this.form.ttsModelId) {
            this.loadVoicesForModel(this.form.ttsModelId);
          }
        } else {
          this.$message.error(data.msg || '获取 TTS 模型列表失败');
        }
      });
    },

    loadVoicesForModel(ttsModelId) {
      if (!ttsModelId) {
        this.voiceOptions = [];
        return;
      }
      this.loadingVoices = true;
      Api.model.getModelVoices(ttsModelId, '', ({ data }) => {
        this.loadingVoices = false;
        if (data.code === 0 && Array.isArray(data.data)) {
          this.voiceOptions = data.data.map(v => {
            const isSeed2 = (v.name && v.name.includes('2.0')) || (v.id && v.id.includes('uranus'));
            return {
              value: v.id,
              label: v.name,
              voiceDemo: v.voiceDemo || '',
              languages: v.languages || '',
              isSeed2,
            };
          });

          // 如果没有选择具体音色且列表不为空，自动选第一个
          if (this.voiceMode === 'custom' && !this.form.ttsVoiceId && this.voiceOptions.length > 0) {
            this.form.ttsVoiceId = this.voiceOptions[0].value;
          }
        } else {
          this.voiceOptions = [];
        }
      });
    },

    handleTtsModelChange(newModelId) {
      this.form.ttsVoiceId = '';
      this.stopAudio();
      this.loadVoicesForModel(newModelId);
    },

    handleVoiceSelect() {
      this.stopAudio();
    },

    handleImportHuoshan() {
      this.$confirm(
        '确定要从火山官方语音库一键导入/同步预置音色吗？\n将导入包括通用男女声、特色方言、角色扮演、童声以及 Seed 2.0 大模型全量官方音色。',
        '同步火山音色库',
        {
          confirmButtonText: '立即导入',
          cancelButtonText: '取消',
          type: 'info',
        }
      ).then(() => {
        this.importingHuoshan = true;
        Api.timbre.importHuoshanVoices(this.form.ttsModelId, res => {
          this.importingHuoshan = false;
          if (res.code === 0) {
            this.$message.success(`成功同步 ${res.data} 个火山音色！`);
            this.loadVoicesForModel(this.form.ttsModelId);
          } else {
            this.$message.error(res.msg || '导入火山音色失败');
          }
        });
      }).catch(() => {});
    },

    togglePlayVoice(voice) {
      if (!voice || !voice.voiceDemo) {
        this.$message.warning('该音色暂无官方试听音频');
        return;
      }

      if (this.playingVoiceId === voice.value) {
        this.stopAudio();
        return;
      }

      this.stopAudio();
      try {
        this.audioPlayer = new Audio(voice.voiceDemo);
        this.playingVoiceId = voice.value;
        this.audioPlayer.play().catch(e => {
          console.warn('播放试听音频失败:', e);
          this.$message.warning('试听音频播放失败，请稍后再试');
          this.playingVoiceId = null;
        });
        this.audioPlayer.onended = () => {
          this.playingVoiceId = null;
        };
        this.audioPlayer.onerror = () => {
          this.playingVoiceId = null;
        };
      } catch (err) {
        console.error(err);
        this.playingVoiceId = null;
      }
    },

    togglePlaySelected() {
      if (!this.form.ttsVoiceId) return;
      const voice = this.voiceOptions.find(v => v.value === this.form.ttsVoiceId);
      if (voice) {
        this.togglePlayVoice(voice);
      }
    },

    stopAudio() {
      if (this.audioPlayer) {
        try {
          this.audioPlayer.pause();
          this.audioPlayer = null;
        } catch (e) {}
      }
      this.playingVoiceId = null;
    },

    handleCancel() {
      this.stopAudio();
      this.localVisible = false;
      this.$emit('update:visible', false);
    },

    handleClose() {
      this.handleCancel();
    },

    handleConfirm() {
      this.stopAudio();
      const deviceId = this.device.device_id || this.device.id;
      if (!deviceId) {
        this.$message.error('未找到有效设备ID');
        return;
      }

      let payload = {};
      if (this.voiceMode === 'inherit') {
        // 清除独立专属配置，恢复跟随智能体
        payload = {
          ttsModelId: '',
          ttsVoiceId: '',
          ttsVolume: null,
          ttsRate: null,
          ttsPitch: null,
        };
      } else {
        if (!this.form.ttsVoiceId) {
          this.$message.warning('请选择一个专属音色');
          return;
        }
        payload = {
          ttsModelId: this.form.ttsModelId || '',
          ttsVoiceId: this.form.ttsVoiceId || '',
          ttsVolume: this.form.ttsVolume,
          ttsRate: this.form.ttsRate,
          ttsPitch: this.form.ttsPitch,
        };
      }

      this.submitting = true;
      Api.device.updateDeviceInfo(deviceId, payload, ({ data }) => {
        this.submitting = false;
        if (data.code === 0) {
          this.$message.success(
            this.voiceMode === 'inherit'
              ? '已恢复跟随智能体默认音色'
              : '设备专属音色设置成功！'
          );
          this.localVisible = false;
          this.$emit('update:visible', false);
          this.$emit('refresh');
        } else {
          this.$message.error(data.msg || '保存配置失败');
        }
      });
    },
  },
};
</script>

<style lang="scss" scoped>
.device-voice-config-container {
  padding: 4px 10px 10px;
}

.device-brief-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 16px;
  background: #f1f5f9;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  margin-bottom: 20px;

  .brief-icon {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    background: linear-gradient(135deg, #4e75ff 0%, #3b82f6 100%);
    color: #ffffff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    flex-shrink: 0;
  }

  .brief-info {
    flex: 1;

    .brief-row {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 4px;

      .device-alias {
        font-size: 15px;
        font-weight: 700;
        color: #1e293b;
      }

      .device-mac {
        font-size: 12px;
        color: #64748b;
        font-family: monospace;
        background: #e2e8f0;
        padding: 1px 6px;
        border-radius: 4px;
      }
    }

    .brief-agent {
      font-size: 13px;
      color: #475569;
      display: flex;
      align-items: center;
      gap: 6px;

      strong {
        color: #3b82f6;
      }

      .current-voice-hint {
        color: #10b981;
        font-size: 12px;
      }
    }
  }
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 10px;
}

.mode-selector-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 20px;
}

.mode-card {
  border: 2px solid #e2e8f0;
  border-radius: 12px;
  padding: 14px;
  cursor: pointer;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  background: #ffffff;
  transition: all 0.2s ease;

  &:hover {
    border-color: #cbd5e1;
    background: #f8fafc;
  }

  &.is-active {
    border-color: #4e75ff;
    background: #f0f4ff;

    .mode-radio-icon {
      color: #4e75ff;
    }

    .mode-title {
      color: #1e40af;
    }
  }

  .mode-radio-icon {
    font-size: 20px;
    color: #94a3b8;
    margin-top: 2px;
  }

  .mode-content {
    flex: 1;

    .mode-title {
      font-size: 14px;
      font-weight: 600;
      color: #1e293b;
      margin-bottom: 4px;
    }

    .mode-desc {
      font-size: 12px;
      color: #64748b;
      line-height: 1.4;
    }
  }
}

.custom-voice-section {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
  margin-top: 6px;
}

.form-item-group {
  margin-bottom: 16px;

  .form-label-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;

    .form-label {
      font-size: 13px;
      font-weight: 600;
      color: #334155;
    }

    .voice-count-hint {
      font-size: 12px;
      color: #64748b;
    }

    .quick-import-btn {
      border: 1px dashed #3b82f6;
      background: #eff6ff;
      color: #2563eb;
      border-radius: 14px;
      font-size: 12px;
      padding: 3px 10px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      transition: all 0.2s;

      &:hover:not(:disabled) {
        background: #dbeafe;
        border-color: #2563eb;
      }

      &:disabled {
        opacity: 0.6;
        cursor: not-allowed;
      }
    }
  }

  .full-width-select {
    width: 100%;
  }

  .voice-select-row {
    display: flex;
    gap: 10px;
    align-items: center;

    .voice-select-inner {
      flex: 1;
    }

    .test-listen-btn {
      flex-shrink: 0;
      border-radius: 8px;
      height: 38px;
    }
  }
}

.voice-option-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;

  .voice-option-text {
    display: flex;
    align-items: center;
    gap: 6px;

    .voice-name {
      font-size: 13px;
      color: #1e293b;
    }

    .voice-lang-tag {
      background: #f1f5f9;
      color: #64748b;
      padding: 1px 6px;
      border-radius: 4px;
      font-size: 11px;
    }

    .voice-seed-tag {
      background: #fdf2f8;
      color: #db2777;
      border: 1px solid #fbcfe8;
      padding: 1px 5px;
      border-radius: 4px;
      font-size: 10px;
      font-weight: 600;
    }
  }

  .voice-preview-btn {
    border: none;
    background: transparent;
    color: #4e75ff;
    cursor: pointer;
    font-size: 12px;
    display: inline-flex;
    align-items: center;
    gap: 2px;
    padding: 2px 6px;
    border-radius: 4px;
    transition: all 0.15s;

    &:hover {
      background: #eff6ff;
    }

    &.is-playing {
      color: #ef4444;
      font-weight: 600;
    }
  }
}

.sliders-card {
  background: #f8fafc;
  border-radius: 10px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  border: 1px solid #edf2f7;

  .slider-item {
    .slider-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 2px;

      .slider-label {
        font-size: 13px;
        font-weight: 500;
        color: #475569;
      }

      .slider-val {
        font-size: 13px;
        font-weight: 700;
        color: #3b82f6;
        font-family: monospace;
      }
    }

    .slider-scale-hint {
      display: flex;
      justify-content: space-between;
      font-size: 11px;
      color: #94a3b8;
      margin-top: -4px;
    }
  }
}
</style>
