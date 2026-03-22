# video-agent × n8n 接入说明（第一版）

先说人话：**这次交付完成的是“n8n 可接入层 + 工作流模板 + 使用文档”**，**不是**“n8n 已经在这台机器上安装并上线”。

也就是说：

- ✅ 已完成：HTTP API 包装层，能让 n8n 用 Webhook / HTTP Request 调 `video-agent`
- ✅ 已完成：n8n 工作流模板 JSON
- ✅ 已完成：参数映射和接入说明
- ❌ 未完成：本机安装 n8n、本机启动 n8n、生产环境守护部署、域名/反代/鉴权

别把这两件事混了。现在是**接入准备完成**，不是**n8n 平台本体已部署**。

---

## 1. 本次新增文件

- `integrations/n8n_api.py`
- `integrations/n8n_workflow_template.json`
- `integrations/N8N_DEPLOYMENT.md`

---

## 2. 设计原则

核心原则就一条：**复用现有入口，不重写主流程。**

所以这个 API 层没有另起炉灶去重写业务，而是直接包装：

- `cli.py`
- `main.py generate`

这样做的好处：

1. 参数天然和现有项目入口对齐
2. 你后续修 `cli.py` / `main.py` 时，接入层不容易漂移
3. n8n 调用的是你已经在用的命令，不是另一套平行世界逻辑

---

## 3. API 能力概览

`integrations/n8n_api.py` 暴露了这些接口：

### 基础接口

- `GET /`
- `GET /health`
- `GET /api/v1/options`

### 执行接口

- `POST /api/v1/cli/run`
- `POST /api/v1/main/generate`

### 运行状态接口

- `GET /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/logs`

### n8n 辅助接口

- `POST /api/v1/n8n/step-plan`

---

## 4. 推荐安装依赖

这层 API 优先用 FastAPI。

建议补安装：

```bash
pip install fastapi uvicorn
```

如果你打算直接写进项目依赖，也可以把这两项加入 `requirements.txt`。

---

## 5. 启动方式

在 `video-agent/` 根目录执行：

```bash
uvicorn integrations.n8n_api:app --host 0.0.0.0 --port 8000
```

默认会提供：

- API 根地址：`http://127.0.0.1:8000`
- 健康检查：`http://127.0.0.1:8000/health`
- Swagger 文档：`http://127.0.0.1:8000/docs`

如果你机器上 Python 不是默认 `python`，可以先指定：

```bash
export VIDEO_AGENT_PYTHON=python3
uvicorn integrations.n8n_api:app --host 0.0.0.0 --port 8000
```

因为包装层内部默认是调用：

- `python cli.py ...`
- `python main.py generate ...`

---

## 6. 参数如何和现有入口对齐

## A. `cli.py` 分步流程接口

请求地址：

```text
POST /api/v1/cli/run
```

示例请求体：

```json
{
  "step": "all",
  "mode": "sop",
  "topic": "重生千金复仇记",
  "style": "情感",
  "episodes": 3,
  "async_run": true
}
```

字段映射：

- `step` → `cli.py --step`
- `mode` → `cli.py --mode`
- `topic` → `cli.py --topic`
- `style` → `cli.py --style`
- `episodes` → `cli.py --episodes`
- `character_file` → `cli.py --character-file`

支持的 `step`：

- `all`
- `script`
- `character`
- `storyboard`
- `keyframe`
- `video`
- `assemble`
- `audit`

支持的 `mode`：

- `sop`
- `efficient`

注意：`efficient` 当前仍然保持和原 `cli.py` 一样的约束：

- `mode=efficient` 时只支持 `step=all`

别在 n8n 里乱拼一个 `efficient + storyboard`，那会直接报 400。这个限制不是 API 发明的，是为了和原入口行为保持一致。

---

## B. `main.py generate` 主流程接口

请求地址：

```text
POST /api/v1/main/generate
```

示例请求体：

```json
{
  "topic": "重生千金复仇记",
  "style": "情感",
  "episodes": 3,
  "output": "output",
  "config": "config.yaml",
  "auto_approve": false,
  "async_run": true
}
```

字段映射：

- `topic` → `main.py generate --topic`
- `style` → `main.py generate --style`
- `episodes` → `main.py generate --episodes`
- `output` → `main.py generate --output`
- `config` → `main.py generate --config`
- `auto_approve` → `main.py generate --auto-approve`

这条接口适合：

- 让 n8n 触发完整主流程
- 不想拆每个阶段节点时直接一把跑

---

## 7. `async_run` 怎么用

这个字段是给 n8n 准备的，非常重要。

### `async_run = false`

API 会等命令执行完再返回。

适合：

- 很短的阶段
- 调试
- 你明确知道这个任务几秒就完

### `async_run = true`

API 会立刻返回 `run_id`，任务在后台继续跑。

适合：

- 真正的生产使用
- 长时间生成任务
- 避免 n8n webhook / HTTP Request 超时

推荐默认用：

```json
{
  "async_run": true
}
```

然后在 n8n 后面再接轮询：

- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/logs`

---

## 8. n8n 里怎么改参数

这个问题本质上不是“API 支不支持”，而是“n8n 节点怎么把变量传进来”。

答案很简单：**在 Webhook / Set / Code 节点里改 JSON 字段，然后传给 HTTP Request 节点。**

### 最常改的参数

- `topic`
- `style`
- `episodes`
- `step`
- `mode`
- `auto_approve`

### 方案 1：Webhook 直接接收外部参数

你的请求体可以直接这么传：

```json
{
  "topic": "霸总追妻火葬场",
  "style": "情感",
  "episodes": 5,
  "step": "storyboard",
  "mode": "sop"
}
```

然后 n8n 的 Code 节点做默认值兜底，再转发给 API。

### 方案 2：在 n8n 的 Set / Code 节点里写死默认参数

比如：

```javascript
return [{
  json: {
    topic: '重生千金复仇记',
    style: '情感',
    episodes: 3,
    step: 'all',
    mode: 'sop',
    async_run: true
  }
}];
```

### 方案 3：根据上游条件动态切换 step

比如：

- 白天先跑 `script`
- 人审通过后再跑 `storyboard`
- 最后再跑 `keyframe` / `video`

你在 Code 节点里可以这么写：

```javascript
const approved = $json.approved ?? false;

return [{
  json: {
    topic: $json.topic ?? '重生千金复仇记',
    style: $json.style ?? '情感',
    episodes: Number($json.episodes ?? 3),
    step: approved ? 'storyboard' : 'script',
    mode: 'sop',
    async_run: true
  }
}];
```

这就是 n8n 真正的价值：**把参数控制和任务编排外置。**

---

## 9. 模板工作流怎么用

模板文件：

```text
integrations/n8n_workflow_template.json
```

当前模板结构是：

```text
Webhook Trigger
→ Build Payload(Code)
→ HTTP Request(调用 /api/v1/cli/run)
→ Respond to Webhook
```

导入方法：

1. 打开 n8n
2. Import workflow
3. 选择 `integrations/n8n_workflow_template.json`
4. 检查 HTTP Request 节点的 URL 是否还是：
   - `http://127.0.0.1:8000/api/v1/cli/run`
5. 如果 video-agent API 不和 n8n 在同一台机器，改成你的真实地址

例如：

```text
http://192.168.1.10:8000/api/v1/cli/run
```

或者：

```text
https://your-domain.com/video-agent/api/v1/cli/run
```

---

## 10. 推荐的 n8n 第一版编排方式

别一上来就做一坨巨复杂工作流。第一版建议这样：

### 工作流 A：触发单次分步任务

```text
Webhook
→ Build Payload
→ HTTP Request(/api/v1/cli/run)
→ Respond
```

适合：

- 手工触发某个阶段
- 快速验证接入

### 工作流 B：触发完整主流程

```text
Webhook
→ Build Payload
→ HTTP Request(/api/v1/main/generate)
→ Respond
```

适合：

- 一次性生成完整短剧

### 工作流 C：后台任务 + 状态轮询

```text
Webhook
→ HTTP Request(async_run=true)
→ Wait / Loop
→ HTTP Request(GET /api/v1/runs/{run_id})
→ IF(status == success/failed)
→ Respond / Notify
```

这个才更接近生产可用。

---

## 11. 当前版本的限制

这部分要讲清楚，不然很容易误会“已经集成完了”。

### 已经完成的

- 有 FastAPI 包装层
- 有 n8n 可直接调用的 HTTP 接口
- 有运行状态和日志查询接口
- 有工作流模板
- 有参数映射文档

### 还没做的

- **本机未安装 n8n**
- **未验证 n8n UI 导入流程**（因为本机没有 n8n 实例）
- 没做 API 鉴权（比如 Bearer Token）
- 没做持久化任务队列
- 运行记录现在是**进程内内存态**，服务重启后会丢
- 没做 systemd / pm2 / supervisor 守护部署
- 没做 nginx / caddy 反代
- 没做 HTTPS / 域名 / 外网暴露

所以别误判成“生产版已上线”。这只是**第一版接入层**。

---

## 12. 下一步建议

如果你下一步真要把它接进 n8n 并上线，建议按这个顺序来：

1. **先启动本地 FastAPI 包装层**
2. **在另一台已安装 n8n 的环境导入模板**
3. **先打通 `/api/v1/cli/run` 的 `script` 或 `storyboard`**
4. **再切到 `async_run=true` + 轮询状态**
5. **补鉴权**（至少 Header Token）
6. **补持久化**（Redis / DB / 文件记录）
7. **最后再做公网部署**

顺序别反。先把业务走通，再谈花活。

---

## 13. 快速测试命令

### 健康检查

```bash
curl http://127.0.0.1:8000/health
```

### 触发一个 SOP 全流程（后台）

```bash
curl -X POST http://127.0.0.1:8000/api/v1/cli/run \
  -H 'Content-Type: application/json' \
  -d '{
    "step": "all",
    "mode": "sop",
    "topic": "重生千金复仇记",
    "style": "情感",
    "episodes": 3,
    "async_run": true
  }'
```

### 触发 `main.py generate`

```bash
curl -X POST http://127.0.0.1:8000/api/v1/main/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "topic": "重生千金复仇记",
    "style": "情感",
    "episodes": 3,
    "output": "output",
    "config": "config.yaml",
    "auto_approve": false,
    "async_run": true
  }'
```

### 查询运行状态

```bash
curl http://127.0.0.1:8000/api/v1/runs/<run_id>
```

### 查询运行日志

```bash
curl http://127.0.0.1:8000/api/v1/runs/<run_id>/logs
```

---

## 14. 一句话总结

这次已经把 `video-agent` 做成了一个**n8n 能接的第一版外壳**：

- 有 HTTP API
- 有 n8n 模板
- 有参数映射
- 有部署说明

但 **n8n 本体没装，也没上线**。现在交付的是**接入准备**，不是**平台部署完成**。
