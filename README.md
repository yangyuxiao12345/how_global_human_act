# ZELL 多智能体社会模拟平台

ZELL 是一个本地运行的多智能体社会模拟项目。它可以创建一组拥有独立身份、人物画像和记忆的 AI 智能体，让这些智能体针对同一事件分别思考和行动，并通过地图、关系图谱、工作台和数据面板展示模拟结果。

当前版本已经完成中文界面和中文对话适配，默认通过 Ollama 调用本地模型。

## 功能

### 智能体

- 手动输入需要生成的智能体数量
- 随机生成姓名、年龄、地区、职业和性格
- 为每个智能体生成独立人物画像
- 保存智能体的记忆、情绪、资源和当前位置
- 查看单个智能体的详细资料和历史行为

### 社会模拟

- 输入自定义事件并触发模拟
- 设置模拟年份
- 运行多周期智能体决策
- 生成思考、情绪、行动和后续计划
- 判断智能体是否迁移
- 记录智能体对个人、组织或机构的信任变化

### 数据展示

- 世界地图：查看智能体的地理分布
- 关系图谱：查看智能体、地区、职业和其他属性之间的联系
- 图谱工作台：使用自然语言查询智能体关系和群体特征
- 事件面板：查看历次模拟、周期变化和智能体回应
- 搜索：对模拟结果进行语义搜索和模糊搜索
- 报告：查看或导出模拟分析报告

### 模型管理

- 检查 Ollama 服务状态
- 获取本地已安装的模型列表
- 在页面中切换当前模型
- 模型不可用时提供备用响应
- 对新生成的对话强制使用简体中文

## 技术栈

| 部分 | 技术 |
| --- | --- |
| 前端 | React 18、TypeScript、Vite、Tailwind CSS |
| 地图 | Leaflet、MapLibre GL |
| 关系图谱 | Cytoscape、D3 Force、PixiJS |
| 后端 | Python 3.12、FastAPI、Uvicorn |
| 本地模型 | Ollama |
| 数据 | SQLite、智能体 Markdown 档案 |
| 部署 | Docker Compose |

## 运行要求

- Docker Desktop
- Ollama
- 建议至少保留 2 GB 可用磁盘空间
- 运行更多或更大的模型时，需要相应增加内存或显存

## 快速启动

### 1. 安装并启动 Ollama

