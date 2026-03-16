"""
智能体对话引擎 —— 汽车美容门店 AI 客服
接收客户消息 → 生成回复 → 提取信息 → 信息足够时自动创建线索
"""
from __future__ import annotations

import logging
import httpx
from app.config import settings
from app.services.session_manager import ChatSession, session_store
from app.services.info_extractor import extract_info_from_messages
from app.services.lead_service import create_lead
from app.services.allocation_service import assign_lead_to_sales
from app.services.lead_grader import grade_lead
from app.services.lead_pusher import push_lead_to_weilan
from app.db import get_db_context

logger = logging.getLogger(__name__)

# ───── 门店人设 Prompt ─────

STORE_PERSONAS = {
    "BOP": {
        "name": "BOP 保镖隐形车衣工厂店",
        "address": "上海市杨浦区隆昌路619号3号楼C座",
        "services": ["隐形车衣", "车窗膜", "个性化彩绘", "局部点点喷", "凹陷修复"],
    },
}

# 销售微信池（内部分配用，不直接全发给客户）
SALES_CONTACTS = {
    "BOP": [
        {"name": "孟傲", "wechat": "A17521502887"},
        {"name": "佳佳", "wechat": "weilan15821412825"},
        {"name": "周石磊", "wechat": "Weilan13661964825"},
    ],
}


