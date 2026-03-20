# 后端重构计划

> 契约文件：[api-contract.md](api-contract.md)
> 前端重构计划：[frontend-refactor-ui.md](frontend-refactor-ui.md)

---

## 一、重构范围

### 1.1 需要变更的文件

| 文件 | 动作 | 说明 |
|------|------|------|
| `backend/server/http_handler.py` | **删除** | BaseHTTPRequestHandler → FastAPI 替代 |
| `backend/server/runtime.py` | **重构** | 保留业务逻辑，提取 Pydantic models |
| `backend/server/__init__.py` | **更新** | 导出新 app |
| `frontend/__init__.py` | **重构** | 移除模板替换逻辑，仅做 dist/ 挂载 |
| `monitor.py` | **重构** | 从 BaseHTTPRequestHandler 切换到 uvicorn |
| `pyproject.toml` | **更新** | 添加新依赖 |

### 1.2 完全不动的文件

| 文件 | 原因 |
|------|------|
| `backend/workflow.py` | 核心状态机，无需改动 |
| `backend/codex_cli.py` | Codex CLI 调用层 |
| `backend/prompts.py` | prompt 模板 |
| `backend/tracing.py` | trace 装饰器 |
| `backend/snapshot.py` | 快照聚合（被 routes 层调用，接口不变） |
| `backend/writers.py` | 产物生成 |
| `backend/demo_repo.py` | 演示仓库 |
| `cli.py` | CLI 入口 |

---

## 二、目标目录结构

```
backend/server/
├── __init__.py              # 导出 create_app
├── app.py                   # FastAPI 应用工厂 + 中间件 + 静态文件挂载
├── deps.py                  # 依赖注入（MonitorAppState 单例）
├── models.py                # Pydantic response/request models
├── routes/
│   ├── __init__.py
│   ├── runs.py              # GET /api/runs + POST /api/runs
│   ├── snapshot.py          # GET /api/runs/{id}/snapshot
│   └── artifacts.py         # GET /api/runs/{id}/artifact + /log
├── ws.py                    # WebSocket /ws/runs/{id}/snapshot
└── runtime.py               # 保留原有业务逻辑（create_run, load_snapshot 等）
```

---

## 三、执行步骤（含并行/串行标注）

### 🔗 串行前置：备份旧文件

```
步骤 0: 备份
├─ 0.1 复制 http_handler.py → .agent_cache/.backup/
├─ 0.2 复制 monitor.py → .agent_cache/.backup/
└─ 0.3 复制 frontend/__init__.py → .agent_cache/.backup/
```

---

### 🔗 串行层 S1：基础设施（必须先完成）

```
S1.1 pyproject.toml — 添加依赖
     新增: fastapi>=0.115.0, uvicorn[standard]>=0.34.0, websockets>=15.0
     放入 [project.optional-dependencies] monitor = [...]
     更新 [project.scripts] 入口不变

S1.2 backend/server/models.py — 定义 Pydantic 模型
     从 api-contract.md 类型定义翻译为 Pydantic v2 models:
     - RunMeta, RunList
     - SnapshotResponse (可复用 Any dict，后续渐进类型化)
     - ArtifactResponse
     - CreateRunRequest, CreateRunResponse

S1.3 backend/server/deps.py — 依赖注入
     - 全局 MonitorAppState 实例持有
     - FastAPI Depends() 函数
```

> S1.2 和 S1.3 互不依赖，**可并行**。

---

### 🔀 并行层 P1：路由实现（依赖 S1）

以下三个路由模块互不依赖，**全部可并行**：

```
P1.1 routes/runs.py
     - GET /api/runs → 调用 runtime.list_runs()
     - POST /api/runs → 调用 runtime.create_run()
     
P1.2 routes/snapshot.py
     - GET /api/runs/{run_id}/snapshot → 调用 runtime.load_snapshot()
     
P1.3 routes/artifacts.py
     - GET /api/runs/{run_id}/artifact → 调用 runtime.read_artifact()
     - GET /api/runs/{run_id}/log → 调用 runtime.read_run_log()
```

---

### 🔀 并行层 P2：WebSocket + App 工厂（依赖 S1）

与 P1 **可并行**：