从 [Ollama 官网](https://ollama.com/) 安装 Ollama，然后下载项目默认模型：

```powershell
ollama pull qwen2.5:0.5b
```

确认模型存在：

```powershell
ollama list
```

列表中应包含：

```text
qwen2.5:0.5b
```

### 2. 启动项目

在项目根目录运行：

```powershell
docker compose up -d --build
```

### 3. 打开页面

- 前端：<http://localhost:3000>
- 后端：<http://localhost:8000>
- 服务状态：<http://localhost:8000/health>
- 模型状态：<http://localhost:8000/api/llm/health>

模型状态接口正常时会返回类似结果：

```json
{
  "status": "healthy",
  "provider": "ollama",
  "model": "qwen2.5:0.5b"
}
```

## 使用方法

1. 打开前端页面。
2. 在左侧输入要创建的智能体数量。
3. 点击“生成智能体”。
4. 等待人物画像生成完成。
5. 设置年份并输入需要模拟的事件。
6. 点击“触发事件”。
7. 在地图、图谱、工作台或事件面板查看结果。

首次使用建议先生成 3–10 个智能体。每个新智能体都需要生成多段人物画像，数量越多，等待时间越长。

## Ollama 配置

项目当前在 `docker-compose.yml` 中使用：

```yaml
environment:
  LLM_PROVIDER: ollama
  LLM_BASE_URL: http://host.docker.internal:11434
  LLM_MODEL: qwen2.5:0.5b
```

`host.docker.internal` 用于让 Docker 容器访问宿主电脑上的 Ollama。不要将它改成 `localhost`，因为容器中的 `localhost` 指向后端容器本身。

## 更换模型

先通过 Ollama 下载模型：

```powershell
ollama pull qwen2.5:1.5b
```

然后修改 `docker-compose.yml`：

```yaml
LLM_MODEL: qwen2.5:1.5b
```

重新创建后端容器：

```powershell
docker compose up -d --build backend
```

也可以直接在页面左侧的“大语言模型”区域选择已经安装的模型。

模型越大，通常生成效果越好，但速度更慢，并需要更多内存或显存。

## 生成速度说明

人物画像由 6 个部分组成。首次创建智能体时，每个智能体都需要多次调用本地模型。批量生成会并行处理，但总耗时仍受以下因素影响：

- 智能体数量
- 模型大小
- CPU 和 GPU 性能
- 可用内存或显存
- Ollama 当前负载

生成期间不要关闭 Ollama 或 Docker Desktop。

## 数据保存

Docker Compose 使用两个持久化卷：

| 数据卷 | 内容 |
| --- | --- |
| `backend_data` | SQLite 数据库和模拟记录 |
| `backend_agents_data` | 智能体人物画像文件 |

停止或重新创建普通容器不会清除这些数据。

以下命令会连同数据卷一起删除数据，请谨慎使用：

```powershell
docker compose down -v
```

## 常用命令

启动服务：

```powershell
docker compose up -d
```

重新构建并启动：

```powershell
docker compose up -d --build
```

查看运行状态：

```powershell
docker compose ps
```

查看后端日志：

```powershell
docker compose logs -f backend
```

查看前端日志：

```powershell
docker compose logs -f frontend
```

停止服务：

```powershell
docker compose down
```

## 主要接口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/health` | 后端健康检查 |
| GET | `/api/llm/health` | Ollama 和模型状态 |
| GET | `/api/llm/models` | 获取可用模型 |
| POST | `/api/llm/model` | 切换模型 |
| POST | `/api/agents/generate-personas-batch` | 批量生成人物画像 |
| GET | `/api/agents/generation-status` | 查询生成进度 |
| POST | `/api/simulation/start` | 启动模拟 |
| GET | `/api/simulation/status` | 查询模拟状态 |
| GET | `/api/graph/relationships` | 获取关系图谱 |
| POST | `/api/workbench/chat` | 查询模拟图谱 |
| GET | `/api/dashboard/runs` | 获取模拟记录 |
| GET | `/api/dashboard/search` | 搜索模拟结果 |
| GET | `/api/runs/{run_id}/report` | 获取模拟报告 |

## 项目结构

```text
.
├─ backend/
│  ├─ app/services/       模型、搜索、报告与人物画像服务
│  ├─ app/simulation/     智能体、记忆、决策与模拟执行
│  └─ main.py             FastAPI 接口
├─ frontend/
│  └─ src/
│     ├─ components/      页面组件
│     ├─ lib/             前端接口与工具
│     └─ App.tsx          主界面
├─ docs/                  项目文档
├─ assets/                图片资源
└─ docker-compose.yml     容器与模型配置
```

## 本地开发

### 后端

```powershell
cd backend
uv sync --all-groups
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

后端要求 Python 3.12 或更高版本。

### 前端

```powershell
cd frontend
npm install
npm run dev
```

开发服务器默认运行在 <http://localhost:5173>。

## 常见问题

### 模型状态不正常

检查 Ollama 是否运行：

```powershell
ollama list
```

然后访问 <http://localhost:8000/api/llm/health>。如果模型不存在，请先执行 `ollama pull`。

### 页面一直显示正在生成

查看后端实时日志：

```powershell
docker compose logs -f backend
```

如果日志仍持续出现模型响应记录，说明任务正在运行。大量智能体会显著增加生成时间。

### 历史对话仍然显示英文

中文输出规则只影响新生成的内容。数据库中已经保存的旧模拟不会被自动改写，请重新创建一次模拟。

### 页面无法访问

确认容器均为运行状态：

```powershell
docker compose ps
```

默认端口为前端 `3000`、后端 `8000`、Ollama `11434`。

## 当前状态

当前版本适合本地体验、小规模多智能体实验、事件推演和群体行为观察。大规模模拟的速度主要受本地模型推理能力限制。
