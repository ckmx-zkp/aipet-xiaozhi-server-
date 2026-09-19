<template>
  <div class="device-card">
    <!-- 头部：头像 + 名称 + 状态与操作 -->
    <div class="card-header">
      <div class="header-main">
        <div class="agent-avatar-wrap">
          <img :src="agentAvatar" class="agent-avatar" alt="agent avatar" />
          <span class="status-indicator" :class="{ 'is-active': isRecentlyActive }"></span>
        </div>
        <div class="agent-title-info">
          <el-tooltip :content="device.agentName" placement="top" effect="light">
            <div class="agent-name">{{ device.agentName }}</div>
          </el-tooltip>
          <div class="agent-sub-status">
            <span class="device-badge">
              <i class="el-icon-cpu"></i> {{ device.deviceCount || 0 }} {{ $t('home.devicesCountUnit') || '台设备' }}
            </span>
          </div>
        </div>
      </div>
      <div class="header-actions">
        <el-tooltip effect="light" :content="device.systemPrompt || $t('roleConfig.noPrompt') || '暂无人设提示词'" placement="top" popper-class="device-item-tooltip">
          <button class="icon-action-btn" title="查看人设">
            <i class="el-icon-info"></i>
          </button>
        </el-tooltip>
        <button class="icon-action-btn delete-btn" title="删除智能体" @click.stop="handleDelete">
          <i class="el-icon-delete"></i>
        </button>
      </div>
    </div>

    <!-- 中部：模型配置芯片（Chips） -->
    <div class="model-chips-container">
      <div class="model-chip llm-chip" :title="device.llmModelName">
        <div class="chip-icon"><i class="el-icon-magic-stick"></i></div>
        <div class="chip-text">
          <span class="chip-label">{{ $t('home.languageModel') }}:</span>
          <span class="chip-value">{{ device.llmModelName || '-' }}</span>
        </div>
      </div>
      <div class="model-chip tts-chip" :title="`${device.ttsModelName} (${device.ttsVoiceName})`">
        <div class="chip-icon"><i class="el-icon-headset"></i></div>
        <div class="chip-text">
          <span class="chip-label">{{ $t('home.voiceModel') }}:</span>
          <span class="chip-value">{{ device.ttsVoiceName || device.ttsModelName || '-' }}</span>
        </div>
      </div>
    </div>

    <!-- 操作按钮组 -->
    <div class="action-buttons-row">
      <button class="action-pill primary-pill" @click="handleConfigure">
        <i class="el-icon-setting"></i>
        <span>{{ $t('home.configureRole') }}</span>
      </button>

      <button class="action-pill secondary-pill" @click="handleDeviceManage">
        <span>{{ $t('home.deviceManagement') }}</span>
        <span class="pill-count">({{ device.deviceCount || 0 }})</span>
      </button>

      <div
        :class="['action-pill', 'secondary-pill', { 'disabled-pill': device.memModelId === 'Memory_nomem' }]"
        @click="handleChatHistory"
      >
        <el-tooltip effect="light" v-if="device.memModelId === 'Memory_nomem'" :content="$t('home.enableMemory')" placement="top">
          <span>{{ $t('home.chatHistory') }}</span>
        </el-tooltip>
        <span v-else>{{ $t('home.chatHistory') }}</span>
      </div>

      <button
        v-if="featureStatus.voiceprintRecognition"
        class="action-pill secondary-pill"
        @click="handleVoicePrint"
      >
        <span>{{ $t('home.voiceprintRecognition') }}</span>
      </button>
    </div>

    <!-- 底部：对话时间与标签 -->
    <div class="card-footer">
      <div class="footer-time">
        <i class="el-icon-time"></i>
        <span>{{ formattedLastConnectedTime }}</span>
      </div>
      <div class="footer-tags" v-if="tags.length > 0">
        <el-tooltip :content="tags.join(', ')" placement="top" effect="light">
          <div class="tag-capsules">
            <span v-for="(tag, idx) in tags.slice(0, 2)" :key="idx" class="tag-capsule">
              {{ tag }}
            </span>
            <span v-if="tags.length > 2" class="tag-more">+{{ tags.length - 2 }}</span>
          </div>
        </el-tooltip>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'DeviceItem',
  props: {
    device: { type: Object, required: true },
    featureStatus: {
      type: Object,
      default: () => ({
        voiceprintRecognition: false,
        voiceClone: false,
        knowledgeBase: false
      })
    }
  },
  computed: {
    // 根据 agentId 计算一个确定性头像 (1-16)
    agentAvatar() {
      const id = String(this.device.agentId || this.device.id || '1');
      let hash = 0;
      for (let i = 0; i < id.length; i++) {
        hash = (hash << 5) - hash + id.charCodeAt(i);
        hash |= 0;
      }
      const avatarIndex = (Math.abs(hash) % 16) + 1;
      try {
        return require(`@/assets/device-avatars/xiaozhi-logo${avatarIndex}.png`);
      } catch (e) {
        return require('@/assets/xiaozhi-logo.png');
      }
    },
    isRecentlyActive() {
      if (!this.device.lastConnectedAt) return false;
      const lastTime = new Date(this.device.lastConnectedAt).getTime();
      const now = Date.now();
      return now - lastTime < 3600 * 1000; // 1 小时内活跃
    },
    formattedLastConnectedTime() {
      if (!this.device.lastConnectedAt) return this.$t('home.noConversation');

      const lastTime = new Date(this.device.lastConnectedAt);
      const now = new Date();
      const diffMinutes = Math.floor((now - lastTime) / (1000 * 60));

      if (diffMinutes <= 1) {
        return this.$t('home.justNow');
      } else if (diffMinutes < 60) {
        return this.$t('home.minutesAgo', { minutes: diffMinutes });
      } else if (diffMinutes < 24 * 60) {
        const hours = Math.floor(diffMinutes / 60);
        const minutes = diffMinutes % 60;
        return this.$t('home.hoursAgo', { hours, minutes });
      } else {
        return this.device.lastConnectedAt;
      }
    },
    tags() {
      if (!this.device.tags) return [];
      return this.device.tags.map((tag) => tag.tagName);
    }
  },
  methods: {
    handleDelete() {
      this.$emit('delete', this.device);
    },
    handleConfigure() {
      this.$router.push({ path: '/role-config', query: { agentId: this.device.agentId } });
    },
    handleVoicePrint() {
      this.$router.push({ path: '/voice-print', query: { agentId: this.device.agentId } });
    },
    handleDeviceManage() {
      this.$router.push({ path: '/device-management', query: { agentId: this.device.agentId } });
    },
    handleChatHistory() {
      if (this.device.memModelId === 'Memory_nomem') {
        return;
      }
      this.$emit('chat-history', { agentId: this.device.agentId, agentName: this.device.agentName });
    }
  }
};
</script>

