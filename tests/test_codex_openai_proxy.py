from backend.codex_openai_proxy import (
    _anthropic_response, _openai_payload, openai_chat_completions_url,
)


def test_openai_url_accepts_root_v1_or_full_path():
    expected = "http://relay.test:18080/v1/chat/completions"
    assert openai_chat_completions_url("http://relay.test:18080") == expected
    assert openai_chat_completions_url("http://relay.test:18080/v1") == expected
    assert openai_chat_completions_url(expected) == expected


def test_anthropic_request_converts_messages_and_tools():
    payload = _openai_payload({
        "model": "codex:deepseek-chat", "stream": True, "max_tokens": 123,
        "system": [{"type": "text", "text": "Be useful"}],
        "messages": [
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "call_1", "name": "Read",
                 "input": {"file_path": "/tmp/a"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "call_1", "content": "ok"},
                {"type": "text", "text": "continue"},
            ]},
        ],
        "tools": [{"name": "Read", "description": "read file",
                   "input_schema": {"type": "object", "properties": {}}}],
    })
    assert payload["model"] == "deepseek-chat"
    assert payload["messages"][0] == {"role": "system", "content": "Be useful"}
    assert payload["messages"][1]["tool_calls"][0]["function"]["name"] == "Read"
    assert payload["messages"][2] == {"role": "tool", "tool_call_id": "call_1", "content": "ok"}
    assert payload["messages"][3]["content"][0]["text"] == "continue"
    assert payload["tools"][0]["function"]["name"] == "Read"
    assert payload["stream_options"] == {"include_usage": True}


def test_all_system_frames_are_merged_at_beginning():
    payload = _openai_payload({
        "model": "codex:Qwen3.6-27B",
        "system": "top-level instructions",
        "messages": [
            {"role": "user", "content": "hello"},
            {"role": "system", "content": "resumed session instructions"},
            {"role": "assistant", "content": "hi"},
            {"role": "developer", "content": "extra policy"},
        ],
    })
    roles = [m["role"] for m in payload["messages"]]
    assert roles == ["system", "user", "assistant"]
    assert "top-level instructions" in payload["messages"][0]["content"]
    assert "resumed session instructions" in payload["messages"][0]["content"]
    assert "extra policy" in payload["messages"][0]["content"]


def test_openai_tool_response_converts_to_anthropic():
    result = _anthropic_response({
        "id": "chatcmpl_1",
        "choices": [{"message": {"content": None, "tool_calls": [{
            "id": "call_1", "type": "function",
            "function": {"name": "Read", "arguments": '{"file_path":"a"}'},
        }]}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 4},
    }, "codex:deepseek-chat")
    assert result["stop_reason"] == "tool_use"
    assert result["content"][0]["type"] == "tool_use"
    assert result["content"][0]["input"] == {"file_path": "a"}
    assert result["usage"] == {"input_tokens": 10, "output_tokens": 4}
