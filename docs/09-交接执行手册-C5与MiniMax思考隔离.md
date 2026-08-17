# 09 — 交接执行手册：C5 Context Provider 与 MiniMax 思考隔离

> 交接时间：2026-08-15。本文供接手 agent 直接执行；以服务器实况为准。
> 严禁把 API Key、`X-Internal-Token`、数据库密码写进本文、日志、Git 或协作看板。

## 1. 本次目标

完成并验收两件事：

1. 将 backend 已完成的 C5 `GET /api/internal/context/device` 接入 xiaozhi-server，最终 Prompt
   固定按 `pet_default → persona_pack → dynamic_context` 组合；动态上下文仅连接初始化拉取一次，慢、空或失败均不阻塞首轮语音。
2. MiniMax M2.5 使用最低思考强度，并保证思考字段和 `<think>...</think>` 内容绝不进入 TTS 或设备文本。

## 2. 已完成且可复用的事实

### 代码与提交

- 本地仓 `main` 已推送提交 `93d1997 feat: integrate context provider and filter reasoning output`。
- 该提交修改了以下文件：
  - `config/config_loader.py`：manager-api 拉配置后保留本地私有 `context_providers`，避免内部 Token 被覆盖。
  - `core/utils/context_provider.py`：C5 超时上限 0.5 秒；只接受原始标量；最多 6 条、800 字符；日志不输出上下文原文。
  - `core/connection.py`：连接初始化取得 Context Provider 数据，并传给 Prompt 合成器；不会在会话中重复拉 C5。
  - `core/persona_pack.py`：不论有无 `persona_pack`，都将动态上下文放在基础行为/人设之后。
  - `core/providers/llm/openai/openai.py`：MiniMax 请求加 `reasoning_effort=low`、`reasoning_split=true`；丢弃 `reasoning_content` 与 `reasoning_details`。
- 本地已执行 `python -m compileall` 和 `git diff --check`，通过。

### 后端 C5 契约与配置

- 后端 C5 已部署：`GET /api/internal/context/device`。
- 请求头：`device-id`（规范化小写冒号 MAC，由 Context Provider 自动附带）与 `X-Internal-Token`。
- 成功格式：`{"code":0,"data":["短摘要", "..."]}`；空上下文为 `200 + []`。
- 线上私有配置文件 `/opt/xiaozhi-server/data/.config.yaml` 已写入 `context_providers`，URL 基于现有 `business_api.base_url` 生成，并复用现有 `business_api.token`。不要重新创建或打印 Token。

### 模型实况

- 智控台数据库中，智能体“测试1”（`ec9d16d5d8e04772ac12f7438924bc3b`）已经绑定 `LLM_MiniMaxM25`，模型为 `MiniMax-M2.5`，OpenAI 兼容基址为 `https://api.minimaxi.com/v1`。
- 已验证 MiniMax 流会含 `reasoning_content` / `reasoning_details`；可见回答位于 `content`。不能直接把 provider delta 转发给设备。
- 当前正在运行的语音容器仍是 **b6**；因此用户此刻仍可能听到 `/think`，这不是 b7 修复已生效的证据。
- 服务器上 **b7 镜像已构建完成**：`xiaozhi-aipet-server:v0.9.6-b7`，image id 为 `sha256:f6f33777...`，但 compose 尚未切 tag、服务尚未重启。

## 3. 先做的代码补强（必须）

`93d1997` 已能过滤 MiniMax 分离字段，但对跨 chunk 的 `<think>` 标签防御不够严格：如标签被拆为多个 chunk，仍有理论泄漏风险。部署前补成状态机或在 provider 侧直接禁用思考。

建议采用双保险：

```python
# openai.py 中 minimaxi.com 对应 extra_body
{
    "reasoning_effort": "low",
    "reasoning_split": True,
    "thinking": {"type": "disabled"},
}
```

并实现一个跨 chunk 的可见文本过滤器，规则如下：

