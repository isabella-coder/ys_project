"""
微信小程序对接
- access_token 缓存 + 自动刷新
- code2session: 用登录 code 换取 openid
- send_subscribe_message: 发送订阅消息通知
"""
from __future__ import annotations

import logging
import time

import httpx
from app.config import settings

logger = logging.getLogger(__name__)

# ───── access_token 缓存 ─────

_token_cache: dict = {"access_token": "", "expires_at": 0}


async def get_access_token() -> str:
    """获取小程序 access_token（自动缓存 + 刷新）"""
    if _token_cache["access_token"] and time.time() < _token_cache["expires_at"] - 60:
        return _token_cache["access_token"]

    appid = settings.WX_MINI_APPID
    secret = settings.WX_MINI_SECRET
    if not appid or not secret:
        logger.warning("WX_MINI_APPID / WX_MINI_SECRET 未配置，跳过 access_token 获取")
        return ""

    url = "https://api.weixin.qq.com/cgi-bin/token"
    params = {
        "grant_type": "client_credential",
        "appid": appid,
        "secret": secret,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    if "errcode" in data and data["errcode"] != 0:
        logger.error(f"获取微信 access_token 失败: {data}")
        return ""

    token = data.get("access_token", "")
    expires_in = data.get("expires_in", 7200)

    _token_cache["access_token"] = token
    _token_cache["expires_at"] = time.time() + expires_in

    logger.info(f"微信 access_token 刷新成功，有效期 {expires_in}s")
    return token


async def code2session(js_code: str) -> dict:
    """
    用小程序 wx.login() 拿到的 code 换取 openid + session_key。
    返回 {"openid": "...", "session_key": "...", "unionid": "..."}
    """
    appid = settings.WX_MINI_APPID
    secret = settings.WX_MINI_SECRET
    if not appid or not secret:
        logger.warning("WX_MINI_APPID / WX_MINI_SECRET 未配置")
        return {}

    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": appid,
        "secret": secret,
        "js_code": js_code,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    if "errcode" in data and data["errcode"] != 0:
        logger.error(f"code2session 失败: {data}")
        return {}

    return {
        "openid": data.get("openid", ""),
        "session_key": data.get("session_key", ""),
        "unionid": data.get("unionid", ""),
    }


async def send_subscribe_message(
    openid: str,
    template_id: str,
    data: dict,
    page: str = "",
) -> bool:
    """
    发送订阅消息。
    data 格式: {"thing1": {"value": "新线索提醒"}, "name2": {"value": "张三"}, ...}
    """
    if not openid or not template_id:
        logger.warning(f"send_subscribe_message 参数不完整: openid={openid}, template_id={template_id}")
        return False

    access_token = await get_access_token()
    if not access_token:
        return False

    url = f"https://api.weixin.qq.com/cgi-bin/message/subscribe/send?access_token={access_token}"
    payload = {
        "touser": openid,
        "template_id": template_id,
        "data": data,
    }
    if page:
        payload["page"] = page

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            result = resp.json()

        if result.get("errcode", 0) != 0:
            logger.warning(f"订阅消息发送失败: {result}")
            return False

        logger.info(f"订阅消息发送成功: openid={openid}")
        return True
    except Exception as e:
        logger.error(f"订阅消息发送异常: {e}")
        return False
