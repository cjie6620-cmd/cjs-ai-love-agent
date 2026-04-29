-- AI Love Agent PostgreSQL / pgvector 向量表结构脚本
-- 使用方式：
-- 1. 先确保 ai_love_vector 数据库与 ai_love 账号已存在
-- 2. 连接到 ai_love_vector 数据库后执行本脚本
--
-- 职责说明：
-- 1. 这里只存“向量检索相关数据”，不存主业务事务数据
-- 2. 主业务事务数据在 MySQL ai_love 库里
-- 3. 这里重点服务 RAG / 长期记忆检索 / 风格复刻检索 / 回答语义缓存
--
-- 表职责划分：
-- 1. memory_embeddings：长期记忆向量，服务用户记忆召回
-- 2. knowledge_embeddings：知识库分片向量，服务知识检索增强
-- 3. style_sample_embeddings：风格样本向量，服务语气与表达风格模仿
-- 4. response_semantic_cache_entries：回答语义缓存，服务相似问题复用

CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS response_semantic_cache_entries;
DROP TABLE IF EXISTS style_sample_embeddings;
DROP TABLE IF EXISTS knowledge_embeddings;
DROP TABLE IF EXISTS memory_embeddings;

-- =========================================================
-- 第一部分：长期记忆向量
-- 一条记录代表一条可检索的长期记忆
-- 常见内容：偏好、关系状态、边界、关键事件、稳定事实
-- =========================================================

