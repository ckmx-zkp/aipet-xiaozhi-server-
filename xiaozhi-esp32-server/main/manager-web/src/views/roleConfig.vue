<template>
  <div class="welcome role-config-page">
    <HeaderBar />

    <div class="main-wrapper" v-loading="agentReloading">
      <!-- 顶部吸顶控制条 -->
      <div class="agent-control-header">
        <div class="header-left">
          <div class="header-icon">
            <img loading="lazy" src="@/assets/home/setting-user.png" alt="" />
          </div>
          <div class="header-title-wrap">
            <div class="title-row">
              <span class="header-title">{{ form.agentName || $t("roleConfig.title") }}</span>
              <span v-if="currentVersionNo" class="current-version-tag">
                {{ $t("roleConfig.currentVersion", { version: currentVersionNo }) }}
              </span>
            </div>
            <div class="header-tags">
              <el-tag
                v-for="tag in dynamicTags"
                :key="tag.id"
                class="custom-tag"
                closable
                :disable-transitions="false"
                @close="handleClose(tag.id)">
                {{tag.tagName}}
              </el-tag>
              <el-input
                class="input-new-tag"
                v-if="inputVisible"
                v-model="inputValue"
                ref="saveTagInput"
                size="small"
                maxLength="20"
                @keyup.enter.native="handleInputConfirm"
                @blur="handleInputConfirm"
              />
              <button class="add-tag-pill-btn" v-else @click="showInput">+ {{ $t("roleConfig.addTag") }}</button>
            </div>
          </div>
        </div>

        <div class="header-actions">
          <div class="hint-text">
            <i class="el-icon-info"></i>
            <span>{{ $t("roleConfig.restartNotice") }}</span>
          </div>
          <button class="config-btn secondary-btn" @click="showSnapshotDialog = true">
            <i class="el-icon-time"></i>
            <span>{{ $t("roleConfig.snapshotHistory") }}</span>
          </button>
          <button class="config-btn neutral-btn" @click="resetConfig">
            <i class="el-icon-refresh-left"></i>
            <span>{{ $t("roleConfig.reset") }}</span>
          </button>
          <button
            class="config-btn primary-btn"
            :disabled="configInteractionBlocked"
            @click="saveConfig"
          >
            <i class="el-icon-check"></i>
            <span>{{ $t("roleConfig.saveConfig") }}</span>
          </button>
          <button class="custom-close-btn" @click="goToHome" title="返回">
            <i class="el-icon-close"></i>
          </button>
        </div>
      </div>

      <!-- 表单卡片区域 -->
      <div class="sections-scroll-area">
        <el-form ref="form" :model="form" label-position="top">
          <div class="config-sections-container">
            
            <!-- 分区 1：基础档案 -->
            <div class="section-card">
              <div class="section-header">
                <div class="section-icon basic-icon"><i class="el-icon-user"></i></div>
                <div class="section-title-wrap">
                  <h3 class="section-title">{{ $t('roleConfig.agentName') }} & 基础档案</h3>
                  <p class="section-desc">设定智能体的基本名称、套用预设模板或配置上下文连接</p>
                </div>
              </div>
              <div class="section-body">
                <div class="form-row-2">
                  <el-form-item class="form-item-flex">
                    <template #label>
                      <el-tooltip :content="$t('roleConfig.tooltip.agentName')" placement="top" effect="light" popper-class="custom-tooltip">
                        <span class="custom-label">{{ $t('roleConfig.agentName') }} <i class="el-icon-question"></i></span>
                      </el-tooltip>
                    </template>
                    <el-input
                      v-model="form.agentName"
                      class="modern-input"
                      maxlength="64"
                      :placeholder="$t('roleConfig.pleaseEnterContent')"
                    />
                  </el-form-item>

                  <el-form-item class="form-item-flex context-provider-item">
                    <template #label>
                      <el-tooltip :content="$t('roleConfig.tooltip.contextProvider')" placement="top" effect="light" popper-class="custom-tooltip">
                        <span class="custom-label">{{ $t('roleConfig.contextProvider') }} <i class="el-icon-question"></i></span>
                      </el-tooltip>
                    </template>
                    <div class="context-provider-inner">
                      <span class="provider-status-text">
                        {{ $t('roleConfig.contextProviderSuccess', { count: currentContextProviders.length }) }}
                        <a href="https://github.com/xinnan-tech/xiaozhi-esp32-server/blob/main/docs/context-provider-integration.md" target="_blank" class="doc-link">{{ $t('roleConfig.contextProviderDocLink') }}</a>
                      </span>
                      <button
                        type="button"
                        class="modern-pill-btn"
                        @click="openContextProviderDialog"
                      >
                        <i class="el-icon-connection"></i>
                        {{ $t('roleConfig.editContextProvider') }}
                      </button>
                    </div>
                  </el-form-item>
                </div>

                <!-- 预设角色模板 -->
                <el-form-item style="margin-bottom: 0;">
                  <template #label>
                    <el-tooltip :content="$t('roleConfig.tooltip.roleTemplate')" placement="top" effect="light" popper-class="custom-tooltip">
                      <span class="custom-label">{{ $t('roleConfig.roleTemplate') }} <i class="el-icon-question"></i></span>
                    </el-tooltip>
                  </template>
                  <div class="template-container">
                    <div
                      v-for="(template, index) in templates"
                      :key="`template-${index}`"
                      class="template-pill-item"
                      :class="{ 'template-loading': loadingTemplate }"
                      @click="selectTemplate(template)"
                    >
                      <i class="el-icon-magic-stick"></i>
                      <span>{{ template.agentName }}</span>
                    </div>
                  </div>
                </el-form-item>
              </div>
            </div>

            <!-- 分区 2：模型大脑与智能 -->
            <div class="section-card">
              <div class="section-header">
                <div class="section-icon brain-icon"><i class="el-icon-cpu"></i></div>
                <div class="section-title-wrap">
                  <h3 class="section-title">AI 大脑与多模态模型</h3>
                  <p class="section-desc">配置对话核心语言模型（LLM）、端侧协同模型（SLM）及视觉感知（VLLM）</p>
                </div>
                <div class="section-header-extra" v-if="allFunctions.length > 0 || currentFunctions.length > 0">
                  <button type="button" class="modern-pill-btn function-manage-btn" @click="openFunctionDialog">
                    <i class="el-icon-s-operation"></i>
                    <span>{{ $t("roleConfig.editFunctions") }} ({{ currentFunctions.length }})</span>
                  </button>
                </div>
              </div>
              <div class="section-body">
                <div class="form-row-2">
                  <el-form-item class="form-item-flex">
                    <template #label>
                      <el-tooltip :content="$t('roleConfig.tooltip.llm')" placement="top" effect="light" popper-class="custom-tooltip">
                        <span class="custom-label">{{ $t('roleConfig.llm') }} <i class="el-icon-question"></i></span>
                      </el-tooltip>
                    </template>
                    <el-select
                      v-model="form.model.llmModelId"
                      filterable
                      :placeholder="$t('roleConfig.pleaseSelect')"
                      class="modern-select"
                      @change="handleModelChange('LLM', $event)"
                    >
                      <el-option
                        v-for="(item, optionIndex) in modelOptions['LLM']"
                        :key="`option-llm-${optionIndex}`"
                        :label="item.label"
                        :value="item.value"
                      />
                    </el-select>
                  </el-form-item>

                  <el-form-item class="form-item-flex">
                    <template #label>
                      <el-tooltip :content="$t('roleConfig.tooltip.slm')" placement="top" effect="light" popper-class="custom-tooltip">
                        <span class="custom-label">{{ $t('roleConfig.slm') }} <i class="el-icon-question"></i></span>
                      </el-tooltip>
                    </template>
                    <el-select
                      v-model="form.model.slmModelId"
                      filterable
                      :placeholder="$t('roleConfig.pleaseSelect')"
                      class="modern-select"
                    >
                      <el-option
                        v-for="(item, optionIndex) in modelOptions['LLM']"
                        :key="`option-slm-${optionIndex}`"
                        :label="item.label"
                        :value="item.value"
                      />
                    </el-select>
                  </el-form-item>
                </div>

                <!-- VLLM 视觉多模态 与 Intent 意图识别 -->
                <div class="form-row-2" v-if="modelOptions['VLLM'] || modelOptions['Intent']">
                  <el-form-item class="form-item-flex" v-if="modelOptions['VLLM']">
                    <template #label>
                      <el-tooltip :content="$t('roleConfig.tooltip.vllm')" placement="top" effect="light" popper-class="custom-tooltip">
                        <span class="custom-label">{{ $t('roleConfig.vllm') }} <i class="el-icon-question"></i></span>
                      </el-tooltip>
                    </template>
                    <el-select
                      v-model="form.model.vllmModelId"
                      filterable
                      clearable
                      :placeholder="$t('roleConfig.pleaseSelect')"
                      class="modern-select"
                      @change="handleModelChange('VLLM', $event)"
                    >
                      <el-option
                        v-for="(item, optionIndex) in modelOptions['VLLM']"
                        :key="`option-vllm-${optionIndex}`"
                        :label="item.label"
                        :value="item.value"
                      />
                    </el-select>
                  </el-form-item>

                  <el-form-item class="form-item-flex" v-if="modelOptions['Intent']">
                    <template #label>
                      <el-tooltip :content="$t('roleConfig.tooltip.intent')" placement="top" effect="light" popper-class="custom-tooltip">
                        <span class="custom-label">{{ $t('roleConfig.intent') }} <i class="el-icon-question"></i></span>
                      </el-tooltip>
                    </template>
                    <el-select
                      v-model="form.model.intentModelId"
                      filterable
                      clearable
                      :placeholder="$t('roleConfig.pleaseSelect')"
                      class="modern-select"
                      @change="handleModelChange('Intent', $event)"
                    >
                      <el-option
                        v-for="(item, optionIndex) in modelOptions['Intent']"
                        :key="`option-intent-${optionIndex}`"
                        :label="item.label"
                        :value="item.value"
                      />
                    </el-select>
                  </el-form-item>
                </div>

                <!-- 当前启用的工具微徽标 -->
                <div v-if="currentFunctions.length > 0" class="current-functions-bar">
                  <span class="functions-bar-label">已启用 MCP 函数工具:</span>
                  <div class="functions-capsules-wrap">
                    <el-tooltip
                      v-for="func in currentFunctions"
                      :key="func.name"
                      effect="light"
                      placement="top"
                    >
                      <div slot="content">
                        <div><strong>{{ $t("roleConfig.functionName") }}:</strong> {{ func.name }}</div>
                      </div>
                      <span class="function-mini-tag">
                        <span class="func-dot"></span>
                        {{ func.name }}
                      </span>
                    </el-tooltip>
                  </div>
                </div>
              </div>
            </div>

            <!-- 分区 3：声音与表达 -->
            <div class="section-card">
              <div class="section-header">
                <div class="section-icon voice-icon"><i class="el-icon-headset"></i></div>
                <div class="section-title-wrap">
                  <h3 class="section-title">语音交互与声音</h3>
                  <p class="section-desc">配置智能体的语音活动检测（VAD）、语音识别（ASR）与语音合成音色（TTS）</p>
                </div>
              </div>
              <div class="section-body">
                <!-- VAD 与 ASR -->
                <div class="form-row-2">
                  <el-form-item v-if="featureStatus.vad" class="form-item-flex">
                    <template #label>
                      <el-tooltip :content="$t('roleConfig.tooltip.vad')" placement="top" effect="light" popper-class="custom-tooltip">
                        <span class="custom-label">{{ $t('roleConfig.vad') }} <i class="el-icon-question"></i></span>
                      </el-tooltip>
                    </template>
                    <el-select
                      v-model="form.model.vadModelId"
                      filterable
                      :placeholder="$t('roleConfig.pleaseSelect')"
                      class="modern-select"
                      @change="handleModelChange('VAD', $event)"
                    >
                      <el-option
                        v-for="(item, optionIndex) in modelOptions['VAD']"
                        :key="`option-vad-${optionIndex}`"
                        :label="item.label"
                        :value="item.value"
                      />
                    </el-select>
                  </el-form-item>

                  <el-form-item v-if="featureStatus.asr" class="form-item-flex">
                    <template #label>
                      <el-tooltip :content="$t('roleConfig.tooltip.asr')" placement="top" effect="light" popper-class="custom-tooltip">
                        <span class="custom-label">{{ $t('roleConfig.asr') }} <i class="el-icon-question"></i></span>
                      </el-tooltip>
                    </template>
                    <el-select
                      v-model="form.model.asrModelId"
                      filterable
                      :placeholder="$t('roleConfig.pleaseSelect')"
                      class="modern-select"
                      @change="handleModelChange('ASR', $event)"
                    >
                      <el-option
                        v-for="(item, optionIndex) in modelOptions['ASR']"
                        :key="`option-asr-${optionIndex}`"
                        :label="item.label"
                        :value="item.value"
                      />
                    </el-select>
                  </el-form-item>
                </div>

                <!-- TTS 模型 与 语言筛选 -->
                <div class="form-row-2">
                  <el-form-item class="form-item-flex">
                    <template #label>
                      <el-tooltip :content="$t('roleConfig.tooltip.tts')" placement="top" effect="light" popper-class="custom-tooltip">
                        <span class="custom-label">{{ $t('roleConfig.tts') }} <i class="el-icon-question"></i></span>
                      </el-tooltip>
                    </template>
                    <el-select
                      v-model="form.model.ttsModelId"
                      filterable
                      :disabled="voiceOptionsLoading"
                      :placeholder="$t('roleConfig.pleaseSelect')"
                      class="modern-select"
                      @change="handleModelChange('TTS', $event)"
                    >
                      <el-option
                        v-for="(item, optionIndex) in modelOptions['TTS']"
                        v-if="!item.isHidden"
                        :key="`option-tts-${optionIndex}`"
                        :label="item.label"
                        :value="item.value"
                      />
                    </el-select>
                  </el-form-item>

                  <el-form-item class="form-item-flex">
                    <template #label>
                      <el-tooltip :content="$t('roleConfig.tooltip.language')" placement="top" effect="light" popper-class="custom-tooltip">
                        <span class="custom-label">{{ $t('roleConfig.language') }} <i class="el-icon-question"></i></span>
                      </el-tooltip>
                    </template>
                    <el-select
                      v-model="selectedLanguage"
                      :disabled="voiceOptionsLoading"
                      :placeholder="$t('roleConfig.selectLanguage')"
                      class="modern-select"
                      @change="handleLanguageChange"
                    >
                      <el-option
                        v-for="(lang, index) in languageOptions"
                        :key="`lang-${index}`"
                        :label="lang.label"
                        :value="lang.value"
                      />
                    </el-select>
                  </el-form-item>
                </div>

                <!-- 音色选择与试听播放 -->
                <div class="form-row-full">
                  <el-form-item style="margin-bottom: 0;">
                    <template #label>
                      <el-tooltip :content="$t('roleConfig.tooltip.voiceType')" placement="top" effect="light" popper-class="custom-tooltip">
                        <span class="custom-label">{{ $t('roleConfig.voiceType') }} <i class="el-icon-question"></i></span>
                      </el-tooltip>
                    </template>
                    <div class="voice-row-inner">
                      <el-select
                        v-model="form.ttsVoiceId"
                        filterable
                        :disabled="voiceOptionsLoading"
                        :placeholder="$t('roleConfig.pleaseSelect')"
                        class="modern-select voice-select"
                        @change="handleVoiceChange"
                      >
                        <el-option
                          v-for="(item, index) in voiceOptions"
                          :key="`voice-${index}`"
                          :label="item.label"
                          :value="item.value"
                        >
                          <div class="voice-option-row">
                            <span>{{ item.label }}</span>
                            <template v-if="hasAudioPreview(item)">
                              <el-button
                                type="text"
                                :icon="
                                  playingVoice &&
                                  currentPlayingVoiceId === item.value &&
                                  !isPaused
                                    ? 'el-icon-video-pause'
                                    : 'el-icon-video-play'
                                "
                                size="small"
                                @click.stop="toggleAudioPlayback(item.value)"
                                :loading="false"
                                class="play-button"
                              />
                            </template>
                          </div>
                        </el-option>
                      </el-select>

                      <button
                        type="button"
                        class="modern-pill-btn"
                        @click="openTtsAdvancedSettings"
                      >
                        <i class="el-icon-tune"></i>
                        {{ $t('roleConfig.advancedSettings') }}
                      </button>
                    </div>
                  </el-form-item>
                </div>
              </div>
            </div>

            <!-- 分区 4：人设提示词与记忆 -->
            <div class="section-card">
              <div class="section-header">
                <div class="section-icon prompt-icon"><i class="el-icon-chat-line-round"></i></div>
                <div class="section-title-wrap">
                  <h3 class="section-title">人设提示词与长期记忆</h3>
                  <p class="section-desc">定制智能体性格、口吻、回复规范及上下文历史记忆</p>
                </div>
              </div>
              <div class="section-body">
                <!-- 系统人设提示词 -->
                <el-form-item>
                  <template #label>
                    <el-tooltip :content="$t('roleConfig.tooltip.roleIntroduction')" placement="top" effect="light" popper-class="custom-tooltip">
                      <span class="custom-label">{{ $t('roleConfig.roleIntroduction') }} (System Prompt) <i class="el-icon-question"></i></span>
                    </el-tooltip>
                  </template>
                  <el-input
                    type="textarea"
                    rows="7"
                    resize="vertical"
                    :placeholder="$t('roleConfig.pleaseEnterContent')"
                    v-model="form.systemPrompt"
                    maxlength="2000"
                    show-word-limit
                    class="modern-textarea"
                  />
                </el-form-item>

                <!-- 记忆模型与聊天历史 -->
                <div class="form-row-2">
                  <el-form-item class="form-item-flex" v-if="modelOptions['Memory']">
                    <template #label>
                      <el-tooltip :content="$t('roleConfig.tooltip.memory')" placement="top" effect="light" popper-class="custom-tooltip">
                        <span class="custom-label">{{ $t('roleConfig.memory') }} <i class="el-icon-question"></i></span>
                      </el-tooltip>
                    </template>
                    <el-select
                      v-model="form.model.memModelId"
                      filterable
                      :placeholder="$t('roleConfig.pleaseSelect')"
                      class="modern-select"
                      @change="handleModelChange('Memory', $event)"
                    >
                      <el-option
                        v-for="(item, optionIndex) in modelOptions['Memory']"
                        :key="`option-mem-${optionIndex}`"
                        :label="item.label"
                        :value="item.value"
                      />
                    </el-select>
                  </el-form-item>

                  <el-form-item
                    class="form-item-flex"
                    v-if="form.model.memModelId && form.model.memModelId !== 'Memory_nomem'"
                  >
                    <template #label>
                      <span class="custom-label">上下文对话历史记录形式</span>
                    </template>
                    <div class="modern-radio-wrap">
                      <el-radio-group
                        v-model="form.chatHistoryConf"
                        @change="updateChatHistoryConf"
                        class="modern-pill-radios"
                      >
                        <el-radio-button :label="1">{{ $t("roleConfig.reportText") }}</el-radio-button>
                        <el-radio-button :label="2">{{ $t("roleConfig.reportTextVoice") }}</el-radio-button>
                      </el-radio-group>
                    </div>
                  </el-form-item>
                </div>

                <!-- 长期记忆摘要 -->
                <el-form-item style="margin-bottom: 0;">
                  <template #label>
                    <el-tooltip :content="$t('roleConfig.tooltip.memoryHis')" placement="top" effect="light" popper-class="custom-tooltip">
                      <span class="custom-label">{{ $t('roleConfig.memoryHis') }} <i class="el-icon-question"></i></span>
                    </el-tooltip>
                  </template>
                  <el-input
                    type="textarea"
                    rows="3"
                    resize="vertical"
                    v-model="form.summaryMemory"
                    maxlength="2000"
                    show-word-limit
                    class="modern-textarea"
                    :disabled="form.model.memModelId !== 'Memory_mem_local_short'"
                    :placeholder="form.model.memModelId === 'Memory_mem_local_short' ? '智能体对话中自动萃取的长期记忆摘要...' : '当前记忆模型无需配置长期摘要'"
                  />
                </el-form-item>
              </div>
            </div>

          </div>
        </el-form>
      </div>
    </div>
    <function-dialog
      v-model="showFunctionDialog"
      :functions="currentFunctions"
      :all-functions="allFunctions"
      :agent-id="$route.query.agentId"
      @update-functions="handleUpdateFunctions"
      @dialog-closed="handleDialogClosed"
    />
    <context-provider-dialog
      :visible.sync="showContextProviderDialog"
      :providers="currentContextProviders"
      @confirm="handleUpdateContext"
    />
    <tts-advanced-settings
      :visible.sync="showTtsAdvancedDialog"
      :settings="ttsSettings"
      :checked-replacement-word-ids="checkedReplacementWordIds"
      @save="handleTtsSettingsSave"
    />
      <agent-snapshot-dialog
        v-if="$route.query.agentId"
        :visible.sync="showSnapshotDialog"
        :agent-id="$route.query.agentId"
        :current-version-no="currentVersionNo"
        @restored="handleSnapshotRestored"
      />
    <el-footer>
      <version-footer />
    </el-footer>
  </div>
