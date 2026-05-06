"""
llm_client.py
─────────────
统一 LLM 调用层，支持两种模式：
  - ollama  : 调用本地 Ollama API（默认）
  - remote  : 调用任意 OpenAI 兼容接口
              （OpenAI / DeepSeek / 通义千问 / 硅基流动 / 自定义）

运行时配置通过 LLMConfig 数据类持有，优先级：
  请求参数 > 运行时 set_config() > settings 全局默认
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Generator, Optional, Tuple

import requests

from app.config import settings

logger = logging.getLogger(__name__)


# ── 配置数据类 ──────────────────────────────────────────────────────────────
@dataclass
class LLMConfig:
    """LLM 运行时配置，可由前端动态设置"""

    provider: str = "ollama"          # "ollama" | "remote"

    # Ollama 本地配置
    ollama_base_url: str = ""
    ollama_model: str = ""

    # 远程 API 配置（OpenAI 兼容）
    remote_base_url: str = ""         # 如 https://api.deepseek.com/v1
    remote_api_key: str = ""
    remote_model: str = ""            # 如 deepseek-chat / gpt-4o

    # 通用推理参数
    temperature: float = 0.3
    top_p: float = 0.9
    max_tokens: int = 4096

    def effective_ollama_url(self) -> str:
        return self.ollama_base_url or settings.ollama_base_url

    def effective_ollama_model(self) -> str:
        return self.ollama_model or settings.ollama_model


# ── 预置远程服务商配置 ───────────────────────────────────────────────────────
REMOTE_PRESETS = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    },
    "qwen": {
        "name": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-max", "qwen-plus", "qwen-turbo", "qwen-long"],
    },
    "siliconflow": {
        "name": "硅基流动",
        "base_url": "https://api.siliconflow.cn/v1",
        "models": ["deepseek-ai/DeepSeek-V3", "Qwen/Qwen2.5-72B-Instruct", "Pro/deepseek-ai/DeepSeek-R1"],
    },
    "custom": {
        "name": "自定义",
        "base_url": "",
        "models": [],
    },
}


# ── LLM 客户端 ───────────────────────────────────────────────────────────────
class LLMClient:
    """
    统一 LLM 调用客户端。

    全局只有一个单例（llm_client），持有当前运行时配置。
    外部通过 set_config() 更新配置，通过 chat() 调用模型。
    """

    def __init__(self):
        # 初始化为全局默认值
        self._config = LLMConfig(
            provider="ollama",
            ollama_base_url=settings.ollama_base_url,
            ollama_model=settings.ollama_model,
        )

    def set_config(self, config: LLMConfig):
        """更新运行时配置（线程安全：Python GIL 保证赋值原子性）"""
        self._config = config
        logger.info(
            f"[LLMClient] 配置已更新 -> provider={config.provider}, "
            f"model={config.effective_ollama_model() if config.provider == 'ollama' else config.remote_model}"
        )

    def get_config(self) -> LLMConfig:
        return self._config

    # ── Ollama 调用 ─────────────────────────────────────────────────────────
    def _call_ollama(
        self,
        prompt: str,
        system: str,
        config: LLMConfig,
    ) -> Tuple[str, Optional[str]]:
        url = f"{config.effective_ollama_url()}/api/chat"
        payload = {
            "model": config.effective_ollama_model(),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {
                "temperature": config.temperature,
                "top_p": config.top_p,
            },
        }
        response = requests.post(url, json=payload, timeout=600)
        response.raise_for_status()
        data = response.json()
        message = data.get("message", {})
        content = message.get("content", "")
        thinking = message.get("thinking", None)
        return content, thinking

    # ── OpenAI 兼容远程调用 ─────────────────────────────────────────────────
    def _call_remote(
        self,
        prompt: str,
        system: str,
        config: LLMConfig,
    ) -> Tuple[str, Optional[str]]:
        url = f"{config.remote_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.remote_api_key}",
        }
        payload = {
            "model": config.remote_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": config.temperature,
            "top_p": config.top_p,
            "max_tokens": config.max_tokens,
            "stream": False,
        }
        response = requests.post(url, json=payload, headers=headers, timeout=600)
        response.raise_for_status()
        data = response.json()

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")

        # DeepSeek-R1 在远程也会返回 reasoning_content
        thinking = message.get("reasoning_content", None)
        return content, thinking

    # ── Ollama 流式调用 ──────────────────────────────────────────────────────
    def _stream_ollama(
        self,
        prompt: str,
        system: str,
        config: LLMConfig,
    ) -> Generator[tuple, None, None]:
        """yield (chunk_text, chunk_type)，chunk_type='thinking'|'text'"""
        url = f"{config.effective_ollama_url()}/api/chat"
        payload = {
            "model": config.effective_ollama_model(),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": True,
            "options": {"temperature": config.temperature, "top_p": config.top_p},
        }
        with requests.post(url, json=payload, timeout=600, stream=True) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except Exception:
                    continue
                msg = data.get("message", {})
                # Ollama thinking 模型（如 qwq / deepseek-r1）会带 thinking 字段
                thinking_chunk = msg.get("thinking", "")
                content_chunk = msg.get("content", "")
                if thinking_chunk:
                    yield (thinking_chunk, "thinking")
                if content_chunk:
                    yield (content_chunk, "text")
                if data.get("done"):
                    break

    # ── 远程 OpenAI 兼容流式调用 ─────────────────────────────────────────────
    def _stream_remote(
        self,
        prompt: str,
        system: str,
        config: LLMConfig,
    ) -> Generator[tuple, None, None]:
        """yield (chunk_text, chunk_type)，chunk_type='thinking'|'text'"""
        url = f"{config.remote_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.remote_api_key}",
        }
        payload = {
            "model": config.remote_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": config.temperature,
            "top_p": config.top_p,
            "max_tokens": config.max_tokens,
            "stream": True,
        }
        with requests.post(url, json=payload, headers=headers, timeout=600, stream=True) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                text = line.decode("utf-8") if isinstance(line, bytes) else line
                if text.startswith("data:"):
                    text = text[5:].strip()
                if text == "[DONE]":
                    break
                try:
                    data = json.loads(text)
                except Exception:
                    continue
                delta = data.get("choices", [{}])[0].get("delta", {})
                # DeepSeek-R1 / 其他推理模型的思维链
                thinking_chunk = delta.get("reasoning_content", "") or ""
                content_chunk = delta.get("content", "") or ""
                if thinking_chunk:
                    yield (thinking_chunk, "thinking")
                if content_chunk:
                    yield (content_chunk, "text")

    # ── 统一流式对外接口 ──────────────────────────────────────────────────────
    def chat_stream(
        self,
        prompt: str,
        system: str,
        config_override: Optional[LLMConfig] = None,
    ) -> Generator[tuple, None, None]:
        """流式调用，逐 token yield (chunk_text, chunk_type)
        chunk_type: 'text' | 'thinking'
        """
        cfg = config_override or self._config
        if cfg.provider == "remote":
            if not cfg.remote_base_url or not cfg.remote_model:
                raise ValueError("远程 API 未配置：请填写 Base URL 和模型名")
            yield from self._stream_remote(prompt, system, cfg)
        else:
            yield from self._stream_ollama(prompt, system, cfg)

    # ── 统一对外接口 ─────────────────────────────────────────────────────────
    def chat(
        self,
        prompt: str,
        system: str,
        config_override: Optional[LLMConfig] = None,
    ) -> Tuple[str, Optional[str]]:
        """
        统一调用接口。

        Args:
            config_override: 单次请求级别配置覆盖，None 时使用全局运行时配置。
        """
        cfg = config_override or self._config

        try:
            if cfg.provider == "remote":
                if not cfg.remote_base_url or not cfg.remote_model:
                    raise ValueError("远程 API 未配置：请填写 Base URL 和模型名")
                return self._call_remote(prompt, system, cfg)
            else:
                return self._call_ollama(prompt, system, cfg)
        except requests.exceptions.Timeout:
            raise RuntimeError("模型调用超时，请检查服务是否正常运行")
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(f"无法连接到模型服务: {e}")
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"模型 API 返回错误: {e.response.status_code} {e.response.text[:200]}")

    # ── 工具方法：拉取 Ollama 已安装模型列表 ───────────────────────────────
    def list_ollama_models(self, base_url: str = None) -> list:
        """获取本地 Ollama 已安装的模型列表"""
        url = f"{(base_url or settings.ollama_base_url).rstrip('/')}/api/tags"
        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            models = resp.json().get("models", [])
            return [
                {
                    "name": m.get("name", ""),
                    "size": m.get("size", 0),
                    "modified_at": m.get("modified_at", ""),
                }
                for m in models
            ]
        except Exception as e:
            logger.warning(f"[LLMClient] 拉取 Ollama 模型列表失败: {e}")
            return []


# 全局单例
llm_client = LLMClient()