<style lang="scss" scoped>
.device-card {
  background: #ffffff;
  border-radius: 18px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 16px -2px rgba(15, 23, 42, 0.04), 0 2px 6px -1px rgba(15, 23, 42, 0.02);
  padding: 20px 20px 16px;
  display: flex;
  flex-direction: column;
  transition: all 0.28s cubic-bezier(0.4, 0, 0.2, 1);
  box-sizing: border-box;
  position: relative;
  overflow: hidden;

  &:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 28px -4px rgba(78, 117, 255, 0.14), 0 4px 12px -2px rgba(78, 117, 255, 0.06);
    border-color: rgba(78, 117, 255, 0.35);
  }
}

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 14px;
}

.header-main {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.agent-avatar-wrap {
  position: relative;
  width: 48px;
  height: 48px;
  flex-shrink: 0;
  border-radius: 14px;
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.8), 0 2px 8px rgba(78, 117, 255, 0.12);

  .agent-avatar {
    width: 36px;
    height: 36px;
    object-fit: contain;
    border-radius: 10px;
  }

  .status-indicator {
    position: absolute;
    bottom: -1px;
    right: -1px;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #cbd5e1;
    border: 2px solid #ffffff;

    &.is-active {
      background: #10b981;
      box-shadow: 0 0 6px #10b981;
    }
  }
}

