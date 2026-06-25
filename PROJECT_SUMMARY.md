# SmartSpace SaaS - 企业级智慧空间与物业管理系统

## 项目概述

SmartSpace SaaS 是一个面向物业管理企业的多租户SaaS系统，提供车位管理、车辆调度、计费结算、审计追踪等核心功能。

**技术栈：**
- **后端：** Python 3.10 + FastAPI + SQLAlchemy 2.0
- **数据库：** SQLite（可平滑迁移至PostgreSQL）
- **前端：** HTML5 + TailwindCSS + Alpine.js
- **测试：** pytest + pytest-asyncio

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    前端展示层 (Frontend)                      │
│  HTML5 + TailwindCSS + Alpine.js                            │
│  - 仪表盘 (Dashboard)                                        │
│  - 车辆管理 (Vehicle Management)                             │
│  - 车位管理 (Parking Management)                             │
│  - 计费中心 (Billing Center)                                 │
│  - 审计日志 (Audit Logs)                                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    API网关层 (FastAPI)                        │
│  - JWT认证                                                   │
│  - 多租户隔离                                                │
│  - 权限控制 (RBAC)                                           │
│  - 请求追踪                                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    业务逻辑层 (Services)                      │
│  - VehicleService (车辆调度)                                 │
│  - BillingService (计费结算)                                 │
│  - AuditService (审计日志)                                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    数据访问层 (SQLAlchemy)                     │
│  - 异步ORM                                                   │
│  - 参数化查询 (防SQL注入)                                     │
│  - 事务管理                                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    数据库层 (SQLite)                          │
│  14张业务表 + 23个优化索引                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 数据库E-R关系

### 核心实体关系

```
tenants (租户)
    ├── users (用户) 1:N
    ├── parking_zones (停车区域) 1:N
    ├── parking_spaces (车位) 1:N
    ├── vehicles (车辆) 1:N
    ├── billing_accounts (计费账户) 1:N
    ├── vehicle_logs (车辆日志) 1:N
    ├── billing_transactions (交易流水) 1:N
    └── audit_logs (审计日志) 1:N

users (用户)
    ├── user_roles (用户角色) N:N
    └── roles (角色) N:N

roles (角色)
    └── role_permissions (角色权限) N:N
        └── permissions (权限) N:N

parking_zones (停车区域)
    └── parking_spaces (车位) 1:N

vehicles (车辆)
    └── vehicle_logs (车辆日志) 1:N

billing_accounts (计费账户)
    └── billing_transactions (交易流水) 1:N
```

### 表结构概览

| 表名 | 用途 | 关键字段 |
|------|------|----------|
| tenants | 租户管理 | id, code, status, max_spaces |
| users | 用户管理 | id, tenant_id, username, password_hash |
| roles | 角色管理 | id, tenant_id, name, is_system |
| permissions | 权限定义 | id, code, module |
| user_roles | 用户角色关联 | user_id, role_id |
| role_permissions | 角色权限关联 | role_id, permission_id |
| parking_zones | 停车区域 | id, tenant_id, hourly_rate |
| parking_spaces | 车位管理 | id, zone_id, status, current_vehicle_id |
| vehicles | 车辆信息 | id, tenant_id, plate_number |
| vehicle_logs | 车辆调度日志 | id, action, entry_time, exit_time, fee_amount |
| billing_accounts | 计费账户 | id, balance, credit_limit |
| billing_transactions | 交易流水 | id, amount, idempotency_key |
| audit_logs | 审计日志 | id, action, severity, old_value, new_value |
| system_configs | 系统配置 | key, value, value_type |

---

## 核心功能实现

### 1. 多租户隔离

- **行级隔离：** 所有业务表包含 `tenant_id` 字段
- **中间件验证：** `TenantIsolation` 依赖自动校验租户权限
- **横向越权防护：** 用户只能访问自己租户的数据

### 2. RBAC权限控制

- **角色管理：** 支持系统内置角色和自定义角色
- **权限粒度：** 17个细粒度权限（space:read, billing:write等）
- **动态校验：** `PermissionChecker` 依赖实时查询用户权限

### 3. 车辆调度（高并发防护）

- **原子化状态变更：** 使用乐观锁防止车位状态冲突
- **幂等性校验：** 同一分钟内的重复入场请求被拦截
- **事务保证：** 车位更新、日志记录在同一事务中

```python
# 乐观锁实现
update_result = await db.execute(
    update(ParkingSpace)
    .where(
        and_(
            ParkingSpace.id == space.id,
            ParkingSpace.status == "available"  # 确保状态未变
        )
    )
    .values(status="occupied", ...)
)
if update_result.rowcount == 0:
    raise HTTPException(409, "车位已被其他车辆占用")
```

### 4. 计费系统（事务隔离+幂等性）

- **幂等键：** 每个交易有唯一幂等键，防止重复扣款
- **事务隔离：** 余额更新和流水记录在同一事务中
- **对账机制：** 记录交易前后余额，支持财务审计

### 5. 审计日志（自动拦截）

