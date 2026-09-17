"""Configuration with environment or in-memory credentials; no keys in config files."""

from dataclasses import dataclass, field, fields
import os
from pathlib import Path
import tomllib
from urllib.parse import urlsplit


@dataclass
class Config:
    _runtime_api_key: str | None = field(default=None, init=False, repr=False)
    base_url: str = "https://integrate.api.nvidia.com/v1"
    model: str = "nvidia/nemotron-3-super-120b-a12b"
    api_key_env: str = "NVIDIA_API_KEY"
    tool_format: str = "native"
    temperature: float = 1.0
    top_p: float = 0.95
    max_tokens: int = 16000
    context_chars: int = 120000
    # Run caps are optional. None means unlimited; Stop remains available in the UI.
    max_steps: int | None = None
    max_seconds: int | None = None
    max_total_tokens: int | None = None
    request_timeout: int = 120
    command_timeout: int = 120
    execution: str = "local"
    auto_approve: bool = False
    docker_image: str = "sparkle-coder-tools:local"
    docker_network: bool = False
    allow_insecure_http: bool = False
    verify: list[str] = field(default_factory=list)
    extra_body: dict = field(default_factory=lambda: {
        "chat_template_kwargs": {"force_nonempty_content": True}
    })

    @property
    def api_key(self) -> str:
        if self._runtime_api_key is not None:
            return self._runtime_api_key
        return os.environ.get(self.api_key_env, "")

    def validate(self) -> None:
        for name in ("base_url", "model", "api_key_env", "docker_image"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} must be a nonempty string.")
        for name in ("auto_approve", "docker_network", "allow_insecure_http"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be true or false, without quotes.")
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("base_url must be an HTTP(S) API base URL ending in /v1.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Keep credentials and query parameters out of base_url.")
        local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
        if parsed.scheme == "http" and not local and not self.allow_insecure_http:
            raise ValueError("Remote endpoints require HTTPS; local loopback HTTP is allowed.")
        if self.tool_format not in ("native", "json"):
            raise ValueError("tool_format must be native or json.")
        if self.execution not in ("local", "docker"):
            raise ValueError("execution must be local or docker.")
        if type(self.max_tokens) is not int or self.max_tokens <= 0:
            raise ValueError("max_tokens must be a positive integer.")
        for name in ("max_steps", "max_seconds", "max_total_tokens"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value <= 0):
                raise ValueError(f"{name} must be a positive integer or null for unlimited.")
        for name in ("request_timeout", "command_timeout"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer.")
        if type(self.context_chars) is not int or self.context_chars < 12000:
            raise ValueError("context_chars must be at least 12000.")
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("model must be the exact nonempty ID exposed by the server.")
        if (type(self.temperature) not in (int, float) or type(self.top_p) not in (int, float)
                or not 0 <= self.temperature <= 2 or not 0 < self.top_p <= 1):
            raise ValueError("Invalid temperature or top_p.")
        if not isinstance(self.verify, list) or not all(isinstance(x, str) and x.strip() for x in self.verify):
            raise ValueError("verify must be a list of nonempty command strings.")
        if not isinstance(self.extra_body, dict):
            raise ValueError("extra_body must be a TOML table.")
        reserved = {"model", "messages", "tools", "tool_choice", "stream", "max_tokens",
                    "temperature", "top_p", "n", "max_completion_tokens"}
        if reserved.intersection(self.extra_body):
            raise ValueError("extra_body cannot override model, messages, tools, or sampling limits.")

    def require_credentials(self) -> None:
        if urlsplit(self.base_url).hostname == "integrate.api.nvidia.com" and not self.api_key:
            raise ValueError("Add an NVIDIA API key in connection settings before using NVIDIA's hosted API.")

    def public_info(self) -> dict:
        return {"base_url": self.base_url, "model": self.model,
                "tool_format": self.tool_format, "execution": self.execution}


def load_config(workspace: Path, overrides: dict | None = None) -> Config:
    path = workspace / "nemotron.toml"
    if path.is_symlink():
        raise ValueError("nemotron.toml must not be a symlink.")
    data = tomllib.loads(path.read_text("utf-8")) if path.exists() else {}
    allowed = {f.name for f in fields(Config) if f.init}
    unknown = set(data) - allowed
    if unknown:
        raise ValueError("Unknown configuration keys: " + ", ".join(sorted(unknown)))
    data.update({key: value for key, value in {
        "base_url": os.environ.get("NEMOTRON_BASE_URL"),
        "model": os.environ.get("NEMOTRON_MODEL"),
    }.items() if value})
    # Optional run caps use None as an explicit "unlimited" override. This lets
    # the browser and CLI remove legacy caps from an older nemotron.toml.
    unlimited = {"max_steps", "max_seconds", "max_total_tokens"}
    data.update({key: value for key, value in (overrides or {}).items()
                 if value is not None or key in unlimited})
    config = Config(**data)
    config.validate()
    return config


CONFIG_TEMPLATE = '''# Personal Nemotron coding agent. Keep API keys in environment variables or enter them in the app.
base_url = "https://integrate.api.nvidia.com/v1"
model = "nvidia/nemotron-3-super-120b-a12b"
api_key_env = "NVIDIA_API_KEY"
tool_format = "native"

# NVIDIA recommends these sampling settings for Nemotron 3 Super.
temperature = 1.0
top_p = 0.95
max_tokens = 16000
context_chars = 120000
# Run caps are optional. Omit them for unlimited model calls, elapsed time, and total tokens.
# max_steps = 40
# max_seconds = 1800
# max_total_tokens = 250000
request_timeout = 120
command_timeout = 120

# Local commands require approval by default and run with your OS permissions.
execution = "local"
auto_approve = false
docker_image = "sparkle-coder-tools:local"
docker_network = false

# Optional checks run independently whenever the model proposes completion.
# Example: verify = ["python3 -m unittest discover -s tests -v"]
verify = []

[extra_body.chat_template_kwargs]
force_nonempty_content = true
'''