-- 长期记忆向量表：保存用户长期关系记忆
CREATE TABLE memory_embeddings (
  id VARCHAR(36) PRIMARY KEY,
  user_id VARCHAR(36) NOT NULL,
  session_id VARCHAR(36),
  memory_type VARCHAR(32) NOT NULL,
  canonical_key VARCHAR(96) NOT NULL DEFAULT '',
  content TEXT NOT NULL,
  importance_score DOUBLE PRECISION NOT NULL DEFAULT 0,
  confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
  status VARCHAR(16) NOT NULL DEFAULT 'active',
  source_session_id VARCHAR(36) NOT NULL DEFAULT '',
  merged_into_id VARCHAR(36),
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  embedding VECTOR(1536) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE memory_embeddings IS '长期记忆向量表：保存用户长期关系记忆';
COMMENT ON COLUMN memory_embeddings.id IS '长期记忆主键 UUID';
COMMENT ON COLUMN memory_embeddings.user_id IS '所属用户 ID';
COMMENT ON COLUMN memory_embeddings.session_id IS '来源会话 ID';
COMMENT ON COLUMN memory_embeddings.memory_type IS '记忆类型，例如偏好、关系、边界等';
COMMENT ON COLUMN memory_embeddings.canonical_key IS '归一化记忆键，用于合并与去重';
COMMENT ON COLUMN memory_embeddings.content IS '长期记忆正文';
COMMENT ON COLUMN memory_embeddings.importance_score IS '重要性评分';
COMMENT ON COLUMN memory_embeddings.confidence IS '记忆置信度';
COMMENT ON COLUMN memory_embeddings.status IS '记忆状态：active/merged/deleted 等';
COMMENT ON COLUMN memory_embeddings.source_session_id IS '原始来源会话 ID';
COMMENT ON COLUMN memory_embeddings.merged_into_id IS '被合并到的目标记忆 ID';
COMMENT ON COLUMN memory_embeddings.metadata_json IS '记忆扩展元数据 JSON';
COMMENT ON COLUMN memory_embeddings.embedding IS '记忆内容向量，维度 1536';
COMMENT ON COLUMN memory_embeddings.created_at IS '创建时间';
COMMENT ON COLUMN memory_embeddings.last_seen_at IS '最近命中或确认时间';
COMMENT ON COLUMN memory_embeddings.updated_at IS '更新时间';

-- 普通索引：支撑按用户、会话、类型、状态等条件做过滤检索
CREATE INDEX IF NOT EXISTS idx_memory_embeddings_user_id
  ON memory_embeddings (user_id);

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_session_id
  ON memory_embeddings (session_id);

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_memory_type
  ON memory_embeddings (memory_type);

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_canonical_key
  ON memory_embeddings (canonical_key);

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_status
  ON memory_embeddings (status);

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_user_key_status
  ON memory_embeddings (user_id, canonical_key, status);

-- 强约束：同一用户同一 canonical_key 只能有一条 active 记忆
CREATE UNIQUE INDEX IF NOT EXISTS uk_memory_embeddings_active_user_key
  ON memory_embeddings (user_id, canonical_key)
  WHERE status = 'active' AND canonical_key <> '';

-- 向量索引：支撑 embedding 的相似度检索，lists 可按数据量继续调优
CREATE INDEX IF NOT EXISTS idx_memory_embeddings_embedding
  ON memory_embeddings
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- =========================================================
-- 第二部分：知识库向量
-- 一条记录代表一个知识分片，通常来自文档切块后的片段
-- 适合承载恋爱建议、安全边界、沟通方法等知识内容
-- =========================================================

-- 知识库向量表：保存恋爱建议和安全知识分片
CREATE TABLE knowledge_embeddings (
  id VARCHAR(36) PRIMARY KEY,
  tenant_id VARCHAR(36) NOT NULL DEFAULT 'default',
  knowledge_id VARCHAR(64) NOT NULL,
  category VARCHAR(32) NOT NULL,
  title VARCHAR(255) NOT NULL,
  content TEXT NOT NULL,
  source VARCHAR(255) NOT NULL DEFAULT '',
  created_by VARCHAR(36) NOT NULL DEFAULT '',
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  embedding VECTOR(1536) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE knowledge_embeddings IS '知识库向量表：保存恋爱建议和安全知识分片';
COMMENT ON COLUMN knowledge_embeddings.id IS '知识向量主键 UUID';
COMMENT ON COLUMN knowledge_embeddings.tenant_id IS '所属租户 ID';
COMMENT ON COLUMN knowledge_embeddings.knowledge_id IS '知识条目业务 ID';
COMMENT ON COLUMN knowledge_embeddings.category IS '知识分类';
COMMENT ON COLUMN knowledge_embeddings.title IS '知识标题';
COMMENT ON COLUMN knowledge_embeddings.content IS '知识内容分片';
COMMENT ON COLUMN knowledge_embeddings.source IS '知识来源';
COMMENT ON COLUMN knowledge_embeddings.created_by IS '创建人用户 ID';
COMMENT ON COLUMN knowledge_embeddings.metadata_json IS '知识扩展元数据 JSON';
COMMENT ON COLUMN knowledge_embeddings.embedding IS '知识内容向量，维度 1536';
COMMENT ON COLUMN knowledge_embeddings.created_at IS '创建时间';

-- 普通索引：支撑按知识条目或分类做过滤
CREATE INDEX IF NOT EXISTS idx_knowledge_embeddings_knowledge_id
  ON knowledge_embeddings (knowledge_id);

CREATE INDEX IF NOT EXISTS idx_knowledge_embeddings_tenant_category
  ON knowledge_embeddings (tenant_id, category);

CREATE INDEX IF NOT EXISTS idx_knowledge_embeddings_category
  ON knowledge_embeddings (category);

-- 向量索引：支撑知识分片相似度检索
CREATE INDEX IF NOT EXISTS idx_knowledge_embeddings_embedding
  ON knowledge_embeddings
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- =========================================================
-- 第三部分：风格样本向量
-- 一条记录代表一条风格训练样本，用来召回用户偏好的表达方式
-- 常用于“像谁说话”“保持某种语气”的场景
-- =========================================================

-- 风格样本向量表：保存语气复刻样本
CREATE TABLE style_sample_embeddings (
  id VARCHAR(36) PRIMARY KEY,
  user_id VARCHAR(36) NOT NULL,
  profile_id VARCHAR(36) NOT NULL,
  source_message TEXT NOT NULL,
  normalized_text TEXT NOT NULL,
  style_tags JSONB NOT NULL DEFAULT '{}'::jsonb,
  embedding VECTOR(1536) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE style_sample_embeddings IS '风格样本向量表：保存语气复刻样本';
COMMENT ON COLUMN style_sample_embeddings.id IS '风格样本主键 UUID';
COMMENT ON COLUMN style_sample_embeddings.user_id IS '所属用户 ID';
COMMENT ON COLUMN style_sample_embeddings.profile_id IS '关联画像或智能体配置 ID';
COMMENT ON COLUMN style_sample_embeddings.source_message IS '原始样本消息';
COMMENT ON COLUMN style_sample_embeddings.normalized_text IS '归一化后的样本文本';
COMMENT ON COLUMN style_sample_embeddings.style_tags IS '风格标签 JSON';
COMMENT ON COLUMN style_sample_embeddings.embedding IS '风格样本文本向量，维度 1536';
COMMENT ON COLUMN style_sample_embeddings.created_at IS '创建时间';

-- 普通索引：支撑按用户和画像配置过滤样本
CREATE INDEX IF NOT EXISTS idx_style_sample_embeddings_user_id
  ON style_sample_embeddings (user_id);

CREATE INDEX IF NOT EXISTS idx_style_sample_embeddings_profile_id
  ON style_sample_embeddings (profile_id);

-- 向量索引：支撑风格相似样本检索
CREATE INDEX IF NOT EXISTS idx_style_sample_embeddings_embedding
  ON style_sample_embeddings
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- =========================================================
-- 第四部分：回答语义缓存
-- 一条记录代表一次可复用的 ChatResponse
-- 默认按用户、会话、模式和上下文指纹隔离，避免跨用户或跨上下文误用
-- =========================================================

CREATE TABLE response_semantic_cache_entries (
  id VARCHAR(36) PRIMARY KEY,
  user_id VARCHAR(36) NOT NULL,
  session_id VARCHAR(36) NOT NULL,
  mode VARCHAR(32) NOT NULL,
  context_fingerprint VARCHAR(64) NOT NULL,
  normalized_message TEXT NOT NULL,
  response_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  embedding VECTOR(1536) NOT NULL,
  hit_count INTEGER NOT NULL DEFAULT 0,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE response_semantic_cache_entries IS '回答语义缓存表：保存可按语义相似度复用的 ChatResponse';
COMMENT ON COLUMN response_semantic_cache_entries.user_id IS '所属用户 ID';
COMMENT ON COLUMN response_semantic_cache_entries.session_id IS '所属会话 ID';
COMMENT ON COLUMN response_semantic_cache_entries.mode IS '对话模式';
COMMENT ON COLUMN response_semantic_cache_entries.context_fingerprint IS '会话上下文指纹';
COMMENT ON COLUMN response_semantic_cache_entries.normalized_message IS '归一化后的用户输入';
COMMENT ON COLUMN response_semantic_cache_entries.response_payload IS '可返回给前端的 ChatResponse JSON';
COMMENT ON COLUMN response_semantic_cache_entries.embedding IS '用户输入向量，维度 1536';
COMMENT ON COLUMN response_semantic_cache_entries.hit_count IS '缓存命中次数';
COMMENT ON COLUMN response_semantic_cache_entries.expires_at IS '缓存过期时间';

CREATE INDEX IF NOT EXISTS idx_response_semantic_cache_scope
  ON response_semantic_cache_entries (user_id, session_id, mode, context_fingerprint, expires_at);

CREATE INDEX IF NOT EXISTS idx_response_semantic_cache_expires_at
  ON response_semantic_cache_entries (expires_at);

CREATE INDEX IF NOT EXISTS idx_response_semantic_cache_embedding
  ON response_semantic_cache_entries
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);