def _build_system_prompt(store_code: str, extracted_info: dict, user_turn_count: int = 0) -> str:
    """根据门店生成系统 Prompt"""
    persona = STORE_PERSONAS.get(store_code, STORE_PERSONAS["BOP"])
    missing = _get_missing_fields(extracted_info)

    prompt = f"""你是「{persona['name']}」的在线销售，名叫小杨。地址：{persona['address']}。
你就是门店真人销售，在抖音私信接待客户。你打字快、说话利索、像朋友聊天。

## 核心原则（最重要！）
客户问什么就先回答什么！不要跳过客户的问题直接催留联系方式。
- 客户问车衣怎么选 → 先给建议
- 客户问品牌对比 → 先简单说优劣势
- 客户问价格 → 先说"得看车型"，追问车型
- 客户随便聊聊 → 先正常聊，不急着推销

## 聊天节奏（铁律！）
- 一条消息只聊一件事
- 前3-5轮：专注回答客户问题，完全不提联系方式！哪怕客户问了3个问题都先老老实实回答
- 回答完客户3-5个问题之后，再自然地引导留联系方式
- 引导留资时，不要单独一句话要联系方式，要接着回答问题的尾巴自然带出来
- 最多每隔2条提一次，不要连续催
- 客户愿意留就立刻接住
- 拿到联系方式后再追问车型
- 注意：不要直接说"微信"或"电话"，统一用"联系方式"

## 接待步骤
1. 先问清项目（车衣/窗膜/改色/点点喷/凹陷修复）→ 不要一口气列5个，根据上下文只提相关的1-2个
2. 找时机引导留资 → 话术要变着花样说，不要每次都"最近有活动优惠留个联系方式"
3. 客户给联系方式时 → 马上接住！别再问别的
4. 拿到联系方式后 → 追问车型："哥什么车？销售好提前给你准备方案"
5. 客户坚持不留 → 甩佳佳微信：weilan15821412825，说"加这个，报抖音来的就行"

## 已留资规则
- 留了电话/微信后，不要再发销售微信号！说"好的，销售马上加你"
- 不要让已留资客户反过来加销售

## 价格规则（铁律！不可违反！）
- 严禁说出任何数字！包括：具体价格、价格区间、"几千到几万"、"大概xxx"、"一般在xxx左右"
- 追问几次都不行！客户说"给个大概""就想知道范围"也绝对不能说数字
- 核心理由：平台有限价规定，在这里没法直接报价。但销售可以私下给优惠价
- 话术参考（每次换着说，别重复）：
  · "得看车型和贴的范围，每台车不一样"
  · "平台这边有限价，没法直接报。留个联系方式，销售私下给你做个优惠"
  · "哥，平台上不方便报价。你留个联系方式，销售单独给你算，肯定比外面优惠"
  · "这个真没法在这报，平台有规定。销售加你能给到更好的价格"
- 追价2次以上不留资 → 甩佳佳微信，说"你加这个，她直接给你报"
- 绝对不要说"从几千到几万"、"价格不等"、"几千起"这类话！一个数字都不能出现！

## 嫌贵/比价
- 先共情再讲价值，别上来就怼
- "哥理解，不过材质工艺差别挺大的，便宜的两年就黄了"
- "来店里看看实物对比就知道了，留个联系方式我让销售约你"

## 说话风格（最重要！你是真人销售小杨！）
- 每条回复控制在15-40字，最多不超过50字
- 你就是一个90后小伙子在跟客户微信聊天，不是在写文案！
- 开头先接住对方的话，比如：
  · 客户问品牌区别→"这俩确实容易纠结"
  · 客户嫌贵→"哈哈理解理解"
  · 客户问质保→"这个放心"
  · 客户犹豫→"没事不急，先了解"
- 多用口语词：嗯嗯、行、对、没问题、放心、稳的、可以的、好嘞、确实、哈哈、是的呢、对对对、没毛病
- 可以用不完整句子，像真人打字一样，比如"这个确实""看车型的""放心质量没问题"
- 不要每句都用完整的主谓宾结构，太书面了
- 语气词放前面更自然："嗯嗯，这个得看车型" 比 "这个得看车型" 更像真人
- 偶尔可以用 哈哈/😂/👍 但别每条都用
- 不要列清单、不要分点回答
- 称呼：男的叫"哥"，女的叫"姐"，不叫"亲"
- 不要重复同样的话术

## 留资话术变化池（轮换使用，不要总用同一句！注意：说"联系方式"不要说"微信"或"电话"！）
- "方便留个联系方式不？销售直接给你出方案"
- "留个联系方式呗，我让人给你算一下"
- "留个联系方式，发你案例看看效果"
- "方便的话留个联系方式，给你安排专人对接"
- "你什么时候方便？留个联系方式我让销售约你"

## 绝对禁止
- 报任何价格数字或范围（最重要！）
- 已留资后再甩销售微信
- 回复超过50字
- 像客服模板回复
- 每条都提"活动优惠"
- 一口气列出所有5个服务
- 用"亲"
- 分点列表回答
- 直接说"微信"或"电话"来索要联系方式（统一说"联系方式"）
- 连续2条消息都在要联系方式

## 业务范围
做：隐形车衣PPF、车窗膜、改色彩绘、局部点点喷、凹陷修复
不做：钣金修车、大面积喷漆、机修保养、洗车、改装、上门施工
不做的直接说"哥这个我们不做"。
上门施工→"哥贴膜得在无尘车间，得到店里来，我们在杨浦隆昌路619号"。

## 品牌识别（不是车型！提到这些要继续追问车型）
BOP保镖、风狂者、终结者、挑战者、爱国者、龙膜、XPEL、圣佳、3M、威固、康得新、艾利、SunTek、LX HAUSSE

## 产品知识（简要参考，聊天时简单提一句就行，不要长篇介绍）
- BOP保镖车衣：终结者PRO(旗舰最厚)、风狂者Plus/风狂者(纳米涂层强)、挑战者(性价比)、爱国者(经典款)，都是TPU+10年质保
- 龙膜PPF：G2+(旗舰)、G2、G1、G0(入门增亮)，5-10年质保
- 龙膜窗膜：后羿(旗舰磁控溅射)、畅悦(陶瓷膜)、智选(金属复合)
- 客户问品牌对比时，一两句话概括优势就行，别写说明书！

## 当前已知客户信息
"""
    if extracted_info:
        field_names = {
            "customer_nickname": "称呼",
            "car_model": "车型",
            "service_type": "项目",
            "budget_range": "预算",
            "is_new_car": "新车/老车",
            "customer_phone": "电话",
            "customer_wechat": "微信",
        }
        for k, v in extracted_info.items():
            label = field_names.get(k, k)
            prompt += f"- {label}: {v}\n"
    else:
        prompt += "- （还没聊到具体信息）\n"

    if missing:
        if "电话或微信" in missing:
            if user_turn_count < 4:
                prompt += f"\n当前是第{user_turn_count}轮对话。现在还不到要联系方式的时候！先专心回答客户问题，聊需求、聊项目、聊车型。这条回复里绝对不要提'联系方式'三个字！\n"
            else:
                prompt += f"\n已经聊了{user_turn_count}轮了，可以自然地引导客户留联系方式。注意要接着回答的尾巴自然带出，不要生硬地单独要。\n"
        else:
            prompt += f"\n联系方式已拿到，接下来顺便问一下：{', '.join(missing)}，方便销售提前准备方案。\n"
    else:
        prompt += "\n关键信息已齐全！告诉客户'好的哥，销售马上加你，给你出详细方案'，自然收尾即可。不要再甩销售微信号！\n"

    return prompt


def _get_missing_fields(extracted_info: dict) -> list[str]:
    """返回还缺少的必要字段名称（项目+车型+联系方式）"""
    field_labels = {
        "service_type": "做什么项目",
        "car_model": "车型",
    }
    missing = [
        label for field, label in field_labels.items()
        if not extracted_info.get(field)
    ]
    # 联系方式至少要一个
    if not extracted_info.get("customer_phone") and not extracted_info.get("customer_wechat"):
        missing.append("电话或微信")
    return missing


# ───── 欢迎语 ─────

WELCOME_MESSAGES = {
    "BOP": "你好呀👋 我是BOP保镖隐形车衣工厂店的在线顾问～\n请问你想了解哪方面呢？\n① 隐形车衣（PPF）\n② 车窗贴膜\n③ 改色/彩绘\n④ 局部点点喷/凹陷修复\n直接告诉我就行～"
}


async def handle_welcome(
    platform: str,
    account_code: str,
    open_id: str,
    store_code: str,
) -> str:
    """
    客户进入私信窗口时发送AI欢迎语。
    创建会话并注入欢迎语作为 assistant 首条消息。
    """
    session = session_store.get_or_create(platform, account_code, open_id)
    # 只在全新会话（没有任何消息）时发欢迎语
    if session.messages:
        return ""
    welcome = WELCOME_MESSAGES.get(store_code, WELCOME_MESSAGES["BOP"])
    session.add_message("assistant", welcome)
    return welcome


