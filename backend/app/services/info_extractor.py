"""
信息提取器 —— 通过 LLM JSON Mode 从对话中提取结构化客户信息
"""
from __future__ import annotations

import json
import logging
import re
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

EXTRACT_PROMPT = """你是一个信息提取助手。请从以下客户对话中提取结构化信息。
如果某个字段在对话中没有提到，值设为 null。不要编造。

需要提取的字段：
- customer_nickname: 客户昵称/称呼
- car_model: 车型（汽车品牌+型号，如 "宝马X5"、"特斯拉Model 3"、"小米YU7"）。注意区分：
  * 以下是车衣/贴膜品牌，不是车型：BOP保镖、终结者、终结者PRO、风狂者、风狂者Plus、挑战者、爱国者、XPEL、龙膜、龙小侠、G2+、G2、G1、G0、无极、无极之上、极一、极零、后羿、畅悦、智选、圣佳、3M、威固、康得新、艾利、SunTek、LX HAUSSE。
  * 以下是汽车车型：YU7/yu7=小米YU7，SU7/su7=小米SU7，Model 3/Y/X/S=特斯拉，ES6/ES8/ET5/ET7/EC6/EC7/EL6/EL8=蔚来，L6/L7/L8/L9/MEGA=理想，P5/P7/G3/G6/G9/X9/MONA=小鹏，U7/U8/U9=仰望，M5/M7/M9=问界，S7/R7=智界，S9=享界，001/007/009=极氪，汉/唐/宋/秦/海豹/海鸥/元PLUS=比亚迪，D9/N7/N8=腾势，FREE/梦想家/追光=岚图，11/12=阿维塔，SL03/S7=深蓝，C01/C10/C11/C16/T03=零跑，S/GT/X/L=哪吒。
- service_type: 需要的服务类型（如"隐形车衣"、"车窗膜"、"改色彩绘"等）
- film_brand: 客户提到的车衣/贴膜品牌（如"风狂者"、"XPEL"、"龙膜"等）
- budget_range: 预算范围（如"5000-8000"、"1万左右"）
- customer_phone: 手机号
- customer_wechat: 客户的微信号（注意：yu7、su7、es6、et5等是汽车车型，不是微信号！只有客户明确说"微信是xxx"或"vx xxx"时才提取微信号。weilan15821412825、A17521502887、Weilan13661964825 是门店销售的微信号，不是客户微信，绝对不能提取！）

严格输出 JSON，不要输出其它内容：
{"customer_nickname": ..., "car_model": ..., "service_type": ..., "film_brand": ..., "budget_range": ..., "customer_phone": ..., "customer_wechat": ...}
"""


async def extract_info_from_messages(messages: list[dict]) -> dict:
    """
    调用 LLM 从对话历史中提取客户信息。
    messages: [{"role": "user"/"assistant", "content": "..."}]
    返回: {"customer_nickname": "...", "car_model": "...", ...}
    """
    # 构造对话摘要给 LLM
    conversation_text = "\n".join(
        f"{'客户' if m['role'] == 'user' else '客服'}: {m['content']}"
        for m in messages
    )

    llm_messages = [
        {"role": "system", "content": EXTRACT_PROMPT},
        {"role": "user", "content": conversation_text},
    ]

    try:
        result = await _call_llm(llm_messages, temperature=0.0)
        parsed = _parse_json_response(result)
        # 过滤 null / 空字符串
        cleaned = {k: v for k, v in parsed.items() if v}
        # 后处理：已知车型代号不能当微信号
        cleaned = _fix_car_model_as_wechat(cleaned)
        # 后处理：排除门店销售微信号（不是客户微信）
        cleaned = _filter_sales_wechat(cleaned)
        return cleaned
    except Exception as e:
        logger.warning(f"信息提取失败: {e}")
        fallback = _fallback_extract(messages)
        if fallback:
            logger.info(f"启用本地兜底提取: {fallback}")
        return fallback


def _parse_json_response(text: str) -> dict:
    """从 LLM 返回中解析 JSON（兼容 markdown code block）"""
    text = text.strip()
    # 去除 ```json ... ``` 包裹
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    return json.loads(text)


