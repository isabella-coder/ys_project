"""
抖音开放平台对接
- client_token: 应用级别 token（用于 webhook 验证等）
- user_token: 用户授权 token（用于私信回复，需先完成 OAuth 授权）
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Optional

import httpx
from app.config import settings

logger = logging.getLogger(__name__)

# ───── Token 缓存 ─────

# 应用级 client_token
_client_token_cache: dict = {"access_token": "", "expires_at": 0}

# 用户授权 token（授权方抖音号用于发私信）
_user_token_cache: dict = {
    "access_token": "",
    "refresh_token": "",
    "open_id": "",
    "expires_at": 0,
    "refresh_expires_at": 0,
}


async def get_client_token() -> str:
    """获取应用级 client_token（用于非用户授权场景）"""
    if _client_token_cache["access_token"] and time.time() < _client_token_cache["expires_at"] - 60:
        return _client_token_cache["access_token"]

    url = "https://open.douyin.com/oauth/client_token/"
    payload = {
        "client_key": settings.DOUYIN_CLIENT_KEY,
        "client_secret": settings.DOUYIN_CLIENT_SECRET,
        "grant_type": "client_credential",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json().get("data", {})

    token = data.get("access_token", "")
    expires_in = data.get("expires_in", 7200)

    _client_token_cache["access_token"] = token
    _client_token_cache["expires_at"] = time.time() + expires_in

    logger.info(f"抖音 client_token 刷新成功，有效期 {expires_in}s")
    return token


async def exchange_code_for_token(authorization_code: str) -> dict:
    """
    用 OAuth 授权码换取用户 access_token。
    抖音企业号授权后回调会带 authorization_code，用它来获取可发私信的 token。
    """
    url = "https://open.douyin.com/oauth/access_token/"
    payload = {
        "client_key": settings.DOUYIN_CLIENT_KEY,
        "client_secret": settings.DOUYIN_CLIENT_SECRET,
        "code": authorization_code,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        result = resp.json()

    data = result.get("data", {})
    error_code = data.get("error_code", 0)
    if error_code != 0:
        desc = data.get("description", "unknown")
        logger.error(f"抖音授权码换 token 失败: {error_code} - {desc}")
        return {"success": False, "error": desc}

    # 缓存用户级 token
    _user_token_cache["access_token"] = data.get("access_token", "")
    _user_token_cache["refresh_token"] = data.get("refresh_token", "")
    _user_token_cache["open_id"] = data.get("open_id", "")
    _user_token_cache["expires_at"] = time.time() + data.get("expires_in", 86400)
    _user_token_cache["refresh_expires_at"] = time.time() + data.get("refresh_expires_in", 86400 * 30)

    logger.info(f"抖音用户 token 获取成功，open_id={data.get('open_id')}, 有效期 {data.get('expires_in')}s")
    return {"success": True, "open_id": data.get("open_id")}


async def refresh_user_token() -> bool:
    """用 refresh_token 刷新用户 access_token"""
    if not _user_token_cache["refresh_token"]:
        logger.warning("无 refresh_token，无法刷新用户 token")
        return False

    url = "https://open.douyin.com/oauth/refresh_token/"
    payload = {
        "client_key": settings.DOUYIN_CLIENT_KEY,
        "grant_type": "refresh_token",
        "refresh_token": _user_token_cache["refresh_token"],
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json().get("data", {})

        if data.get("error_code", 0) != 0:
            logger.error(f"刷新用户 token 失败: {data.get('description')}")
            return False

        _user_token_cache["access_token"] = data.get("access_token", "")
        _user_token_cache["refresh_token"] = data.get("refresh_token", "")
        _user_token_cache["expires_at"] = time.time() + data.get("expires_in", 86400)
        _user_token_cache["refresh_expires_at"] = time.time() + data.get("refresh_expires_in", 86400 * 30)

        logger.info("抖音用户 token 刷新成功")
        return True
    except Exception as e:
        logger.error(f"刷新用户 token 异常: {e}")
        return False


async def get_user_access_token() -> str:
    """获取用户级 access_token（用于发私信），自动刷新过期 token"""
    if _user_token_cache["access_token"] and time.time() < _user_token_cache["expires_at"] - 60:
        return _user_token_cache["access_token"]

    # token 过期，尝试 refresh
    if _user_token_cache["refresh_token"] and time.time() < _user_token_cache["refresh_expires_at"]:
        if await refresh_user_token():
            return _user_token_cache["access_token"]

    logger.warning("用户 access_token 不可用，需要重新授权")
    return ""


# ───── 签名验证 ─────

def verify_signature(timestamp: str, nonce: str, body: bytes, signature: str) -> bool:
    """
    验证抖音 Webhook 签名
    sign = sha256(token + timestamp + nonce + body)
    """
    token = settings.DOUYIN_WEBHOOK_TOKEN
    raw = token + timestamp + nonce + body.decode("utf-8")
    expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return hmac.compare_digest(expected, signature)


# ───── 发送私信 ─────

async def send_private_message(open_id: str, text: str) -> bool:
    """
    向抖音用户发送私信回复
    需要用户级 access_token（通过 OAuth 授权获得）
    """
    access_token = await get_user_access_token()
    if not access_token:
        logger.error("无可用的用户 access_token，无法发送私信。请先完成抖音授权。")
        return False

    url = "https://open.douyin.com/im/send/msg/"
    headers = {
        "Content-Type": "application/json",
        "access-token": access_token,
    }
    payload = {
        "open_id": open_id,
        "msg_type": "text",
        "content": json.dumps({"text": text}),
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            result = resp.json()

        if result.get("err_no") == 0:
            return True
        else:
            logger.error(f"抖音发送私信失败: {result}")
            return False
    except Exception as e:
        logger.error(f"抖音私信 API 异常: {e}")
        return False


# ───── 解析 Webhook 事件 ─────

def parse_im_event(body: dict) -> Optional[dict]:
    """
    从抖音 Webhook 事件体中解析私信消息。
    返回: {"open_id": "...", "content": "...", "msg_id": "...", "msg_type": "..."} 或 None
    """
    event = body.get("event", "")

    # 进入会话事件
    if event in ("enter_session", "enter", "im_enter"):
        open_id = body.get("from_user_id", "")
        if open_id:
            return {
                "open_id": open_id,
                "content": "",
                "msg_id": "",
                "msg_type": "enter",
            }
        return None

    # 抖音私信的事件类型
    if event not in ("im", "receive_msg"):
        return None

    content_list = body.get("content", [])
    if not content_list:
        return None

    # content 可能是 JSON string
    if isinstance(content_list, str):
        try:
            content_list = json.loads(content_list)
        except (json.JSONDecodeError, TypeError):
            return None

    # 适配不同格式
    if isinstance(content_list, dict):
        content_list = [content_list]

    for item in content_list:
        msg_type = item.get("msg_type", item.get("message_type", ""))
        open_id = item.get("open_id") or body.get("from_user_id", "")
        msg_id = item.get("msg_id", "")
        if msg_type == "text":
            text_payload = item.get("content", item.get("text", ""))
            if isinstance(text_payload, str):
                try:
                    text_payload = json.loads(text_payload)
                except (json.JSONDecodeError, TypeError):
                    text_payload = {"text": text_payload}
            return {
                "open_id": open_id,
                "content": text_payload.get("text", ""),
                "msg_id": msg_id,
                "msg_type": "text",
            }
        elif msg_type in ("image", "img", "video", "card", "share"):
            return {
                "open_id": open_id,
                "content": "",
                "msg_id": msg_id,
                "msg_type": msg_type,
            }

    return None
