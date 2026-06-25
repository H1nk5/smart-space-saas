-- ============================================================
-- 企业级智慧空间与物业管理SaaS系统 - 多租户数据库设计
-- 数据库: SQLite (可平滑迁移至 PostgreSQL)
-- 日期: 2026-06-25
-- ============================================================

-- 启用外键约束 (SQLite特有)
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ============================================================
-- 1. 租户表 - 多租户隔离的核心
-- ============================================================
CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,           -- 租户唯一编码
    contact_name TEXT,
    contact_phone TEXT,
    contact_email TEXT,
    address TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'cancelled')),
    max_spaces INTEGER NOT NULL DEFAULT 100,
    max_users INTEGER NOT NULL DEFAULT 50,
    config_json TEXT,                     -- 租户自定义配置(JSON)
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at TEXT                       -- 软删除
);

-- ============================================================
-- 2. 用户表 - 支持多租户用户体系
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    tenant_id TEXT NOT NULL,
    username TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    password_hash TEXT NOT NULL,
    real_name TEXT,
    avatar_url TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'locked')),
    last_login_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at TEXT,

    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    UNIQUE(tenant_id, username)
);

-- ============================================================
-- 3. 角色权限表 - RBAC权限模型
-- ============================================================
CREATE TABLE IF NOT EXISTS roles (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,                   -- 角色名称: admin, manager, operator, viewer
    description TEXT,
    is_system BOOLEAN NOT NULL DEFAULT 0, -- 系统内置角色不可删除
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    UNIQUE(tenant_id, name)
);

CREATE TABLE IF NOT EXISTS permissions (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    code TEXT NOT NULL UNIQUE,            -- 权限编码: space:read, billing:write, etc.
    name TEXT NOT NULL,
    module TEXT NOT NULL,                 -- 所属模块: space, billing, vehicle, audit
    description TEXT
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id TEXT NOT NULL,
    permission_id TEXT NOT NULL,
    PRIMARY KEY (role_id, permission_id),
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
    FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id TEXT NOT NULL,
    role_id TEXT NOT NULL,
    assigned_at TEXT NOT NULL DEFAULT (datetime('now')),
    assigned_by TEXT,
    PRIMARY KEY (user_id, role_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
);

-- ============================================================
-- 4. 车位空间表 - 核心资源管理
-- ============================================================
CREATE TABLE IF NOT EXISTS parking_zones (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,                   -- 区域名称: A区, B区, 地下一层
    location TEXT,                        -- 位置描述
    total_spaces INTEGER NOT NULL DEFAULT 0,
    hourly_rate INTEGER NOT NULL DEFAULT 500,  -- 单位:分/小时
    daily_rate INTEGER NOT NULL DEFAULT 3000,  -- 单位:分/天
    monthly_rate INTEGER NOT NULL DEFAULT 30000, -- 单位:分/月
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'maintenance', 'closed')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

CREATE TABLE IF NOT EXISTS parking_spaces (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    tenant_id TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    space_number TEXT NOT NULL,           -- 车位编号: A-001, B-023
    space_type TEXT NOT NULL DEFAULT 'standard' CHECK (space_type IN ('standard', 'compact', 'disabled', 'ev_charging', 'vip')),
    status TEXT NOT NULL DEFAULT 'available' CHECK (status IN ('available', 'occupied', 'reserved', 'maintenance')),
    current_vehicle_id TEXT,              -- 当前停放车辆ID
    occupied_since TEXT,                  -- 占用开始时间
    reserved_by TEXT,                     -- 预留人用户ID
    reserved_until TEXT,                  -- 预留截止时间
    hourly_rate INTEGER,                  -- 覆盖区域默认费率(分)
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (zone_id) REFERENCES parking_zones(id),
    UNIQUE(tenant_id, space_number)
);

-- ============================================================
-- 5. 车辆与调度日志 - 高并发状态管理
-- ============================================================
CREATE TABLE IF NOT EXISTS vehicles (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    tenant_id TEXT NOT NULL,
    plate_number TEXT NOT NULL,           -- 车牌号
    vehicle_type TEXT NOT NULL DEFAULT 'sedan' CHECK (vehicle_type IN ('sedan', 'suv', 'truck', 'motorcycle', 'ev')),
    owner_name TEXT,
    owner_phone TEXT,
    owner_user_id TEXT,                   -- 关联用户(可选)
    is_vip BOOLEAN NOT NULL DEFAULT 0,
    vip_expire_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (owner_user_id) REFERENCES users(id),
    UNIQUE(tenant_id, plate_number)
);

CREATE TABLE IF NOT EXISTS vehicle_logs (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    tenant_id TEXT NOT NULL,
    vehicle_id TEXT NOT NULL,
    space_id TEXT,                        -- 关联车位(出场时可能为空)
    action TEXT NOT NULL CHECK (action IN ('entry', 'exit', 'reserve', 'cancel_reserve')),
    plate_number TEXT NOT NULL,
    entry_time TEXT,
    exit_time TEXT,
    duration_minutes INTEGER,
    fee_amount INTEGER DEFAULT 0,         -- 费用(分)
    fee_status TEXT NOT NULL DEFAULT 'pending' CHECK (fee_status IN ('pending', 'calculated', 'paid', 'waived', 'disputed')),
    operator_id TEXT,                     -- 操作员用户ID
    gate_id TEXT,                         -- 闸机/入口ID
    snapshot_url TEXT,                    -- 车牌识别截图
    remark TEXT,
    idempotency_key TEXT UNIQUE,          -- 幂等键(防重复)
    version INTEGER NOT NULL DEFAULT 1,   -- 乐观锁版本号
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id),
    FOREIGN KEY (space_id) REFERENCES parking_spaces(id),
    FOREIGN KEY (operator_id) REFERENCES users(id)
);