# 已知汽车车型代号（小写），不能被识别为微信号
_CAR_MODEL_CODES = {
    # 小米
    "su7", "su7ultra", "yu7",
    # 特斯拉
    "model3", "modely", "modelx", "models",
    # 蔚来
    "es6", "es8", "et5", "et5t", "et7", "ec6", "ec7", "el6", "el8",
    # 理想
    "l6", "l7", "l8", "l9", "mega",
    # 小鹏
    "p5", "p7", "p7i", "g3", "g6", "g9", "x9", "mona",
    # 仰望
    "u7", "u8", "u9",
    # 问界
    "m5", "m7", "m9",
    # 智界
    "s7", "r7",
    # 享界
    "s9",
    # 极氪
    "zeekr001", "zeekr007", "zeekr009", "zeekrx",
    # 零跑
    "c01", "c10", "c11", "c16", "t03",
    # 腾势
    "d9", "n7", "n8",
}

# 已知车型代号 → 完整车型名映射
_CAR_CODE_TO_MODEL = {
    # 小米
    "su7": "小米SU7", "su7ultra": "小米SU7 Ultra", "yu7": "小米YU7",
    # 特斯拉
    "model3": "特斯拉Model 3", "modely": "特斯拉Model Y",
    "modelx": "特斯拉Model X", "models": "特斯拉Model S",
    # 蔚来
    "es6": "蔚来ES6", "es8": "蔚来ES8", "et5": "蔚来ET5", "et5t": "蔚来ET5T",
    "et7": "蔚来ET7", "ec6": "蔚来EC6", "ec7": "蔚来EC7",
    "el6": "蔚来EL6", "el8": "蔚来EL8",
    # 理想
    "l6": "理想L6", "l7": "理想L7", "l8": "理想L8", "l9": "理想L9", "mega": "理想MEGA",
    # 小鹏
    "p5": "小鹏P5", "p7": "小鹏P7", "p7i": "小鹏P7i",
    "g3": "小鹏G3", "g6": "小鹏G6", "g9": "小鹏G9", "x9": "小鹏X9", "mona": "小鹏MONA M03",
    # 仰望
    "u7": "仰望U7", "u8": "仰望U8", "u9": "仰望U9",
    # 问界
    "m5": "问界M5", "m7": "问界M7", "m9": "问界M9",
    # 智界
    "s7": "智界S7", "r7": "智界R7",
    # 享界
    "s9": "享界S9",
    # 零跑
    "c01": "零跑C01", "c10": "零跑C10", "c11": "零跑C11", "c16": "零跑C16", "t03": "零跑T03",
    # 腾势
    "d9": "腾势D9", "n7": "腾势N7", "n8": "腾势N8",
}


def _fix_car_model_as_wechat(info: dict) -> dict:
    """修正LLM把车型代号误识别为微信号的情况"""
    wechat = info.get("customer_wechat", "").strip().lower()
    if wechat in _CAR_MODEL_CODES:
        # 把误识别的微信号移到车型
        if not info.get("car_model"):
            info["car_model"] = _CAR_CODE_TO_MODEL.get(wechat, wechat.upper())
        elif info.get("car_model") and wechat in _CAR_CODE_TO_MODEL:
            # 车型已有值但客户可能在纠正，更新车型
            info["car_model"] = _CAR_CODE_TO_MODEL[wechat]
        del info["customer_wechat"]
    return info


# 门店销售微信号（小写），LLM 可能从 AI 回复中误提取
_SALES_WECHAT_IDS = {
    "weilan15821412825",   # 佳佳
    "a17521502887",        # 孟傲
    "weilan13661964825",   # 周石磊
}


def _filter_sales_wechat(info: dict) -> dict:
    """排除门店销售微信号，避免被当成客户微信"""
    wechat = info.get("customer_wechat", "").strip().lower()
    if wechat in _SALES_WECHAT_IDS:
        del info["customer_wechat"]
    return info


async def _call_llm(messages: list[dict], temperature: float = 0.0) -> str:
    """
    调用 LLM API（兼容 OpenAI 格式：DeepSeek / 通义千问 / OpenAI / 本地 Ollama）
    """
    url = settings.LLM_API_URL.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json", "User-Agent": "claude-code/1.0"}
    if settings.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.LLM_API_KEY}"

    payload = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 500,
    }

    async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        msg = data["choices"][0]["message"]
        return msg.get("content") or msg.get("reasoning_content") or ""


