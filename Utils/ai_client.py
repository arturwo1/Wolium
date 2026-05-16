from dataclasses import dataclass, field
from typing import Any
from random import shuffle
from huggingface_hub import AsyncInferenceClient
from asyncio import sleep
from httpx import AsyncClient
from Utils.config import o_url

@dataclass
class HuggingFaceConfig:
  type: str = "huggingface"
  api_keys: list[str] = field(default_factory=list)
  models: list[str] = field(default_factory=list)
  priority: int = 0

@dataclass
class OllamaConfig:
  type: str = "ollama"
  base_url: str = o_url
  models: list[str] = field(default_factory=list)
  priority: int = 10

@dataclass
class ToolCall:
  id: str
  name: str
  arguments: str

@dataclass
class CompletionResult:
  content: str
  tool_calls: list[ToolCall]
  provider: str
  model: str

class HuggingFaceProvider:
  def __init__(self, config: HuggingFaceConfig):
    self.config = config

  def _make_client(self) -> AsyncInferenceClient:
    from random import randint
    keys = self.config.api_keys
    mdls = self.config.models
    return AsyncInferenceClient(
      model=mdls[randint(0, len(mdls) - 1)],
      api_key=keys[randint(0, len(keys) - 1)],
    )

  async def complete(self, messages: list, tools: list, temperature: float, max_tokens: int, top_p: float) -> CompletionResult:
    client = self._make_client()
    completion = await client.chat.completions.create(
      model=client.model,
      messages=messages,
      max_tokens=max_tokens,
      temperature=temperature,
      top_p=top_p,
      tools=tools or None,
      tool_choice="auto" if tools else None,
    )
    msg = completion.choices[0].message
    raw_tool_calls = getattr(msg, "tool_calls", None) or []
    tool_calls = [
      ToolCall(id=tc.id, name=tc.function.name, arguments=tc.function.arguments)
      for tc in raw_tool_calls
    ]
    return CompletionResult(
      content=msg.content or "",
      tool_calls=tool_calls,
      provider="huggingface",
      model=client.model,
    )

class OllamaProvider:
  def __init__(self, config: OllamaConfig):
    self.config = config

  def _pick_model(self) -> str:
    from random import choice
    return choice(self.config.models)

  async def complete(self, messages: list, tools: list, temperature: float, max_tokens: int, top_p: float) -> CompletionResult:
    model = self._pick_model()
    url = f"{self.config.base_url.rstrip('/')}/v1/chat/completions"

    payload: dict[str, Any] = {
      "model": model,
      "messages": messages,
      "temperature": temperature,
      "max_tokens": max_tokens,
      "top_p": top_p,
      "stream": False,
    }
    if tools:
      payload["tools"] = tools
      payload["tool_choice"] = "auto"

    async with AsyncClient(timeout=120) as client:
      resp = await client.post(url, json=payload)
      resp.raise_for_status()
      data = resp.json()

    msg = data["choices"][0]["message"]
    raw_tool_calls = msg.get("tool_calls") or []
    tool_calls = [
      ToolCall(
        id=tc.get("id", ""),
        name=tc["function"]["name"],
        arguments=tc["function"]["arguments"],
      )
      for tc in raw_tool_calls
    ]
    return CompletionResult(
      content=msg.get("content") or "",
      tool_calls=tool_calls,
      provider="ollama",
      model=model,
    )

_RETRYABLE = (
  'Connection aborted', 'Payment Required', 'Bad Gateway',
  'Gateway Timeout', 'overloaded', 'Model too busy', 'Internal Server Error',
)

def is_retryable(e: Exception) -> bool:
  s = str(e)
  return any(marker in s for marker in _RETRYABLE)

class AIClient:
  def __init__(self, configs: list):
    self._providers: list[tuple[int, Any]] = []
    for cfg in configs:
      if cfg.type == "huggingface" and cfg.api_keys and cfg.models:
        self._providers.append((cfg.priority, HuggingFaceProvider(cfg)))
      elif cfg.type == "ollama" and cfg.models:
        self._providers.append((cfg.priority, OllamaProvider(cfg)))
    self._providers.sort(key=lambda x: x[0])

  async def complete(
    self,
    messages: list,
    tools: list | None = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    top_p: float = 0.9,
  ) -> CompletionResult:
    last_exc: Exception | None = None
    for _, provider in self._providers:
      try:
        return await provider.complete(messages, tools or [], temperature, max_tokens, top_p)
      except Exception as e:
        last_exc = e
        if is_retryable(e):
          await sleep(1)
          continue
        continue
    raise last_exc or RuntimeError("No AI providers available")