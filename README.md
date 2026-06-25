<div align="center">

# 🏢 SmartSpace SaaS

**企业级智慧空间与物业管理系统**

多租户隔离 · 车辆调度 · 智能计费 · 审计追踪

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-D71F00?style=flat-square&logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![SQLite](https://img.shields.io/badge/SQLite-3.0+-003B57?style=flat-square&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3.0+-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

</div>

---

## 📋 系统概述

SmartSpace SaaS 是一套面向物业管理企业的多租户SaaS平台，提供车位管理、车辆调度、计费结算、审计追踪等核心能力。系统采用前后端分离架构，支持管理员、操作员、车主三种角色独立访问。

| 维度 | 说明 |
|------|------|
| 定位 | 物业停车场管理SaaS平台 |
| 架构 | 前后端分离，RESTful API |
| 部署 | 单机部署，可扩展至分布式 |
| 租户 | 多租户隔离，支持多物业公司 |
| 角色 | 管理员 / 操作员 / 车主 |

---

## ✨ 功能特性

### 核心功能模块

| 模块 | 功能 | 说明 |
|------|------|------|
| 🏢 多租户管理 | 租户隔离 | 行级数据隔离，支持多物业公司独立运营 |
| 👤 用户权限 | RBAC控制 | 角色权限管理，细粒度接口鉴权 |
| 🚗 车辆调度 | 入场/出场 | 自动分配车位，实时状态更新 |
| 🅿️ 车位管理 | 状态监控 | 车位热力图，占用率统计 |
| 💰 计费系统 | 按时计费 | 多支付方式，账单流水 |
| 📝 审计日志 | 操作追踪 | 高危操作告警，不可篡改 |
| 🔒 安全防护 | 多层防御 | 幂等校验，乐观锁，防SQL注入 |

### 三端界面

| 端 | 文件 | 目标用户 | 核心功能 |
|---|------|----------|----------|
| 👨‍💼 管理端 | `app.html` | 物业管理员 | 仪表盘、车位管理、审计日志 |
| 🚗 操作端 | `operator.html` | 岗亭操作员 | 车辆出入、快速结算 |
| 👤 用户端 | `user.html` | 车主 | 停车记录、在线充值 |

---

## 🛠️ 技术栈

| 层级 | 技术 | 职责 |
|------|------|------|
| 后端框架 | FastAPI | 异步高性能API |
| ORM | SQLAlchemy 2.0 | 异步数据库操作 |
| 数据库 | SQLite | 轻量级存储（可迁移PostgreSQL） |
| 认证 | JWT + bcrypt | Token认证，密码哈希 |
| 前端 | TailwindCSS + Alpine.js | 响应式UI，轻量级交互 |
| 测试 | pytest | 异步测试框架 |

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

### 3. 启动服务

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### 4. 访问系统

- **入口页面：** 打开 `frontend/index.html`
- **API文档：** http://localhost:8080/docs

### 测试账号

| 租户编码 | 用户名 | 密码 |
|----------|--------|------|
| TEST | admin | admin123 |

---

## 📁 项目结构

```
smart-space-saas/
├── backend/                    # 后端服务
│   ├── app/
│   │   ├── api/                # API路由层
│   │   │   ├── auth.py         # 认证接口
│   │   │   ├── vehicles.py     # 车辆接口
│   │   │   ├── spaces.py       # 车位接口
│   │   │   ├── billing.py      # 计费接口
│   │   │   └── audit.py        # 审计接口
│   │   ├── core/               # 核心模块
│   │   │   ├── config.py       # 配置管理
│   │   │   ├── database.py     # 数据库连接
│   │   │   └── security.py     # 安全认证
│   │   ├── models/             # 数据模型
│   │   ├── services/           # 业务服务
│   │   └── main.py             # 应用入口
│   ├── tests/                  # 测试代码
│   └── requirements.txt        # 依赖清单
├── frontend/                   # 前端页面
│   ├── index.html              # 入口页面
│   ├── app.html                # 管理端
│   ├── operator.html           # 操作员端
│   └── user.html               # 用户端
├── schema.sql                  # 数据库Schema
└── README.md                   # 项目文档
```

---

## 📡 接口文档

### 认证接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/login` | 用户登录 |
| GET | `/api/v1/auth/me` | 获取当前用户 |

### 车辆接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/vehicles/entry` | 车辆入场 |
| POST | `/api/v1/vehicles/exit` | 车辆出场 |
| POST | `/api/v1/vehicles/force-exit` | 强制放行 |
| GET | `/api/v1/vehicles/status` | 停车场状态 |
| GET | `/api/v1/vehicles/logs` | 车辆日志 |

### 车位接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/spaces/` | 车位列表 |
| POST | `/api/v1/spaces/` | 创建车位 |
| PUT | `/api/v1/spaces/{id}` | 更新车位 |

### 计费接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/billing/payment` | 充值 |
| POST | `/api/v1/billing/refund` | 退款 |
| GET | `/api/v1/billing/transactions` | 交易记录 |

### 审计接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/audit/` | 审计日志 |
| GET | `/api/v1/audit/high-risk` | 高危操作 |

---

## 🗄️ 数据库设计

### 核心表结构

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| tenants | 租户表 | id, code, status |
| users | 用户表 | id, tenant_id, username |
| roles / permissions | 权限表 | RBAC模型 |
| parking_spaces | 车位表 | id, status, current_vehicle_id |
| vehicles | 车辆表 | id, plate_number |
| vehicle_logs | 调度日志 | action, entry_time, exit_time |
| billing_transactions | 交易流水 | amount, idempotency_key |
| audit_logs | 审计日志 | action, severity |

### E-R关系

```
tenants ─┬─ users ─── roles ─── permissions
         ├─ parking_spaces
         ├─ vehicles ─── vehicle_logs
         ├─ billing_transactions
         └─ audit_logs
```

---

## 🔒 安全设计

| 机制 | 说明 |
|------|------|
| JWT认证 | Token过期时间8小时 |
| 密码加密 | bcrypt哈希存储 |
| SQL防护 | 全参数化查询 |
| 租户隔离 | 行级数据隔离 |
| 幂等校验 | 防重复提交 |
| 乐观锁 | 防并发冲突 |
| 审计追踪 | 全操作记录 |

---

## 🧪 测试

```bash
cd backend
python -m pytest tests/ -v
```

### 测试覆盖

| 类型 | 数量 | 说明 |
|------|------|------|
| 越权测试 | 7 | 多租户隔离验证 |
| 并发测试 | 4 | 幂等性、事务隔离 |
| 边界测试 | 7 | 满车位、强制放行 |
| **总计** | **18** | **100%通过** |

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

## 📄 开源许可

MIT © [H1nk5](https://github.com/H1nk5)

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给个Star！**

</div>
