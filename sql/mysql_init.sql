-- AI Love Agent MySQL 初始化脚本
-- 作用：
-- 1. 初始化主业务库 ai_love
-- 2. 保存账号、会话、消息、风控、异步投递等事务型数据
-- 3. 适用于 MySQL 8.0+
-- 4. 库和账号由 docker-compose 的 mysql 服务统一创建
--
-- 业务分层说明：
-- 1. 用户域：users / auth_accounts / auth_refresh_tokens
-- 2. 对话域：agent_profiles / conversation_sessions / conversation_messages
-- 3. 风控域：safety_events
-- 4. 长期记忆治理域：user_memory_settings / audit_events / memory_event_outbox
--
-- 关键关联关系：
-- 1. users 是用户根表，登录账号、刷新令牌、会话、风控事件都围绕它展开
-- 2. conversation_sessions 归属某个 user，可选绑定 agent_profiles
-- 3. conversation_messages 归属某个 conversation_sessions，删除会话时消息级联删除
-- 4. memory_event_outbox 是长期记忆异步事件补投表，不直接依赖外键，便于失败重试
-- 5. user_memory_settings 控制长期记忆授权，默认关闭，不影响普通聊天记录

USE ai_love;

-- =========================================================
-- 第一部分：用户与认证
-- users：用户主表，保存用户业务身份与基础画像
-- auth_accounts：登录账号表，保存用户名和密码哈希
-- auth_refresh_tokens：刷新令牌表，支持多端登录、退出登录、令牌轮换
-- =========================================================

DROP TABLE IF EXISTS auth_refresh_tokens;
DROP TABLE IF EXISTS auth_accounts;
DROP TABLE IF EXISTS conversation_messages;
DROP TABLE IF EXISTS safety_events;
DROP TABLE IF EXISTS conversation_sessions;
DROP TABLE IF EXISTS agent_profiles;
DROP TABLE IF EXISTS memory_event_outbox;
DROP TABLE IF EXISTS audit_events;
DROP TABLE IF EXISTS knowledge_jobs;
DROP TABLE IF EXISTS knowledge_documents;
DROP TABLE IF EXISTS user_roles;
DROP TABLE IF EXISTS role_permissions;
DROP TABLE IF EXISTS roles;
DROP TABLE IF EXISTS permissions;
DROP TABLE IF EXISTS user_memory_settings;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS tenants;

