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

## Window 12: e-Invoice AI 预校验 + Credit Note + Consolidated

### [2026-04-30] CN cancel 不能复用 apply_sales_out

**场景**：Credit Note DRAFT 取消时要回滚库存（把 `apply_sales_return` 入库的 qty 扣回去）
**犯的错**：plan 阶段直接说 "调一次 `apply_sales_out` 把退货数量扣回去"。手测点 Cancel CN → 报 "Cannot ship 20.0000 of sku=1 ... insufficient on_hand/reserved"
**根因**：`apply_sales_out` 的原子 SQL 是 `WHERE reserved >= qty AND on_hand >= qty`，因为它服务的正常路径是 SO confirm（`apply_reserve` 把 reserved +=qty）→ DO ship（同时扣 reserved + on_hand）。CN 退货入库走 `apply_sales_return` 只动 `on_hand`，根本没经过 `apply_reserve`，reserved=0 导致 SQL 永远失败
**纠正**：新增 `inventory.apply_sales_return_reverse`，SQL 只要求 `on_hand >= qty`，不动 reserved；audit 用 `ADJUSTMENT_OUT + source_type=CN` 标识"撤销退货"
**预防**：(a) 新增 inventory 写操作前画一遍 6 维库存的状态转移图，明确每个原子函数的入口前置条件；(b) 用 mock 写的 service 单测能跑过不代表逻辑对——`apply_sales_out` 在测试里被 AsyncMock 替代，根本没执行真实 SQL，永远不会暴露这个 bug。教训：service 测试 mock inventory 函数时，应该断言**调用的是哪个具体函数名**（用 `apply_sales_return_reverse` 而不是 `apply_sales_out`），让函数名本身做契约

---

## Window 15: Dashboard + AI 日报

### [2026-05-04] `docker compose restart` 不重读 env_file

**场景**:Window 15 演示 AI 日报,DB 已开 `ai_master_enabled=1` + `ai_features.DASHBOARD_SUMMARY=true`,`.env` 改 `AI_ENABLED=true`,`docker compose restart backend` 后前端仍显示 "AI digest is disabled for this organization."
**犯的错**:以为 `docker compose restart` 会重新加载 `env_file` 指向的 `.env`。实际上 restart 只是重启已存在的容器实例,环境变量是容器创建时从 `.env` 快照进容器的,**restart 不重新读快照**。`docker compose exec backend env | grep AI_ENABLED` 仍是 `false`(老快照)
**纠正**:`docker compose up -d --force-recreate backend` 销毁并按当前 `.env` 重建容器,新进程才能拿到新值。验证手段:`docker compose exec backend python -c "from app.core.config import settings; print(settings.AI_ENABLED)"`
**预防**:任何修改 `.env`(尤其涉及 feature flag / API key / DB URL)后,统一用 `docker compose up -d <service>` 而非 `restart`。如果只改了代码文件不改 env,`restart` 才安全。把这条挂进 CLAUDE.md Part 12 部署/DevOps 备注里。

---

### [2026-04-28] PyCharm Docker Compose Interpreter 的 Debug 模式会劫持容器 entrypoint

**场景**：用 PyCharm 配 Docker Compose Interpreter 跑 backend
**犯的错**：用 PyCharm 的 Run/Debug Configurations 启动 backend，PyCharm 会通过 docker API 直接 create container 时把 `Cmd` 替换成 `python /opt/.pycharm_helpers/pydev/pydevd.py --client host.docker.internal --port 63655 --file /app/app/main.py`，绕过 Dockerfile 的 `CMD`。当 PyCharm Debug Server 不在监听时，pydevd 立即 ConnectionRefused → exit → docker restart 死循环
**纠正**：(a) 立即修复：`docker compose down && docker compose up -d` 从普通终端跑（任何不是 PyCharm 启动按钮的方式都行，包括 PyCharm 内嵌 Terminal）；(b) 长期方案：用 `pydevd_pycharm.settrace()` 模式 + Python Debug Server 调试，不要用 Docker Compose Interpreter 的 Debug 按钮
**预防**：CLAUDE.md 加一条 IDE 集成规则：Docker 容器统一从命令行启停；PyCharm 仅做代码补全 + git + 测试 runner，不通过 PyCharm 启停 docker。如果要远程调试，走 settrace 模式。

---

## Window 16: UI 打磨 + i18n 全量补齐

### [2026-05-04] react-i18next typed t() 默认返回 TFunctionDetailedResult，subagent 大量 `as string` 都 build fail

