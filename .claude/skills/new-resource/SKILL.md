---
name: new-resource
version: 1.0.0
description: |
  Use this skill when adding a new CRUD resource module to the erp-os backend
  or frontend, generating the full 5-layer stack (SQLAlchemy model, Pydantic
  schemas, Repository, Service, FastAPI Router) plus Alembic migration,
  unit tests, frontend ProTable list page, and TypeScript client regeneration.
  Trigger keywords: new resource, scaffold CRUD, add module, new endpoint,
  generate repository, add model, /new-resource slash command.
  Do NOT use for: modifying existing resources (use Edit directly),
  non-CRUD endpoints (custom business flows), frontend-only changes.
---

# New Resource Scaffolder

一键生成 erp-os 项目标准 CRUD 五件套 + 前端 ProTable 页面 + 测试。

## 适用场景

在 erp-os 项目新增一个"资源型"实体（如 `Warehouse`、`Brand`、`UOM`、`TaxRate`）时使用。典型特征：
- 需要 List / Create / Read / Update / Delete 五个操作
- 遵循 CLAUDE.md Part 6 的分层约定
- 每个字段可映射到 UI 表单（ProForm）

## 不适用场景

- 复杂业务流（PO 状态流转、e-Invoice 提交）—— 这些需要自定义 action endpoint
- 只读视图（报表）
- 修改现有资源（直接用 Edit 工具）

---

## 执行步骤

当触发时，按以下顺序生成文件。所有模板在本 skill 的 `templates/` 目录。

### Step 1: 解析参数

从触发消息解析出：

- `resource_name_pascal`: 如 `Warehouse`
- `resource_name_snake`: 如 `warehouse`
- `resource_name_snake_plural`: 如 `warehouses`（表名）
- `resource_name_kebab`: 如 `warehouse`（URL 用）
- `resource_name_kebab_plural`: 如 `warehouses`（URL 用）

### Step 2: 询问字段定义

如果用户没给字段，询问：
```
请提供 Warehouse 模型的字段（key: type）：
  code: str (unique, max 32)
  name: str (max 120)
  type: Enum(MAIN, BRANCH, TRANSIT)
  ...
是否需要关联其他表？
是否需要 soft-delete / org_scoped / version 字段？（默认全部开启）
```

### Step 3: 生成 Backend 文件（9 个）

| 文件 | 模板 | 路径 |
|---|---|---|
| Model | `templates/model.py.jinja` | `backend/app/models/{snake}.py` |
| Schemas | `templates/schema.py.jinja` | `backend/app/schemas/{snake}.py` |
| Repository | `templates/repository.py.jinja` | `backend/app/repositories/{snake}.py` |
| Service | `templates/service.py.jinja` | `backend/app/services/{snake}.py` |
| Router | `templates/router.py.jinja` | `backend/app/routers/{snake}.py` |
| Unit test | `templates/test_service.py.jinja` | `backend/tests/unit/test_{snake}_service.py` |
| Integration test | `templates/test_router.py.jinja` | `backend/tests/integration/test_{snake}_router.py` |
| Alembic migration | `templates/migration.py.jinja` | `backend/alembic/versions/{timestamp}_add_{snake}.py` |
| Factory | `templates/factory.py.jinja` | `backend/tests/factories/{snake}.py` |

### Step 4: 注册 Router

在 `backend/app/main.py` 添加：
```python
from app.routers import warehouse
app.include_router(warehouse.router, prefix="/api/warehouses", tags=["warehouses"])
```

### Step 5: 生成 Frontend 文件（3-4 个）

| 文件 | 模板 | 路径 |
|---|---|---|
| List Page | `templates/ListPage.tsx.jinja` | `frontend/src/pages/{PascalCase}/ListPage.tsx` |
| Detail/Edit Page | `templates/EditPage.tsx.jinja` | `frontend/src/pages/{PascalCase}/EditPage.tsx` |
| Columns config | `templates/columns.tsx.jinja` | `frontend/src/pages/{PascalCase}/columns.tsx` |
| i18n keys | 追加到 `frontend/src/locales/en-US/{snake}.json` 和 `zh-CN/{snake}.json` | — |