-- ============================================================
-- 6. 账单流水表 - 计费对账隔离
-- ============================================================
CREATE TABLE IF NOT EXISTS billing_accounts (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    tenant_id TEXT NOT NULL,
    user_id TEXT,                         -- 关联用户(可选)
    vehicle_id TEXT,                      -- 关联车辆(可选)
    account_type TEXT NOT NULL DEFAULT 'individual' CHECK (account_type IN ('individual', 'corporate', 'monthly_subscriber')),
    balance INTEGER NOT NULL DEFAULT 0,   -- 余额(分)
    credit_limit INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'frozen', 'closed')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
);

CREATE TABLE IF NOT EXISTS billing_transactions (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    tenant_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    vehicle_log_id TEXT,                  -- 关联车辆日志
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('charge', 'payment', 'refund', 'adjustment', 'subscription')),
    amount INTEGER NOT NULL,              -- 金额(分), 正数收入/负数支出
    balance_after INTEGER NOT NULL,       -- 交易后余额(分)
    description TEXT,
    payment_method TEXT CHECK (payment_method IN ('cash', 'wechat', 'alipay', 'card', 'account_balance', 'free')),
    payment_reference TEXT,               -- 外部支付流水号
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'failed', 'reversed')),
    operator_id TEXT,                     -- 操作员
    idempotency_key TEXT UNIQUE,          -- 幂等键
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT,

    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (account_id) REFERENCES billing_accounts(id),
    FOREIGN KEY (vehicle_log_id) REFERENCES vehicle_logs(id),
    FOREIGN KEY (operator_id) REFERENCES users(id)
);