- **全局拦截：** 权限变更、扣费、强制放行等高危操作自动记录
- **不可篡改：** 审计日志只增不改，记录完整变更历史
- **严重级别：** debug/info/warning/critical 四级分类

---

## 测试覆盖

### 测试统计

| 指标 | 数值 |
|------|------|
| 测试文件数 | 4 |
| 测试用例数 | 18 |
| 通过率 | 100% |
| 执行时间 | ~14秒 |

### 测试场景

#### 越权请求测试 (7个)
- ✅ 跨租户访问拒绝 (403)
- ✅ 未授权访问拒绝 (401)
- ✅ 无效Token拒绝 (401)
- ✅ 无权限用户操作拒绝 (403)
- ✅ 同租户正常访问 (200)
- ✅ 强制放行权限检查
- ✅ 审计日志租户隔离

#### 并发计费测试 (4个)
- ✅ 5次并发出场只有1次成功
- ✅ 交易原子性验证
- ✅ 重复支付防护
- ✅ 退款创建负向交易

#### 车辆调度边界值测试 (7个)
- ✅ 满车位入场拒绝 (409)
- ✅ 完整入场-出场流程
- ✅ 重复入场防护
- ✅ 不存在车辆出场 (404)
- ✅ 无入场记录出场 (404)
- ✅ 强制放行+审计日志
- ✅ 停车场状态统计

---

## 安全审计结论

### ✅ 已通过检查

1. **SQL注入防护：** 全部使用SQLAlchemy参数化查询，无原生SQL拼接
2. **密码安全：** 使用bcrypt哈希存储，不可逆
3. **JWT认证：** Token有过期时间，支持多租户claims
4. **权限控制：** RBAC模型，细粒度权限校验
5. **多租户隔离：** 行级数据隔离，防止横向越权
6. **幂等性设计：** 关键操作有幂等键，防止重复提交
7. **事务完整性：** 财务操作使用数据库事务
8. **审计追踪：** 高危操作自动记录，不可篡改

### ⚠️ 生产环境建议

1. **密钥管理：** SECRET_KEY需从环境变量读取，当前为开发默认值
2. **HTTPS强制：** 生产环境需配置SSL/TLS
3. **CORS限制：** 生产环境需限制allow_origins
4. **数据库迁移：** SQLite适合开发，生产建议PostgreSQL
5. **日志系统：** 集成ELK或类似日志系统
6. **监控告警：** 接入Prometheus/Grafana监控

---

## 前端响应式断点

| 断点 | 宽度 | 布局调整 |
|------|------|----------|
| Mobile | < 640px | 单列布局，表格横向滚动 |
| Tablet | 640px - 1024px | 2-3列网格，侧边栏折叠 |
| Desktop | 1024px - 1440px | 4-6列网格，完整导航 |
| Wide | > 1440px | 最大宽度1280px居中 |

### 关键组件响应式

- **统计卡片：** 1列 → 2列 → 4列
- **车位热力图：** 10列 → 15列 → 20列 → 25列
- **数据表格：** 横向滚动，固定首列
- **模态框：** 移动端全屏，桌面端居中

---

## 代码统计

| 类型 | 文件数 | 代码行数 |
|------|--------|----------|
| 后端API | 6 | 1,251 |
| 数据模型 | 8 | 401 |
| 业务服务 | 3 | 1,026 |
| 核心模块 | 4 | 294 |
| 测试代码 | 4 | 790 |
| 前端页面 | 1 | ~500 |
| **总计** | **26** | **~4,262** |

---

## 快速启动

### 后端启动

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 访问地址

- API文档: http://localhost:8000/docs
- ReDoc文档: http://localhost:8000/redoc
- 前端页面: 直接打开 frontend/index.html

### 运行测试

```bash
cd backend
python -m pytest tests/ -v
```

---

## 项目结构

```
smart-space-saas/
├── backend/
│   ├── app/
│   │   ├── api/           # API路由
│   │   │   ├── auth.py    # 认证API
│   │   │   ├── vehicles.py # 车辆API
│   │   │   ├── spaces.py  # 车位API
│   │   │   ├── billing.py # 计费API
│   │   │   └── audit.py   # 审计API
│   │   ├── core/          # 核心模块
│   │   │   ├── config.py  # 配置
│   │   │   ├── database.py # 数据库
│   │   │   └── security.py # 安全
│   │   ├── models/        # 数据模型
│   │   ├── services/      # 业务服务
│   │   └── main.py        # 应用入口
│   ├── tests/             # 测试代码
│   └── requirements.txt   # 依赖
├── frontend/
│   └── index.html         # 前端页面
├── schema.sql             # 数据库Schema
└── PROJECT_SUMMARY.md     # 本文档
```

---

## 交付清单

- ✅ 完整后端API（FastAPI）
- ✅ 数据库Schema（SQLite）
- ✅ 前端管理界面（HTML5）
- ✅ 自动化测试（18个用例）
- ✅ 安全审计报告
- ✅ 项目文档

---

**项目状态：** ✅ 已完成  
**交付日期：** 2026-06-25  
**版本：** v1.0.0
