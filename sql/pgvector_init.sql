-- AI Love Agent PostgreSQL / pgvector 初始化脚本（bootstrap）
-- 这个版本只负责“数据库与账号初始化”，适合在 Navicat / DBeaver / DataGrip 中执行。
--
-- 使用方式：
-- 1. 连接 PostgreSQL 管理库（通常是 postgres）
-- 2. 执行本脚本，完成账号与数据库准备
-- 3. 再切换连接到 ai_love_vector 数据库，执行 sql/pgvector_schema.sql


-- =========================================================
-- 第一部分：库与账号初始化
-- 建议连接 postgres 库执行
-- =========================================================

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ai_love') THEN
    CREATE ROLE ai_love LOGIN PASSWORD 'ai_love';
  END IF;
END
$$;

-- PostgreSQL 不支持 CREATE DATABASE IF NOT EXISTS。
-- 如果数据库已经存在，执行这句时会报“已存在”，可以直接忽略。
CREATE DATABASE ai_love_vector OWNER ai_love;