-- ============================================================
-- 7. 全时段审计日志表 - 不可篡改的操作记录
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    tenant_id TEXT NOT NULL,
    user_id TEXT,                         -- 操作人
    action TEXT NOT NULL,                 -- 操作类型: CREATE, UPDATE, DELETE, LOGIN, LOGOUT, FORCE_EXIT, etc.
    resource_type TEXT NOT NULL,          -- 资源类型: vehicle, space, billing, user, role, etc.
    resource_id TEXT,                     -- 资源ID
    old_value TEXT,                       -- 变更前值(JSON)
    new_value TEXT,                       -- 变更后值(JSON)
    ip_address TEXT,
    user_agent TEXT,
    request_id TEXT,                      -- 请求追踪ID
    severity TEXT NOT NULL DEFAULT 'info' CHECK (severity IN ('debug', 'info', 'warning', 'critical')),
    description TEXT,                     -- 人类可读描述
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ============================================================
-- 8. 系统配置表 - 可扩展的键值存储
-- ============================================================
CREATE TABLE IF NOT EXISTS system_configs (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    tenant_id TEXT,                       -- NULL表示全局配置
    key TEXT NOT NULL,
    value TEXT,
    value_type TEXT NOT NULL DEFAULT 'string' CHECK (value_type IN ('string', 'integer', 'boolean', 'json')),
    description TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),

    UNIQUE(tenant_id, key)
);

-- ============================================================
-- 索引优化 - 高频查询场景
-- ============================================================

-- 用户表索引
CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_phone ON users(tenant_id, phone);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(tenant_id, email);

-- 车位表索引
CREATE INDEX IF NOT EXISTS idx_spaces_tenant ON parking_spaces(tenant_id);
CREATE INDEX IF NOT EXISTS idx_spaces_zone ON parking_spaces(zone_id);
CREATE INDEX IF NOT EXISTS idx_spaces_status ON parking_spaces(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_spaces_vehicle ON parking_spaces(current_vehicle_id);

-- 车辆表索引
CREATE INDEX IF NOT EXISTS idx_vehicles_tenant ON vehicles(tenant_id);
CREATE INDEX IF NOT EXISTS idx_vehicles_plate ON vehicles(tenant_id, plate_number);

-- 车辆日志索引
CREATE INDEX IF NOT EXISTS idx_vehicle_logs_tenant ON vehicle_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_vehicle_logs_vehicle ON vehicle_logs(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_vehicle_logs_entry ON vehicle_logs(tenant_id, entry_time);
CREATE INDEX IF NOT EXISTS idx_vehicle_logs_status ON vehicle_logs(tenant_id, fee_status);
CREATE INDEX IF NOT EXISTS idx_vehicle_logs_idempotency ON vehicle_logs(idempotency_key);

-- 账单流水索引
CREATE INDEX IF NOT EXISTS idx_billing_tenant ON billing_transactions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_billing_account ON billing_transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_billing_created ON billing_transactions(tenant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_billing_idempotency ON billing_transactions(idempotency_key);

-- 审计日志索引
CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(tenant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_severity ON audit_logs(tenant_id, severity);

-- ============================================================
-- 初始数据 - 系统权限配置
-- ============================================================
INSERT OR IGNORE INTO permissions (id, code, name, module) VALUES
    ('perm-001', 'space:read', '查看车位', 'space'),
    ('perm-002', 'space:write', '管理车位', 'space'),
    ('perm-003', 'vehicle:read', '查看车辆', 'vehicle'),
    ('perm-004', 'vehicle:write', '管理车辆', 'vehicle'),
    ('perm-005', 'vehicle:entry', '车辆入场', 'vehicle'),
    ('perm-006', 'vehicle:exit', '车辆出场', 'vehicle'),
    ('perm-007', 'vehicle:force_exit', '强制放行', 'vehicle'),
    ('perm-008', 'billing:read', '查看账单', 'billing'),
    ('perm-009', 'billing:write', '管理账单', 'billing'),
    ('perm-010', 'billing:payment', '收费操作', 'billing'),
    ('perm-011', 'billing:refund', '退款操作', 'billing'),
    ('perm-012', 'user:read', '查看用户', 'user'),
    ('perm-013', 'user:write', '管理用户', 'user'),
    ('perm-014', 'role:read', '查看角色', 'role'),
    ('perm-015', 'role:write', '管理角色', 'role'),
    ('perm-016', 'audit:read', '查看审计日志', 'audit'),
    ('perm-017', 'system:config', '系统配置', 'system');