</template>

<script>
import Api from "@/apis/api";
import { getServiceUrl } from "@/apis/api";
import RequestService from "@/apis/httpRequest";
import FunctionDialog from "@/components/FunctionDialog.vue";
import ContextProviderDialog from "@/components/ContextProviderDialog.vue";
import TtsAdvancedSettings from "@/components/TtsAdvancedSettings.vue";
import AgentSnapshotDialog from "@/components/AgentSnapshotDialog.vue";
import HeaderBar from "@/components/HeaderBar.vue";
import i18n from "@/i18n";
import featureManager from "@/utils/featureManager"; 
import VersionFooter from "@/components/VersionFooter.vue";

export default {
  name: "RoleConfigPage",
  components: { HeaderBar, FunctionDialog, ContextProviderDialog, TtsAdvancedSettings, AgentSnapshotDialog, VersionFooter },
  data() {
    return {
      showContextProviderDialog: false,
      showTtsAdvancedDialog: false,
      showSnapshotDialog: false,
      ttsSettings: {
        volume: 0,
        speed: 0,
        pitch: 0
      },
      tempSummaryMemory: "",
      form: {
        agentCode: "",
        agentName: "",
        ttsVoiceId: "",
        ttsVolume: null,
        ttsRate: null,
        ttsPitch: null,
        chatHistoryConf: 0,
        systemPrompt: "",
        summaryMemory: "",
        langCode: "",
        language: "",
        sort: "",
        model: {
          ttsModelId: "",
          vadModelId: "",
          asrModelId: "",
          llmModelId: "",
          slmModelId: "",
          vllmModelId: "",
          memModelId: "",
          intentModelId: "",
        },
      },
      models: [
        { label: this.$t("roleConfig.vad"), key: "vadModelId", type: "VAD" },
        { label: this.$t("roleConfig.asr"), key: "asrModelId", type: "ASR" },
        { label: this.$t("roleConfig.llm"), key: "llmModelId", type: "LLM" },
        { label: this.$t("roleConfig.slm"), key: "slmModelId", type: "SLM" },
        { label: this.$t("roleConfig.vllm"), key: "vllmModelId", type: "VLLM" },
        { label: this.$t("roleConfig.intent"), key: "intentModelId", type: "Intent" },
        { label: this.$t("roleConfig.memory"), key: "memModelId", type: "Memory" },
        { label: this.$t("roleConfig.tts"), key: "ttsModelId", type: "TTS" },
      ],
      llmModeTypeMap: new Map(),
      modelOptions: {},
      templates: [],
      loadingTemplate: false,
      voiceOptions: [],
      voiceDetails: {}, // 保存完整的音色信息
      showFunctionDialog: false,
      currentVersionNo: null,
      currentFunctions: [],
      currentContextProviders: [],
      allFunctions: [],
      originalFunctions: [],
      playingVoice: false,
      isPaused: false,
      currentAudio: null,
      currentPlayingVoiceId: null,
      // 语言筛选相关状态
      languageOptions: [], // 语言选项列表
      selectedLanguage: '', // 当前选中的语言
      ttsLanguageTouched: false,
      ttsVoiceTouched: false,
      voiceFetchSeq: 0,
      voiceOptionsLoading: false,
      lastValidTtsDraft: null,
      agentReloading: false,
      agentReloadSeq: 0,
      agentConfigFetchSeq: 0,
      agentTagsFetchSeq: 0,
      currentVersionFetchSeq: 0,
      agentConfigLoaded: false,
      agentFunctionsLoaded: false,
      agentTagsLoaded: false,
      currentVersionLoaded: false,
      pluginMetadataReady: false,
      pluginMetadataLoading: null,
      // 功能状态
      featureStatus: {
        vad: false, // 语言检测活动功能状态
        asr: false, // 语音识别功能状态
      },
      dynamicTags: [],
      originalTagNames: [],
      inputVisible: false,
      inputValue: '',
      checkedReplacementWordIds: []
    };
  },
  computed: {
    configInteractionBlocked() {
      return this.agentReloading
        || this.voiceOptionsLoading
        || !this.agentConfigLoaded
        || !this.agentFunctionsLoaded
        || !this.agentTagsLoaded;
    }
  },
  methods: {
    goToHome() {
      this.$router.push("/home");
    },
    normalizeFunctionParams(params, fallback = {}) {
      if (params === null || params === undefined || params === '') {
        return { ...fallback };
      }
      if (typeof params === 'string') {
        try {
          const parsed = JSON.parse(params);
          return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
            ? parsed
            : { ...fallback };
        } catch (error) {
          return { ...fallback };
        }
      }
      if (typeof params === 'object' && !Array.isArray(params)) {
        return { ...params };
      }
      return { ...fallback };
    },
    async saveConfig() {
      if (this.configInteractionBlocked) {
        return;
      }
      const configData = {
        agentCode: this.form.agentCode,
        agentName: this.form.agentName,
        asrModelId: this.form.model.asrModelId,
        vadModelId: this.form.model.vadModelId,
        llmModelId: this.form.model.llmModelId,
        slmModelId: this.form.model.slmModelId,
        vllmModelId: this.form.model.vllmModelId,
        ttsModelId: this.form.model.ttsModelId,
        chatHistoryConf: this.form.chatHistoryConf,
        memModelId: this.form.model.memModelId,
        intentModelId: this.form.model.intentModelId,
        systemPrompt: this.form.systemPrompt,
        summaryMemory: this.form.summaryMemory,
        langCode: this.form.langCode,
        language: this.form.language,
        sort: this.form.sort,
        functions: this.currentFunctions.map((item) => {
          return {
            pluginId: item.id,
            paramInfo: this.normalizeFunctionParams(item.params),
          };
        }),
        contextProviders: this.currentContextProviders,
        correctWordFileIds: this.checkedReplacementWordIds,
      };
      const tagNames = this.dynamicTags.map(tag => tag.tagName);
      const tagsChanged = !this.isSameStringList(tagNames, this.originalTagNames);
      if (tagsChanged) {
        configData.tagNames = tagNames;
      }
      if (this.shouldSubmitTtsLanguage()) {
        configData.ttsLanguage = this.selectedLanguage;
      }
      if (this.ttsVoiceTouched && this.form.ttsVoiceId !== null && this.form.ttsVoiceId !== undefined) {
        configData.ttsVoiceId = this.form.ttsVoiceId;
      }
      const submittedTtsLanguageTouched = this.ttsLanguageTouched;
      const submittedTtsVoiceTouched = this.ttsVoiceTouched;
      const submittedTtsLanguage = configData.ttsLanguage;
      const submittedTtsVoiceId = configData.ttsVoiceId;
      const submittedVoiceFetchSeq = this.voiceFetchSeq;

      // 只在用户设置了TTS参数时才传递（不为null/undefined）
      if (this.form.ttsVolume !== null && this.form.ttsVolume !== undefined) {
        configData.ttsVolume = this.form.ttsVolume;
      }
      if (this.form.ttsRate !== null && this.form.ttsRate !== undefined) {
        configData.ttsRate = this.form.ttsRate;
      }
      if (this.form.ttsPitch !== null && this.form.ttsPitch !== undefined) {
        configData.ttsPitch = this.form.ttsPitch;
      }
      const agentId = this.$route.query.agentId;
      Api.agent.updateAgentConfig(agentId, configData, ({ data }) => {
        if (data.code === 0) {
          const afterSave = () => {
            if (tagsChanged) {
              this.originalTagNames = [...tagNames];
            }
            if (submittedVoiceFetchSeq === this.voiceFetchSeq
              && submittedTtsLanguageTouched
              && this.selectedLanguage === submittedTtsLanguage) {
              this.form.ttsLanguage = submittedTtsLanguage;
              this.ttsLanguageTouched = false;
            }
            if (submittedVoiceFetchSeq === this.voiceFetchSeq
              && submittedTtsVoiceTouched
              && this.form.ttsVoiceId === submittedTtsVoiceId) {
              this.ttsVoiceTouched = false;
            }
            if (submittedVoiceFetchSeq === this.voiceFetchSeq) {
              this.lastValidTtsDraft = this.captureTtsDraft();
            }
            this.$message.success({
              message: i18n.t("roleConfig.saveSuccess"),
              showClose: true,
            });
            this.fetchCurrentVersion(agentId);
          };
          afterSave();
        } else {
          this.$message.error({
            message: data.msg || i18n.t("roleConfig.saveFailed"),
            showClose: true,
          });
        }
      });
      
    },
    async reloadAgentPage(agentId, options = {}) {
      if (!agentId) {
        return false;
      }
      const requestSeq = ++this.agentReloadSeq;
      this.agentReloading = true;
      if (options.closeEditors) {
        this.showSnapshotDialog = false;
        this.showFunctionDialog = false;
        this.showContextProviderDialog = false;
        this.showTtsAdvancedDialog = false;
        this.inputVisible = false;
      }

      const results = await Promise.all([
        this.fetchAgentConfig(agentId, { showError: false }),
        this.getAgentTags(agentId, { showError: false }),
        this.fetchCurrentVersion(agentId, { showError: false })
      ]);
      if (requestSeq !== this.agentReloadSeq) {
        return false;
      }

      this.agentReloading = false;
      if (!this.pluginMetadataReady && this.agentConfigLoaded) {
        this.$message.error(i18n.t("roleConfig.fetchPluginsFailed"));
      } else if (!results.every(Boolean)) {
        this.$message.error(i18n.t("roleConfig.fetchConfigFailed"));
      }
      return results.every(Boolean);
    },
    handleSnapshotRestored() {
      const agentId = this.$route.query.agentId;
      if (agentId) {
        this.reloadAgentPage(agentId, { closeEditors: true });
      }
    },
    fetchCurrentVersion(agentId, options = {}) {
      const requestSeq = ++this.currentVersionFetchSeq;
      this.currentVersionLoaded = false;
      if (!agentId) {
        this.currentVersionNo = null;
        this.currentVersionLoaded = true;
        return Promise.resolve(true);
      }

      return new Promise((resolve) => {
        const handleFailure = (error) => {
          if (requestSeq !== this.currentVersionFetchSeq) {
            resolve(false);
            return;
          }
          this.currentVersionLoaded = false;
          if (options.showError !== false) {
            this.$message.error(error?.data?.msg || i18n.t("roleConfig.fetchConfigFailed"));
          }
          resolve(false);
        };
        Api.agent.getDeviceConfig(agentId, ({ data }) => {
          if (requestSeq !== this.currentVersionFetchSeq) {
            resolve(false);
            return;
          }
          if (data?.code === 0) {
            this.currentVersionNo = data.data?.currentVersionNo || null;
            this.currentVersionLoaded = true;
            resolve(true);
          } else {
            handleFailure(data);
          }
        }, handleFailure);
      });
    },
    resetConfig() {
      this.$confirm(i18n.t("roleConfig.confirmReset"), i18n.t("message.info"), {
        confirmButtonText: i18n.t("button.ok"),
        cancelButtonText: i18n.t("button.cancel"),
        type: "warning",
      })
        .then(() => {
          this.selectedLanguage = "";
          this.ttsLanguageTouched = true;
          this.ttsVoiceTouched = true;
          this.form = {
            agentCode: "",
            agentName: "",
            ttsVoiceId: "",
            ttsLanguage: "",
            chatHistoryConf: 0,
            systemPrompt: "",
            summaryMemory: "",
            langCode: "",
            language: "",
            sort: "",
            model: {
              ttsModelId: "",
              vadModelId: "",
              asrModelId: "",
              llmModelId: "",
              slmModelId: "",
              vllmModelId: "",
              memModelId: "",
              intentModelId: "",
            },
          };
          this.fetchVoiceOptions("");
          this.dynamicTags = [];
          this.currentFunctions = [];
          this.$message.success({
            message: i18n.t("roleConfig.resetSuccess"),
            showClose: true,
          });
        })
        .catch(() => {});
    },
    fetchTemplates() {
      Api.agent.getAgentTemplate(({ data }) => {
        if (data.code === 0) {
          this.templates = data.data;
        } else {
          this.$message.error(data.msg || i18n.t("roleConfig.fetchTemplatesFailed"));
        }
      });
    },
    selectTemplate(template) {
      if (this.loadingTemplate) return;
      this.loadingTemplate = true;
      try {
        this.applyTemplateData(template);
        this.$message.success({
          message: `${template.agentName}${i18n.t("roleConfig.templateApplied")}`,
          showClose: true,
        });
      } catch (error) {
        this.$message.error({
          message: i18n.t("roleConfig.applyTemplateFailed"),
          showClose: true,
        });
        console.error("应用模板失败:", error);
      } finally {
        this.loadingTemplate = false;
      }
    },
    applyTemplateData(templateData) {
      const rollbackState = this.cloneTtsDraft(this.lastValidTtsDraft) || this.captureTtsDraft();
      const currentLanguage = this.selectedLanguage;
      this.form = {
        ...this.form,
        agentName: templateData.agentName || this.form.agentName,
        ttsVoiceId: templateData.ttsVoiceId || this.form.ttsVoiceId,
        chatHistoryConf: templateData.chatHistoryConf || this.form.chatHistoryConf,
        systemPrompt: templateData.systemPrompt || this.form.systemPrompt,
        summaryMemory: templateData.summaryMemory || this.form.summaryMemory,
        langCode: templateData.langCode || this.form.langCode,
        model: {
          ttsModelId: templateData.ttsModelId || this.form.model.ttsModelId,
          vadModelId: templateData.vadModelId || this.form.model.vadModelId,
          asrModelId: templateData.asrModelId || this.form.model.asrModelId,
          llmModelId: templateData.llmModelId || this.form.model.llmModelId,
          slmModelId: templateData.llmModelId || this.form.model.slmModelId,
          vllmModelId: templateData.vllmModelId || this.form.model.vllmModelId,
          memModelId: templateData.memModelId || this.form.model.memModelId,
          intentModelId: templateData.intentModelId || this.form.model.intentModelId,
        },
      };
      if (templateData.ttsLanguage) {
        this.selectedLanguage = templateData.ttsLanguage;
      }
      if (templateData.ttsModelId || templateData.ttsVoiceId || templateData.ttsLanguage) {
        this.fetchVoiceOptions(this.form.model.ttsModelId, {
          autoSelectVoice: true,
          preferredLanguage: templateData.ttsLanguage || (templateData.ttsVoiceId ? "" : currentLanguage),
          preferredVoiceId: templateData.ttsVoiceId || "",
          rollbackState,
          markTouched: true
        });
      }
    },
    buildCurrentFunctions(savedMappings) {
      if (!Array.isArray(savedMappings)) {
        throw new TypeError("Invalid agent function mappings");
      }
      return savedMappings.map((mapping) => {
        const pluginId = mapping.pluginId || mapping.id;
        const meta = this.pluginMetadataReady
          ? this.allFunctions.find((item) => item.id === pluginId)
          : null;
        return {
          id: pluginId,
          name: meta?.name || mapping.name || pluginId,
          params: this.normalizeFunctionParams(mapping.paramInfo ?? mapping.params, meta?.params || {}),
          fieldsMeta: meta?.fieldsMeta || []
        };
      }).filter((item) => item.id);
    },
    enrichCurrentFunctionsWithMetadata() {
      if (!this.agentFunctionsLoaded || !this.pluginMetadataReady) {
        return;
      }
      this.currentFunctions = this.currentFunctions.map((item) => {
        const meta = this.allFunctions.find((candidate) => candidate.id === item.id);
        if (!meta) {
          return {
            ...item,
            params: this.normalizeFunctionParams(item.params),
            fieldsMeta: item.fieldsMeta || []
          };
        }
        return {
          ...item,
          name: meta.name || item.name || item.id,
          params: this.normalizeFunctionParams(item.params, meta.params),
          fieldsMeta: meta.fieldsMeta || []
        };
      });
      this.originalFunctions = JSON.parse(JSON.stringify(this.currentFunctions));
    },
    fetchAgentConfig(agentId, options = {}) {
      const requestSeq = ++this.agentConfigFetchSeq;
      this.agentConfigLoaded = false;
      this.agentFunctionsLoaded = false;
      this.voiceFetchSeq += 1;
      this.voiceOptionsLoading = false;

      return new Promise((resolve) => {
        const handleFailure = (error) => {
          if (requestSeq !== this.agentConfigFetchSeq) {
            resolve(false);
            return;
          }
          this.agentConfigLoaded = false;
          this.agentFunctionsLoaded = false;
          if (options.showError !== false) {
            this.$message.error(error?.data?.msg || i18n.t("roleConfig.fetchConfigFailed"));
          }
          resolve(false);
        };

        Api.agent.getDeviceConfig(agentId, ({ data }) => {
          if (requestSeq !== this.agentConfigFetchSeq) {
            resolve(false);
            return;
          }
          if (data?.code !== 0 || !data.data) {
            handleFailure(data);
            return;
          }

          try {
            const agentData = data.data;
            if (agentData.functions != null && !Array.isArray(agentData.functions)) {
              throw new TypeError("Invalid agent function mappings");
            }
            if (agentData.contextProviders != null && !Array.isArray(agentData.contextProviders)) {
              throw new TypeError("Invalid context providers");
            }
            if (agentData.correctWordFileIds != null && !Array.isArray(agentData.correctWordFileIds)) {
              throw new TypeError("Invalid correct-word mappings");
            }
            this.tempSummaryMemory = "";
            this.ttsLanguageTouched = false;
            this.ttsVoiceTouched = false;
            this.form = {
              ...this.form,
              ...agentData,
              model: {
                ttsModelId: agentData.ttsModelId,
                vadModelId: agentData.vadModelId,
                asrModelId: agentData.asrModelId,
                llmModelId: agentData.llmModelId,
                slmModelId: agentData.slmModelId,
                vllmModelId: agentData.vllmModelId,
                memModelId: agentData.memModelId,
                intentModelId: agentData.intentModelId,
              },
            };
            this.selectedLanguage = agentData.ttsLanguage || "";
            this.voiceOptions = [];
            this.voiceDetails = {};
            this.languageOptions = [];
            this.lastValidTtsDraft = this.captureTtsDraft();
            this.fetchVoiceOptions(agentData.ttsModelId, {
              preferredLanguage: agentData.ttsLanguage,
              preferredVoiceId: agentData.ttsVoiceId
            });

            this.ttsSettings = {
              volume: this.form.ttsVolume || 0,
              speed: this.form.ttsRate || 0,
              pitch: this.form.ttsPitch || 0
            };
            this.checkedReplacementWordIds = agentData.correctWordFileIds || [];
            this.currentContextProviders = agentData.contextProviders || [];
            this.currentFunctions = this.buildCurrentFunctions(agentData.functions || []);
            this.originalFunctions = JSON.parse(JSON.stringify(this.currentFunctions));
            this.agentFunctionsLoaded = true;
            this.agentConfigLoaded = true;

            const metadataPromise = this.pluginMetadataReady
              ? Promise.resolve(true)
              : this.fetchAllFunctions({ showError: options.showError });
            metadataPromise.then((metadataReady) => {
              if (requestSeq === this.agentConfigFetchSeq && metadataReady) {
                this.enrichCurrentFunctionsWithMetadata();
                this.updateIntentOptionsVisibility();
              }
              resolve(true);
            }).catch(handleFailure);
          } catch (error) {
            handleFailure(error);
          }
        }, handleFailure);
      });
    },
    fetchModelOptions() {
      this.models.forEach((model) => {
        if (model.type != "LLM") {
          Api.model.getModelNames(model.type, "", ({ data }) => {
            if (data.code === 0) {
              this.$set(
                this.modelOptions,
                model.type,
                data.data.map((item) => ({
                  value: item.id,
                  label: item.modelName,
                  isHidden: false,
                }))
              );

              // 如果是意图识别选项，需要根据当前LLM类型更新可见性
              if (model.type === "Intent") {
                this.updateIntentOptionsVisibility();
              }
            } else {
              this.$message.error(data.msg || i18n.t("roleConfig.fetchModelsFailed"));
            }
          });
        } else {
          Api.model.getLlmModelCodeList("", ({ data }) => {
            if (data.code === 0) {
              let LLMdata = [];
              data.data.forEach((item) => {
                LLMdata.push({
                  value: item.id,
                  label: item.modelName,
                  isHidden: false,
                });
                this.llmModeTypeMap.set(item.id, item.type);
              });
              this.$set(this.modelOptions, model.type, LLMdata);
            } else {
              this.$message.error(data.msg || i18n.t("roleConfig.fetchModelsFailed"));
            }
          });
        }
      });
    },
    fetchVoiceOptions(modelId, options = {}) {
      const requestSeq = ++this.voiceFetchSeq;
      if (!modelId) {
        this.voiceOptionsLoading = false;
        this.voiceOptions = [];
        this.voiceDetails = {};
        this.languageOptions = [];
        this.selectedLanguage = '';
        this.lastValidTtsDraft = this.captureTtsDraft();
        return;
      }
      this.voiceOptionsLoading = true;
      Api.model.getModelVoices(modelId, "", ({ data }) => {
        if (requestSeq !== this.voiceFetchSeq) {
          return;
        }
        const draft = data.code === 0
          ? this.buildTtsDraft(modelId, data.data, options)
          : null;
        if (!draft) {
          this.handleVoiceOptionsFailure(requestSeq, options.rollbackState);
          return;
        }
        this.applyTtsDraft(draft, options);
        this.voiceOptionsLoading = false;
        this.lastValidTtsDraft = this.captureTtsDraft();
      }, () => {
        this.handleVoiceOptionsFailure(requestSeq, options.rollbackState);
      });
    },
    cloneTtsDraft(draft) {
      return draft ? JSON.parse(JSON.stringify(draft)) : null;
    },
    captureTtsDraft() {
      return {
        modelId: this.form.model.ttsModelId,
        language: this.selectedLanguage,
        storedLanguage: this.form.ttsLanguage,
        voiceId: this.form.ttsVoiceId,
        languageTouched: this.ttsLanguageTouched,
        voiceTouched: this.ttsVoiceTouched,
        voiceOptions: this.cloneTtsDraft(this.voiceOptions) || [],
        voiceDetails: this.cloneTtsDraft(this.voiceDetails) || {},
        languageOptions: this.cloneTtsDraft(this.languageOptions) || []
      };
    },
    restoreTtsDraft(draft) {
      const restored = this.cloneTtsDraft(draft);
      if (!restored) {
        return false;
      }
      this.form.model.ttsModelId = restored.modelId;
      this.selectedLanguage = restored.language;
      this.form.ttsLanguage = restored.storedLanguage;
      this.form.ttsVoiceId = restored.voiceId;
      this.ttsLanguageTouched = restored.languageTouched;
      this.ttsVoiceTouched = restored.voiceTouched;
      this.voiceOptions = restored.voiceOptions;
      this.voiceDetails = restored.voiceDetails;
      this.languageOptions = restored.languageOptions;
      this.lastValidTtsDraft = restored;
      return true;
    },
    splitVoiceLanguages(voice) {
      return voice && voice.languages
        ? voice.languages.split(/[、；;,，]/).map(lang => lang.trim()).filter(Boolean)
        : [];
    },
    buildTtsDraft(modelId, voices, options = {}) {
      if (!Array.isArray(voices) || voices.length === 0) {
        return null;
      }
      const voiceDetails = voices.reduce((result, voice) => {
        if (voice && voice.id) {
          result[voice.id] = voice;
        }
        return result;
      }, {});
      const validVoices = Object.values(voiceDetails);
      if (validVoices.length === 0) {
        return null;
      }

      const allLanguages = new Set();
      validVoices.forEach((voice) => {
        this.splitVoiceLanguages(voice).forEach((language) => allLanguages.add(language));
      });
      const languageOptions = Array.from(allLanguages).map((language) => ({
        value: language,
        label: language
      }));
      const languageExists = (language) => language
        && languageOptions.some((option) => option.value === language);
      const preferredVoiceId = options.preferredVoiceId || this.form.ttsVoiceId;
      const preferredVoiceLanguage = this.splitVoiceLanguages(voiceDetails[preferredVoiceId])[0] || "";
      const languageCandidates = [
        options.preferredLanguage,
        preferredVoiceLanguage,
        this.form.ttsLanguage,
        this.selectedLanguage,
        languageOptions[0]?.value
      ];
      const preferredVoiceHasNoLanguage = Boolean(
        voiceDetails[preferredVoiceId]
        && this.splitVoiceLanguages(voiceDetails[preferredVoiceId]).length === 0
      );
      let language = options.preferredLanguage === "" && preferredVoiceHasNoLanguage
        ? ""
        : languageCandidates.find(languageExists) || "";
      const filterVoices = (targetLanguage) => validVoices.filter((voice) => {
        const languages = this.splitVoiceLanguages(voice);
        return languages.length === 0 || languages.includes(targetLanguage);
      });
      let filteredVoices = filterVoices(language);
      if (filteredVoices.length === 0) {
        const fallbackVoice = validVoices.find((voice) => this.splitVoiceLanguages(voice).length > 0);
        if (fallbackVoice) {
          language = this.splitVoiceLanguages(fallbackVoice)[0];
          filteredVoices = filterVoices(language);
        } else {
          filteredVoices = validVoices;
        }
      }
      if (filteredVoices.length === 0) {
        return null;
      }

      const preferredVoice = filteredVoices.find((voice) => voice.id === preferredVoiceId);
      const voice = preferredVoice || (options.autoSelectVoice ? filteredVoices[0] : null);
      return {
        modelId,
        language,
        voiceId: voice?.id || preferredVoiceId || "",
        voiceDetails,
        languageOptions,
        voiceOptions: filteredVoices.map((item) => ({
          value: item.id,
          label: item.name,
          voiceDemo: item.voiceDemo,
          voice_demo: item.voice_demo,
          isClone: Boolean(item.isClone),
          train_status: item.trainStatus
        }))
      };
    },
    applyTtsDraft(draft, options = {}) {
      this.form.model.ttsModelId = draft.modelId;
      this.voiceDetails = draft.voiceDetails;
      this.languageOptions = draft.languageOptions;
      this.voiceOptions = draft.voiceOptions;
      this.selectedLanguage = draft.language;
      this.form.ttsLanguage = draft.language;
      this.form.ttsVoiceId = draft.voiceId;
      if (options.markTouched) {
        this.ttsLanguageTouched = true;
        this.ttsVoiceTouched = true;
      }
      this.ttsSettings = {
        volume: this.form.ttsVolume !== null && this.form.ttsVolume !== undefined ? this.form.ttsVolume : 0,
        speed: this.form.ttsRate !== null && this.form.ttsRate !== undefined ? this.form.ttsRate : 0,
        pitch: this.form.ttsPitch !== null && this.form.ttsPitch !== undefined ? this.form.ttsPitch : 0
      };
    },
    handleVoiceOptionsFailure(requestSeq, rollbackState) {
      if (requestSeq !== this.voiceFetchSeq) {
        return;
      }
      this.voiceOptionsLoading = false;
      if (!this.restoreTtsDraft(rollbackState)) {
        this.voiceOptions = [];
        this.voiceDetails = {};
        this.languageOptions = [];
      }
      this.$message.error(i18n.t("ttsModel.fetchVoicesFailed"));
    },
    getVoiceDefaultLanguage(voiceId) {
      if (!voiceId || !this.voiceDetails || !this.voiceDetails[voiceId]?.languages) {
        return "";
      }
      const languages = this.voiceDetails[voiceId].languages
        .split(/[、；;,，]/)
        .map(lang => lang.trim())
        .filter(Boolean);
      return languages[0] || "";
    },
    
    // 根据语言筛选音色
    filterVoicesByLanguage(options = {}) {
      if (!this.voiceDetails || Object.keys(this.voiceDetails).length === 0) {
        this.voiceOptions = [];
        return;
      }

      const allVoices = Object.values(this.voiceDetails);

      // 根据选中的语言筛选音色
      const filteredVoices = allVoices.filter(voice => {
        const languagesArray = this.splitVoiceLanguages(voice);
        if (languagesArray.length === 0) {
          // 未声明语言的合法音色由 provider 自行解释，不在前端强制过滤。
          return true;
        }
        return languagesArray.includes(this.selectedLanguage);
      });

      this.voiceOptions = filteredVoices.map((voice) => ({
        value: voice.id,
        label: voice.name,
        voiceDemo: voice.voiceDemo,
        voice_demo: voice.voice_demo,
        isClone: Boolean(voice.isClone),
        train_status: voice.trainStatus,
      }));

      // 检查当前选中的音色是否支持当前语言，如果不支持则选择第一个
      const currentVoiceSupportsLanguage = this.form.ttsVoiceId &&
        filteredVoices.some(voice => voice.id === this.form.ttsVoiceId);

      if (!currentVoiceSupportsLanguage && options.autoSelectVoice) {
        this.form.ttsVoiceId = filteredVoices.length > 0 ? filteredVoices[0].id : '';
        this.ttsVoiceTouched = true;
      }

      // 同步到ttsSettings（如果值为null，使用0作为显示默认值，但不修改form中的值）
      this.ttsSettings = {
        volume: this.form.ttsVolume !== null && this.form.ttsVolume !== undefined ? this.form.ttsVolume : 0,
        speed: this.form.ttsRate !== null && this.form.ttsRate !== undefined ? this.form.ttsRate : 0,
        pitch: this.form.ttsPitch !== null && this.form.ttsPitch !== undefined ? this.form.ttsPitch : 0
      };
    },
    handleLanguageChange() {
      this.ttsLanguageTouched = true;
      this.form.ttsLanguage = this.selectedLanguage;
      this.filterVoicesByLanguage({ autoSelectVoice: true });
      if (this.form.ttsVoiceId) {
        this.lastValidTtsDraft = this.captureTtsDraft();
      }
    },
    handleVoiceChange() {
      this.ttsVoiceTouched = true;
      if (this.selectedLanguage) {
        this.form.ttsLanguage = this.selectedLanguage;
        this.ttsLanguageTouched = true;
      }
      if (this.form.ttsVoiceId) {
        this.lastValidTtsDraft = this.captureTtsDraft();
      }
    },
    shouldSubmitTtsLanguage() {
      return this.ttsLanguageTouched;
    },

    getFunctionDisplayChar(name) {
      if (!name || name.length === 0) return "";

      for (let i = 0; i < name.length; i++) {
        const char = name[i];
        if (/[\u4e00-\u9fa5a-zA-Z0-9]/.test(char)) {
          return char;
        }
      }

      // 如果没有找到有效字符，返回第一个字符
      return name.charAt(0);
    },
    showFunctionIcons(type) {
      return type === "Intent" && this.form.model.intentModelId !== "Intent_nointent";
    },
    handleModelChange(type, value) {
      if (type === "Intent" && value !== "Intent_nointent") {
        this.fetchAllFunctions().then((metadataReady) => {
          if (metadataReady) {
            this.enrichCurrentFunctionsWithMetadata();
          }
        });
      }
      if (type === "Memory") {
        if (value === "Memory_nomem") {
          // 无记忆功能的模型，默认不记录聊天记录
          this.form.chatHistoryConf = 0;
        } else {
          // 有记忆功能的模型，默认记录文本和语音
          this.form.chatHistoryConf = 2;
        }
        if (value === "Memory_nomem" || value === "Memory_mem_report_only") {
          this.tempSummaryMemory = this.form.summaryMemory;
          this.form.summaryMemory = "";
        } else if (this.tempSummaryMemory !== "" && this.form.summaryMemory === "") {
          this.form.summaryMemory = this.tempSummaryMemory;
          this.tempSummaryMemory = "";
        }
      }
      if (type === "LLM") {
        // 当LLM类型改变时，更新意图识别选项的可见性
        this.updateIntentOptionsVisibility();
      }
      if (type === "TTS") {
        const rollbackState = this.cloneTtsDraft(this.lastValidTtsDraft);
        this.fetchVoiceOptions(value, {
          autoSelectVoice: true,
          preferredLanguage: rollbackState?.language || this.selectedLanguage,
          rollbackState,
          markTouched: true
        });
      }
    },
    parsePluginFields(fields) {
      if (Array.isArray(fields)) {
        return fields;
      }
      if (typeof fields !== "string" || !fields.trim()) {
        return [];
      }
      try {
        const parsed = JSON.parse(fields);
        return Array.isArray(parsed) ? parsed : [];
      } catch (error) {
        return [];
      }
    },
    fetchAllFunctions(options = {}) {
      if (this.pluginMetadataReady) {
        return Promise.resolve(true);
      }
      if (this.pluginMetadataLoading) {
        return this.pluginMetadataLoading;
      }

      this.pluginMetadataLoading = new Promise((resolve) => {
        let settled = false;
        const finish = (ready, error) => {
          if (settled) {
            return;
          }
          settled = true;
          this.pluginMetadataReady = ready;
          if (!ready && options.showError !== false) {
            this.$message.error(error?.data?.msg || error?.msg || i18n.t("roleConfig.fetchPluginsFailed"));
          }
          resolve(ready);
        };

        Api.model.getPluginFunctionList(null, ({ data }) => {
          if (data?.code !== 0) {
            finish(false, data);
            return;
          }
          try {
            this.allFunctions = (data.data || []).map((item) => {
              const fieldsMeta = this.parsePluginFields(item.fields);
              const params = fieldsMeta.reduce((result, field) => {
                if (field?.key) {
                  result[field.key] = field.default;
                }
                return result;
              }, {});
              return { ...item, fieldsMeta, params };
            });
            finish(true);
          } catch (error) {
            finish(false, error);
          }
        }, (error) => finish(false, error));
      }).finally(() => {
        this.pluginMetadataLoading = null;
      });

      return this.pluginMetadataLoading;
    },
    openFunctionDialog() {
      if (this.agentReloading || !this.agentFunctionsLoaded) {
        return;
      }
      if (this.pluginMetadataReady) {
        this.enrichCurrentFunctionsWithMetadata();
        this.showFunctionDialog = true;
        return;
      }
      this.fetchAllFunctions().then((metadataReady) => {
        if (metadataReady) {
          this.enrichCurrentFunctionsWithMetadata();
          this.showFunctionDialog = true;
        }
      });
    },
    openContextProviderDialog() {
      this.showContextProviderDialog = true;
    },
    openTtsAdvancedSettings() {
      this.showTtsAdvancedDialog = true;
    },
    handleTtsSettingsSave(settings) {
      const { replacementWordIds, changedTtsFields = [], ...ttsSettings } = settings;
      this.checkedReplacementWordIds = replacementWordIds;
      // 保存TTS设置
      this.ttsSettings = ttsSettings;
      const changedFields = new Set(changedTtsFields);
      if (changedFields.has("volume")) {
        this.form.ttsVolume = ttsSettings.volume;
      }
      if (changedFields.has("speed")) {
        this.form.ttsRate = ttsSettings.speed;
      }
      if (changedFields.has("pitch")) {
        this.form.ttsPitch = ttsSettings.pitch;
      }
    },
    handleUpdateContext(providers) {
      this.currentContextProviders = providers;
    },
    handleUpdateFunctions(selected) {
      this.currentFunctions = selected;
    },
    handleDialogClosed(saved) {
      if (!saved) {
        this.currentFunctions = JSON.parse(JSON.stringify(this.originalFunctions));
      } else {
        this.originalFunctions = JSON.parse(JSON.stringify(this.currentFunctions));
      }
      this.showFunctionDialog = false;
    },
    updateIntentOptionsVisibility() {
      // 根据当前选择的LLM类型更新意图识别选项的可见性
      const currentLlmId = this.form.model.llmModelId;
      if (!currentLlmId || !this.modelOptions["Intent"]) return;

      const llmType = this.llmModeTypeMap.get(currentLlmId);
      if (!llmType) return;

      this.modelOptions["Intent"].forEach((item) => {
        if (item.value === "Intent_function_call") {
          // 如果llmType是openai或ollama，允许选择function_call
          // 否则隐藏function_call选项
          if (llmType === "openai" || llmType === "ollama") {
            item.isHidden = false;
          } else {
            item.isHidden = true;
          }
        } else {
          // 其他意图识别选项始终可见
          item.isHidden = false;
        }
      });

      // 如果当前选择的意图识别是function_call，但LLM类型不支持，则设置为可选的第一项
      if (
        this.form.model.intentModelId === "Intent_function_call" &&
        llmType !== "openai" &&
        llmType !== "ollama"
      ) {
        // 找到第一个可见的选项
        const firstVisibleOption = this.modelOptions["Intent"].find(
          (item) => !item.isHidden
        );
        if (firstVisibleOption) {
          this.form.model.intentModelId = firstVisibleOption.value;
        } else {
          // 如果没有可见选项，设置为Intent_nointent
          this.form.model.intentModelId = "Intent_nointent";
        }
      }
    },
    // 检查是否有音频预览
    hasAudioPreview(item) {
      // 检查是否为克隆音频
      // 使用后端实际返回的 isClone 字段
      const isCloneAudio = Boolean(item.isClone);
      
      // 检查是否有有效的音频URL，只使用后端实际返回的字段
      const hasValidAudioUrl = !!((item.voice_demo || item.voiceDemo)?.trim());
      
      // 克隆音频始终显示播放按钮，普通音频需要有有效URL才显示
      return isCloneAudio || hasValidAudioUrl;
    },

    // 播放/暂停音频切换
    toggleAudioPlayback(voiceId) {
      // 如果点击的是当前正在播放的音频，则切换暂停/播放状态
      if (this.playingVoice && this.currentPlayingVoiceId === voiceId) {
        if (this.isPaused) {
          // 从暂停状态恢复播放
          this.currentAudio.play().catch((error) => {
            console.error("恢复播放失败:", error);
            this.$message.warning(this.$t('roleConfig.cannotResumeAudio'));
          });
          this.isPaused = false;
        } else {
          // 暂停播放
          this.currentAudio.pause();
          this.isPaused = true;
        }
        return;
      }

      // 否则开始播放新的音频
      this.playVoicePreview(voiceId);
    },

    // 播放音色预览
    playVoicePreview(voiceId = null) {
      // 如果传入了voiceId，则使用传入的，否则使用当前选中的
      const targetVoiceId = voiceId || this.form.ttsVoiceId;

      if (!targetVoiceId) {
        this.$message.warning(this.$t('roleConfig.selectVoiceFirst'));
        return;
      }

      // 停止当前正在播放的音频
      if (this.currentAudio) {
        this.currentAudio.pause();
        this.currentAudio = null;
      }

      // 重置播放状态
      this.isPaused = false;
      this.currentPlayingVoiceId = targetVoiceId;

      try {
        // 从保存的音色详情中获取音频URL
        const voiceDetail = this.voiceDetails[targetVoiceId];

        // 添加调试信息
        console.log("当前选择的音色ID:", targetVoiceId);
        console.log("音色详情:", voiceDetail);

        // 尝试多种可能的音频属性名
        let audioUrl = null;
        let isCloneAudio = false;

        if (voiceDetail) {
          // 使用后端实际返回的 isClone 字段判断是否为克隆音频
          isCloneAudio = Boolean(voiceDetail.isClone);
          console.log(
            "克隆音频判断结果:",
            isCloneAudio,
            "训练状态:",
            voiceDetail.train_status
          );

          // 获取音频URL
          if (isCloneAudio && voiceDetail.id) {
            // 对于克隆音频，使用后端提供的正确接口
            // 注意：这里需要通过两步获取音频URL
            // 1. 首先获取音频下载ID
            // 2. 然后使用这个ID构建播放URL
            // 由于异步操作，我们需要先请求getAudioId
            console.log("检测到克隆音频，准备获取音频URL:", voiceDetail.id);

            // 创建一个Promise来处理异步获取音频URL的操作
            const getCloneAudioUrl = () => {
              return new Promise((resolve) => {
                // 首先调用getAudioId接口获取临时UUID
                RequestService.sendRequest()
                  .url(`${getServiceUrl()}/voiceClone/audio/${voiceDetail.id}`)
                  .method("POST")
                  .success((res) => {
                    if (res.data.code === 0 && res.data.data) {
                      // 处理返回的数据格式，在res.data基础上再套一层.data
                      const audioId = res.data.data;
                      console.log("获取到的音频ID:", audioId);
                      // 使用返回的UUID构建播放URL
                      const playUrl = `${getServiceUrl()}/voiceClone/play/${audioId}`;
                      console.log("构建克隆音频播放URL:", playUrl);
                      resolve(playUrl);
                    } else {
                      console.error("获取音频ID失败:", res.msg);
                      resolve(null);
                    }
                  })
                  .networkFail((err) => {
                    console.error("请求音频ID接口失败:", err);
                    resolve(null);
                  })
                  .send();
              });
            };

            // 设置播放状态
            this.playingVoice = true;
            // 创建Audio实例
            this.currentAudio = new Audio();
            // 设置音量
            this.currentAudio.volume = 1.0;

            // 设置超时，防止加载过长时间
            const timeoutId = setTimeout(() => {
              if (this.currentAudio && this.playingVoice) {
                this.$message.warning(this.$t('roleConfig.audioLoadTimeout'));
                this.playingVoice = false;
              }
            }, 10000); // 10秒超时

            // 监听播放错误
            this.currentAudio.onerror = () => {
              clearTimeout(timeoutId);
              console.error("克隆音频播放错误");
              this.$message.warning(this.$t('roleConfig.cloneAudioPlayFailed'));
              this.playingVoice = false;
            };

            // 监听播放开始，清除超时
            this.currentAudio.onplay = () => {
              clearTimeout(timeoutId);
            };

            // 监听播放结束
            this.currentAudio.onended = () => {
              this.playingVoice = false;
            };

            // 处理异步获取URL并播放
            getCloneAudioUrl().then((url) => {
              if (url) {
                // 设置音频URL并播放
                this.currentAudio.src = url;
                this.currentAudio.play().catch((error) => {
                  clearTimeout(timeoutId);
                  console.error("播放克隆音频失败:", error);
                  this.$message.warning(this.$t('roleConfig.cannotPlayCloneAudio'));
                  this.playingVoice = false;
                });
              } else {
                clearTimeout(timeoutId);
                this.$message.warning(this.$t('roleConfig.getCloneAudioFailed'));
                this.playingVoice = false;
              }
            });

            // 返回，避免继续执行下面的普通音频播放逻辑
            return;
          } else {
            // 对于普通音频，只使用后端实际返回的字段
            audioUrl =
              voiceDetail.voiceDemo ||
              voiceDetail.voice_demo;
          }

          // 如果没有找到，尝试检查是否有URL格式的字段
          if (!audioUrl) {
            for (const key in voiceDetail) {
              const value = voiceDetail[key];
              if (
                typeof value === "string" &&
                (value.startsWith("http://") ||
                  value.startsWith("https://") ||
                  value.endsWith(".mp3") ||
                  value.endsWith(".wav") ||
                  value.endsWith(".ogg"))
              ) {
                audioUrl = value;
                console.log(`发现可能的音频URL在字段 '${key}':`, audioUrl);
                break;
              }
            }
          }
        }

        if (!audioUrl) {
          // 如果没有音频URL，显示友好的提示
          this.$message.warning(this.$t('roleConfig.noPreviewAudio'));
          return;
        }

        // 非克隆音频的处理逻辑
        if (!isCloneAudio) {
          // 设置播放状态
          this.playingVoice = true;

          // 创建并播放音频
          this.currentAudio = new Audio();
          this.currentAudio.src = audioUrl;

          // 设置音量
          this.currentAudio.volume = 1.0;

          // 设置超时，防止加载过长时间
          const timeoutId = setTimeout(() => {
            if (this.currentAudio && this.playingVoice) {
              this.$message.warning(this.$t('roleConfig.audioLoadTimeout'));
              this.playingVoice = false;
            }
          }, 10000); // 10秒超时

          // 监听播放错误
          this.currentAudio.onerror = () => {
            clearTimeout(timeoutId);
            console.error("音频播放错误");
            this.$message.warning(this.$t('roleConfig.audioPlayFailed'));
            this.playingVoice = false;
          };

          // 监听播放开始，清除超时
          this.currentAudio.onplay = () => {
            clearTimeout(timeoutId);
          };

          // 监听播放结束
          this.currentAudio.onended = () => {
            this.playingVoice = false;
          };

          // 开始播放音频
          this.currentAudio.play().catch((error) => {
            clearTimeout(timeoutId);
            console.error("播放失败:", error);
            this.$message.warning(this.$t('roleConfig.cannotPlayAudio'));
            this.playingVoice = false;
          });
        }
      } catch (error) {
        console.error("播放音频过程出错:", error);
        this.$message.error(this.$t('roleConfig.audioPlayError'));
        this.playingVoice = false;
      }
    },
    updateChatHistoryConf() {
      if (this.form.model.memModelId === "Memory_nomem") {
        this.form.chatHistoryConf = 0;
      }
    },
    // 加载功能状态
    async loadFeatureStatus() {
      try {
        // 确保featureManager已初始化完成
        await featureManager.waitForInitialization();
        const config = featureManager.getConfig();
        this.featureStatus.voiceprintRecognition = config.voiceprintRecognition || false;
        this.featureStatus.vad = config.vad || false;
        this.featureStatus.asr = config.asr || false;
      } catch (error) {
        console.error("加载功能状态失败:", error);
      }
    },
    handleClose(id) {
      this.dynamicTags = this.dynamicTags.filter((item) => item.id !== id);
    },

    showInput() {
      this.inputVisible = true;
      this.$nextTick(_ => {
        this.$refs.saveTagInput.$refs.input.focus();
      });
    },

    handleInputConfirm() {
      let inputValue = this.inputValue;
      if (inputValue) {
        const tag = { id: `tmp-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`, tagName: inputValue };
        this.dynamicTags.push(tag);
      }
      this.inputVisible = false;
      this.inputValue = '';
    },
    getAgentTags(agentId, options = {}) {
      const requestSeq = ++this.agentTagsFetchSeq;
      this.agentTagsLoaded = false;
      if (!agentId) {
        this.dynamicTags = [];
        this.originalTagNames = [];
        this.agentTagsLoaded = true;
        return Promise.resolve(true);
      }

      return new Promise((resolve) => {
        const handleFailure = (error) => {
          if (requestSeq !== this.agentTagsFetchSeq) {
            resolve(false);
            return;
          }
          this.agentTagsLoaded = false;
          if (options.showError !== false) {
            this.$message.error(error?.data?.msg || i18n.t("roleConfig.fetchConfigFailed"));
          }
          resolve(false);
        };
        Api.agent.getAgentTags(agentId, ({ data }) => {
          if (requestSeq !== this.agentTagsFetchSeq) {
            resolve(false);
            return;
          }
          if (data?.code === 0) {
            try {
              this.dynamicTags = Array.isArray(data.data) ? data.data : [];
              this.originalTagNames = this.dynamicTags.map(tag => tag.tagName);
              this.agentTagsLoaded = true;
              resolve(true);
            } catch (error) {
              handleFailure(error);
            }
          } else {
            handleFailure(data);
          }
        }, handleFailure);
      });
    },
    isSameStringList(left, right) {
      if (!Array.isArray(left) || !Array.isArray(right) || left.length !== right.length) {
        return false;
      }
      return left.every((value, index) => value === right[index]);
    },
    handleSaveAgentTags(agentId, tagNames = this.dynamicTags.map(tag => tag.tagName)) {
      return new Promise((resolve, reject) => {
        Api.agent.saveAgentTags(agentId, { tagNames }, ({ data }) => {
          if (data.code === 0) {
            this.originalTagNames = [...tagNames];
            resolve();
          } else {
            reject(data.msg);
          }
        });
      });
    }
  },
  beforeDestroy() {
    this.agentReloadSeq += 1;
    this.agentConfigFetchSeq += 1;
    this.agentTagsFetchSeq += 1;
    this.currentVersionFetchSeq += 1;
    this.voiceFetchSeq += 1;
  },
  async mounted() {
    this.lastValidTtsDraft = this.captureTtsDraft();
    const agentId = this.$route.query.agentId;
    if (agentId) {
      this.reloadAgentPage(agentId);
    }
    this.fetchModelOptions();
    this.fetchTemplates();
    // 加载功能状态，确保featureManager已初始化
    await this.loadFeatureStatus();
  },
};
</script>

