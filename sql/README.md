# sql 模块说明

## 1. 模块定位

`sql` 是数据库初始化脚本目录，负责维护 MySQL 与 pgvector 相关的建库、建表和基础初始化脚本。

它解决的是“项目数据库如何快速初始化并与代码保持一致”的问题。

## 2. 目录结构

- `mysql_init.sql`
  作用：MySQL 初始化脚本。
  功能：创建 `ai_love` 数据库、账号授权和核心业务表。
- `pgvector_init.sql`
  作用：PostgreSQL / pgvector bootstrap 脚本。
  功能：创建 `ai_love_vector` 数据库和 `ai_love` 账号。
- `pgvector_schema.sql`
  作用：PostgreSQL / pgvector 表结构脚本。
  功能：创建 `vector` 扩展、业务向量表和索引结构。
- `README.md`
  作用：SQL 目录说明文档。
  功能：解释脚本用途、执行方式和维护规范。

## 3. 推荐执行方式

### MySQL

```bash
mysql -uroot -p < sql/mysql_init.sql
```

### PostgreSQL / pgvector

```bash
psql -U postgres -d postgres -f sql/pgvector_init.sql
psql -U ai_love -d ai_love_vector -f sql/pgvector_schema.sql
```

如果使用可视化客户端：

- 先连接 `postgres` 库，执行 `pgvector_init.sql`。
- 再切换到 `ai_love_vector` 库，执行 `pgvector_schema.sql`。

## 4. 依赖边界

- SQL 脚本与 `persistence`、`rag/vector_store` 的表结构保持一致。
- 运行时模块不直接依赖本目录文件，但部署和初始化过程依赖本目录内容。
- 表结构变更要同时更新 ORM、仓储、SQL 与文档。

## 5. 企业规范做法

- SQL 脚本按数据库类型拆分，避免一个脚本同时兼容所有引擎。
- 建库、建表、授权、扩展安装要清晰分段。
- 默认账号、库名、表结构要与 `.env.example` 和代码约定保持一致。
- 任何表结构变更都要有对应文档说明，避免只改代码不改 SQL。

## 6. 维护要求

- 当前默认账号密码与 `.env.example` 一致，默认是 `ai_love / ai_love`。
- 如果本地账号密码不同，修改脚本中的用户名密码即可。
- 后续新增迁移脚本或初始化脚本时，同步更新本 README。
