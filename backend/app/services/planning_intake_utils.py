import re

from app.services.planning_calendar_utils import safe_text

INTAKE_DRAFT_KEYS = (
    "client_name",
    "industry",
    "target_audience",
    "unique_advantage",
    "ip_requirements",
    "style_preference",
    "business_goal",
    "city",
    "business_district",
    "store_type",
    "avg_ticket",
    "core_products_or_services",
    "top_reasons_to_choose",
    "customer_common_questions",
    "common_hesitations",
    "primary_consumption_scenes",
    "on_camera_roles",
    "shootable_scenes",
    "peak_hours",
    "store_constraints",
    "publishing_rhythm",
    "time_windows",
    "goal_target",
    "iteration_rule",
)
INTAKE_REQUIRED_KEYS = ("client_name", "industry", "target_audience", "ip_requirements")
INTAKE_FIELD_LABELS = {
    "client_name": "客户/品牌名称",
    "industry": "行业垂类",
    "target_audience": "目标受众画像",
    "ip_requirements": "门店打法与内容方向",
}
INDUSTRY_KEYWORDS = {
    "美妆个护": ("美妆", "护肤", "化妆", "彩妆", "护发"),
    "餐饮美食": ("美食", "餐饮", "探店", "小吃", "咖啡", "烘焙"),
    "健身健康": ("健身", "减脂", "增肌", "养生", "瑜伽", "跑步"),
    "本地生活": ("同城", "本地", "门店", "团购", "生活服务"),
    "娱乐休闲": ("ktv", "k歌", "唱歌", "自助ktv", "自助k歌", "电玩城", "娱乐"),
    "教育知识": ("教育", "学习", "考研", "英语", "知识", "课程"),
    "电商带货": ("电商", "带货", "选品", "直播", "转化", "成交"),
    "家居家装": ("家居", "装修", "收纳", "软装"),
    "母婴亲子": ("母婴", "育儿", "亲子", "宝妈"),
}
INDUSTRY_AUDIENCE_DEFAULT = {
    "美妆个护": "20-35岁女性，关注护肤效率、妆容质感与高性价比产品选择。",
    "餐饮美食": "18-35岁城市用户，关注真实口味、价格透明和可复购餐饮选择。",
    "健身健康": "22-40岁上班族，关注减脂效率、时间友好和可持续健康习惯。",
    "本地生活": "18-40岁本地用户，关注同城优惠、实用服务与避坑信息。",
    "娱乐休闲": "18-35岁年轻用户，关注解压放松、朋友社交与高性价比娱乐体验。",
    "教育知识": "18-35岁学生与职场人，关注可落地的学习方法和提效路径。",
    "电商带货": "20-40岁有消费决策需求的用户，关注选购建议、真实测评和优惠信息。",
    "家居家装": "25-45岁家庭用户，关注实用收纳、装修避坑和预算优化。",
    "母婴亲子": "23-38岁新手父母，关注育儿效率、情绪支持和实操型经验。",
    "泛生活": "18-35岁泛兴趣用户，关注真实经验、实用建议和情绪价值内容。",
}
INDUSTRY_ADVANTAGE_DEFAULT = {
    "娱乐休闲": [
        "低门槛随时可玩，不用组局也能快速开唱",
        "高性价比，适合学生党和年轻人高频复购",
        "私密空间更友好，社恐和独处场景也成立",
    ],
    "餐饮美食": [
        "真实测评+价格透明，帮助用户快速做决策",
        "场景化推荐，覆盖工作餐/聚会/约会等真实需求",
        "高频更新本地新店与回头店，形成持续参考价值",
    ],
    "健身健康": [
        "低门槛动作方案，普通人也能坚持执行",
        "碎片时间友好，兼顾效率和可持续性",
        "持续复盘体感和数据，降低试错成本",
    ],
    "美妆个护": [
        "以成分和肤质场景做决策，不只讲感受",
        "高性价比和避坑导向，提升信任感",
        "对比测评和实拍反馈，内容可复用性高",
    ],
}
INDUSTRY_PILLARS_DEFAULT = {
    "娱乐休闲": [
        "场景种草：约会、聚会、下班解压、周末打卡",
        "情绪共鸣：社恐友好、情绪释放、深夜放松",
        "门店体验：环境、音质、曲库、收费、流程透明",
        "活动转化：新客福利、双人套餐、节日主题活动",
    ],
    "餐饮美食": [
        "场景推荐：工作餐、约会餐、聚会餐",
        "真实测评：口味、价格、份量、服务",
        "避坑清单：踩雷点与替代方案",
        "福利转化：套餐、团购、限时活动",
    ],
    "健身健康": [
        "痛点拆解：减脂焦虑、坚持困难、时间不足",
        "实操方案：10-20分钟训练与饮食策略",
        "跟练打卡：周计划+阶段复盘",
        "案例转化：真实前后变化与咨询引导",
    ],
}
INDUSTRY_TOPIC_TITLES = {
    "娱乐休闲": [
        "一个人想唱歌又不想社交，来这就够了",
        "情侣约会第二场，为什么越来越多人选自助KTV",
        "下班压力大，30分钟快速放空的方式",
        "学生党预算有限，也能实现唱歌自由",
        "商场里最容易被忽略的快乐角落",
        "社恐友好型娱乐空间到底是什么体验",
        "吃完饭不知道去哪？这套续摊方案直接抄",
        "同样是唱歌，自助KTV和传统KTV差在哪",
        "第一次来不会操作？从进门到点歌全流程",
        "本周福利怎么用最划算，一条视频讲清楚",
    ],
}
PLACEHOLDER_PATTERNS = (
    "信息不足",
    "待确认",
    "后补充",
    "补齐",
    "无法判断",
    "暂无法",
    "待补充",
)


