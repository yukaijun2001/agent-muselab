"""Lightweight OpenAI-compatible LLM used only for session titles."""
from __future__ import annotations

import json
import os
import re

import aiohttp


def _config() -> tuple[str, str, str]:
    url = os.environ.get("MUSELAB_TITLE_LLM_URL", "").strip()
    key = os.environ.get("MUSELAB_TITLE_LLM_API_KEY", "").strip()
    model = os.environ.get("MUSELAB_TITLE_LLM_MODEL", "").strip()
    return url, key, model


def _clean_title(value: str, limit: int = 24) -> str:
    title = (value or "").strip().splitlines()[0].strip()
    title = re.sub(r"^(标题|会话标题|title)\s*[:：]\s*", "", title,
                   flags=re.IGNORECASE)
    title = title.strip(" `\"'《》【】[]。.，,：:")
    if len(title) > limit:
        title = title[:limit].rstrip(" ，,。.!！?？:：")
    return title


async def generate_session_title(user_text: str, assistant_text: str = "") -> str:
    """Return a concise topic title, or empty string on configuration/error."""
    url, key, model = _config()
    if not (url and key and model and user_text.strip()):
        return ""
    prompt = (
        "请根据下面对话生成一个简洁、具体的中文会话标题。要求：8到18个汉字；"
        "直接输出标题；不要引号、句号、解释或‘标题：’前缀；概括核心任务而不是照抄问题。\n\n"
        f"用户：{user_text[:2000]}\n"
        f"助手：{assistant_text[:2000]}"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是对话标题生成器，只输出一个短标题。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 64,
        "stream": False,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    timeout = aiohttp.ClientTimeout(total=20, connect=8)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as client:
            async with client.post(url, json=payload, headers=headers) as response:
                if response.status != 200:
                    return ""
                data = await response.json(content_type=None)
        content = (((data.get("choices") or [{}])[0].get("message") or {})
                   .get("content") or "")
        # Some reasoning models wrap the final title after </think>.
        if "</think>" in content:
            content = content.rsplit("</think>", 1)[-1]
        return _clean_title(content)
    except (aiohttp.ClientError, TimeoutError, ValueError, json.JSONDecodeError):
        return ""
