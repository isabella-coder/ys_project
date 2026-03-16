"""轻量认证 API（小程序登录）"""

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.auth_service import list_active_sales, login_sales
from app.api.auth_guard import get_auth_profile_from_header
from app.integrations.wechat_mini import code2session
from app.models import Sales

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/sales")
async def sales_options(db: Session = Depends(get_db)):
    """获取可登录销售列表（用于登录页下拉）"""
    return {
        "code": 0,
        "data": {
            "items": list_active_sales(db),
        },
    }


@router.post("/login")
async def login(payload: dict, request: Request, db: Session = Depends(get_db)):
    """销售登录（支持可选的 wx_code 绑定 openid）"""
    sales_id = (payload.get("sales_id") or "").strip()
    password = payload.get("password") or ""
    wx_code = (payload.get("wx_code") or "").strip()

    if not sales_id or not password:
        return {
            "code": 400,
            "message": "请输入账号和密码",
        }

    client_ip = request.client.host if request.client else ""

    try:
        session = login_sales(db, sales_id, password, client_ip=client_ip)
    except ValueError as exc:
        return {
            "code": 401,
            "message": str(exc),
        }

    # 如果前端传了 wx_code，换取 openid 并绑定到销售
    if wx_code:
        try:
            wx_result = await code2session(wx_code)
            openid = wx_result.get("openid", "")
            if openid:
                sales = db.query(Sales).filter(Sales.sales_id == sales_id).first()
                if sales and sales.wx_openid != openid:
                    sales.wx_openid = openid
                    db.commit()
                    logger.info(f"销售 {sales_id} 绑定 wx_openid: {openid[:10]}...")
        except Exception as e:
            logger.warning(f"wx_code 换 openid 失败（不影响登录）: {e}")

    return {
        "code": 0,
        "data": session,
    }


@router.get("/me")
async def me(authorization: str = Header(default="")):
    """根据 Bearer token 获取当前登录用户"""
    profile = get_auth_profile_from_header(authorization)
    if not profile:
        return {
            "code": 401,
            "message": "登录状态失效，请重新登录",
        }

    return {
        "code": 0,
        "data": profile,
    }
