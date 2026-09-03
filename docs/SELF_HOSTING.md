# 自行托管 ZELL

本指南介绍一种面向生产环境的 ZELL 部署方式。

## ZELL 是什么

ZELL 是一个可自行托管的知识智能与多智能体模拟平台。你可以在自己的基础设施中运行整套服务，自主管理模型端点，并将数据保留在自己的环境内。

## 部署模式

### 本地分离服务（开发模式）

后端：

```bash
cd backend
uv sync --all-groups
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

前端：

```bash
cd frontend
npm ci
npm run dev
```

## 必需的运行参数

在部署环境中设置以下变量：

- `LLM_PROVIDER`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `LLM_TIMEOUT`
- `LLM_MAX_TOKENS`
- `LLM_TEMPERATURE`
- `LLM_TOP_P`
- `CORS_ORIGINS`

可选调优项：

- `BOOTSTRAP_PROFILE_COUNT`
- `POST_BOOTSTRAP_PROFILE_COUNT`
- `BOOTSTRAP_AGENT_LIMIT`
- `SEMANTIC_SCAN_MAX_RESPONSES`

## 安全检查清单

- 将后端置于 TLS 之后（Nginx、Caddy 或 Traefik）
- 将 `CORS_ORIGINS` 限制在可信域名
- 避免将内部大语言模型端点暴露到公网
- 使用最小权限运行容器或用户
- 定期扫描依赖项

## 持久化与数据

当前后端数据路径包括：

- `backend/agents.db`
- `backend/agents_data/`

生产环境应为两者挂载持久化卷。

## 健康检查与冒烟测试

检查服务状态：

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/llm/health
```

初始化世界数据：

```bash
curl -X POST http://localhost:8000/api/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"count": 1200, "with_agents": true}'
```

启动一次模拟：

```bash
curl -X POST http://localhost:8000/api/simulation/start \
  -H "Content-Type: application/json" \
  -d '{"event": "区域性气候冲击", "cycles": 2, "year": 2026}'
```

列出模拟记录：

```bash
curl http://localhost:8000/api/dashboard/runs
```

## 扩展建议

- 横向扩展 API 时应配合共享或持久化存储
- 对于更大的工作负载，将 SQLite 迁移至网络数据库
- 通过合理选择模型大小和队列策略控制大语言模型延迟
- 公网环境中应对高成本生成端点进行限流

## 可观测性

建议增加：

- 反向代理访问日志
- 结构化后端日志
- 指标采集（CPU、内存、请求延迟）
- 针对 `/health` 和关键 API 路由的可用性检查
