# Lessons Learned

> 开发过程中踩到的坑 + 纠正后的教训。每次被纠正必记一条，开新 session 前 Claude 自动读此文件。

## 格式

每条教训按这个格式：

```markdown
### [YYYY-MM-DD] 简短标题

**场景**：做什么时出的问题
**犯的错**：具体做错了什么
**纠正**：正确做法
**预防**：如何避免下次
```

---

## Window 01: 脚手架

（待填）

## Window 02: 数据模型

（待填）

## Window 03: 认证系统

### [2026-04-24] LoginAttempt 重复定义

**场景**：Window 03 补加 `LoginAttempt` 模型到 `organization.py`  
**犯的错**：没有先确认 Window 02 已在 `models/audit.py` 定义了同名 + 同表名的模型  
**纠正**：删掉 `organization.py` 里的重复定义，从 `audit.py` 导入  
**预防**：开始新 window 前 `grep -rn "class LoginAttempt\|login_attempts" app/models/` 先确认

### [2026-04-24] `from __future__ import annotations` + slowapi + Body() 组合炸弹

**场景**：为路由函数添加 slowapi `@limiter.limit()` 装饰器  
**犯的错**：路由文件顶部有 `from __future__ import annotations`，导致 Pydantic 模型注解变成 ForwardRef；加 `Body(...)` 后 Pydantic 无法 rebuild TypeAdapter  
**纠正**：路由文件（`routers/`）禁用 `from __future__ import annotations`；其他层保留无碍  
**预防**：写路由文件时不加 future import；slowapi 装饰器必须配合显式 `= Body(...)` 使用

---

## Window 09: OCR AI（SSE 流式）

### [2026-04-28] SSE + FastAPI dependency 生命周期：流里的 session 已被提交

**场景**：OCR 服务在 SSE generator 的 `finally` 块里 `session.add(AICallLog(...))`，期望随请求结束一起 commit
**犯的错**：FastAPI 的 `get_db` dependency 在 endpoint 返回 `EventSourceResponse` 对象的瞬间就走 cleanup（commit），而 generator 是在 cleanup **之后**才被消费；所以 generator 里 `session.add()` 进入的是已经 commit 完的 session，写入静默丢失。表现：`uploaded_files` 行有（在 generator 之前 add+flush），`ai_call_logs` 行没有（在 generator 之内 add）
**纠正**：日志写入用独立的 `async with AsyncSessionLocal() as log_session: ... await log_session.commit()`，跟请求 session 完全脱钩
**预防**：但凡在 SSE generator / `BackgroundTasks` / `StreamingResponse` 的可迭代对象里写 DB，都不能复用请求 session，必须开独立 session。把这条挂到 CLAUDE.md 的 D 级 AI 规则备注里。

### [2026-04-28] SSE 解析器 CRLF/LF 不通用

**场景**：前端 `SSEUploader.tsx` 用 `fetch` + `ReadableStream` 解析 SSE，按 `\n\n` 切帧
**犯的错**：sse-starlette（Python 主流 SSE 库）按 SSE spec 默认发 CRLF (`\r\n\r\n`)，前端 `buffer.indexOf('\n\n')` 在 `\r\n\r\n` 里找不到匹配（中间夹 `\r`）→ buffer 不断累积、`onSuccess` 永不触发 → UI 看起来"上传完无反应"。后端日志一切正常
**纠正**：解析前 `chunk.replace(/\r\n?/g, '\n')` 全部归一成 LF，再走 `\n\n` 切帧逻辑
**预防**：写 SSE 客户端解析器**第一行**就归一行尾。SSE spec 明文允许 `\n\n` / `\r\r` / `\r\n\r\n` 三种分隔符，三种都要支持。后续 e-Invoice 预校验、Dashboard AI 日报如果用 SSE，复用同一个 `SSEUploader` 即可，不要再各写各的解析器

### [2026-04-28] PyCharm Docker Compose Interpreter 的 Debug 模式会劫持容器 entrypoint

**场景**：用 PyCharm 配 Docker Compose Interpreter 跑 backend
**犯的错**：用 PyCharm 的 Run/Debug Configurations 启动 backend，PyCharm 会通过 docker API 直接 create container 时把 `Cmd` 替换成 `python /opt/.pycharm_helpers/pydev/pydevd.py --client host.docker.internal --port 63655 --file /app/app/main.py`，绕过 Dockerfile 的 `CMD`。当 PyCharm Debug Server 不在监听时，pydevd 立即 ConnectionRefused → exit → docker restart 死循环
**纠正**：(a) 立即修复：`docker compose down && docker compose up -d` 从普通终端跑（任何不是 PyCharm 启动按钮的方式都行，包括 PyCharm 内嵌 Terminal）；(b) 长期方案：用 `pydevd_pycharm.settrace()` 模式 + Python Debug Server 调试，不要用 Docker Compose Interpreter 的 Debug 按钮
**预防**：CLAUDE.md 加一条 IDE 集成规则：Docker 容器统一从命令行启停；PyCharm 仅做代码补全 + git + 测试 runner，不通过 PyCharm 启停 docker。如果要远程调试，走 settrace 模式。

---

## 通用教训

（每完成一个 Phase 提炼一次）