<style lang="scss" scoped>
::v-deep .el-radio-group {
  .is-active {
    .el-radio-button__inner {
      &:hover {
        color: #fff !important;
      }
    }
  }
}

.role-config-page {
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
  max-width: 1400px;
  width: 100%;
  margin: 0 auto;
  box-sizing: border-box;
  overflow: hidden;
}

/* 顶部吸顶控制条 */
.agent-control-header {
  background: #ffffff;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 16px -2px rgba(15, 23, 42, 0.04);
  padding: 14px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  flex-shrink: 0;
  gap: 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
  flex: 1;
  min-width: 0;
}

.header-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.8), 0 2px 6px rgba(78, 117, 255, 0.15);

  img {
    width: 24px;
    height: 24px;
  }
}

.header-title-wrap {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 10px;

  .header-title {
    font-size: 18px;
    font-weight: 700;
    color: #1e293b;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .current-version-tag {
    padding: 2px 8px;
    border-radius: 20px;
    background: #eff6ff;
    color: #3b82f6;
    font-size: 11px;
    font-weight: 600;
    border: 1px solid #dbeafe;
  }
}

.header-tags {
  display: flex;
  align-items: center;
  gap: 6px;
  overflow-x: auto;

  .custom-tag {
    background: #f1f5f9;
    color: #475569;
    border: none;
    border-radius: 6px;
    font-size: 12px;
    height: 24px;
    line-height: 24px;
    padding: 0 8px;
  }

  .add-tag-pill-btn {
    border: 1px dashed #cbd5e1;
    background: transparent;
    color: #64748b;
    border-radius: 6px;
    font-size: 12px;
    height: 24px;
    padding: 0 8px;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      border-color: #4e75ff;
      color: #4e75ff;
    }
  }

  .input-new-tag {
    width: 80px;
    &::v-deep .el-input__inner {
      height: 24px;
      line-height: 24px;
      padding: 0 6px;
      font-size: 12px;
    }
  }
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;

  .hint-text {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    color: #94a3b8;
    margin-right: 4px;
  }

  .config-btn {
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
      box-shadow: 0 2px 8px rgba(78, 117, 255, 0.3);

      &:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(78, 117, 255, 0.4);
      }
    }

    &.secondary-btn {
      background: #ffffff;
      color: #475569;
      border: 1px solid #e2e8f0;

      &:hover {
        background: #f8fafc;
        color: #1e293b;
        border-color: #cbd5e1;
      }
    }

    &.neutral-btn {
      background: #f1f5f9;
      color: #475569;

      &:hover {
        background: #e2e8f0;
      }
    }
  }

  .custom-close-btn {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    border: 1px solid #e2e8f0;
    background: #ffffff;
    color: #94a3b8;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;

    &:hover {
      background: #fee2e2;
      color: #ef4444;
      border-color: #fecaca;
    }
  }
}

