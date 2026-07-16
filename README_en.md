<h1 align="center">MuseLab</h1>

<p align="center"><strong>A local-first, self-hosted AI workspace for files and conversations</strong></p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/model-Qwen3.6--27B-6b7cff" alt="Qwen3.6-27B">
  <img src="https://img.shields.io/badge/protocol-OpenAI%20Compatible-111827" alt="OpenAI Compatible">
  <img src="https://img.shields.io/badge/deploy-self--hosted-f59e0b" alt="Self-hosted">
</p>

MuseLab combines AI chat, personal files, document previews, agent tools, and persistent conversations in one browser workspace. Files and session data remain on your own machine, while models are accessed through a configurable OpenAI-compatible endpoint.

The current deployment uses `Qwen3.6-27B` by default and includes a built-in protocol bridge that connects OpenAI Chat Completions to the Claude Agent SDK tool loop.

## Features

- **Qwen3.6-27B chat** — both primary conversations and session titles use the lightweight model.
- **OpenAI-compatible API** — the upstream endpoint uses `/v1/chat/completions`.
- **Anthropic-to-OpenAI bridge** — retains Claude Agent SDK streaming, tool calls, Skills, and MCP support.
- **Local file workspace** — browse, search, upload, edit, preview, and organize personal files.
- **Rich previews** — Markdown, source code, images, PDFs, spreadsheets, and sandboxed HTML.
- **Automatic session titles** — a lightweight LLM generates a concise title after the first completed turn.
- **Draft conversations** — an empty composer creates no history entry; the session is persisted only after the first message.
- **Streaming responses** — OpenAI SSE chunks are translated into Anthropic-compatible stream events.
- **Agent tools** — file reading and editing, command execution, MCP, and Skills.
- **Responsive PWA** — designed for desktop and mobile browsers.

## Architecture

```text
Browser
  ├─ Alpine.js single-page interface
  ├─ Fetch / SSE
  ↓
FastAPI
  ├─ Session and file APIs
  ├─ Anthropic Messages-compatible endpoint
  ├─ Anthropic → OpenAI message conversion
  └─ Agent tools and session management
  ↓
OpenAI-compatible /v1/chat/completions
  ↓
Qwen3.6-27B
```

The frontend requires no Vite, Webpack, or Node build step:

- `frontend/index.html` — Alpine templates and page structure
- `frontend/app.js` — state, interactions, API calls, and SSE handling
- `frontend/styles.css` — design system and responsive styles
- `frontend/i18n/` — interface translations

## Requirements

- Python 3.12+
- macOS or Linux
- An accessible OpenAI-compatible Chat Completions service
- A Claude Agent SDK runtime environment

## Installation

### macOS

```bash
bash scripts/install-macos.sh
```

### Linux

```bash
bash scripts/install-linux.sh
```

### Manual start

```bash
uv sync
uv run python -m backend.main
```

Open the application at:

```text
http://127.0.0.1:8765
```

## Model configuration

Configure the primary conversation model in `.env`:

```env
CODEX_GATEWAY_BASE_URL=http://your-host:8000/v1
CODEX_GATEWAY_API_KEY=replace-with-your-key
MUSELAB_DEFAULT_MODEL=codex:Qwen3.6-27B
MUSELAB_MODEL=codex:Qwen3.6-27B
```

`CODEX_GATEWAY_BASE_URL` may point to either the server root or its `/v1` base. MuseLab normalizes it to:

```text
POST /v1/chat/completions
```

Do not append `/chat/completions` to the base URL more than once.

## Automatic session titles

The title model may use the same OpenAI-compatible service as the primary chat model:

```env
MUSELAB_TITLE_LLM_URL=http://your-host:8000/v1/chat/completions
MUSELAB_TITLE_LLM_API_KEY=replace-with-your-key
MUSELAB_TITLE_LLM_MODEL=Qwen3.6-27B
```

After the first response completes, title generation runs in the background. A delayed generated title never overwrites a title that the user renamed manually.

## Data storage

The archive root is configured through `MUSELAB_ROOT`:

```env
MUSELAB_ROOT=/absolute/path/to/archive
```

The project also maintains:

- `sessions/index.json` — session metadata
- `sessions/*.sidecar.json` — message annotations and attachment metadata
- `provider_overrides.json` — provider overrides
- `.env` — service, model, and credential configuration

These files may contain personal information or credentials and should not be committed to a public repository.

## Common commands

### Start

```bash
uv run python -m backend.main
```

### Start in the background

```bash
nohup uv run python -m backend.main >/tmp/muselab.log 2>&1 &
```

### Stop

```bash
pkill -f "python.*backend.main"
```

### View logs

```bash
tail -f /tmp/muselab.log
```

### Run tests

```bash
.venv/bin/pytest -q
```

## Security recommendations

- Never commit `.env`, API keys, session data, or personal archives.
- Prefer HTTPS model endpoints; HTTP transmits credentials and conversation content in plaintext.
- Rotate an API key immediately if it appears in chat, logs, screenshots, or source history.
- When exposing MuseLab beyond localhost, use a reverse proxy, HTTPS, and a strong authentication token.
- Back up the archive, sessions, and provider configuration regularly.

## Project structure

```text
backend/                 FastAPI, sessions, agent runtime, and protocol bridge
frontend/                Alpine.js single-page application
docs/                    User and architecture documentation
scripts/                 Installation, diagnostics, and maintenance scripts
sessions/                Local session metadata
tests/                   Backend, frontend, and protocol conversion tests
provider_overrides.json  Provider customization
```

## Documentation

- [Quick start](docs/quickstart.md)
- [Configuration](docs/configuration.md)
- [Providers](docs/providers.md)
- [Model routing](docs/routing.md)
- [Architecture](docs/architecture.md)
- [Session internals](docs/backend-sessions.md)
- [Data and backup](docs/data-and-backup.md)
- [Troubleshooting](docs/troubleshooting.md)

## License

This project is used and distributed under the [MIT License](LICENSE). Distributions and modified versions must retain the copyright notice and permission text required by the license.
