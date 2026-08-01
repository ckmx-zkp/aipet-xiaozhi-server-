# xiaozhi-server — 自建小智兼容后台

> 职责：设备接入、OTA/激活、实时语音会话、智能体 Prompt 加载、设备 MCP 路由。  
> 技术起点：[xinnan-tech/xiaozhi-esp32-server](https://github.com/xinnan-tech/xiaozhi-esp32-server)（建议钉版本后二次开发）  
> 产品母文档：`../ESP32_XIAOZHI/` 下业务设计 / 服务器需求 / 赛道决策

## 本仓库不负责

- 星座知识库、PersonaCompiler、可审计记忆真源 → 见 `../ai-pet-backend`
- Web 管理台 UI → 见 `../ai-pet-admin`
- ESP32 固件 → 见 `../ESP32_XIAOZHI/xiaozhi-esp32`

## 文档索引

| 文档 | 说明 |
|------|------|
| [docs/00-文档索引与协作边界.md](./docs/00-文档索引与协作边界.md) | 三仓分工、依赖顺序 |
| [docs/01-项目概述与范围.md](./docs/01-项目概述与范围.md) | 目标、非目标、版本对齐 |
| [docs/02-部署OTA与设备接入.md](./docs/02-部署OTA与设备接入.md) | Compose、OTA URL、激活 |
| [docs/03-会话智能体与人设注入.md](./docs/03-会话智能体与人设注入.md) | 如何加载业务侧 persona_pack |
| [docs/04-设备MCP与外设路由.md](./docs/04-设备MCP与外设路由.md) | 眼睛等工具路由、隔离原则 |
| [docs/05-与业务后端集成接口.md](./docs/05-与业务后端集成接口.md) | 旁路事件、Webhook、拉 pack |
| [docs/06-开发任务清单.md](./docs/06-开发任务清单.md) | 可执行 backlog |
| [docs/07-模型与采购清单（甲方版）.md](./docs/07-模型与采购清单（甲方版）.md) | 模型选型对标小智官方云、采购/费用清单 |
| [docs/08-部署配置基线与运维.md](./docs/08-部署配置基线与运维.md) | **服务器有效配置基线（脱敏）、已踩的坑、运维命令；改配置必回写** |

## 建议启动顺序

1. 按官方文档拉起 `xiaozhi-esp32-server` 全模块 + 全 API  
2. 固件改 `ota_url` 指向本服务，完成激活与一轮对话  
3. 按 `docs/05` 接通业务后端旁路与人设注入  