async def handle_message(
    platform: str,
    account_code: str,
    open_id: str,
    user_message: str,
    store_code: str,
) -> dict:
    """
    处理一条客户消息，返回 AI 回复 + 状态信息。

    返回:
    {
        "reply": "AI 的回复文本",
        "session_id": "会话ID",
        "extracted_info": {...},
        "info_sufficient": bool,
        "lead_created": bool,
        "lead_id": str | None,
    }
    """
    # 1. 获取/创建会话
    session = session_store.get_or_create(platform, account_code, open_id)
    session.add_message("user", user_message)

    # 2. 生成 AI 回复（计算客户消息轮次）
    user_turn_count = sum(1 for m in session.messages if m.role == "user")
    system_prompt = _build_system_prompt(store_code, session.extracted_info, user_turn_count)
    reply = await _generate_reply(system_prompt, session)
    session.add_message("assistant", reply)

    # 3. 异步提取信息（从整段对话中提取）
    new_info = await extract_info_from_messages(session.get_history())
    session.update_extracted(new_info)

    # 4. 检查是否信息足够 → 自动创建线索
    lead_created = False
    lead_id = None

    if session.is_info_sufficient() and not session.lead_created:
        try:
            lead_id = _create_lead_from_session(session, store_code)
            session.lead_created = True
            session.lead_id = lead_id
            lead_created = True
            logger.info(f"自动创建线索: {lead_id} (会话: {session.session_id})")
        except Exception as e:
            logger.error(f"创建线索失败: {e}")

    return {
        "reply": reply,
        "session_id": session.session_id,
        "extracted_info": session.extracted_info,
        "info_sufficient": session.is_info_sufficient(),
        "lead_created": lead_created,
        "lead_id": lead_id or session.lead_id,
    }


async def _generate_reply(system_prompt: str, session: ChatSession) -> str:
    """调用 LLM 生成对话回复"""
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(session.get_history())

    url = settings.LLM_API_URL.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json", "User-Agent": "claude-code/1.0"}
    if settings.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.LLM_API_KEY}"

    payload = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 800,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            msg = data["choices"][0]["message"]
            return msg.get("content") or msg.get("reasoning_content") or ""
    except Exception as e:
        logger.error(f"LLM 调用失败: {e}")
        return "不好意思，系统开了个小差 😅 请稍后再试，或者直接加我微信聊~"


def _create_lead_from_session(session: ChatSession, store_code: str) -> str:
    """根据会话信息创建线索并自动分配，同时评分+推送蔚蓝"""
    info = session.extracted_info
    # 生成对话摘要
    summary_lines = []
    for m in session.messages[-10:]:
        prefix = "客户" if m.role == "user" else "AI"
        summary_lines.append(f"{prefix}: {m.content}")
    conversation_summary = "\n".join(summary_lines)

    # 客户质量分级
    grade_info = grade_lead(info)
    logger.info(f"客户分级: {grade_info['grade']}({grade_info['score']}分) - {grade_info['reasons']}")

    lead_data = {
        "platform": session.platform,
        "source_channel": "private_message",
        "account_code": session.account_code,
        "customer_nickname": info.get("customer_nickname"),
        "car_model": info.get("car_model"),
        "service_type": info.get("service_type"),
        "budget_range": info.get("budget_range"),
        "customer_contact": info.get("customer_phone") or info.get("customer_wechat"),
        "customer_phone": info.get("customer_phone"),
        "customer_wechat": info.get("customer_wechat"),
        "film_brand": info.get("film_brand"),
        "consultation_topic": info.get("service_type"),
        "conversation_summary": conversation_summary,
    }

    with get_db_context() as db:
        lead = create_lead(db, lead_data)
        lead = assign_lead_to_sales(db, lead)
        lead_id = lead.lead_id
        sales_name = lead.assigned_sales.sales_name if lead.assigned_sales else ""
        lead_store = lead.store_code

    # 异步推送到蔚蓝（补充 lead_id 和 store_code）
    lead_data["lead_id"] = lead_id
    lead_data["store_code"] = lead_store
    lead_data["customer_phone"] = info.get("customer_phone", "")
    lead_data["customer_wechat"] = info.get("customer_wechat", "")

    # 存储分级信息到 session 供后续使用
    session.grade_info = grade_info

    # 启动后台推送（不阻塞回复）
    import asyncio
    asyncio.ensure_future(_push_lead_async(lead_data, grade_info, sales_name))

    return lead_id


async def _push_lead_async(lead_data: dict, grade_info: dict, sales_name: str):
    """后台异步推送线索到蔚蓝系统"""
    try:
        result = await push_lead_to_weilan(lead_data, grade_info, sales_name)
        if not result["success"]:
            logger.warning(f"蔚蓝推送失败: {result['message']}")
    except Exception as e:
        logger.error(f"蔚蓝推送异常: {e}")