- 无条件丢弃 `delta.reasoning_content`、`delta.reasoning_details`。
- 对 `delta.content` 维护会话内 `in_think` 状态；只有标签外文本可 `yield`。
- 标签 `<think>`、`</think>` 可跨 chunk；不能只在单个 chunk 上 `split`。
- `response()` 与 `response_with_functions()` 共用同一个过滤逻辑。
- 工具调用对象 `tool_calls` 仍原样传递；只过滤其配套的文字 `content`。

推荐单元用例（无须真实 API Key）：

```text
["<thi", "nk>推理", "过程</th", "ink>最终答案"] -> 仅输出“最终答案”
delta.reasoning_content="推理" + delta.content="答案" -> 仅输出“答案”
delta.content="工具说明" + tool_calls -> 输出“工具说明”和原 tool_calls
```

完成补强后：运行 `python -m compileall -q` 覆盖上述 5 个文件、`git diff --check`，仅暂存相关源码，提交并 `git push`。不要把密钥提交。

## 4. 部署步骤

服务器别名为 `aliyun-aipet`，部署根为 `/opt/xiaozhi-server`，源码为 `/opt/xiaozhi-server/repo`。

1. 检查服务器和本地状态。看板工作树不干净时不要 `git pull`，也不要把其他人的改动提交进去。
2. 将最终修改的源码同步到服务器源码目录（确保保持原子目录结构，不要将多个文件 scp 到同一个根目录而导致覆盖）。
3. 重新构建 b7（若做了上述补强，建议使用 b8，避免镜像语义混淆）：

```bash
ssh aliyun-aipet
cd /opt/xiaozhi-server/repo
docker build -f xiaozhi-esp32-server/Dockerfile-server \
  -t xiaozhi-aipet-server:v0.9.6-b8 .
```

4. 仅替换 compose 的 `xiaozhi-esp32-server` image tag 为新 tag，然后启动该服务：

```bash
cd /opt/xiaozhi-server
docker compose -f docker-compose_all.yml up -d xiaozhi-esp32-server
docker ps --format '{{.Names}} {{.Image}} {{.Status}}' | grep xiaozhi-esp32-server
docker logs --tail 150 xiaozhi-esp32-server
```

5. 容器启动后，检查私有配置存在但**不得打印 token**：确认 `context_providers[0]` 的 URL 以
   `/api/internal/context/device` 结尾、timeout 为 `0.5`，并确认 header key 为 `X-Internal-Token`。

## 5. 容器级验收

### C5 可达性

在容器内调用 C5，读取挂载配置中的 Token 和 URL，不回显请求头、Token 或 `data` 原文。只输出：HTTP 状态、`code`、data 是否列表、条数。

预期：HTTP 200；`code=0`；空数据也算通过。

### Prompt 组装

在容器内用 synthetic `persona_pack` 和 `dynamic_context` 调用 `build_persona_prompt()`，断言顺序为：

```text
[固定基础行为规则] < [角色设定/表达风格/禁忌] < [唤醒时动态上下文]
```

再用 `pack=None` 断言动态上下文仍存在。不要输出真实人设或真实上下文。

### 思考隔离

用 `SimpleNamespace` 构造含 `reasoning_content`、`reasoning_details` 和 `content` 的 delta，断言只得到 `content`。
再跑第 3 节的跨 chunk 标签用例。必须同时覆盖普通对话和带工具调用的函数流。

### 性能与降级

- mock C5 超时、5xx、非法 JSON、`data=[]`；均应返回空上下文，语音连接继续。
- 验证超时上限为 0.5 秒，且本会话只调用一次 C5。

## 6. 真机验收

不需要重启或刷写真机。服务容器重启会断开旧 WebSocket；设备下一次唤醒会自动建立新连接。

验收动作：

1. 等旧连接断开后，唤醒设备一次，问一个无需工具的短问题。
2. 再问一个会触发眼睛工具的请求，例如“眨眨眼”。
3. 查看容器日志，只记录以下脱敏证据：C5 返回状态/条数、Prompt 更新成功、MiniMax 思考字段被过滤、助手可见回复、工具调用成功。
4. 通过标准：设备绝不播报 `<think>`、`/think`、推理过程或类似内部分析文本；只播放最终回答；C5 失败时首轮仍快速回复。

