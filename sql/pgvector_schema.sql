-- AI Love Agent PostgreSQL / pgvector 向量表结构脚本
-- 使用方式：
-- 1. 先确保 ai_love_vector 数据库与 ai_love 账号已存在
-- 2. 连接到 ai_love_vector 数据库后执行本脚本

CREATE EXTENSION IF NOT EXISTS vector;

-- 长期记忆向量表：保存用户长期关系记忆
CREATE TABLE IF NOT EXISTS memory_embeddings (
  id VARCHAR(36) PRIMARY KEY,
  user_id VARCHAR(36) NOT NULL,
  session_id VARCHAR(36),
  memory_type VARCHAR(32) NOT NULL,
  content TEXT NOT NULL,
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  embedding VECTOR(1536) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_user_id
  ON memory_embeddings (user_id);

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_session_id
  ON memory_embeddings (session_id);

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_memory_type
  ON memory_embeddings (memory_type);

CREATE INDEX IF NOT EXISTS idx_memory_embeddings_embedding
  ON memory_embeddings
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- 知识库向量表：保存恋爱建议和安全知识分片
CREATE TABLE IF NOT EXISTS knowledge_embeddings (
  id VARCHAR(36) PRIMARY KEY,
  knowledge_id VARCHAR(64) NOT NULL,
  category VARCHAR(32) NOT NULL,
  title VARCHAR(255) NOT NULL,
  content TEXT NOT NULL,
  source VARCHAR(255) NOT NULL DEFAULT '',
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  embedding VECTOR(1536) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_embeddings_knowledge_id
  ON knowledge_embeddings (knowledge_id);

CREATE INDEX IF NOT EXISTS idx_knowledge_embeddings_category
  ON knowledge_embeddings (category);

CREATE INDEX IF NOT EXISTS idx_knowledge_embeddings_embedding
  ON knowledge_embeddings
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- 风格样本向量表：保存语气复刻样本
CREATE TABLE IF NOT EXISTS style_sample_embeddings (
  id VARCHAR(36) PRIMARY KEY,
  user_id VARCHAR(36) NOT NULL,
  profile_id VARCHAR(36) NOT NULL,
  source_message TEXT NOT NULL,
  normalized_text TEXT NOT NULL,
  style_tags JSONB NOT NULL DEFAULT '{}'::jsonb,
  embedding VECTOR(1536) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_style_sample_embeddings_user_id
  ON style_sample_embeddings (user_id);

CREATE INDEX IF NOT EXISTS idx_style_sample_embeddings_profile_id
  ON style_sample_embeddings (profile_id);

CREATE INDEX IF NOT EXISTS idx_style_sample_embeddings_embedding
  ON style_sample_embeddings
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);