/* 滚动区域与卡片列表 */
.sections-scroll-area {
  flex: 1;
  overflow-y: auto;
  padding-right: 4px;

  &::-webkit-scrollbar {
    width: 6px;
  }
  &::-webkit-scrollbar-thumb {
    background: #cbd5e1;
    border-radius: 6px;
  }
}

.config-sections-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-bottom: 24px;
}

.section-card {
  background: #ffffff;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 2px 8px -1px rgba(15, 23, 42, 0.03);
  padding: 22px 24px;
  transition: box-shadow 0.2s;

  &:hover {
    box-shadow: 0 6px 16px -2px rgba(15, 23, 42, 0.06);
  }
}

.section-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f1f5f9;

  .section-icon {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 17px;
    flex-shrink: 0;

    &.basic-icon {
      background: #eff6ff;
      color: #3b82f6;
    }
    &.brain-icon {
      background: #f5f3ff;
      color: #8b5cf6;
    }
    &.voice-icon {
      background: #ecfdf5;
      color: #10b981;
    }
    &.prompt-icon {
      background: #fff7ed;
      color: #f97316;
    }
  }

  .section-title-wrap {
    flex: 1;
    text-align: left;

    .section-title {
      font-size: 16px;
      font-weight: 700;
      color: #1e293b;
      margin: 0 0 2px 0;
    }

    .section-desc {
      font-size: 12px;
      color: #64748b;
      margin: 0;
    }
  }

  .section-header-extra {
    margin-left: auto;
  }
}