def _fallback_extract(messages: list[dict]) -> dict:
    """LLM 不可用时，基于规则的最小信息提取兜底。"""
    user_text = "\n".join(
        str(m.get("content", "")) for m in messages if str(m.get("role", "")) == "user"
    )
    if not user_text.strip():
        return {}

    info = {
        "customer_nickname": "",
        "car_model": "",
        "service_type": "",
        "budget_range": "",
        "customer_phone": "",
        "customer_wechat": "",
    }

    # 客户称呼
    m = re.search(r"(?:我叫|叫我|称呼我)\s*([\u4e00-\u9fa5A-Za-z0-9]{1,12})", user_text)
    if m:
        info["customer_nickname"] = m.group(1)
    else:
        m2 = re.search(r"([\u4e00-\u9fa5]{1,4}(?:先生|女士|小姐))", user_text)
        if m2:
            info["customer_nickname"] = m2.group(1)

    # 车衣/贴膜品牌（不是车型）
    film_brands = [
        "BOP保镖", "保镖", "终结者PRO", "终结者", "风狂者Plus", "风狂者plus", "风狂者",
        "挑战者", "爱国者",
        "XPEL", "xpel",
        "龙膜", "龙小侠", "无极之上", "无极", "极一", "极零", "后羿", "畅悦", "智选",
        "圣佳", "3M", "3m", "威固", "康得新", "艾利", "SunTek", "suntek", "LX HAUSSE", "lx hausse",
    ]
    for brand in film_brands:
        if brand.lower() in user_text.lower():
            info["film_brand"] = brand
            break

    # 车型（汽车品牌，排除车衣品牌）
    # 先匹配英文车型代号（如 YU7, SU7, Model Y 等）
    en_car_map = {
        r'(?i)\byu7\b': '小米YU7', r'(?i)\bsu7\s*ultra\b': '小米SU7 Ultra', r'(?i)\bsu7\b': '小米SU7',
        r'(?i)\bmodel\s*[3yxs]\b': None,
        r'(?i)\b(?:es|et|ec|el)[0-9](?:t)?\b': None,
        r'(?i)\b[l][6-9]\b': None, r'(?i)\bmega\b': '理想MEGA',
        r'(?i)\b[p][5-7](?:i)?\b': None, r'(?i)\b[g][3-9]\b': None, r'(?i)\b[x][9]\b': None, r'(?i)\bmona\b': '小鹏MONA M03',
        r'(?i)\bu[7-9]\b': None,
        r'(?i)\bm[5-9]\b': None,
        r'(?i)\b[s][7]\b': None, r'(?i)\b[r][7]\b': None, r'(?i)\b[s][9]\b': None,
        r'(?i)\b[c](?:01|10|11|16)\b': None, r'(?i)\bt03\b': None,
        r'(?i)\b[d][9]\b': None, r'(?i)\b[n][7-8]\b': None,
    }
    for pattern, mapped in en_car_map.items():
        en_match = re.search(pattern, user_text)
        if en_match:
            info["car_model"] = mapped if mapped else en_match.group(0).strip()
            break

    # 再匹配中文品牌+型号
    if not info.get("car_model"):
        car_match = re.search(
            r"(小米|宝马|奔驰|奥迪|特斯拉|保时捷|路虎|大众|丰田|本田|比亚迪|理想|蔚来|小鹏|沃尔沃|凯迪拉克|雷克萨斯|林肯|领克|极氪|问界|仰望|智界|享界|极狐|岚图|阿维塔|深蓝|零跑|哪吒|腾势|海豹|海鸥|汉EV|秦PLUS|宋PLUS)[A-Za-z0-9\-\u4e00-\u9fa5 ]{0,10}",
            user_text,
        )
        if car_match:
            info["car_model"] = car_match.group(0).strip()

    # 服务类型
    service_keywords = ["隐形车衣", "车衣", "改色", "彩绘", "贴膜", "车窗膜", "窗膜", "镀晶", "内饰", "点点喷", "补漆", "凹陷修复", "凹陷", "补膜"]
    for key in service_keywords:
        if key in user_text:
            info["service_type"] = key
            break

    # 预算
    budget_match = re.search(r"(?:预算|价位|大概)\s*([0-9]{3,6}(?:\s*[-~到]\s*[0-9]{3,6})?(?:\s*[万wW])?)", user_text)
    if budget_match:
        info["budget_range"] = budget_match.group(1).replace(" ", "")

    # 手机号
    phone_match = re.search(r"(1[3-9][0-9]{9})", user_text)
    if phone_match:
        info["customer_phone"] = phone_match.group(1)

    # 微信号
    wechat_match = re.search(r"(?:微信|vx|Vx|VX)[:：\s]*([A-Za-z][A-Za-z0-9_-]{5,19})", user_text)
    if wechat_match:
        info["customer_wechat"] = wechat_match.group(1)

    # 兜底：有车型和项目时补一个默认称呼，避免线索创建被阻塞
    if not info["customer_nickname"] and info["car_model"] and info["service_type"]:
        info["customer_nickname"] = "意向客户"

    return {k: v for k, v in info.items() if v}