CREATE TABLE tenants (
  id VARCHAR(36) NOT NULL PRIMARY KEY,
  name VARCHAR(64) NOT NULL,
  code VARCHAR(64) NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'active',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_tenants_code (code),
  KEY idx_tenants_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='企业租户表';

INSERT INTO tenants (id, name, code, status)
VALUES ('default', 'Default Tenant', 'default', 'active');

-- 用户主表：一条记录代表一个业务用户，是多数业务表的外键起点
CREATE TABLE users (
  id CHAR(36) NOT NULL PRIMARY KEY COMMENT '用户主键 UUID',
  tenant_id VARCHAR(36) NOT NULL DEFAULT 'default' COMMENT '所属租户',
  external_user_id VARCHAR(64) NOT NULL COMMENT '外部用户标识，用于对接前端或第三方账号',
  nickname VARCHAR(64) NOT NULL DEFAULT '' COMMENT '用户昵称',
  avatar_url VARCHAR(512) NOT NULL DEFAULT '' COMMENT '用户头像地址',
  status VARCHAR(16) NOT NULL DEFAULT 'active' COMMENT '用户状态：active/disabled',
  profile_summary JSON NOT NULL DEFAULT (JSON_OBJECT()) COMMENT '用户基础画像摘要 JSON',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  last_active_at DATETIME NULL COMMENT '最近活跃时间',
  UNIQUE KEY uk_users_external_user_id (external_user_id),
  KEY idx_users_tenant_id (tenant_id),
  KEY idx_users_status (status),
  CONSTRAINT fk_users_tenant_id
    FOREIGN KEY (tenant_id) REFERENCES tenants (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户主表：保存账号、昵称、头像和基础画像';

-- 用户长期记忆设置表：没有记录时也按关闭处理，避免默认收集长期记忆
CREATE TABLE user_memory_settings (
  id CHAR(36) NOT NULL PRIMARY KEY COMMENT '设置记录主键 UUID',
  user_id CHAR(36) NOT NULL COMMENT '关联用户 ID，每个用户最多一条设置',
  memory_enabled BOOLEAN NOT NULL DEFAULT FALSE COMMENT '是否开启长期记忆，默认关闭',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  UNIQUE KEY uk_user_memory_settings_user_id (user_id),
  CONSTRAINT fk_user_memory_settings_user_id
    FOREIGN KEY (user_id) REFERENCES users (id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户长期记忆设置表：控制长期记忆授权开关';

-- 登录账号表：把“登录凭证”与“用户资料”拆开，便于后续扩展多种登录方式
CREATE TABLE auth_accounts (
  id CHAR(36) NOT NULL PRIMARY KEY COMMENT '登录账号主键 UUID',
  user_id CHAR(36) NOT NULL COMMENT '关联用户 ID',
  login_name VARCHAR(128) NOT NULL COMMENT '登录名',
  password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希值',
  status VARCHAR(16) NOT NULL DEFAULT 'active' COMMENT '账号状态：active/disabled 等',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  UNIQUE KEY uk_auth_accounts_login_name (login_name),
  KEY idx_auth_accounts_user_id (user_id),
  KEY idx_auth_accounts_status (status),
  CONSTRAINT fk_auth_accounts_user_id
    FOREIGN KEY (user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='登录账号表：保存账号和密码哈希';

-- 刷新令牌表：不直接存明文 token，只存哈希，便于安全校验与失效控制
CREATE TABLE auth_refresh_tokens (
  id CHAR(36) NOT NULL PRIMARY KEY COMMENT '刷新令牌主键 UUID',
  user_id CHAR(36) NOT NULL COMMENT '关联用户 ID',
  token_hash VARCHAR(128) NOT NULL COMMENT '刷新令牌哈希值',
  user_agent VARCHAR(255) NOT NULL DEFAULT '' COMMENT '签发令牌时的客户端 User-Agent',
  expires_at DATETIME NOT NULL COMMENT '令牌过期时间',
  revoked BOOLEAN NOT NULL DEFAULT FALSE COMMENT '是否已撤销',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  UNIQUE KEY uk_auth_refresh_tokens_token_hash (token_hash),
  KEY idx_auth_refresh_tokens_user_id (user_id),
  KEY idx_auth_refresh_tokens_user_id_revoked (user_id, revoked),
  CONSTRAINT fk_auth_refresh_tokens_user_id
    FOREIGN KEY (user_id) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='刷新令牌表：保存 refresh token 哈希';

CREATE TABLE permissions (
  id CHAR(36) NOT NULL PRIMARY KEY,
  code VARCHAR(64) NOT NULL,
  name VARCHAR(64) NOT NULL,
  description VARCHAR(255) NOT NULL DEFAULT '',
  module VARCHAR(32) NOT NULL DEFAULT '',
  UNIQUE KEY uk_permissions_code (code),
  KEY idx_permissions_module (module)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='权限点表';

CREATE TABLE roles (
  id CHAR(36) NOT NULL PRIMARY KEY,
  tenant_id VARCHAR(36) NOT NULL,
  code VARCHAR(32) NOT NULL,
  name VARCHAR(64) NOT NULL,
  description VARCHAR(255) NOT NULL DEFAULT '',
  is_system BOOLEAN NOT NULL DEFAULT FALSE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_roles_tenant_code (tenant_id, code),
  KEY idx_roles_tenant_id (tenant_id),
  CONSTRAINT fk_roles_tenant_id
    FOREIGN KEY (tenant_id) REFERENCES tenants (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色表';

CREATE TABLE role_permissions (
  id CHAR(36) NOT NULL PRIMARY KEY,
  role_id CHAR(36) NOT NULL,
  permission_id CHAR(36) NOT NULL,
  UNIQUE KEY uk_role_permissions_role_permission (role_id, permission_id),
  KEY idx_role_permissions_role_id (role_id),
  KEY idx_role_permissions_permission_id (permission_id),
  CONSTRAINT fk_role_permissions_role_id
    FOREIGN KEY (role_id) REFERENCES roles (id)
    ON DELETE CASCADE,
  CONSTRAINT fk_role_permissions_permission_id
    FOREIGN KEY (permission_id) REFERENCES permissions (id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色权限关系表';

CREATE TABLE user_roles (
  id CHAR(36) NOT NULL PRIMARY KEY,
  user_id CHAR(36) NOT NULL,
  role_id CHAR(36) NOT NULL,
  UNIQUE KEY uk_user_roles_user_role (user_id, role_id),
  KEY idx_user_roles_user_id (user_id),
  KEY idx_user_roles_role_id (role_id),
  CONSTRAINT fk_user_roles_user_id
    FOREIGN KEY (user_id) REFERENCES users (id)
    ON DELETE CASCADE,
  CONSTRAINT fk_user_roles_role_id
    FOREIGN KEY (role_id) REFERENCES roles (id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户角色关系表';

INSERT INTO permissions (id, code, name, description, module) VALUES
('perm-admin-access', 'admin:access', '进入后台', '允许访问管理员后台', 'admin'),
('perm-user-read', 'user:read', '查看用户', '查看用户列表与详情', 'user'),
('perm-user-write', 'user:write', '编辑用户', '编辑用户基础状态和资料', 'user'),
('perm-user-disable', 'user:disable', '禁用用户', '禁用或启用用户账号', 'user'),
('perm-role-read', 'role:read', '查看角色', '查看角色和权限', 'role'),
('perm-role-write', 'role:write', '编辑角色', '创建和编辑角色权限', 'role'),
('perm-knowledge-read', 'knowledge:read', '查看知识库', '查看和检索知识库', 'knowledge'),
('perm-knowledge-write', 'knowledge:write', '写入知识库', '上传文件和录入文本知识', 'knowledge'),
('perm-knowledge-delete', 'knowledge:delete', '删除知识', '删除知识文档和索引', 'knowledge'),
('perm-knowledge-reindex', 'knowledge:reindex', '重建知识', '触发单文档或全量重建', 'knowledge'),
('perm-knowledge-job-read', 'knowledge:job:read', '查看知识任务', '查看知识索引任务', 'knowledge'),
('perm-knowledge-job-retry', 'knowledge:job:retry', '重试知识任务', '重试或取消知识索引任务', 'knowledge'),
('perm-audit-read', 'audit:read', '查看审计', '查看后台操作审计日志', 'audit'),
('perm-safety-read', 'safety:read', '查看安全事件', '查看风控与安全事件', 'safety'),
('perm-system-read', 'system:read', '查看系统状态', '查看系统健康与配置摘要', 'system'),
('perm-system-manage', 'system:manage', '管理系统', '执行系统级管理动作', 'system');

INSERT INTO roles (id, tenant_id, code, name, description, is_system) VALUES
('role-default-user', 'default', 'user', '普通用户', '普通聊天用户，不可进入后台', TRUE),
('role-default-admin', 'default', 'admin', '管理员', '拥有后台全部权限', TRUE);

INSERT INTO role_permissions (id, role_id, permission_id)
SELECT CONCAT('rp', LEFT(MD5(code), 30)), 'role-default-admin', id FROM permissions;

-- =========================================================
-- 第二部分：智能体与会话
-- agent_profiles：智能体配置表，定义不同模式的人设和 Prompt 版本
-- conversation_sessions：会话表，承载一次完整聊天线程
-- conversation_messages：消息表，保存会话中的逐条消息
-- =========================================================

-- 智能体配置表：保存不同模式的人设、提示词版本和可扩展参数
CREATE TABLE agent_profiles (
  id CHAR(36) NOT NULL PRIMARY KEY COMMENT '智能体配置主键 UUID',
  code VARCHAR(32) NOT NULL COMMENT '智能体配置编码',
  display_name VARCHAR(64) NOT NULL COMMENT '智能体展示名称',
  mode VARCHAR(32) NOT NULL COMMENT '智能体工作模式',
  description VARCHAR(255) NOT NULL DEFAULT '' COMMENT '智能体配置说明',
  system_prompt_version VARCHAR(32) NOT NULL DEFAULT 'v1' COMMENT '系统提示词版本号',
  settings_json JSON NOT NULL DEFAULT (JSON_OBJECT()) COMMENT '智能体扩展配置 JSON',
  is_enabled BOOLEAN NOT NULL DEFAULT TRUE COMMENT '是否启用',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  UNIQUE KEY uk_agent_profiles_code (code),
  KEY idx_agent_profiles_mode (mode)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='智能体配置表：保存人设与 Prompt 版本';

-- 会话表：一条记录代表一次聊天线程，用来挂标题、滚动摘要、风险级别和上下文元信息
CREATE TABLE conversation_sessions (
  id CHAR(36) NOT NULL PRIMARY KEY COMMENT '会话主键 UUID',
  user_id CHAR(36) NOT NULL COMMENT '所属用户 ID',
  agent_profile_id CHAR(36) NULL COMMENT '使用的智能体配置 ID',
  title VARCHAR(128) NOT NULL DEFAULT '' COMMENT '会话标题',
  mode VARCHAR(32) NOT NULL COMMENT '会话模式',
  summary TEXT NOT NULL COMMENT '会话滚动摘要，覆盖最近窗口之外的上下文',
  memory_digest JSON NOT NULL DEFAULT (JSON_OBJECT()) COMMENT '上下文元信息 JSON，含摘要覆盖位置和最近检索摘要',
  message_count BIGINT NOT NULL DEFAULT 0 COMMENT '会话消息数量',
  risk_level VARCHAR(16) NOT NULL DEFAULT 'low' COMMENT '会话风险等级',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  KEY idx_conversation_sessions_user_id (user_id),
  KEY idx_conversation_sessions_mode (mode),
  CONSTRAINT fk_conversation_sessions_user_id
    FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT fk_conversation_sessions_agent_profile_id
    FOREIGN KEY (agent_profile_id) REFERENCES agent_profiles (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会话表：保存会话级别元信息';

-- 消息表：保存 user / assistant / system 的逐条消息，同时记录 trace 和安全标签
CREATE TABLE conversation_messages (
  id CHAR(36) NOT NULL PRIMARY KEY COMMENT '消息主键 UUID',
  conversation_id CHAR(36) NOT NULL COMMENT '所属会话 ID',
  role VARCHAR(16) NOT NULL COMMENT '消息角色：user/assistant/system 等',
  content TEXT NOT NULL COMMENT '消息正文',
  trace_json JSON NOT NULL DEFAULT (JSON_OBJECT()) COMMENT '消息链路追踪信息 JSON',
  safety_tags JSON NOT NULL DEFAULT (JSON_OBJECT()) COMMENT '安全标签 JSON',
  token_count BIGINT NOT NULL DEFAULT 0 COMMENT '消息 token 数量',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  KEY idx_conversation_messages_conversation_id (conversation_id),
  KEY idx_conversation_messages_role (role),
  CONSTRAINT fk_conversation_messages_conversation_id
    FOREIGN KEY (conversation_id) REFERENCES conversation_sessions (id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='消息表：保存逐条消息、trace 与安全标签';

-- =========================================================
-- 第三部分：风控审计
-- safety_events：保存风控判定结果，便于审计、回溯和运营分析
-- =========================================================

-- 风控事件表：保存输入输出风险命中和处理动作，可按用户、会话、场景检索
CREATE TABLE safety_events (
  id CHAR(36) NOT NULL PRIMARY KEY COMMENT '风控事件主键 UUID',
  user_id CHAR(36) NOT NULL COMMENT '关联用户 ID',
  conversation_id CHAR(36) NULL COMMENT '关联会话 ID',
  scene VARCHAR(32) NOT NULL COMMENT '风控场景',
  risk_type VARCHAR(64) NOT NULL COMMENT '风险类型',
  risk_level VARCHAR(16) NOT NULL COMMENT '风险等级',
  input_snapshot TEXT NOT NULL COMMENT '输入内容快照',
  output_snapshot TEXT NOT NULL COMMENT '输出内容快照',
  action VARCHAR(32) NOT NULL DEFAULT 'pass' COMMENT '风控处理动作',
  detail_json JSON NOT NULL DEFAULT (JSON_OBJECT()) COMMENT '风控详情 JSON',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  KEY idx_safety_events_user_id (user_id),
  KEY idx_safety_events_conversation_id (conversation_id),
  KEY idx_safety_events_scene (scene),
  KEY idx_safety_events_risk_type (risk_type),
  KEY idx_safety_events_risk_level (risk_level),
  CONSTRAINT fk_safety_events_user_id
    FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT fk_safety_events_conversation_id
    FOREIGN KEY (conversation_id) REFERENCES conversation_sessions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='风控事件表：保存风险命中和处理动作';

CREATE TABLE knowledge_documents (
  id CHAR(36) NOT NULL PRIMARY KEY,
  tenant_id VARCHAR(36) NOT NULL,
  doc_id VARCHAR(64) NOT NULL,
  title VARCHAR(255) NOT NULL DEFAULT '',
  filename VARCHAR(255) NOT NULL DEFAULT '',
  category VARCHAR(64) NOT NULL DEFAULT 'relationship_knowledge',
  source VARCHAR(255) NOT NULL DEFAULT '',
  object_name VARCHAR(512) NOT NULL DEFAULT '',
  content_text TEXT NOT NULL,
  status VARCHAR(24) NOT NULL DEFAULT 'pending',
  chunk_count BIGINT NOT NULL DEFAULT 0,
  created_by CHAR(36) NOT NULL,
  last_job_id CHAR(36) NOT NULL DEFAULT '',
  error_message TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_knowledge_documents_tenant_doc (tenant_id, doc_id),
  KEY idx_knowledge_documents_tenant_status (tenant_id, status),
  KEY idx_knowledge_documents_category (category),
  CONSTRAINT fk_knowledge_documents_tenant_id
    FOREIGN KEY (tenant_id) REFERENCES tenants (id),
  CONSTRAINT fk_knowledge_documents_created_by
    FOREIGN KEY (created_by) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库文档元数据表';

CREATE TABLE knowledge_jobs (
  id CHAR(36) NOT NULL PRIMARY KEY,
  tenant_id VARCHAR(36) NOT NULL,
  job_type VARCHAR(32) NOT NULL,
  status VARCHAR(24) NOT NULL DEFAULT 'pending',
  document_id CHAR(36) NULL,
  filename VARCHAR(255) NOT NULL DEFAULT '',
  progress BIGINT NOT NULL DEFAULT 0,
  result_json JSON NOT NULL DEFAULT (JSON_OBJECT()),
  error_message TEXT NOT NULL,
  created_by CHAR(36) NOT NULL,
  started_at DATETIME NULL,
  finished_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_knowledge_jobs_tenant_status (tenant_id, status),
  KEY idx_knowledge_jobs_document (document_id),
  KEY idx_knowledge_jobs_created_by (created_by),
  CONSTRAINT fk_knowledge_jobs_tenant_id
    FOREIGN KEY (tenant_id) REFERENCES tenants (id),
  CONSTRAINT fk_knowledge_jobs_document_id
    FOREIGN KEY (document_id) REFERENCES knowledge_documents (id),
  CONSTRAINT fk_knowledge_jobs_created_by
    FOREIGN KEY (created_by) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库异步任务表';

CREATE TABLE audit_events (
  id CHAR(36) NOT NULL PRIMARY KEY,
  tenant_id VARCHAR(36) NOT NULL,
  actor_user_id CHAR(36) NOT NULL DEFAULT '',
  action VARCHAR(64) NOT NULL,
  resource_type VARCHAR(64) NOT NULL,
  resource_id VARCHAR(96) NOT NULL DEFAULT '',
  ip VARCHAR(64) NOT NULL DEFAULT '',
  user_agent VARCHAR(255) NOT NULL DEFAULT '',
  detail_json JSON NOT NULL DEFAULT (JSON_OBJECT()),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_audit_events_tenant_id (tenant_id),
  KEY idx_audit_events_actor_user_id (actor_user_id),
  KEY idx_audit_events_action (action),
  KEY idx_audit_events_resource_type (resource_type),
  CONSTRAINT fk_audit_events_tenant_id
    FOREIGN KEY (tenant_id) REFERENCES tenants (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='管理员后台审计日志表';

-- =========================================================
-- 第四部分：异步补投
-- memory_event_outbox：长期记忆事件 Outbox，保证消息系统短暂异常时业务不丢数据
-- =========================================================

-- 长期记忆 RocketMQ Outbox：RocketMQ 临时不可用时保存待补投事件
-- 设计上不加外键，避免异步补偿链路被主事务删除/回滚影响
CREATE TABLE memory_event_outbox (
  id CHAR(36) NOT NULL PRIMARY KEY COMMENT 'Outbox 记录主键 UUID',
  event_id CHAR(36) NOT NULL COMMENT '业务事件 ID',
  task_id VARCHAR(96) NOT NULL COMMENT '幂等任务 ID',
  user_id VARCHAR(64) NOT NULL COMMENT '关联用户标识',
  session_id CHAR(36) NOT NULL DEFAULT '' COMMENT '关联会话 ID',
  payload JSON NOT NULL DEFAULT (JSON_OBJECT()) COMMENT '待投递事件载荷 JSON',
  status VARCHAR(24) NOT NULL DEFAULT 'pending' COMMENT '投递状态：pending/sent/failed 等',
  retry_count BIGINT NOT NULL DEFAULT 0 COMMENT '重试次数',
  next_retry_at DATETIME NULL COMMENT '下次重试时间',
  last_error TEXT NOT NULL COMMENT '最近一次投递错误信息',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  UNIQUE KEY uk_memory_event_outbox_event_id (event_id),
  KEY idx_memory_event_outbox_task_id (task_id),
  KEY idx_memory_event_outbox_user_id (user_id),
  KEY idx_memory_event_outbox_status_next_retry (status, next_retry_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='长期记忆 RocketMQ Outbox 表：保存待补投事件';