### Step 6: 注册 Routes 和 Menu

- 在 `frontend/src/App.tsx` 添加 route
- Menu 由后端下发，在 backend seed 里加一条 `permissions` 记录

### Step 7: 重新生成 TypeScript Client

运行 orval：
```bash
cd frontend && npm run gen:api
```
会从 `http://localhost:8000/openapi.json` 生成类型 + hooks。

### Step 8: 生成 Permission

添加权限到 `backend/scripts/seed_master_data.py`：
```python
permissions = [
    ...,
    {"code": "warehouse.view",   "module": "warehouse", "action": "view"},
    {"code": "warehouse.create", "module": "warehouse", "action": "create"},
    {"code": "warehouse.update", "module": "warehouse", "action": "update"},
    {"code": "warehouse.delete", "module": "warehouse", "action": "delete"},
]
```

### Step 9: 输出摘要

给用户一份总结：
```
✅ Generated 13 files for Warehouse resource:
   Backend: 9 files
   Frontend: 3 files
   Config: 1 file

Next steps (manual):
  1. Review generated files
  2. Run: cd backend && alembic upgrade head
  3. Run: cd frontend && npm run gen:api
  4. Add navigation menu item in seed
  5. Run tests: pytest backend/tests/unit/test_warehouse_service.py -v
```

---

## 遵守的约定（来自 CLAUDE.md）

### 必须包含的字段

每个资源默认生成以下字段（除非用户明确不要）：

```python
id: int                         # PK, auto
organization_id: int            # A2 多租户预留
created_by: int | None          # 审计
updated_by: int | None
created_at: datetime            # UTC
updated_at: datetime            # UTC, on update
deleted_at: datetime | None     # A3 软删除
is_active: bool = True
version: int = 0                # B3 乐观锁
```

### 必须遵守的分层

- Router 只做：参数验证 → 调 Service → 返回 Response schema
- Service 做：业务逻辑 + 开启 transaction + 发布事件
- Repository 做：ORM query（返回 ORM 对象或 dict）
- 绝不在 Router 里 import ORM models

### 必须的 Pydantic schemas

```python
class {Entity}Create(BaseModel): ...     # 创建时输入
class {Entity}Update(BaseModel): ...     # 更新时输入（所有字段 Optional）
class {Entity}Response(BaseModel): ...   # 列表 / 详情返回
class {Entity}Detail({Entity}Response):  # 详情额外字段
    ...
```

### 必须的测试

```python
# test_{snake}_service.py
async def test_create_{snake}_success(...): ...
async def test_create_{snake}_duplicate_code_raises_conflict(...): ...
async def test_update_{snake}_not_found_raises(...): ...
async def test_list_{snake}_pagination(...): ...
async def test_soft_delete_{snake}(...): ...

# test_{snake}_router.py
async def test_{snake}_list_requires_auth(...): ...
async def test_{snake}_list_filters_by_org(...): ...
async def test_{snake}_create_role_enforcement(...): ...
```

---

## 参数推断规则

用户可能说：
- `/new-resource Warehouse` → 询问字段
- `/new-resource Warehouse with code/name/type` → 直接生成，type 字段默认 VARCHAR(32)
- `/new-resource Warehouse like Supplier` → 以 Supplier 为模板复制字段

---

## 生成后的验证 checklist

在回复用户前，检查：

- [ ] 所有文件路径正确，没有覆盖已存在文件
- [ ] Migration 的 revision_id 唯一，`down_revision` 指向最新
- [ ] Model 继承 `BaseModel, SoftDeleteMixin, TimestampedMixin, OrgScopedMixin`
- [ ] Service 层所有方法都有 `organization_id` 过滤
- [ ] Router 所有端点都有 `Depends(get_current_user)`
- [ ] 测试覆盖 happy path + duplicate + not found + soft delete
- [ ] i18n key 中英两份都生成了

---

## 与 slash command 关系

本 skill 被 `.claude/commands/new-resource.md` 调用。Command 是入口，skill 是执行逻辑 + 模板库。