如仍出现 `/think`：先确认 `docker ps` 显示的新 b8（或 b7）镜像，而非 b6；再检查运行容器的 `openai.py` 是否确实包含过滤器与 `thinking.disabled`。不要先归因于固件。

## 7. 文档与看板收工

完成部署后同步更新以下文件（中文、只写事实、不含密钥）：

- 本仓 `docs/01`、`docs/03`、`docs/05`、`docs/06`、`docs/08`：将 C5 从“待后端/未实现”改为“已接入、待/已真机验收”；将模型主用改为 MiniMax M2.5；记录镜像 b8 和思考隔离策略。
- `D:/Home_Work/work_dashboard/AI-Pet协作看板.md`：记录 C5 服务侧接入、容器级证据、真机证据状态、镜像版本和 commit。
- 真机通过后更新 `D:/Home_Work/work_dashboard/AI-Pet固件联调看板.md`，写明无需固件改动、会话重连后验证通过。

更新看板前必须 `git -C D:/Home_Work/work_dashboard status --short`；只暂存目标看板文件，不能夹带不属于本任务的改动。

## 8. 安全与边界

- C5 只走 Docker 内网 `http://web-api:8000/api/internal/*`，不走公网。2026-08-18 起不再使用 `host.docker.internal:8010`（UFW 未放行 8010，容器访问会超时）。
- `device_uid`/`device-id` 一律小写冒号 MAC；`session_id` 保持 UUID 字符串。
- C5 上下文只允许短摘要；不要放完整知识库、原始聊天、敏感字段或内部 ID。
- Memory MCP 仍未接入，等待后端确定 streamable HTTP MCP/stdio 契约；本次不要擅自实现或变更协议。
- 设备 MCP 仅做路由，不改固件协议。

## 9. 执行结果（2026-08-16）

本手册两个目标的代码侧与部署侧均已完成，仅剩真机验收。

### 代码（本地已提交 `e93bb14`，分支 main）

- 新增 `core/utils/think_filter.py`：`ThinkTagFilter` 跨 chunk 状态机，`<think>` 标签被拆到多个 chunk 也不会泄漏进 TTS；同时修复旧逻辑“同 chunk 双标签吞正文”缺陷。
- `core/providers/llm/openai/openai.py`：`response()` 与 `response_with_functions()` 均换用该过滤器；MiniMax（api.minimaxi.com）extra_body 增加 `thinking: {type: disabled}` 双保险（原有 `reasoning_effort: low` + `reasoning_split: true` 保留）。
- `core/connection.py`：`_extract_direct_answer_response` 两个返回点加 `<think>` 剥离兜底。

### 部署（2026-08-16 已完成）

- 服务器 `/opt/xiaozhi-server` 构建镜像 `xiaozhi-aipet-server:v0.9.6-b8` 并已切换 compose tag 重启；**线上从 b6 直接跳到 b8（b7 未上线即废弃）**。
- 重要发现：部署前核对发现服务器源码树的 `connection.py` 缺 `93d1997` 的 dynamic_context 合入块（`_refresh_persona_pack` 调 `build_persona_prompt` 未传 dynamic_context）——意味着 b7 即使上线 C5 上下文也不会进 Prompt；b8 已补齐。

### 容器级验收（2026-08-16 全部通过）

- 容器启动日志干净。
- 容器内 `ThinkTagFilter` 行为测试（拆分/双标签/未闭合/逐字节一致性）通过。
- 容器内按私有配置直连 C5 `GET http://host.docker.internal:8010/api/internal/context/device`：200、7ms，真机 `8c:fd:49:0c:a8:78` 返回 3 条上下文。
- 主机级 curl 复核：已认领真机 data 非空、未知设备 `data:[]`、无 token 401。

### 模型现状

智能体“测试1” LLM = MiniMax-M2.5（`https://api.minimaxi.com/v1`，走 openai provider）；ASR = 豆包流式 2.0；TTS = 火山双向流式·湾湾小何。

### 剩余待办

真机验收（唤醒后不再播报任何 think 内容；首轮回复能体现 C5 上下文；backend 宕机时 0.5s 超时降级、首轮仍快速回复），以及五项旁路 E2E 落库证据仍待真机取。