**场景**：W16 三个并行 subagent 把 ~285 处硬编码文案 t() 化，几乎所有 columns 工厂里都写了 `(key, opts) => t(`ns:${key}`, opts as never) as string`
**犯的错**：react-i18next 14+ 的 `t()` 默认返回类型是 `TFunctionDetailedResult<$SpecialObject, never>` 联合，`as string` cast 触发 TS2352 "may be a mistake"。一打 build 一片红
**纠正**：(a) 短期：bulk sed 把 `) as string` 改成 `) as unknown as string` 强转过关；(b) 长期：在 `frontend/src/i18next.d.ts` 加 module augmentation 设置 `CustomTypeOptions: { returnNull: false, returnEmptyString: true, returnObjects: false }`；未来 `t()` 直接返回 string
**预防**：给 i18n subagent 的 prompt 里明确"`t()` 返回 string，不需要 cast"。或窗口开始前先把 i18next.d.ts 配好再放 subagent

### [2026-05-04] subagent 在 catch 块引用 try 块的 const → TS18004

**场景**：i18n subagent 改 TransferCreatePage / AdjustmentCreatePage 时把 `console.error` 留在 catch 块里，shorthand 引用了 try 块的 `const payload`
**犯的错**：JS 块作用域 const 出 try 块就不可见。subagent 没注意，TS 抛 TS18004 "no value exists in scope for the shorthand property"
**纠正**：把 console.error 引用从 `payload` 改成 `values`(catch 外可见的函数参数)
**预防**：subagent 改完后必须 `npm run build` 才算完成。给 prompt 加一句"如果引用 try 块的局部变量，要么提到 try 外，要么换用 catch 可见的变量"

### [2026-05-04] Worktree 没 node_modules / pytest，验证流程要适配

**场景**：W16 在 `.claude/worktrees/window-16` 开发，Step 8 验证时 worktree 既没 `node_modules` 也没 Python 虚拟环境
**犯的错**：以为 worktree 共享主仓的依赖。实际 worktree 是独立 working dir，需要自己跑 `npm install`(2min, 781 packages)；后端测试更尴尬，worktree/主仓/docker container 都没 pytest
**纠正**：(前端) worktree 单独跑 `npm install`；(后端) `docker exec -u root erp_backend pip install pytest pytest-asyncio` 后 `docker cp` worktree 文件进容器跑测试，测完再 cp 主仓文件还原
**预防**：把 pytest 加到 backend Dockerfile 始终装(requirements-dev.txt 已有, dev profile 应安装)。短期先把 setup 步骤补到 CLAUDE.md Part 14 Window 工作流

## Window 16+ 修补：e-Invoice TIN snapshot 缺失

### [2026-05-04] W11 漏了发票 TIN snapshot — 法律凭证不合规

**场景**：用户在 InvoiceDetailPage 上发现没显示 TIN，让我排查
**犯的错**：W11 实现 invoice 时只在 customer / org 表存了 tin，没在 invoice / credit_note 表 snapshot。CLAUDE.md C4 明文要求"单据涉关键字段必须 snapshot"，但 TIN 这一项被漏。后果：(a) 哪天 customer.tin 改了，旧发票的法律 TIN 也跟着变，违反 LHDN 合规；(b) MyInvois mock 提交 payload 实时 lookup org/customer，跟 W18 真实 LHDN 对接思路不一致
**纠正**：(1) `invoices` / `credit_notes` 各加 `seller_tin VARCHAR(16)` + `buyer_tin VARCHAR(16)`；(2) Alembic migration 同时 backfill 历史行从 org/customer.tin；(3) `generate_draft_from_so` / `generate_monthly_consolidated` 创建草稿时写入 snapshot；(4) `_build_payload` 优先用 invoice 上的 snapshot，fallback 到 live；(5) CN 从 invoice 继承 snapshot；(6) Frontend Detail 页渲染，缺失时红字提示
**预防**：W11/W18 review checklist 加一条"e-Invoice 字段是否 snapshot 完整"。CLAUDE.md C4 已有规则，但要在 e-Invoice 字段列表里补一条 TIN（snapshot 必填项还可能漏：`buyer_name`, `buyer_address`, `seller_name`, `seller_address` — W17/W18 应一并补）

### [2026-05-04] Python 局部 import 遮蔽模块级名字 → UnboundLocalError

**场景**：往 `generate_monthly_consolidated` 里加 `from app.models.partner import Customer` 想做 buyer TIN snapshot 查询
**犯的错**：模块顶部 line 43 已经 `from app.models.partner import Customer`。我又在函数内部第二次写 local import。Python 看到函数内有 `Customer` 赋值 → 把整个函数体里的 `Customer` 当成 local。结果函数前部 line 655 的 `.join(Customer, ...)` 在 local import 之前执行 → UnboundLocalError
**纠正**：删掉冗余的 local import，统一靠模块级 import
**预防**：加 import 前先 `grep "import Customer"` 确认有没有，避免 shadow。也可启用 ruff F823 / F841 类规则检测。这条放进 CLAUDE.md Part 6 backend 命名/import 规范里。

## 通用教训

（每完成一个 Phase 提炼一次）