/* 表单行布局 */
.form-row-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.form-row-full {
  width: 100%;
}

.custom-label {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  display: inline-flex;
  align-items: center;
  gap: 4px;

  i {
    color: #94a3b8;
    font-size: 13px;
  }
}

/* 控件外观升级 */
.modern-input, .modern-select {
  width: 100%;

  &::v-deep .el-input__inner {
    border-radius: 10px;
    border: 1px solid #e2e8f0;
    color: #1e293b;
    height: 38px;
    line-height: 38px;
    transition: all 0.2s;

    &:focus {
      border-color: #4e75ff;
      box-shadow: 0 0 0 3px rgba(78, 117, 255, 0.12);
    }
  }
}

.modern-textarea {
  width: 100%;

  &::v-deep .el-textarea__inner {
    border-radius: 12px;
    border: 1px solid #e2e8f0;
    color: #1e293b;
    padding: 12px 14px;
    font-family: inherit;
    font-size: 13px;
    line-height: 1.6;
    transition: all 0.2s;

    &:focus {
      border-color: #4e75ff;
      box-shadow: 0 0 0 3px rgba(78, 117, 255, 0.12);
    }
  }
}

/* 角色模板胶囊 */
.template-container {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.template-pill-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border-radius: 20px;
  background: #eff6ff;
  color: #3b82f6;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid #dbeafe;

  &:hover {
    background: #dbeafe;
    color: #1d4ed8;
    transform: translateY(-1px);
  }
}

