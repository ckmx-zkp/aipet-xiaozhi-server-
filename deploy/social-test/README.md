# 单实体机社交联调

本模式用于操作员显式同意的一台真实设备与云端模拟方，非 BLE 发现或真实双设备社交。
内容及轮次真源为 backend 的隔离测试房间；虚拟方回执为 simulated，实体侧只接受播放队列排空后的 played。

## 发布与回滚

- 当前发布目录：服务器 `/opt/aipet-social-test-20261117`。
- `prepare.py` 生成未入库的 candidate/backend 构建上下文；从当前语音容器取基础文件并应用本轮 Git 补丁，保留线上既有差异。已部署同版本时请使用原始 b18 容器快照，不要重复应用补丁。
- `Dockerfile.backend` 仅叠加隔离 FastAPI 入口和房间模块，不运行业务迁移。单进程运行，内存房间重启即失效，最多 32 个，每个 180 秒。
- `Dockerfile.voice` 叠加语音侧调度，开启 SOCIAL_TEST_ENABLED，SOCIAL_TEST_BACKEND 只指向 Docker 内网的隔离容器。
- 测试 API 使用业务后端现有私有 env-file，在 `ai-pet-backend_default` 网络创建 `aipet-social-test-api`，不映射公网端口。
- 语音采用原 compose + `voice-override.json`，只重建 `xiaozhi-esp32-server`。不修改原 compose、私有配置或其他业务服务。
- `test_control.py` 在候选语音镜像中运行，验证错房间/错轮次/提前回执不会被接受；普通语音不被拦截。
- 回滚：原 compose 不带测试 override，执行 `up -d --no-deps xiaozhi-esp32-server`；隔离 API 可独立停止。

## 操作

`control_client.py` 放入语音容器后从私有挂载配置取服务密钥，不打印密钥。
`devices` 查询支持本协议的在线设备；`start` 默认选择本轮 COM7 的 MAC，仅用于该联调环境。
查询房间时传 room_id。设备必须已绑定、已声明 social_test_v1、空闲且在线；按 BOOT 退出或超时自动恢复。

2026-11-17 四轮测试的房间 finished：四条模拟回执与四条实体播放回执齐全，用户确认音频完整。
COM25 尚未烧录，后续真实双机内容与身份另行设计，不得把模拟回执改名为实体已播放。

## 双实体机扩展（2026-11-17）

- control_client.py 的 start-dual 使用 COM25 雾星与 COM7 两个已认证连接。双方 ready 后按四轮八段固定台词播放；每段只有对应 speaker/device_uid 的 played 可推进，不能使用 simulated。
- Dockerfile.backend.dual / Dockerfile.voice.dual 从单机测试镜像增量构建；voice-dual-override.json 切到 social-dual-20261117。隔离 API 容器更新为 aipet-social-test-api:dual-20261117，无数据库迁移。
- 双设备首次同时连接暴露 TTS 工厂直接读取 sys.modules 半初始化模块的竞态；改为总经 importlib.import_module 的导入锁，避免第二连接缺失 TTSProvider。四项语音候选测试包含此回归。
- 本地 evidence/ 保存房间状态，仅作为未入 Git 的调试证据；两台连续日志位于固件仓 logs/COM7-live-20261117.log、COM25-live-20261117.log。
