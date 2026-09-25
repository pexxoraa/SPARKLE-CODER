"""Small OpenAI-compatible HTTP adapter for hosted and self-served Nemotron."""

from dataclasses import dataclass
import json
import queue
import threading
import time
import urllib.error
import urllib.request
import uuid

from .config import Config
from . import __version__


class ModelError(RuntimeError):
    def __init__(self, message, *, action="retry"):
        super().__init__(message)
        self.action = action


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
        usage = ({key: max(0, int(usage[key])) for key in ("prompt_tokens", "completion_tokens")}
                 if isinstance(usage, dict) and all(usage.get(k) is not None for k in ("prompt_tokens", "completion_tokens")) else {})
        return Completion(content, normalized, usage, reason)
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        raise ModelError(f"Invalid model response: {exc}") from None


class NemotronClient:
    def __init__(self, config: Config):
        self.config = config
        self.opener = urllib.request.build_opener(NoRedirect())
        self.observe = lambda *_: None
        self.should_stop = lambda: False

    def bind_runtime(self, observe, should_stop):
        self.observe, self.should_stop = observe, should_stop

    def _read(self, request, *, timeout=None):
        # A cancelled request may finish at the provider, but its response cannot
        # execute tools. The run itself stops promptly, even during a slow socket read.
        completed = queue.Queue(maxsize=1)
        def fetch():
            try:
                with self.opener.open(request, timeout=self.config.request_timeout if timeout is None else timeout) as response:
                    result = response.read(12_000_001)
            except Exception as exc:
                if isinstance(exc, urllib.error.HTTPError):
                    exc.close()
                result = exc
            completed.put(result)
        deadline = None if timeout is None else time.monotonic() + timeout
        threading.Thread(target=fetch, name="nemotron-http", daemon=True).start()
        while not self.should_stop():
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError("Optional endpoint response timed out.")
            try:
                result = completed.get(timeout=0.1)
            except queue.Empty:
                continue
            if isinstance(result, Exception):
                raise result
            return result
        raise ModelError("Stopped by the user. The provider may still finish the submitted request.")

    def wait_retry(self, delay):
        while delay > 0:
            if self.should_stop():
                raise ModelError("Stopped by the user during connection recovery.")
            interval = min(0.1, delay)
            time.sleep(interval)
            delay -= interval

    def request(self, path: str, body: dict | None = None):
        headers = {"Accept": "application/json", "User-Agent": "sparkle-coder/" + __version__}
        if self.config.api_key:
            headers["Authorization"] = "Bearer " + self.config.api_key
        payload = None if body is None else json.dumps(body).encode("utf-8")
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if payload is not None and self.config._runtime_cloud:
            headers["Idempotency-Key"] = uuid.uuid4().hex
        attempts = 100 if self.config._runtime_cloud else 3
        recovery_deadline = time.monotonic() + max(300, self.config.request_timeout)
        retry_transport = body is None or self.config._runtime_cloud
        for attempt in range(attempts):
            if self.should_stop():
                raise ModelError("Stopped by the user before the model request.")
            request = urllib.request.Request(self.config.base_url.rstrip("/") + path,
                                             data=payload, headers=headers)
            try:
                raw = self._read(request)
                if len(raw) > 12_000_000:
                    raise ModelError("API response exceeded the 12 MB limit.")
                return json.loads(raw)
            except urllib.error.HTTPError as exc:
                exc.close()
                if (exc.code == 429 or retry_transport and exc.code in (500, 502, 503, 504) or
                        self.config._runtime_cloud and exc.code == 409 and exc.headers.get("Retry-After")) and attempt < attempts - 1 and time.monotonic() < recovery_deadline:
                    if self.config._runtime_cloud and exc.code == 429 and exc.headers.get('X-Sparkle-Safe-Retry') == 'true':
                        # The gateway confirmed no inference charge for this ID.
                        headers['Idempotency-Key'] = uuid.uuid4().hex
                    try:
                        delay = min(60, max(1, float(exc.headers.get("Retry-After", 2 ** attempt))))
                    except (ValueError, TypeError):
                        delay = min(60, 2 ** attempt)
                    self.observe("model_retry", {"attempt": attempt + 2, "delay": delay,
                                                 "reason": f"Model API HTTP {exc.code}"})
                    self.wait_retry(delay)
                    continue
                hints = {
                    401: ("Open Account and reconnect this device." if self.config._runtime_cloud else "Open Connect Nemotron, replace the API key, test the connection, then resume this task."),
                    402: "Not enough available credits. Open Account to check the balance and request a top-up.",
                    409: "An earlier request is still running or needs admin review. Open Account; this request will not be charged twice.",
                    403: "Check model access and endpoint permissions.",
                    404: "Check the base URL and exact model ID.",
                    400: "Check model tool support and extra_body; try JSON tool mode for a server without a tool parser.",
                    429: "The endpoint is rate-limited; resume this session later.",
                }
                raise ModelError(f"Model API HTTP {exc.code}. {hints.get(exc.code, 'The endpoint is unavailable. Resume this saved task when it recovers.')}",
                                 action="connection" if exc.code in (400, 401, 402, 403, 404) else "retry") from None
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if retry_transport and attempt < attempts - 1 and time.monotonic() < recovery_deadline:
                    delay = min(15, 2 ** attempt)
                    self.observe("model_retry", {"attempt": attempt + 2, "delay": delay,
                                                 "reason": f"Connection interrupted ({type(exc).__name__})"})
                    self.wait_retry(delay)
                    continue
                hint = ("For a slow model, increase API response timeout under Connect Nemotron → Run and connection settings. "
                        if isinstance(exc, TimeoutError) or isinstance(getattr(exc, "reason", None), TimeoutError)
                        else "Check the server address and network connection. ")
                raise ModelError(f"Cannot reach the model endpoint ({type(exc).__name__}). " +
                                 ("Connection recovery attempts failed. " if retry_transport else "The request was not automatically repeated because the provider may already have processed it. ") + hint + "Resume this task; your work is saved.") from None
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise ModelError("The endpoint did not return valid JSON.") from None

    def models(self) -> list[str]:
        data = self.request("/models")
        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            raise ModelError("The /models endpoint did not return a model list.")
        return sorted(item["id"] for item in data["data"]
                      if isinstance(item, dict) and isinstance(item.get("id"), str))

    def balance(self) -> dict | None:
        # Optional metadata must not inherit the model's long timeout/retries.
        headers = {"Accept": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = "Bearer " + self.config.api_key
        try:
            request = urllib.request.Request(self.config.base_url.rstrip("/") + "/balance", headers=headers)
            raw = self._read(request, timeout=3)
            if len(raw) > 65536:
                return None
            data = json.loads(raw)
        except (ModelError, OSError, ValueError):
            return None
        if isinstance(data, dict) and type(data.get("balance_tokens")) is int and data["balance_tokens"] >= 0:
            return data
        return None

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
        if "nemotron-3-" in self.config.model:
            body["chat_template_kwargs"] = {**body.get("chat_template_kwargs", {}),
                "enable_thinking": self.config.efficiency == "thorough", "force_nonempty_content": True}
        if self.config.tool_format == "native":
            body.update({"tools": schemas, "tool_choice": "auto"})
        return parse_completion(self.request("/chat/completions", body), self.config.tool_format)
