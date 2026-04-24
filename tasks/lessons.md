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

## 通用教训

（每完成一个 Phase 提炼一次）
