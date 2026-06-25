# 🏢 SmartSpace SaaS

**企业级智慧空间与物业管理系统**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ✨ 功能特性

### 🎯 核心功能

- **多租户隔离** - 行级数据隔离，支持多物业公司独立运营
- **RBAC权限控制** - 细粒度角色权限管理
- **车辆调度** - 车辆入场/出场，自动分配车位
- **计费系统** - 按时计费，支持多种支付方式
- **审计日志** - 全操作追踪，高危操作告警

### 🖥️ 三端界面

| 端 | 说明 | 特点 |
|---|---|---|
| 👨‍💼 管理端 | 系统管理后台 | 仪表盘、车位管理、审计日志 |
| 🚗 操作员端 | 车辆出入管理 | 大按钮设计、快速结算 |
| 👤 用户端 | 车主自助服务 | 停车记录、在线充值 |

---

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.10 + FastAPI |
| ORM | SQLAlchemy 2.0 (异步) |
| 数据库 | SQLite (可迁移PostgreSQL) |
| 前端 | HTML5 + TailwindCSS + Alpine.js |
| 测试 | pytest + pytest-asyncio |
| 认证 | JWT + bcrypt |

---

## 📁 项目结构

```
smart-space-saas/
├── backend/
│   ├── app/
│   │   ├── api/           # API路由
│   │   │   ├── auth.py    # 认证接口
│   │   │   ├── vehicles.py # 车辆接口
│   │   │   ├── spaces.py  # 车位接口
│   │   │   ├── billing.py # 计费接口
│   │   │   └── audit.py   # 审计接口
│   │   ├── core/          # 核心模块
│   │   │   ├── config.py  # 配置管理
│   │   │   ├── database.py # 数据库连接
│   │   │   └── security.py # 安全认证
│   │   ├── models/        # 数据模型
│   │   ├── services/      # 业务服务
│   │   └── main.py        # 应用入口
│   ├── tests/             # 测试代码
│   └── requirements.txt   # 依赖清单
├── frontend/
│   ├── index.html         # 入口页面
│   ├── app.html           # 管理端
│   ├── operator.html      # 操作员端
│   └── user.html          # 用户端
├── schema.sql             # 数据库Schema
├── PROJECT_SUMMARY.md     # 项目文档
└── README.md              # 本文件
```

---

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/H1nk5/smart-space-saas.git
cd smart-space-saas
```

### 2. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 3. 初始化数据库

```bash
python -c "
import sqlite3
conn = sqlite3.connect('smart_space.db')
with open('../schema.sql', 'r') as f:
    conn.executescript(f.read())
conn.close()
print('Database initialized!')
"
```

### 4. 启动后端

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### 5. 打开前端

直接在浏览器中打开 `frontend/index.html`

---

## 📡 API文档

启动后端后访问：

- **Swagger UI:** http://localhost:8080/docs
- **ReDoc:** http://localhost:8080/redoc

### 主要接口

| 模块 | 接口 | 说明 |
|------|------|------|
| 认证 | POST /api/v1/auth/login | 用户登录 |
| 车辆 | POST /api/v1/vehicles/entry | 车辆入场 |
| 车辆 | POST /api/v1/vehicles/exit | 车辆出场 |
| 车位 | GET /api/v1/spaces/ | 获取车位列表 |
| 计费 | POST /api/v1/billing/payment | 充值 |
| 审计 | GET /api/v1/audit/ | 审计日志 |

---

## 🧪 运行测试

```bash
cd backend
python -m pytest tests/ -v
```

**测试覆盖：**
- ✅ 越权请求测试（7个）
- ✅ 并发计费测试（4个）
- ✅ 车辆调度边界值测试（7个）

---

## 🔐 测试账号

| 端 | 租户 | 用户名 | 密码 |
|---|------|--------|------|
| 管理端 | TEST | admin | admin123 |
| 操作员端 | TEST | admin | admin123 |
| 用户端 | TEST | admin | admin123 |

---

## 🗄️ 数据库设计

### 核心表

| 表名 | 说明 |
|------|------|
| tenants | 租户表 |
| users | 用户表 |
| roles / permissions | 角色权限表 |
| parking_zones / parking_spaces | 车位管理 |
| vehicles / vehicle_logs | 车辆调度 |
| billing_accounts / billing_transactions | 计费系统 |
| audit_logs | 审计日志 |

### E-R关系

```
tenants ─┬─ users ─── user_roles ─── roles ─── role_permissions ─── permissions
         ├─ parking_zones ─── parking_spaces
         ├─ vehicles ─── vehicle_logs
         ├─ billing_accounts ─── billing_transactions
         └─ audit_logs
```

---

## 🔒 安全特性

- ✅ JWT Token认证
- ✅ bcrypt密码哈希
- ✅ SQL参数化查询（防注入）
- ✅ 多租户行级隔离
- ✅ RBAC权限控制
- ✅ 操作审计日志
- ✅ 幂等性校验（防重复提交）
- ✅ 乐观锁（防并发冲突）

---

## 📊 代码统计

| 类型 | 文件数 | 代码行数 |
|------|--------|----------|
| 后端API | 6 | 1,251 |
| 数据模型 | 8 | 401 |
| 业务服务 | 3 | 1,026 |
| 测试代码 | 4 | 790 |
| 前端页面 | 4 | 800+ |
| **总计** | **38** | **5,693** |

---

## 📝 开发说明

### 添加新的API

1. 在 `app/models/` 创建数据模型
2. 在 `app/services/` 实现业务逻辑
3. 在 `app/api/` 定义路由
4. 在 `tests/` 编写测试

### 数据库迁移

当前使用SQLite，生产环境建议迁移至PostgreSQL：

1. 修改 `config.py` 中的 `DATABASE_URL`
2. 安装 `asyncpg` 驱动
3. 运行 `alembic` 迁移

---

## 📄 License

MIT License

---

## 🤝 贡献

欢迎提交Issue和Pull Request！

---

## 📧 联系

如有问题，请提交Issue或联系项目维护者。

---

**⭐ 如果这个项目对你有帮助，请给个Star！**
