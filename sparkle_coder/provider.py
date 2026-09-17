"""Small OpenAI-compatible HTTP adapter for hosted and self-served Nemotron."""

from dataclasses import dataclass
import json
import time
import urllib.error
import urllib.request
import uuid

from .config import Config


class ModelError(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ModelError("The API redirected the request. Set the final, trusted base_url explicitly.")


@dataclass
class Completion:
    content: str
    calls: list[dict]
    usage: dict
    finish_reason: str = "stop"


def parse_completion(data: dict, tool_format: str) -> Completion:
    try:
        choice = data["choices"][0]
        message = choice["message"]
        if not isinstance(message, dict):
            raise ValueError("Expected a message object.")
        content = message.get("content") or ""
        reason = choice.get("finish_reason") or "stop"
        if not isinstance(content, str):
            raise ValueError("Expected text content.")
        calls = message.get("tool_calls") or []
        if tool_format == "json" and not calls and reason != "length":
            text = content.strip()
            fence = chr(96) * 3
            if text.startswith(fence) and text.endswith(fence):
                text = text.split("\n", 1)[1].rsplit(fence, 1)[0].strip()
            obj = json.loads(text)
            if not isinstance(obj, dict):
                raise ValueError("JSON tool mode expects an object.")
            if isinstance(obj.get("final"), str):
                content = obj["final"]
            elif isinstance(obj.get("tool"), str) and isinstance(obj.get("arguments"), dict):
                calls = [{"id": "call_" + uuid.uuid4().hex[:12], "type": "function",
                          "function": {"name": obj["tool"], "arguments": json.dumps(obj["arguments"])}}]
                content = ""
            else:
                raise ValueError('Expected {"tool": "...", "arguments": {...}} or {"final": "..."}.')
        if not isinstance(calls, list) or len(calls) > 16:
            raise ValueError("Expected at most 16 tool calls.")
        normalized, ids = [], set()
        for call in calls:
            function = call["function"]
            if not isinstance(function["name"], str):
                raise ValueError("Invalid tool name.")
            arguments = function["arguments"]
            if isinstance(arguments, dict):
                arguments = json.dumps(arguments)
            if not isinstance(arguments, str) or len(arguments) > 300000:
                raise ValueError("Invalid or oversized tool arguments.")
            call_id = call.get("id") or "call_" + uuid.uuid4().hex[:12]
            if not isinstance(call_id, str) or call_id in ids:
                raise ValueError("Tool call IDs must be unique strings.")
            ids.add(call_id)
            normalized.append({"id": call_id, "type": "function",
                               "function": {"name": function["name"], "arguments": arguments}})
        usage = data.get("usage") or {}
        usage = {key: max(0, int(usage.get(key) or 0))
                 for key in ("prompt_tokens", "completion_tokens")}
        return Completion(content, normalized, usage, reason)
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        raise ModelError(f"Invalid model response: {exc}") from None


class NemotronClient:
    def __init__(self, config: Config):
        self.config = config
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, path: str, body: dict | None = None):
        headers = {"Accept": "application/json", "User-Agent": "sparkle-coder/0.3.2"}
        if self.config.api_key:
            headers["Authorization"] = "Bearer " + self.config.api_key
        payload = None if body is None else json.dumps(body).encode("utf-8")
        if payload is not None:
            headers["Content-Type"] = "application/json"
        for attempt in range(3):
            request = urllib.request.Request(self.config.base_url.rstrip("/") + path,
                                             data=payload, headers=headers)
            try:
                with self.opener.open(request, timeout=self.config.request_timeout) as response:
                    raw = response.read(12_000_001)
                if len(raw) > 12_000_000:
                    raise ModelError("API response exceeded the 12 MB limit.")
                return json.loads(raw)
            except urllib.error.HTTPError as exc:
                exc.close()
                if exc.code in (429, 500, 502, 503, 504) and attempt < 2:
                    try:
                        delay = min(10, max(1, float(exc.headers.get("Retry-After", 2 ** attempt))))
                    except ValueError:
                        delay = 2 ** attempt
                    time.sleep(delay)
                    continue
                hints = {
                    401: "Check the API key configured for this model endpoint.",
                    403: "Check model access and endpoint permissions.",
                    404: "Check the base URL and exact model ID.",
                    400: "Check model tool support and extra_body; try JSON tool mode for a server without a tool parser.",
                    429: "The endpoint is rate-limited; resume this session later.",
                }
                raise ModelError(f"Model API HTTP {exc.code}. {hints.get(exc.code, 'Try again or check server logs.')}") from None
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                raise ModelError(f"Cannot reach the model endpoint ({type(exc).__name__}). "
                                 "Check its address, network access, and timeout.") from None
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise ModelError("The endpoint did not return valid JSON.") from None

    def models(self) -> list[str]:
        data = self.request("/models")
        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            raise ModelError("The /models endpoint did not return a model list.")
        return sorted(item["id"] for item in data["data"]
                      if isinstance(item, dict) and isinstance(item.get("id"), str))

    def complete(self, messages: list[dict], schemas: list[dict]) -> Completion:
        if self.config.tool_format == "json":
            # Chat-only servers must not receive native tool messages.
            converted = []
            for message in messages:
                if message["role"] == "tool":
                    converted.append({"role": "user", "content": "TOOL RESULT:\n" + message["content"]})
                elif message.get("tool_calls"):
                    for call in message["tool_calls"]:
                        try:
                            arguments = json.loads(call["function"]["arguments"])
                        except json.JSONDecodeError:
                            arguments = {"invalid_previous_arguments": call["function"]["arguments"]}
                        converted.append({"role": "assistant", "content": json.dumps({
                            "tool": call["function"]["name"],
                            "arguments": arguments,
                        })})
                else:
                    converted.append(message)
            messages = converted
        body = {
            "model": self.config.model, "messages": messages, "stream": False,
            "temperature": self.config.temperature, "top_p": self.config.top_p,
            "max_tokens": self.config.max_tokens, **self.config.extra_body,
        }
        if self.config.tool_format == "native":
            body.update({"tools": schemas, "tool_choice": "auto"})
        return parse_completion(self.request("/chat/completions", body), self.config.tool_format)