/* 上下文提供商与按钮 */
.context-provider-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background: #f8fafc;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
}

.provider-status-text {
  font-size: 13px;
  color: #475569;

  .doc-link {
    color: #4e75ff;
    text-decoration: none;
    margin-left: 6px;
    &:hover {
      text-decoration: underline;
    }
  }
}

.modern-pill-btn {
  border: none;
  background: #eff6ff;
  color: #3b82f6;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    background: #dbeafe;
    color: #1d4ed8;
  }
}

/* 音色选择与试听 */
.voice-row-inner {
  display: flex;
  align-items: center;
  gap: 12px;
}

.voice-select {
  flex: 1;
}

.voice-option-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.play-button {
  color: #4e75ff;
  padding: 0;
  font-size: 15px;
  &:hover {
    color: #2563eb;
  }
}

/* MCP 函数工具条 */
.current-functions-bar {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed #e2e8f0;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;

  .functions-bar-label {
    font-size: 12px;
    color: #64748b;
    font-weight: 500;
  }

  .functions-capsules-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .function-mini-tag {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 2px 8px;
    border-radius: 4px;
    background: #f1f5f9;
    color: #475569;
    font-size: 11px;

    .func-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #10b981;
    }
  }
}

/* 对话历史记录形式 单选 */
.modern-radio-wrap {
  margin-top: 4px;
}

.modern-pill-radios ::v-deep {
  .el-radio-button__inner {
    border-radius: 20px !important;
    margin-right: 8px;
    border: 1px solid #e2e8f0 !important;
    background: #f8fafc;
    color: #475569;
    box-shadow: none !important;
    padding: 8px 16px;
    font-size: 12px;
  }

  .el-radio-button.is-active .el-radio-button__inner {
    background: #4e75ff !important;
    color: #ffffff !important;
    border-color: #4e75ff !important;
  }
}
</style>

<style>
.custom-tooltip {
  max-width: 400px !important;
  word-break: break-word;
  border-radius: 8px !important;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12) !important;
}
</style>