def normalize_draft(raw: dict) -> dict[str, str]:
    return {key: safe_text(raw.get(key)) for key in INTAKE_DRAFT_KEYS}


def is_placeholder_value(value: str) -> bool:
    text = safe_text(value)
    if not text:
        return True
    return any(pattern in text for pattern in PLACEHOLDER_PATTERNS)


def detect_industry(user_message: str) -> str:
    text = user_message.lower()
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return industry
    return "泛生活"


def build_default_ip_requirements(industry: str) -> str:
    return (
        f"门店增长打法：先用真实问题/决策钩子抓停留，再用真实场景和具体证据建立信任，最后自然带出到店或咨询理由。\n"
        f"内容方向：围绕{industry}的真实消费/服务场景，优先做决策建议、避坑提醒、现场证明、顾客高频问题。"
    )


def build_default_client_name(industry: str, user_message: str) -> str:
    compact = re.sub(r"\s+", "", user_message)[:10]
    if compact:
        return f"{compact}账号"
    return f"{industry}策划账号"


def auto_fill_intake_draft(draft: dict[str, str], user_message: str) -> list[str]:
    inferred_fields: list[str] = []
    industry = draft.get("industry") or detect_industry(user_message)
    if not draft.get("industry"):
        draft["industry"] = industry
        inferred_fields.append("industry")
    if not draft.get("client_name"):
        draft["client_name"] = build_default_client_name(industry, user_message)
        inferred_fields.append("client_name")
    if not draft.get("target_audience"):
        draft["target_audience"] = INDUSTRY_AUDIENCE_DEFAULT.get(industry, INDUSTRY_AUDIENCE_DEFAULT["泛生活"])
        inferred_fields.append("target_audience")
    if not draft.get("ip_requirements"):
        draft["ip_requirements"] = build_default_ip_requirements(industry)
        inferred_fields.append("ip_requirements")
    if not draft.get("store_type") and "店" in user_message:
        draft["store_type"] = "实体门店"
        inferred_fields.append("store_type")
    if not draft.get("publishing_rhythm"):
        draft["publishing_rhythm"] = "每月10条（推荐，3天1条）"
        inferred_fields.append("publishing_rhythm")
    if not draft.get("time_windows"):
        draft["time_windows"] = "19:00、21:00"
        inferred_fields.append("time_windows")
    if not draft.get("goal_target"):
        draft["goal_target"] = "30天发布10条，至少跑出1-2条高潜内容"
        inferred_fields.append("goal_target")
    if not draft.get("iteration_rule"):
        draft["iteration_rule"] = "每周复盘1次，每次只调整1-2个变量（开头/标题/结构）"
        inferred_fields.append("iteration_rule")
    return inferred_fields


