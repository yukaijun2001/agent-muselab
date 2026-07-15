"""Anthropic Messages -> OpenAI Chat Completions bridge for Codex Gateway.

Claude Agent SDK remains the agent runtime (tools/MCP/session handling), while
this small bridge lets a ``codex:`` provider use an OpenAI-compatible upstream.
"""
from __future__ import annotations

import hmac
import json
import os
import uuid
from typing import Any, AsyncIterator

import aiohttp
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse


router = APIRouter(prefix="/api/codex-openai", tags=["codex-openai"])


def openai_chat_completions_url(base: str) -> str:
    """Normalize either an OpenAI root or /v1 base to chat/completions."""
    base = (base or "").strip().rstrip("/")
    if not base:
        raise HTTPException(503, "CODEX_GATEWAY_BASE_URL is not configured")
    if base.endswith("/chat/completions"):
        return base
    if not base.endswith("/v1"):
        base += "/v1"
    return base + "/chat/completions"


def _upstream_url() -> str:
    # Use the same live provider resolution as Settings/probe. This honors a
    # provider editor override as well as CODEX_GATEWAY_BASE_URL from .env.
    from . import endpoints
    provider = endpoints.lookup("codex:Qwen3.6-27B")
    base = endpoints._resolve_base_url("CODEX_GATEWAY_API_KEY", provider)
    return openai_chat_completions_url(base)


def _check_key(request: Request) -> str:
    expected = os.environ.get("CODEX_GATEWAY_API_KEY", "")
    supplied = request.headers.get("x-api-key", "")
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        supplied = auth[7:].strip()
    if not expected or not hmac.compare_digest(supplied, expected):
        raise HTTPException(401, "invalid API key")
    return expected


def _openai_content(content: Any) -> Any:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content or "")
    out: list[dict[str, Any]] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        typ = block.get("type")
        if typ == "text":
            out.append({"type": "text", "text": block.get("text", "")})
        elif typ == "image":
            src = block.get("source") or {}
            if src.get("type") == "base64":
                url = f"data:{src.get('media_type', 'image/png')};base64,{src.get('data', '')}"
                out.append({"type": "image_url", "image_url": {"url": url}})
            elif src.get("url"):
                out.append({"type": "image_url", "image_url": {"url": src["url"]}})
    return out or ""


def _convert_messages(body: dict[str, Any]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    system = body.get("system")
    if system:
        if isinstance(system, list):
            system = "\n".join(
                str(x.get("text", "")) for x in system if isinstance(x, dict)
            )
        messages.append({"role": "system", "content": str(system)})

    for msg in body.get("messages") or []:
        role, content = msg.get("role"), msg.get("content", "")
        blocks = content if isinstance(content, list) else []
        if role == "assistant" and blocks:
            text = "".join(
                str(b.get("text", "")) for b in blocks
                if isinstance(b, dict) and b.get("type") == "text"
            )
            tool_calls = []
            for b in blocks:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    tool_calls.append({
                        "id": b.get("id"), "type": "function",
                        "function": {
                            "name": b.get("name", ""),
                            "arguments": json.dumps(b.get("input") or {}, ensure_ascii=False),
                        },
                    })
            converted: dict[str, Any] = {"role": "assistant", "content": text or None}
            if tool_calls:
                converted["tool_calls"] = tool_calls
            messages.append(converted)
        elif role == "user" and blocks:
            normal_blocks = []
            for b in blocks:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    result = b.get("content", "")
                    if isinstance(result, list):
                        result = "\n".join(
                            str(x.get("text", "")) for x in result if isinstance(x, dict)
                        )
                    messages.append({
                        "role": "tool", "tool_call_id": b.get("tool_use_id", ""),
                        "content": str(result),
                    })
                else:
                    normal_blocks.append(b)
            converted_content = _openai_content(normal_blocks)
            if converted_content:
                messages.append({"role": "user", "content": converted_content})
        else:
            messages.append({"role": role, "content": _openai_content(content)})
    # Some Claude CLI resume transcripts contain additional role=system
    # frames among normal messages. Strict OpenAI-compatible servers (notably
    # this Qwen gateway) reject those with "System message must be at the
    # beginning." Collapse every system/developer frame into ONE leading
    # system message while preserving all non-system message order.
    system_parts: list[str] = []
    normal: list[dict[str, Any]] = []
    for message in messages:
        if message.get("role") in ("system", "developer"):
            value = message.get("content", "")
            if isinstance(value, list):
                value = "\n".join(
                    str(x.get("text", "")) for x in value if isinstance(x, dict)
                )
            if str(value).strip():
                system_parts.append(str(value).strip())
        else:
            normal.append(message)
    if system_parts:
        return [{"role": "system", "content": "\n\n".join(system_parts)}, *normal]
    return normal


def _openai_payload(body: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": str(body.get("model", "")).removeprefix("codex:"),
        "messages": _convert_messages(body),
        "stream": bool(body.get("stream")),
    }
    if payload["stream"]:
        payload["stream_options"] = {"include_usage": True}
    if body.get("max_tokens") is not None:
        payload["max_tokens"] = body["max_tokens"]
    if body.get("temperature") is not None:
        payload["temperature"] = body["temperature"]
    tools = []
    for tool in body.get("tools") or []:
        tools.append({"type": "function", "function": {
            "name": tool.get("name", ""),
            "description": tool.get("description", ""),
            "parameters": tool.get("input_schema") or {"type": "object", "properties": {}},
        }})
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    return payload


def _anthropic_response(data: dict[str, Any], request_model: str) -> dict[str, Any]:
    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    content: list[dict[str, Any]] = []
    if msg.get("content"):
        content.append({"type": "text", "text": msg["content"]})
    for call in msg.get("tool_calls") or []:
        fn = call.get("function") or {}
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {"raw": fn.get("arguments", "")}
        content.append({"type": "tool_use", "id": call.get("id") or f"toolu_{uuid.uuid4().hex}",
                        "name": fn.get("name", ""), "input": args})
    usage = data.get("usage") or {}
    return {
        "id": data.get("id") or f"msg_{uuid.uuid4().hex}", "type": "message",
        "role": "assistant", "model": request_model, "content": content,
        "stop_reason": "tool_use" if msg.get("tool_calls") else "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": usage.get("prompt_tokens", 0),
                  "output_tokens": usage.get("completion_tokens", 0)},
    }


