# AI-Novels — Port Configuration

## Port Range: 33xxx

此项目分配的端口号段为 **33xxx**，与另外 4 个 Codex 项目共享端口注册表。

| 服务 | 端口 |
|---|---|
| AI Engine | 33100 |
| BFF | 33180 |
| PostgreSQL | 33432 |
| Redis | 33379 |
| MongoDB | 33217 |
| Neo4j HTTP | 33474 |
| Neo4j Bolt | 33687 |
| ChromaDB | 33801 |
| Qdrant HTTP/gRPC | 33333 / 33334 |
| Prometheus | 33990 |
| Grafana | 33301 |

## Conflict Prevention

- **启动任何服务前**，先读取 `C:\Users\Ryan\Documents\Codex\ports-registry.json` 确认端口占用
- **添加新端口**时，必须使用 `33xxx` 号段，并更新端口注册表
- **禁止使用**常见默认端口 (80, 443, 3306, 6379, 27017, 5432, 8080, 9090 等)

> 完整端口注册表: `C:\Users\Ryan\Documents\Codex\ports-registry.json`
