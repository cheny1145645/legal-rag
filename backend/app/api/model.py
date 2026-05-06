"""
model.py — 模型管理 API
  GET  /api/models           : 列出 Ollama 已安装模型
  GET  /api/llm-presets      : 返回远程服务商预设列表
  POST /api/llm-config       : 更新运行时 LLM 配置（全局持久到重启）
  GET  /api/llm-config       : 获取当前 LLM 配置（脱敏）
  POST /api/llm-test         : 测试当前配置是否可用
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.core.llm_client import llm_client, LLMConfig, REMOTE_PRESETS

router = APIRouter(prefix="/api", tags=["模型管理"])
logger = logging.getLogger(__name__)


# ── 请求/响应 Schema ─────────────────────────────────────────────────────────
class LLMConfigRequest(BaseModel):
    provider: str = "ollama"           # "ollama" | "remote"
    # Ollama
    ollama_base_url: Optional[str] = None
    ollama_model: Optional[str] = None
    # 远程
    remote_base_url: Optional[str] = None
    remote_api_key: Optional[str] = None
    remote_model: Optional[str] = None
    # 推理参数
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None


# ── 获取 Ollama 模型列表 ─────────────────────────────────────────────────────
@router.get("/models")
async def list_models(ollama_url: str = None):
    """
    获取本地 Ollama 已安装模型列表。
    可通过查询参数 ?ollama_url=http://... 指定非默认地址。
    """
    models = llm_client.list_ollama_models(base_url=ollama_url)
    return {"models": models, "count": len(models)}


# ── 获取远程服务商预设 ────────────────────────────────────────────────────────
@router.get("/llm-presets")
async def get_presets():
    """返回内置的远程 API 服务商预设配置"""
    return {"presets": REMOTE_PRESETS}


# ── 更新 LLM 运行时配置 ───────────────────────────────────────────────────────
@router.post("/llm-config")
async def set_llm_config(req: LLMConfigRequest):
    """
    更新全局 LLM 运行时配置。
    立即生效，服务重启后恢复 .env 默认值。
    """
    current = llm_client.get_config()

    new_cfg = LLMConfig(
        provider=req.provider,
        ollama_base_url=req.ollama_base_url or current.ollama_base_url,
        ollama_model=req.ollama_model or current.ollama_model,
        remote_base_url=req.remote_base_url or current.remote_base_url,
        remote_api_key=req.remote_api_key or current.remote_api_key,
        remote_model=req.remote_model or current.remote_model,
        temperature=req.temperature if req.temperature is not None else current.temperature,
        top_p=req.top_p if req.top_p is not None else current.top_p,
        max_tokens=req.max_tokens if req.max_tokens is not None else current.max_tokens,
    )

    llm_client.set_config(new_cfg)
    return {"success": True, "message": "LLM 配置已更新", "provider": new_cfg.provider}


# ── 获取当前 LLM 配置（脱敏） ─────────────────────────────────────────────────
@router.get("/llm-config")
async def get_llm_config():
    """获取当前运行时 LLM 配置，API Key 脱敏显示"""
    cfg = llm_client.get_config()
    api_key = cfg.remote_api_key
    masked_key = ""
    if api_key:
        # 只显示前4位和后4位，中间用 *** 代替
        masked_key = api_key[:4] + "***" + api_key[-4:] if len(api_key) > 8 else "***"

    return {
        "provider": cfg.provider,
        "ollama_base_url": cfg.effective_ollama_url(),
        "ollama_model": cfg.effective_ollama_model(),
        "remote_base_url": cfg.remote_base_url,
        "remote_api_key_masked": masked_key,
        "remote_api_key_set": bool(api_key),
        "remote_model": cfg.remote_model,
        "temperature": cfg.temperature,
        "top_p": cfg.top_p,
        "max_tokens": cfg.max_tokens,
    }


# ── 测试当前配置 ──────────────────────────────────────────────────────────────
@router.post("/llm-test")
async def test_llm_config():
    """
    发送一条简短测试消息，验证当前 LLM 配置是否可用。
    返回响应片段和耗时。
    """
    import time
    t0 = time.time()
    try:
        content, _ = llm_client.chat(
            prompt="请回复'OK'",
            system="你是一个测试助手，只需回复OK。",
        )
        elapsed = round(time.time() - t0, 2)
        cfg = llm_client.get_config()
        return {
            "success": True,
            "provider": cfg.provider,
            "model": cfg.effective_ollama_model() if cfg.provider == "ollama" else cfg.remote_model,
            "response_preview": content[:100],
            "elapsed_s": elapsed,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
