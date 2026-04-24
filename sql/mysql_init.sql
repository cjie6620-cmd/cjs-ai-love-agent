-- AI Love Agent MySQL 初始化脚本
-- 作用：
-- 1. 创建业务库与账号
-- 2. 创建核心业务表
-- 3. 适用于 MySQL 8.0+

CREATE DATABASE IF NOT EXISTS ai_love
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'ai_love'@'%' IDENTIFIED WITH mysql_native_password BY 'ai_love';
CREATE USER IF NOT EXISTS 'ai_love'@'localhost' IDENTIFIED WITH mysql_native_password BY 'ai_love';

ALTER USER 'ai_love'@'%' IDENTIFIED WITH mysql_native_password BY 'ai_love';
ALTER USER 'ai_love'@'localhost' IDENTIFIED WITH mysql_native_password BY 'ai_love';

GRANT ALL PRIVILEGES ON ai_love.* TO 'ai_love'@'%';
GRANT ALL PRIVILEGES ON ai_love.* TO 'ai_love'@'localhost';
FLUSH PRIVILEGES;

USE ai_love;

-- 用户主表：保存账号、昵称、头像和基础画像
CREATE TABLE IF NOT EXISTS users (
  id CHAR(36) NOT NULL PRIMARY KEY,
  external_user_id VARCHAR(64) NOT NULL,
  nickname VARCHAR(64) NOT NULL DEFAULT '',
  avatar_url VARCHAR(512) NOT NULL DEFAULT '',
  profile_summary JSON NOT NULL DEFAULT (JSON_OBJECT()),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  last_active_at DATETIME NULL,
  UNIQUE KEY uk_users_external_user_id (external_user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 智能体配置表：保存不同模式的人设与 Prompt 版本
CREATE TABLE IF NOT EXISTS agent_profiles (
  id CHAR(36) NOT NULL PRIMARY KEY,
  code VARCHAR(32) NOT NULL,
  display_name VARCHAR(64) NOT NULL,
  mode VARCHAR(32) NOT NULL,
  description VARCHAR(255) NOT NULL DEFAULT '',
  system_prompt_version VARCHAR(32) NOT NULL DEFAULT 'v1',
  settings_json JSON NOT NULL DEFAULT (JSON_OBJECT()),
  is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_agent_profiles_code (code),
  KEY idx_agent_profiles_mode (mode)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 会话表：保存会话级别元信息
CREATE TABLE IF NOT EXISTS conversation_sessions (
  id CHAR(36) NOT NULL PRIMARY KEY,
  user_id CHAR(36) NOT NULL,
  agent_profile_id CHAR(36) NULL,
  title VARCHAR(128) NOT NULL DEFAULT '',
  mode VARCHAR(32) NOT NULL,
  summary VARCHAR(500) NOT NULL DEFAULT '',
  memory_digest JSON NOT NULL DEFAULT (JSON_OBJECT()),
  message_count BIGINT NOT NULL DEFAULT 0,
  risk_level VARCHAR(16) NOT NULL DEFAULT 'low',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_conversation_sessions_user_id (user_id),
  KEY idx_conversation_sessions_mode (mode),
  CONSTRAINT fk_conversation_sessions_user_id
    FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT fk_conversation_sessions_agent_profile_id
    FOREIGN KEY (agent_profile_id) REFERENCES agent_profiles (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 消息表：保存逐条消息、trace 与安全标签
CREATE TABLE IF NOT EXISTS conversation_messages (
  id CHAR(36) NOT NULL PRIMARY KEY,
  conversation_id CHAR(36) NOT NULL,
  role VARCHAR(16) NOT NULL,
  content TEXT NOT NULL,
  trace_json JSON NOT NULL DEFAULT (JSON_OBJECT()),
  safety_tags JSON NOT NULL DEFAULT (JSON_OBJECT()),
  token_count BIGINT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_conversation_messages_conversation_id (conversation_id),
  KEY idx_conversation_messages_role (role),
  CONSTRAINT fk_conversation_messages_conversation_id
    FOREIGN KEY (conversation_id) REFERENCES conversation_sessions (id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 风控事件表：保存输入输出风险命中和处理动作
CREATE TABLE IF NOT EXISTS safety_events (
  id CHAR(36) NOT NULL PRIMARY KEY,
  user_id CHAR(36) NOT NULL,
  conversation_id CHAR(36) NULL,
  scene VARCHAR(32) NOT NULL,
  risk_type VARCHAR(64) NOT NULL,
  risk_level VARCHAR(16) NOT NULL,
  input_snapshot TEXT NOT NULL,
  output_snapshot TEXT NOT NULL,
  action VARCHAR(32) NOT NULL DEFAULT 'pass',
  detail_json JSON NOT NULL DEFAULT (JSON_OBJECT()),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_safety_events_user_id (user_id),
  KEY idx_safety_events_conversation_id (conversation_id),
  KEY idx_safety_events_scene (scene),
  KEY idx_safety_events_risk_type (risk_type),
  KEY idx_safety_events_risk_level (risk_level),
  CONSTRAINT fk_safety_events_user_id
    FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT fk_safety_events_conversation_id
    FOREIGN KEY (conversation_id) REFERENCES conversation_sessions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 长期记忆 RocketMQ Outbox：RocketMQ 临时不可用时保存待补投事件
CREATE TABLE IF NOT EXISTS memory_event_outbox (
  id CHAR(36) NOT NULL PRIMARY KEY,
  event_id CHAR(36) NOT NULL,
  task_id VARCHAR(96) NOT NULL,
  user_id VARCHAR(64) NOT NULL,
  session_id CHAR(36) NOT NULL DEFAULT '',
  payload JSON NOT NULL DEFAULT (JSON_OBJECT()),
  status VARCHAR(24) NOT NULL DEFAULT 'pending',
  retry_count BIGINT NOT NULL DEFAULT 0,
  next_retry_at DATETIME NULL,
  last_error TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_memory_event_outbox_event_id (event_id),
  KEY idx_memory_event_outbox_task_id (task_id),
  KEY idx_memory_event_outbox_user_id (user_id),
  KEY idx_memory_event_outbox_status_next_retry (status, next_retry_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
