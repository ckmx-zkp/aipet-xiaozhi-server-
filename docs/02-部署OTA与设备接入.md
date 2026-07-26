# 02 — 部署、OTA 与设备接入

## 部署形态（首台）

与服务器需求文档一致：Docker Compose，与业务后端可同机（4C16G），**实时面与 Agent 限额隔离**。

建议容器：

| 服务 | 说明 |
|------|------|
| xiaozhi-server | 主进程（协议 + 智控台） |
| （可选）mqtt 网关 | 若发行版拆分 |
| redis | 若上游依赖 |

业务 PG 由 `ai-pet-backend` 拥有；本仓勿把业务表建在小智库里（除非上游强制，再评估同步）。

## OTA 对接（固件切换关键）

1. 本仓提供与官方兼容的 OTA HTTP 接口（上游已实现则直接用）。  
2. 固件 `CONFIG_OTA_URL` 或 NVS `wifi/ota_url` 改为：  
   `https://<你的域名>/xiaozhi/ota/`（以实际上游路径为准）。  
3. OTA 响应需下发：`mqtt` 或 `websocket` 凭证、可选 `activation` / `firmware`。  
4. 设备完成激活后，用「你好小智」验证一轮对话。  

## 激活与绑定注意

- 曾绑定官方云的设备可能涉及 eFuse/激活态；切自建时按上游文档做解绑或重新激活。  
- 管理台设备列表的「业务绑定」在 `ai-pet-backend`，与小智侧 device_id 用 MAC/UUID 对齐。  

## 验收

- [ ] 新刷固件（指向自建 OTA）可激活  
- [ ] MQTT/WS 会话建立，TTS 有声  
- [ ] 断网重连后可恢复会话（按上游能力）  