def _sse(event: str, data: dict[str, Any]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()


async def _stream_upstream(resp: aiohttp.ClientResponse, model: str) -> AsyncIterator[bytes]:
    mid = f"msg_{uuid.uuid4().hex}"
    yield _sse("message_start", {"type": "message_start", "message": {
        "id": mid, "type": "message", "role": "assistant", "model": model,
        "content": [], "stop_reason": None, "stop_sequence": None,
        "usage": {"input_tokens": 0, "output_tokens": 0}}})
    text_started = False
    tool_indexes: dict[int, int] = {}
    next_block = 0
    usage = {"output_tokens": 0}
    # readline() preserves SSE record boundaries even when TCP splits a JSON
    # data line across packets; iterating arbitrary chunks would drop it.
    while True:
        raw = await resp.content.readline()
        if not raw:
            break
        for line in raw.decode("utf-8", "replace").splitlines():
            if not line.startswith("data:"):
                continue
            value = line[5:].strip()
            if not value or value == "[DONE]":
                continue
            try:
                chunk = json.loads(value)
            except json.JSONDecodeError:
                continue
            u = chunk.get("usage") or {}
            if u:
                usage = {"input_tokens": u.get("prompt_tokens", 0),
                         "output_tokens": u.get("completion_tokens", 0)}
            delta = ((chunk.get("choices") or [{}])[0].get("delta") or {})
            text = delta.get("content")
            if text:
                if not text_started:
                    yield _sse("content_block_start", {"type": "content_block_start", "index": next_block,
                               "content_block": {"type": "text", "text": ""}})
                    text_started = True
                yield _sse("content_block_delta", {"type": "content_block_delta", "index": 0,
                           "delta": {"type": "text_delta", "text": text}})
            for call in delta.get("tool_calls") or []:
                oi = int(call.get("index", 0))
                if oi not in tool_indexes:
                    if text_started:
                        yield _sse("content_block_stop", {"type": "content_block_stop", "index": 0})
                        text_started = False
                        next_block = 1
                    ai = next_block + len(tool_indexes)
                    tool_indexes[oi] = ai
                    fn = call.get("function") or {}
                    yield _sse("content_block_start", {"type": "content_block_start", "index": ai,
                               "content_block": {"type": "tool_use", "id": call.get("id") or f"toolu_{uuid.uuid4().hex}",
                                                 "name": fn.get("name", ""), "input": {}}})
                args = (call.get("function") or {}).get("arguments")
                if args:
                    yield _sse("content_block_delta", {"type": "content_block_delta", "index": tool_indexes[oi],
                               "delta": {"type": "input_json_delta", "partial_json": args}})
    if text_started:
        yield _sse("content_block_stop", {"type": "content_block_stop", "index": 0})
    for ai in tool_indexes.values():
        yield _sse("content_block_stop", {"type": "content_block_stop", "index": ai})
    yield _sse("message_delta", {"type": "message_delta",
               "delta": {"stop_reason": "tool_use" if tool_indexes else "end_turn", "stop_sequence": None},
               "usage": usage})
    yield _sse("message_stop", {"type": "message_stop"})


@router.post("/messages")
@router.post("/v1/messages")
@router.post("/v1/v1/messages")
async def messages(request: Request):
    key = _check_key(request)
    body = await request.json()
    payload = _openai_payload(body)
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    timeout = aiohttp.ClientTimeout(total=None, connect=30, sock_read=600)
    session = aiohttp.ClientSession(timeout=timeout)
    try:
        resp = await session.post(_upstream_url(), headers=headers, json=payload)
        if resp.status >= 400:
            detail = await resp.text()
            resp.release()
            await session.close()
            return JSONResponse({"type": "error", "error": {"type": "api_error", "message": detail}},
                                status_code=resp.status)
        if payload["stream"]:
            async def generate():
                try:
                    async for item in _stream_upstream(resp, body.get("model", "")):
                        yield item
                finally:
                    resp.release()
                    await session.close()
            return StreamingResponse(generate(), media_type="text/event-stream")
        data = await resp.json()
        resp.release()
        await session.close()
        return JSONResponse(_anthropic_response(data, body.get("model", "")))
    except Exception:
        await session.close()
        raise
