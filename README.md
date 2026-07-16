<h1 align="center">MuseLab</h1>

<p align="center"><strong>本地优先、自托管的 AI 文件与对话工作台</strong></p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/model-Qwen3.6--27B-6b7cff" alt="Qwen3.6-27B">
  <img src="https://img.shields.io/badge/protocol-OpenAI%20Compatible-111827" alt="OpenAI Compatible">
  <img src="https://img.shields.io/badge/deploy-self--hosted-f59e0b" alt="Self-hosted">
</p>

MuseLab 将 AI 对话、个人文件、文档预览、Agent 工具和长期会话整合到一个浏览器工作台中。文件与会话数据保存在自己的设备上，模型通过可配置的 OpenAI-compatible 接口调用。

当前版本默认使用独立部署的 `Qwen3.6-27B`，并通过内置协议转换层接入 Claude Agent SDK 的工具循环。

## 当前能力

- **Qwen3.6-27B 对话**：主对话和会话标题都使用独立轻量模型。
- **OpenAI 协议接入**：上游使用 `/v1/chat/completions`。
- **Anthropic → OpenAI 转换**：保留 Claude Agent SDK 的流式输出、工具调用、Skills 与 MCP 能力。
- **本地文件工作台**：浏览、搜索、上传、编辑、预览和管理个人文件。
- **多格式预览**：支持 Markdown、代码、图片、PDF、表格和沙盒 HTML。
- **自动会话标题**：首轮对话完成后，由轻量 LLM 根据主题生成简短标题。
- **草稿式新会话**：未发送消息时不创建会话记录；第一条消息发送后才写入历史。
- **流式聊天**：OpenAI SSE 响应转换为前端可消费的 Anthropic 事件流。
- **Agent 工具**：支持文件读取、编辑、命令执行、MCP 与 Skills。
- **PWA 与响应式布局**：支持桌面浏览器和移动设备。

## 技术架构

```text
浏览器
  ├─ Alpine.js 单页界面
  ├─ Fetch / SSE
  ↓
FastAPI
  ├─ 会话与文件 API
  ├─ Anthropic Messages 兼容端点
  ├─ Anthropic → OpenAI 消息转换
  └─ Agent 工具与会话管理
  ↓
OpenAI-compatible /v1/chat/completions
  ↓
Qwen3.6-27B
```

前端不需要 Vite、Webpack 或 Node 构建流程：

- `frontend/index.html`：Alpine 模板与页面结构
- `frontend/app.js`：状态、交互、API 与 SSE
- `frontend/styles.css`：设计系统和响应式样式
- `frontend/i18n/`：界面文案

## 环境要求

- Python 3.12+
- macOS 或 Linux
- 可访问的 OpenAI-compatible Chat Completions 服务
- Claude Agent SDK 运行环境

## 安装

### macOS

```bash
bash scripts/install-macos.sh
```

### Linux

```bash
bash scripts/install-linux.sh
```

### 手动运行

```bash
uv sync
uv run python -m backend.main
```

启动后访问：

```text
http://127.0.0.1:8765
```

## 模型配置

在 `.env` 中配置主对话模型：

```env
CODEX_GATEWAY_BASE_URL=http://your-host:8000/v1
CODEX_GATEWAY_API_KEY=replace-with-your-key
MUSELAB_DEFAULT_MODEL=codex:Qwen3.6-27B
MUSELAB_MODEL=codex:Qwen3.6-27B
```

`CODEX_GATEWAY_BASE_URL` 可以填写服务根地址或 `/v1` 地址。MuseLab 会规范化为：

```text
POST /v1/chat/completions
```

不要把 `/chat/completions` 重复写入 Base URL。

## 自动会话标题

标题模型可以和主对话模型使用同一个 OpenAI-compatible 服务：

```env
MUSELAB_TITLE_LLM_URL=http://your-host:8000/v1/chat/completions
MUSELAB_TITLE_LLM_API_KEY=replace-with-your-key
MUSELAB_TITLE_LLM_MODEL=Qwen3.6-27B
```

首轮回复完成后，标题任务会在后台运行。用户已手动改名时，异步标题不会覆盖人工名称。

## 数据目录

默认数据位置由 `.env` 的 `MUSELAB_ROOT` 决定：

```env
MUSELAB_ROOT=/absolute/path/to/archive
```

项目本身还会维护：

- `sessions/index.json`：会话元数据
- `sessions/*.sidecar.json`：消息注解与附件信息
- `provider_overrides.json`：Provider 覆盖配置
- `.env`：服务、模型和密钥配置

这些文件可能包含个人信息或访问凭据，不应提交到公开仓库。

## 常用操作

### 启动

```bash
uv run python -m backend.main
```

### 后台启动

```bash
nohup uv run python -m backend.main >/tmp/muselab.log 2>&1 &
```

### 停止

```bash
pkill -f "python.*backend.main"
```

### 查看日志

```bash
tail -f /tmp/muselab.log
```

### 运行测试

```bash
.venv/bin/pytest -q
```

## 安全建议

- 不要把 `.env`、API Key、会话数据或个人档案提交到 Git。
- 模型接口优先使用 HTTPS；HTTP 会以明文传输密钥和对话内容。
- API Key 一旦出现在聊天、日志或截图中，应立即轮换。
- 对外开放服务时，应使用反向代理、HTTPS 和强认证 Token。
- 定期备份 archive、sessions 和 Provider 配置。

## 项目结构

```text
backend/                 FastAPI、会话、Agent 与协议转换
frontend/                Alpine.js 单页应用
docs/                    使用和架构文档
scripts/                 安装、诊断与维护脚本
sessions/                本地会话元数据
tests/                   后端、前端和协议转换测试
provider_overrides.json  Provider 自定义配置
```

## 文档

- [快速入门](docs/quickstart_zh.md)
- [配置说明](docs/configuration_zh.md)
- [Provider 配置](docs/providers_zh.md)
- [模型路由](docs/routing_zh.md)
- [架构说明](docs/architecture_zh.md)
- [会话机制](docs/backend-sessions_zh.md)
- [数据与备份](docs/data-and-backup_zh.md)
- [故障排查](docs/troubleshooting_zh.md)

## License

本项目依据 [MIT License](LICENSE) 使用和分发。分发或发布修改版本时，请保留许可证中要求保留的版权声明与许可文本。
