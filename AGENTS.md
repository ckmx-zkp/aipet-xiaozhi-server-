# AGENTS.md — xiaozhi-server（自建小智兼容后台）

> AI 会话进本仓前先读 `D:/Home_Work/AGENTS.md`，并按其中的安全规则检查/同步 `work_dashboard`；再读项目全景、协作看板和本文件，涉及固件联调再读固件联调看板。看板工作树不干净时不得擅自 pull 或把他人改动提交出去。
> 注意：本仓本地代码 ≠ 线上状态（配置改动在服务器未回同步，见根协作文档第四节）。

## 定位

基于上游 `xinnan-tech/xiaozhi-esp32-server` **v0.9.6 源码快照**二开的实时语音后台：设备接入、OTA/激活、ASR/LLM/TTS 编排、智能体 Prompt 运行时加载、设备 MCP 路由。业务真源（用户/设备/persona/记忆）在 `ai-pet-backend`，本仓**不存业务数据**。

## 必读文档（docs/，按序）

- `docs/00`：三仓协作边界与**硬边界**（什么可进/禁止进本仓）——动手前必读
- `docs/02`：部署、OTA 与设备接入
- `docs/03`：人设注入（persona_pack）
- `docs/04`：设备 MCP 与外设路由
- `docs/05`：与业务后端集成接口（**契约真源**，改接口先改这里）
- `docs/06`：开发任务清单（Epic A–D）
- `docs/08`：部署配置基线与运维——**凡涉及线上模型、容器、内部接口、配置漂移或故障诊断必读**；服务器有效配置以它和服务器实际状态为准，不以本地上游默认 `config.yaml` 推断。

## 技术栈与结构

- `xiaozhi-esp32-server/main/xiaozhi-server/`：Python 3.10 语音服务（入口 `app.py`，`requirements.txt`）
- `xiaozhi-esp32-server/main/manager-api/`：Java Spring Boot（Maven）
- `xiaozhi-esp32-server/main/manager-web/`：Vue 2 + vue-cli（npm，`npm run serve` / `npm run build`）
- 部署：Docker Compose（`docker-compose_all.yml` 全模块：server + manager + MySQL + Redis）

## 命令

- 全模块运行：`docker compose -f docker-compose_all.yml up -d`（服务器部署目录 `/opt/xiaozhi-server`）
- **本仓无自有测试、无 CI**：验证 = 容器 Up + 模拟/真机设备握手与首轮对话通过，结果写进固件联调看板。

## 红线

- 上游代码尽量保持原样，二开改动最小化并在 docs 记录；**MCP 工具只做路由，不改协议**。
- 端口固定：8000=设备 WS，8002=智控台/OTA，8003=视觉/HTTP；与 backend 端口冲突看总看板"待决事项"。
- 密钥不入库（`api.txt` 已 gitignore）；模型密钥在智控台配置，不写进代码和文档。
- 模型链路现状：LLM=GLM-4.5-Flash（备用 Kimi K2.7）、ASR=豆包流式 2.0、TTS=火山双向流式·湾湾小何（以总看板为准）。
- 业务内部接口：仅走内网 `/api/internal/*` 并携带 `X-Internal-Token`；`device_uid` 使用规范化小写冒号 MAC，`session_id` 使用小智连接原生 UUID 字符串。字段与失败降级细节以 `docs/05` 及 backend `docs/06` 为准，禁止在此重复扩展契约。
- 内部 API 路径以 `docs/05` 与 backend 已确认契约为准；若发现 `/internal/*` 与 `/api/internal/*` 前缀不一致，记录为待决项并等待 backend 统一，禁止自行猜测或双写兼容。

## 收工义务

完成任务后更新 `D:/Home_Work/work_dashboard/AI-Pet协作看板.md`（业务集成点）和/或 `D:/Home_Work/work_dashboard/AI-Pet固件联调看板.md`（设备联调点）的状态与进度日志。