.agent-title-info {
  flex: 1;
  min-width: 0;
  text-align: left;

  .agent-name {
    font-size: 16px;
    font-weight: 700;
    color: #1e293b;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    line-height: 1.3;
    margin-bottom: 4px;
  }

  .agent-sub-status {
    display: flex;
    align-items: center;
    gap: 6px;

    .device-badge {
      display: inline-flex;
      align-items: center;
      gap: 3px;
      padding: 1px 8px;
      font-size: 11px;
      font-weight: 500;
      color: #475569;
      background: #f1f5f9;
      border-radius: 20px;
    }
  }
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 4px;

  .icon-action-btn {
    border: none;
    background: transparent;
    cursor: pointer;
    padding: 6px;
    border-radius: 8px;
    color: #94a3b8;
    font-size: 15px;
    line-height: 1;
    transition: all 0.2s ease;

    &:hover {
      background: #f1f5f9;
      color: #4e75ff;
    }

    &.delete-btn:hover {
      background: #fee2e2;
      color: #ef4444;
    }
  }
}

/* 模型配置芯片 */
.model-chips-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.model-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 10px;
  font-size: 12px;
  text-align: left;
  transition: background 0.2s ease;

  .chip-icon {
    width: 22px;
    height: 22px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    flex-shrink: 0;
  }

  .chip-text {
    flex: 1;
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;

    .chip-label {
      color: #64748b;
      margin-right: 4px;
    }

    .chip-value {
      font-weight: 600;
      color: #334155;
    }
  }

  &.llm-chip {
    background: #f8faff;
    border: 1px solid #e0eaff;

    .chip-icon {
      background: #e0ebff;
      color: #3b82f6;
    }
  }

  &.tts-chip {
    background: #faf7ff;
    border: 1px solid #f0e7fe;

    .chip-icon {
      background: #ede4ff;
      color: #8b5cf6;
    }
  }
}

/* 胶囊按钮组 */
.action-buttons-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 14px;
}

.action-pill {
  border: none;
  font-size: 12px;
  font-weight: 500;
  border-radius: 20px;
  padding: 5px 12px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  transition: all 0.22s ease;
  line-height: 1.4;

  &.primary-pill {
    background: linear-gradient(135deg, #4e75ff 0%, #3b82f6 100%);
    color: #ffffff;
    box-shadow: 0 2px 6px rgba(78, 117, 255, 0.25);

    &:hover {
      transform: translateY(-1px);
      box-shadow: 0 4px 10px rgba(78, 117, 255, 0.35);
    }
  }

  &.secondary-pill {
    background: #f1f5f9;
    color: #475569;

    .pill-count {
      font-size: 11px;
      color: #64748b;
    }

    &:hover {
      background: #e2e8f0;
      color: #1e293b;
      transform: translateY(-1px);
    }
  }

  &.disabled-pill {
    background: #f8fafc;
    color: #cbd5e1;
    cursor: not-allowed;

    &:hover {
      transform: none;
      background: #f8fafc;
    }
  }
}

/* 卡片底部 */
.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 10px;
  border-top: 1px solid #f1f5f9;
  font-size: 12px;
  color: #94a3b8;
}

.footer-time {
  display: flex;
  align-items: center;
  gap: 4px;
}

.footer-tags {
  display: flex;
  align-items: center;
}

.tag-capsules {
  display: flex;
  gap: 4px;

  .tag-capsule {
    background: #f1f5f9;
    color: #64748b;
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 11px;
    max-width: 70px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .tag-more {
    font-size: 11px;
    color: #94a3b8;
  }
}
</style>

<style>
.device-item-tooltip {
  max-height: 60vh !important;
  max-width: 400px !important;
  overflow-y: auto !important;
  scrollbar-width: thin;
  word-break: break-word;
  border-radius: 8px !important;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12) !important;
}

.device-item-tooltip .popper__arrow {
  display: none !important;
}
</style>