```
P2.1 ws.py — WebSocket 端点
     - ws /ws/runs/{run_id}/snapshot
     - 1s 间隔推送 load_snapshot() 结果
     - 连接后立即推送一次
     - try/except WebSocketDisconnect 处理断线

P2.2 app.py — FastAPI 应用工厂
     - create_app(app_state: MonitorAppState) -> FastAPI
     - 注册所有 routes/ 蓝图
     - 注册 ws.py WebSocket
     - CORS 中间件
     - 静态文件挂载 (frontend/dist/ 如存在)
     - SPA fallback (/* → index.html)
```

---

### 🔗 串行层 S2：入口更新（依赖 P1 + P2）

```
S2.1 monitor.py 重构
     - 导入 create_app
     - 构建 MonitorAppState
     - uvicorn.run(create_app(state), host=host, port=port)
     - argparse 参数保持兼容

S2.2 frontend/__init__.py 精简
     - 移除 render_dashboard_html() 模板替换逻辑
     - 保留 load_trace_viewer_*() 供 writers.py 使用
     - 新增 get_dist_dir() 返回 dist/ 路径
     
S2.3 backend/server/__init__.py 更新导出
```

> S2.1, S2.2, S2.3 互不依赖，**可并行**。

---

### 🔗 串行层 S3：清理（依赖 S2）

```
S3.1 删除 backend/server/http_handler.py
S3.2 验证: uvicorn 启动 + API 测试
```

---

## 四、依赖关系 DAG

```
S1.1 (pyproject) ─┐
S1.2 (models) ────┤
S1.3 (deps) ──────┤
                   ▼
         ┌── P1.1 (runs.py)
         ├── P1.2 (snapshot.py)
         ├── P1.3 (artifacts.py)     ← 全部可并行
         ├── P2.1 (ws.py)
         └── P2.2 (app.py)
                   │
                   ▼
         ┌── S2.1 (monitor.py)
         ├── S2.2 (frontend/__init__)  ← 可并行
         └── S2.3 (server/__init__)
                   │
                   ▼
              S3 (清理 + 验证)
```

---

## 五、关键实现细节

### 5.1 app.py 应用工厂模板

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

def create_app(app_state: MonitorAppState) -> FastAPI:
    app = FastAPI(title="Agent System Coding Monitor")
    app.state.monitor = app_state
    
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], ...)
    
    app.include_router(runs_router, prefix="/api")
    app.include_router(snapshot_router, prefix="/api")
    app.include_router(artifacts_router, prefix="/api")
    app.add_api_websocket_route("/ws/runs/{run_id}/snapshot", ws_snapshot)
    
    # 静态文件挂载（前端 dist/）
    dist = get_dist_dir()
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="spa")
    
    return app
```

### 5.2 WebSocket 推送核心逻辑

```python
import asyncio, json
from fastapi import WebSocket, WebSocketDisconnect

async def ws_snapshot(websocket: WebSocket, run_id: str):
    await websocket.accept()
    app_state = websocket.app.state.monitor
    try:
        while True:
            snapshot = load_snapshot(app_state.runtime_root, run_id)
            await websocket.send_text(json.dumps(snapshot, ensure_ascii=False))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
```

### 5.3 runtime.py 改动最小化

`runtime.py` 中所有函数签名不变：
- `create_run(app_state, prompt) → dict`
- `load_snapshot(runtime_root, run_id) → dict | None`
- `list_runs(runtime_root) → list[dict]`
- `read_artifact(runtime_root, run_id, path) → dict`
- `read_run_log(runtime_root, run_id) → str`

路由层只做 HTTP 适配（参数提取、错误码映射），不改业务逻辑。

### 5.4 pyproject.toml 变更

```toml
[project.optional-dependencies]
monitor = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.34.0",
  "websockets>=15.0",
]
```

安装方式：`pip install -e ".[monitor]"`

---

## 六、验收标准

- [ ] `pip install -e ".[monitor]"` 成功
- [ ] `agent-system-coding-monitor --port 8080` 可启动
- [ ] `curl http://localhost:8080/api/runs` 返回 200
- [ ] `POST /api/runs` 创建运行成功
- [ ] `GET /api/runs/{id}/snapshot` 返回快照数据
- [ ] `GET /api/runs/{id}/artifact?path=...` 读取产物
- [ ] `GET /api/runs/{id}/log` 返回日志
- [ ] WebSocket `ws://localhost:8080/ws/runs/{id}/snapshot` 可连接并收到推送
- [ ] 旧 `http_handler.py` 已删除
- [ ] `writers.py` 的 trace-viewer HTML 静态导出功能不受影响
