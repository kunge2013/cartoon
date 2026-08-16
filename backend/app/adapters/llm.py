# -*- coding: utf-8 -*-
"""LLM 适配层：OpenAI 兼容协议（DeepSeek / 火山 / GRSai / 自定义端点）。

优先从 provider_accounts 表取账号（provider_code 匹配），回退到 settings K/V。
"""
from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from app.models.provider import ProviderAccount, Setting

DEFAULT_BASE_URLS = {
    "deepseek": "https://api.deepseek.com/v1",
    "grsai": "https://api.grsai.com/v1",
    "volcengine": "https://ark.cn-beijing.volces.com/api/v3",
}
DEFAULT_MODELS = {
    "deepseek": "deepseek-chat",
    "grsai": "deepseek-chat",
    "volcengine": "doubao-pro-32k",
}


class LLMNotConfigured(Exception):
    pass


class LLMError(Exception):
    pass


def resolve_account(db: Session, provider_code: str | None = None) -> dict:
    """返回 {base_url, api_key, model, provider_code}；找不到配置抛 LLMNotConfigured。"""
    q = db.query(ProviderAccount).filter(ProviderAccount.valid.is_(True))
    if provider_code:
        q = q.filter(ProviderAccount.provider_code == provider_code)
    acc = q.order_by(ProviderAccount.id).first()
    if acc is None and not provider_code:
        # 回退：settings K/V（deepseek_api_key 等）
        for code in ("deepseek", "grsai", "volcengine"):
            key_row = (
                db.query(Setting)
                .filter(Setting.key == f"{code}_api_key")
                .first()
            )
            if key_row and key_row.value:
                return {
                    "base_url": DEFAULT_BASE_URLS[code],
                    "api_key": key_row.value,
                    "model": DEFAULT_MODELS[code],
                    "provider_code": code,
                }
        raise LLMNotConfigured("no LLM provider configured (provider_accounts / settings)")
    if acc is None:
        raise LLMNotConfigured(f"provider not configured: {provider_code}")
    return {
        "base_url": acc.base_url or DEFAULT_BASE_URLS.get(acc.provider_code, acc.base_url),
        "api_key": acc.api_key,
        "model": acc.model or DEFAULT_MODELS.get(acc.provider_code, ""),
        "provider_code": acc.provider_code,
    }


def chat(
    db: Session,
    prompt: str,
    provider_code: str | None = None,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    timeout: float = 120.0,
    system: str | None = None,
) -> str:
    """同步调用 OpenAI 兼容 /chat/completions，返回助手文本。"""
    acc = resolve_account(db, provider_code)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model or acc["model"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    url = acc["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {acc['api_key']}"}
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as e:
        raise LLMError(f"network error: {e}") from e
    if resp.status_code != 200:
        raise LLMError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise LLMError(f"bad response shape: {str(data)[:300]}") from e