def build_execution_preview(draft: dict[str, str]) -> str:
    industry = draft.get("industry") or "泛生活"
    client_name = draft.get("client_name") or f"{industry}账号"
    target_audience = draft.get("target_audience") or INDUSTRY_AUDIENCE_DEFAULT.get(industry, INDUSTRY_AUDIENCE_DEFAULT["泛生活"])
    ip_requirements = draft.get("ip_requirements") or build_default_ip_requirements(industry)
    business_goal = draft.get("business_goal") or "先完成30天稳定更新，跑出1-2条高潜内容并沉淀可复用模板。"
    city = draft.get("city") or "同城"
    business_district = draft.get("business_district") or "核心商圈"
    store_type = draft.get("store_type") or industry
    avg_ticket = draft.get("avg_ticket") or "待确认"
    core_products = draft.get("core_products_or_services") or "主营产品/服务待补充"
    top_reasons = draft.get("top_reasons_to_choose") or "真实优势待补充"
    hesitations = draft.get("common_hesitations") or "用户犹豫点待补充"
    scenes = draft.get("primary_consumption_scenes") or "消费场景待补充"
    on_camera_roles = draft.get("on_camera_roles") or "出镜角色待补充"
    shootable_scenes = draft.get("shootable_scenes") or "可拍场景待补充"
    rhythm = draft.get("publishing_rhythm") or "每月10条（推荐，3天1条）"
    time_windows = draft.get("time_windows") or "19:00、21:00"
    goal_target = draft.get("goal_target") or "30天发布10条，至少跑出1-2条高潜内容"
    iteration_rule = draft.get("iteration_rule") or "每周复盘1次，每次只调整1-2个变量（开头/标题/结构）"
    advantages = INDUSTRY_ADVANTAGE_DEFAULT.get(
        industry,
        [
            "低门槛、可持续执行，降低起号试错成本",
            "内容围绕真实场景，用户容易共鸣和转化",
            "结构化内容支柱明确，便于批量产出与复盘",
        ],
    )
    pillars = INDUSTRY_PILLARS_DEFAULT.get(
        industry,
        [
            "场景痛点：把用户真实问题讲清楚",
            "方法方案：提供可执行动作和流程",
            "对比复盘：展示选择逻辑与优化路径",
            "转化内容：结合活动/服务做行动引导",
        ],
    )
    topic_titles = INDUSTRY_TOPIC_TITLES.get(
        industry,
        [
            "这个场景下，为什么大多数人都会做错选择",
            "预算有限时，最值得优先做的3件事",
            "第一次尝试如何避免踩坑",
            "一周内可执行的基础版本方案",
            "同类选择对比：怎么选更稳",
            "真实案例复盘：从低效到高效的关键动作",
            "常见误区盘点：越努力越无效的点",
            "30天起号执行清单（可直接照做）",
            "新手最容易忽略但影响最大的细节",
            "本周行动建议：只改1个变量看结果",
        ],
    )

    advantages_text = "\n".join([f"- {item}" for item in advantages[:3]])
    pillars_text = "\n".join([f"- {item}" for item in pillars[:4]])
    topics_text = "\n".join([f"{idx + 1}. {title}" for idx, title in enumerate(topic_titles[:10])])

    return (
        f"## 可执行策划初稿（{client_name}）\n\n"
        "### 1) 门店基础盘\n"
        f"- 所在地：{city} {business_district}\n"
        f"- 门店类型：{store_type}\n"
        f"- 客单价：{avg_ticket}\n"
        f"- 主营产品/服务：{core_products}\n"
        f"- 用户为什么会来：{top_reasons}\n"
        f"- 用户最常犹豫：{hesitations}\n"
        f"- 主要消费场景：{scenes}\n"
        f"- 谁来出镜：{on_camera_roles}\n"
        f"- 可拍场景：{shootable_scenes}\n\n"
        "### 2) 目标受众\n"
        f"- {target_audience}\n\n"
        "### 3) 独特优势/亮点\n"
        f"{advantages_text}\n\n"
        "### 4) 门店打法与内容方向\n"
        f"- 策略：{ip_requirements}\n"
        f"{pillars_text}\n\n"
        "### 5) 30天执行节奏\n"
        f"- 发布节奏：{rhythm}\n"
        f"- 发布时间窗口：{time_windows}\n"
        f"- 阶段目标：{goal_target}\n"
        f"- 迭代规则：{iteration_rule}\n"
        f"- 商业目标：{business_goal}\n\n"
        "### 6) 首批10条可拍选题\n"
        f"{topics_text}\n\n"
        "如果你愿意，我可以下一步直接把这份初稿转成“30天日历+每条脚本骨架”。"
    )
