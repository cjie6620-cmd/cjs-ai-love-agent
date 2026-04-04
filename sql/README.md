# SQL 初始化说明

当前目录提供两份可直接执行的数据库初始化脚本：

- `mysql_init.sql`
  作用：创建 `ai_love` 数据库、账号授权，以及核心业务表
- `pgvector_init.sql`
  作用：创建 `ai_love_vector` 数据库、`vector` 扩展，以及向量表
  说明：当前版本是纯 SQL 兼容版，适合在 Navicat / DBeaver / DataGrip 中执行

## 推荐执行方式

### MySQL

```bash
mysql -uroot -p < backend/sql/mysql_init.sql
```

### PostgreSQL / pgvector

```bash
psql -U postgres -f backend/sql/pgvector_init.sql
```

如果你用的是可视化客户端：

- 先连接 `postgres` 库，执行“库与账号初始化”部分
- 再切换到 `ai_love_vector` 库，执行“pgvector 与向量表初始化”部分

## 说明

- 脚本里的默认账号密码与 `.env.example` 一致，都是 `ai_love / ai_love`
- 如果你本地账号密码不同，改脚本里的用户名密码即可
- 表创建后，后端会直接按现有表结构运行，不再依赖启动时自动建表
