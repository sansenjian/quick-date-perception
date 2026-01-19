# -*- coding: utf-8 -*-
"""
quick-date-perception - 轻量级日期感知插件

移植自 AstrBot 的 astrbot_plugin_llmperception 核心功能，
为麦麦提供时间、日期、节假日、农历、节气等环境感知能力。
"""

# ==================== 导入 ====================
# 标准库
from typing import List, Tuple, Type, Optional, Dict, Any
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json
import os

# 框架导入
from src.common.logger import get_logger
from src.plugin_system import (
    BasePlugin,
    register_plugin,
    BaseEventHandler,
    BaseCommand,
    BaseTool,
    ComponentInfo,
    ConfigField,
    EventType,
)

# ==================== 日志初始化 ====================
logger = get_logger("quick_date_perception")


# ==================== 常量定义 ====================

# 中文星期名称
WEEKDAY_NAMES = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

# 农历月份名称
LUNAR_MONTHS = ["正月", "二月", "三月", "四月", "五月", "六月",
                "七月", "八月", "九月", "十月", "冬月", "腊月"]

# 农历日期名称
LUNAR_DAYS = [
    "初一", "初二", "初三", "初四", "初五", "初六", "初七", "初八", "初九", "初十",
    "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十",
    "廿一", "廿二", "廿三", "廿四", "廿五", "廿六", "廿七", "廿八", "廿九", "三十"
]

# 二十四节气名称
SOLAR_TERMS = [
    "小寒", "大寒", "立春", "雨水", "惊蛰", "春分",
    "清明", "谷雨", "立夏", "小满", "芒种", "夏至",
    "小暑", "大暑", "立秋", "处暑", "白露", "秋分",
    "寒露", "霜降", "立冬", "小雪", "大雪", "冬至"
]

# 天干
TIAN_GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]

# 地支
DI_ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

# 生肖
SHENG_XIAO = ["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]

# 内置固定节日（作为降级方案）
FIXED_HOLIDAYS = {
    "01-01": "元旦",
    "05-01": "劳动节",
    "05-02": "劳动节",
    "05-03": "劳动节",
    "10-01": "国庆节",
    "10-02": "国庆节",
    "10-03": "国庆节",
    "10-04": "国庆节",
    "10-05": "国庆节",
    "10-06": "国庆节",
    "10-07": "国庆节",
}

# 节假日数据下载 URL 模板
HOLIDAY_URL_TEMPLATE = "https://unpkg.com/holiday-calendar@1.3.0/data/CN/{year}.json"

# 缓存目录路径
CACHE_DIR = "data/holidays"

# LLM 扩展提示词模板
LLM_EXPAND_PROMPT = (
    "你是一个日期信息助手。将以下日期信息整理成自然语言。原始信息: {raw_info}。"
    "输出时必须包含昨天今天明天三天的日期、星期几和节假日。调休工作日需特别说明。"
    "直接输出内容，不要JSON。"
)


# ==================== 辅助函数 ====================

def get_weekday_cn(date: datetime) -> str:
    """
    获取中文星期名称
    
    Args:
        date: datetime 对象
        
    Returns:
        中文星期名称，如 "星期一"
    """
    weekday_index = date.weekday()  # 0=周一, 6=周日
    return WEEKDAY_NAMES[weekday_index]


def format_date_short(date: datetime) -> str:
    """
    格式化为短日期格式
    
    Args:
        date: datetime 对象
        
    Returns:
        短日期格式，如 "1月2日"
    """
    return f"{date.month}月{date.day}日"


def classify_time_period(hour: int) -> str:
    """
    根据小时数分类时间段
    
    Args:
        hour: 小时数 (0-23)
        
    Returns:
        时间段名称：上午、中午、下午、晚上、深夜
    """
    if 5 <= hour < 12:
        return "上午"
    elif 12 <= hour < 14:
        return "中午"
    elif 14 <= hour < 18:
        return "下午"
    elif 18 <= hour < 22:
        return "晚上"
    else:  # 22-23 或 0-4
        return "深夜"


# ==================== 节假日数据管理 ====================

# 尝试导入可选依赖
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    logger.warning("[DatePerception] aiohttp 库未安装，将无法下载节假日数据")

try:
    import chinese_calendar
    CHINESE_CALENDAR_AVAILABLE = True
except ImportError:
    CHINESE_CALENDAR_AVAILABLE = False
    logger.warning("[DatePerception] chinese-calendar 库未安装，将使用备用节假日识别方案")


async def download_holiday_data(year: int) -> Dict[str, Any]:
    """
    从 unpkg.com 下载指定年份的节假日数据
    
    Args:
        year: 年份
        
    Returns:
        节假日数据字典，格式 {date: {name_cn, type, ...}}
        失败时返回空字典
    """
    if not AIOHTTP_AVAILABLE:
        logger.warning(f"[DatePerception] aiohttp 不可用，无法下载 {year} 年节假日数据")
        return {}
    
    url = HOLIDAY_URL_TEMPLATE.format(year=year)
    
    try:
        timeout = aiohttp.ClientTimeout(total=2)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"[DatePerception] 成功下载 {year} 年节假日数据")
                    
                    # 转换为内部格式：{date: {name_cn, type}}
                    holiday_map = {}
                    if "dates" in data:
                        for item in data["dates"]:
                            date_str = item.get("date", "")
                            if date_str:
                                holiday_map[date_str] = {
                                    "name_cn": item.get("name_cn", ""),
                                    "type": item.get("type", "")
                                }
                    
                    return holiday_map
                else:
                    logger.warning(f"[DatePerception] 下载节假日数据失败: HTTP {response.status}")
                    return {}
    except Exception as e:
        logger.error(f"[DatePerception] 下载节假日数据异常: {e}")
        return {}


def save_cached_holiday(year: int, data: Dict[str, Any]) -> None:
    """
    保存节假日数据到本地缓存
    
    Args:
        year: 年份
        data: 节假日数据字典
    """
    try:
        # 确保缓存目录存在
        os.makedirs(CACHE_DIR, exist_ok=True)
        
        cache_file = os.path.join(CACHE_DIR, f"{year}.json")
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"[DatePerception] 节假日数据已缓存: {cache_file}")
    except Exception as e:
        logger.error(f"[DatePerception] 保存节假日缓存失败: {e}")


def load_cached_holiday(year: int) -> Dict[str, Any]:
    """
    从本地缓存加载节假日数据
    
    Args:
        year: 年份
        
    Returns:
        节假日数据字典
        缓存不存在或加载失败时返回空字典
    """
    try:
        cache_file = os.path.join(CACHE_DIR, f"{year}.json")
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.debug(f"[DatePerception] 从缓存加载 {year} 年节假日数据")
            return data
        else:
            return {}
    except Exception as e:
        logger.error(f"[DatePerception] 加载节假日缓存失败: {e}")
        return {}


async def get_holiday_map(year: int) -> Dict[str, Any]:
    """
    获取节假日数据（优先缓存，无则下载）
    
    Args:
        year: 年份
        
    Returns:
        节假日数据字典
    """
    # 优先使用本地缓存
    cached_data = load_cached_holiday(year)
    if cached_data:
        return cached_data
    
    # 缓存不存在，尝试下载
    downloaded_data = await download_holiday_data(year)
    if downloaded_data:
        # 保存到缓存
        save_cached_holiday(year, downloaded_data)
        return downloaded_data
    
    # 下载失败，返回空字典
    return {}


def get_holiday_name(date_str: str, holiday_map: Dict[str, Any]) -> str:
    """
    从节假日数据中获取节假日名称
    
    Args:
        date_str: 日期字符串，格式 "YYYY-MM-DD"
        holiday_map: 节假日数据字典
        
    Returns:
        节假日名称，如 "国庆节"、"劳动节（调休）"
        如果不是节假日返回空字符串
    """
    if not holiday_map or date_str not in holiday_map:
        return ""
    
    holiday_info = holiday_map[date_str]
    name = holiday_info.get("name_cn", "")
    holiday_type = holiday_info.get("type", "")
    
    # 如果是调休工作日，添加（调休）后缀
    if holiday_type == "transfer_workday":
        return f"{name}（调休）" if name else "调休"
    
    return name


def detect_holiday_with_lib(date: datetime) -> str:
    """
    使用 chinese-calendar 库判断节假日
    
    Args:
        date: datetime 对象
        
    Returns:
        节假日状态：节假日名称、"周末"、"工作日"、"调休"
    """
    if not CHINESE_CALENDAR_AVAILABLE:
        return ""
    
    try:
        # 判断是否为节假日
        is_holiday = chinese_calendar.is_holiday(date)
        is_workday = chinese_calendar.is_workday(date)
        
        # 获取节假日名称
        holiday_name = chinese_calendar.get_holiday_detail(date)
        
        if holiday_name:
            # 有节假日名称
            if is_workday:
                # 调休工作日
                return f"{holiday_name[0]}（调休）"
            else:
                # 法定节假日
                return holiday_name[0]
        elif is_holiday:
            # 周末
            return "周末"
        else:
            # 工作日
            return "工作日"
    except Exception as e:
        logger.debug(f"[DatePerception] chinese-calendar 判断失败: {e}")
        return ""


async def detect_holiday(date: datetime) -> str:
    """
    检测节假日（完整降级方案）
    
    多数据源策略：
    1. chinese-calendar 库（优先）
    2. 下载的节假日数据
    3. 内置固定节日
    4. 仅判断周末
    
    Args:
        date: datetime 对象
        
    Returns:
        节假日状态：节假日名称、"周末"、"工作日"
    """
    # 策略 1: 使用 chinese-calendar 库
    if CHINESE_CALENDAR_AVAILABLE:
        result = detect_holiday_with_lib(date)
        if result:
            return result
    
    # 策略 2: 使用下载的节假日数据
    year = date.year
    holiday_map = await get_holiday_map(year)
    date_str = date.strftime("%Y-%m-%d")
    holiday_name = get_holiday_name(date_str, holiday_map)
    
    if holiday_name:
        return holiday_name
    
    # 策略 3: 使用内置固定节日
    month_day = date.strftime("%m-%d")
    if month_day in FIXED_HOLIDAYS:
        return FIXED_HOLIDAYS[month_day]
    
    # 策略 4: 仅判断周末
    weekday = date.weekday()
    if weekday >= 5:  # 5=周六, 6=周日
        return "周末"
    else:
        return "工作日"


# ==================== 农历和节气功能 ====================

# 尝试导入 lunarcalendar
try:
    from lunarcalendar import Converter, Solar, Lunar
    from lunarcalendar import solarterm
    LUNARCALENDAR_AVAILABLE = True
except ImportError:
    LUNARCALENDAR_AVAILABLE = False
    logger.warning("[DatePerception] lunarcalendar 库未安装，将跳过农历和节气功能")


def get_lunar_info(current_time: datetime) -> str:
    """
    获取农历日期信息
    
    Args:
        current_time: 当前时间
        
    Returns:
        农历信息，格式 "农历甲辰年(龙年)正月初一"
        lunarcalendar 不可用或失败时返回空字符串
    """
    if not LUNARCALENDAR_AVAILABLE:
        return ""
    
    try:
        # 转换为农历
        solar = Solar(current_time.year, current_time.month, current_time.day)
        lunar = Converter.Solar2Lunar(solar)
        
        # 计算天干地支年份
        year_offset = (lunar.year - 4) % 60
        tian_gan_index = year_offset % 10
        di_zhi_index = year_offset % 12
        
        tian_gan = TIAN_GAN[tian_gan_index]
        di_zhi = DI_ZHI[di_zhi_index]
        sheng_xiao = SHENG_XIAO[di_zhi_index]
        
        # 农历月份
        month_name = LUNAR_MONTHS[lunar.month - 1]
        if lunar.isleap:
            month_name = f"闰{month_name}"
        
        # 农历日期
        day_name = LUNAR_DAYS[lunar.day - 1]
        
        return f"农历{tian_gan}{di_zhi}年({sheng_xiao}年){month_name}{day_name}"
    except Exception as e:
        logger.debug(f"[DatePerception] 农历转换失败: {e}")
        return ""


def get_solar_term_info(current_time: datetime) -> str:
    """
    获取节气信息
    
    Args:
        current_time: 当前时间
        
    Returns:
        节气信息，如 "立春"、"大寒"
        只在节气当天显示，其他日期返回空字符串
        lunarcalendar 不可用或失败时返回空字符串
    """
    if not LUNARCALENDAR_AVAILABLE:
        return ""
    
    try:
        # 获取当前年份的所有节气
        year = current_time.year
        current_date = current_time.date()
        
        # 节气类名映射（lunarcalendar 使用拼音类名）
        solar_term_classes = {
            "小寒": solarterm.XiaoHan,
            "大寒": solarterm.DaHan,
            "立春": solarterm.LiChun,
            "雨水": solarterm.YuShui,
            "惊蛰": solarterm.JingZhe,
            "春分": solarterm.ChunFen,
            "清明": solarterm.QingMing,
            "谷雨": solarterm.GuYu,
            "立夏": solarterm.LiXia,
            "小满": solarterm.XiaoMan,
            "芒种": solarterm.MangZhong,
            "夏至": solarterm.XiaZhi,
            "小暑": solarterm.XiaoShu,
            "大暑": solarterm.DaShu,
            "立秋": solarterm.LiQiu,
            "处暑": solarterm.ChuShu,
            "白露": solarterm.BaiLu,
            "秋分": solarterm.QiuFen,
            "寒露": solarterm.HanLu,
            "霜降": solarterm.ShuangJiang,
            "立冬": solarterm.LiDong,
            "小雪": solarterm.XiaoXue,
            "大雪": solarterm.DaXue,
            "冬至": solarterm.DongZhi,
        }
        
        # 查找是否有节气在今天
        for term_name, term_class in solar_term_classes.items():
            # 获取节气日期
            term_date = term_class(year)
            
            # 只在节气当天显示
            if term_date == current_date:
                return term_name
        
        # 如果今天不是节气，返回空字符串
        return ""
    except Exception as e:
        logger.debug(f"[DatePerception] 节气计算失败: {e}")
        return ""


# ==================== 三天日期信息功能 ====================

def get_three_days_raw_info() -> Dict[str, Dict[str, str]]:
    """
    获取昨天、今天、明天的基础信息（不含节假日）
    
    Returns:
        {
            "yesterday": {"date_str": "2024-01-01", "date_short": "1月1日", "weekday": "星期一"},
            "today": {...},
            "tomorrow": {...}
        }
    """
    now = datetime.now()
    yesterday = now - timedelta(days=1)
    tomorrow = now + timedelta(days=1)
    
    return {
        "yesterday": {
            "date_str": yesterday.strftime("%Y-%m-%d"),
            "date_short": format_date_short(yesterday),
            "weekday": get_weekday_cn(yesterday)
        },
        "today": {
            "date_str": now.strftime("%Y-%m-%d"),
            "date_short": format_date_short(now),
            "weekday": get_weekday_cn(now)
        },
        "tomorrow": {
            "date_str": tomorrow.strftime("%Y-%m-%d"),
            "date_short": format_date_short(tomorrow),
            "weekday": get_weekday_cn(tomorrow)
        }
    }


async def get_three_days_info() -> str:
    """
    获取三天完整信息，格式化为字符串
    
    Returns:
        格式化的三天日期信息，包含农历和节气，格式：
        "昨天 | 1月1日 星期一【元旦】"
        "今天 | 1月2日 星期二"
        "明天 | 1月3日 星期三"
        "农历甲辰年(龙年)正月初一"
        "今日立春"
    """
    try:
        # 获取基础信息
        raw_info = get_three_days_raw_info()
        
        # 获取节假日信息
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)
        
        yesterday_holiday = await detect_holiday(yesterday)
        today_holiday = await detect_holiday(now)
        tomorrow_holiday = await detect_holiday(tomorrow)
        
        # 格式化输出
        lines = []
        
        # 昨天
        yesterday_info = raw_info["yesterday"]
        yesterday_line = f"昨天 | {yesterday_info['date_short']} {yesterday_info['weekday']}"
        if yesterday_holiday and yesterday_holiday != "工作日":
            yesterday_line += f"【{yesterday_holiday}】"
        lines.append(yesterday_line)
        
        # 今天
        today_info = raw_info["today"]
        today_line = f"今天 | {today_info['date_short']} {today_info['weekday']}"
        if today_holiday and today_holiday != "工作日":
            today_line += f"【{today_holiday}】"
        lines.append(today_line)
        
        # 明天
        tomorrow_info = raw_info["tomorrow"]
        tomorrow_line = f"明天 | {tomorrow_info['date_short']} {tomorrow_info['weekday']}"
        if tomorrow_holiday and tomorrow_holiday != "工作日":
            tomorrow_line += f"【{tomorrow_holiday}】"
        lines.append(tomorrow_line)
        
        # 添加农历信息
        lunar_info = get_lunar_info(now)
        if lunar_info:
            lines.append(lunar_info)
        
        # 添加节气信息
        solar_term_info = get_solar_term_info(now)
        if solar_term_info:
            lines.append(solar_term_info)
        
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"[DatePerception] 获取三天日期信息失败: {e}")
        return "获取日期信息失败"


# ==================== 感知信息构建 ====================

async def build_perception_info(
    current_time: datetime,
    timezone: ZoneInfo,
    enable_holiday: bool = True,
    enable_lunar: bool = True,
    enable_solar_term: bool = True
) -> str:
    """
    构建完整的感知信息
    
    Args:
        current_time: 当前时间
        timezone: 时区
        enable_holiday: 是否启用节假日感知
        enable_lunar: 是否启用农历感知
        enable_solar_term: 是否启用节气感知
        
    Returns:
        格式化的感知信息，如：
        "[发送时间: 2024-01-02 14:30:00 | 周二, 工作日, 下午 | 农历甲辰年(龙年)正月初一 | 今日立春]"
    """
    try:
        info_parts = []
        
        # 1. 发送时间
        time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
        info_parts.append(f"发送时间: {time_str}")
        
        # 2. 星期、节假日状态、时间段
        if enable_holiday:
            weekday = get_weekday_cn(current_time)
            holiday_status = await detect_holiday(current_time)
            time_period = classify_time_period(current_time.hour)
            
            status_parts = [weekday]
            if holiday_status:
                status_parts.append(holiday_status)
            status_parts.append(time_period)
            
            info_parts.append(", ".join(status_parts))
        
        # 3. 农历信息
        if enable_lunar:
            lunar_info = get_lunar_info(current_time)
            if lunar_info:
                info_parts.append(lunar_info)
        
        # 4. 节气信息
        if enable_solar_term:
            solar_term_info = get_solar_term_info(current_time)
            if solar_term_info:
                info_parts.append(solar_term_info)
        
        return "[" + " | ".join(info_parts) + "]"
    except Exception as e:
        logger.error(f"[DatePerception] 构建感知信息失败: {e}")
        return f"[发送时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}]"


async def expand_with_llm(raw_info: str, llm_model: str = "replyer") -> str:
    """
    使用 LLM 将原始日期信息扩展为自然语言
    
    注意：此函数仅在 DateCommand (/date 命令) 中使用，
    不影响 DateTool 和 DateInjectEventHandler 的行为。
    
    Args:
        raw_info: 原始格式化的日期信息
        llm_model: LLM 模型名称
        
    Returns:
        LLM 生成的自然语言描述
        失败时返回原始信息
    """
    try:
        # 导入 LLM API（延迟导入，避免循环依赖）
        from src.llm_models import llm_api
        
        # 获取可用模型
        available_models = llm_api.get_available_models()
        if not available_models:
            logger.warning("[DatePerception] 无可用 LLM 模型")
            return raw_info
        
        # 检查指定模型是否可用
        if llm_model not in available_models:
            logger.warning(f"[DatePerception] 指定模型 {llm_model} 不可用，使用默认模型")
            llm_model = available_models[0] if available_models else None
        
        if not llm_model:
            return raw_info
        
        # 构建提示词
        prompt = LLM_EXPAND_PROMPT.format(raw_info=raw_info)
        
        # 调用 LLM
        response = await llm_api.generate_with_model(
            model_name=llm_model,
            prompt=prompt,
            request_type="date_expand"
        )
        
        if response and response.strip():
            logger.debug(f"[DatePerception] LLM 扩展成功")
            return response.strip()
        else:
            logger.warning("[DatePerception] LLM 返回空结果")
            return raw_info
    except Exception as e:
        logger.error(f"[DatePerception] LLM 扩展失败: {e}")
        return raw_info


# ==================== Tool 组件 ====================

class DateTool(BaseTool):
    """日期查询工具"""
    
    name: str = "get_date_info"
    description: str = "获取当前日期、星期、节假日、农历、节气等完整信息。包括昨天、今天、明天的详细日期信息，支持中国节假日识别、农历转换、二十四节气计算。适用于查询日期、星期几、是否节假日、农历日期、节气等问题。"
    available_for_llm: bool = True
    parameters: List = []  # 不需要参数
    
    async def execute(self, function_args: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行日期查询
        
        Returns:
            {
                "content": str,  # 格式化的日期信息
                "description": str,  # 操作描述
                "error": str  # 错误信息（可选）
            }
        """
        try:
            # 获取三天日期信息
            date_info = await get_three_days_info()
            
            return {
                "content": date_info,
                "description": "日期信息已获取"
            }
        except Exception as e:
            logger.error(f"[DatePerception] DateTool 执行失败: {e}")
            return {
                "content": "",
                "error": f"查询失败: {str(e)}"
            }


# ==================== 注入内容构建 ====================

async def build_injection_content() -> str:
    """
    构建完整的日期注入内容
    
    Returns:
        格式化的注入内容，包含：
        - 当前时间和时间段
        - 三天日期信息（昨天、今天、明天）
        - 农历信息（如果可用）
        - 节气信息（如果可用）
        - 智能提示
    """
    try:
        now = datetime.now()
        
        # 1. 当前时间信息（简洁格式）
        current_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        time_period = classify_time_period(now.hour)
        weekday = get_weekday_cn(now)
        
        lines = [
            "",
            "【当前日期时间】",
            f"时间: {current_time_str} ({weekday}, {time_period})",
            ""
        ]
        
        # 2. 三天日期信息（包含每天的农历和节气）
        lines.append("【三天日期】")
        
        # 获取三天基础信息
        raw_info = get_three_days_raw_info()
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)
        
        # 获取节假日信息
        yesterday_holiday = await detect_holiday(yesterday)
        today_holiday = await detect_holiday(now)
        tomorrow_holiday = await detect_holiday(tomorrow)
        
        # 获取每天的农历和节气信息
        yesterday_lunar = get_lunar_info(yesterday)
        today_lunar = get_lunar_info(now)
        tomorrow_lunar = get_lunar_info(tomorrow)
        
        yesterday_solar_term = get_solar_term_info(yesterday)
        today_solar_term = get_solar_term_info(now)
        tomorrow_solar_term = get_solar_term_info(tomorrow)
        
        # 格式化三天信息（每天一行，包含农历和节气）
        yesterday_info = raw_info["yesterday"]
        yesterday_line = f"昨天: {yesterday_info['date_short']} {yesterday_info['weekday']}"
        if yesterday_holiday and yesterday_holiday != "工作日":
            yesterday_line += f" ({yesterday_holiday})"
        if yesterday_lunar:
            yesterday_line += f" | {yesterday_lunar}"
        if yesterday_solar_term:
            yesterday_line += f" | {yesterday_solar_term}"
        lines.append(yesterday_line)
        
        today_info = raw_info["today"]
        today_line = f"今天: {today_info['date_short']} {today_info['weekday']}"
        if today_holiday and today_holiday != "工作日":
            today_line += f" ({today_holiday})"
        if today_lunar:
            today_line += f" | {today_lunar}"
        if today_solar_term:
            today_line += f" | {today_solar_term}"
        lines.append(today_line)
        
        tomorrow_info = raw_info["tomorrow"]
        tomorrow_line = f"明天: {tomorrow_info['date_short']} {tomorrow_info['weekday']}"
        if tomorrow_holiday and tomorrow_holiday != "工作日":
            tomorrow_line += f" ({tomorrow_holiday})"
        if tomorrow_lunar:
            tomorrow_line += f" | {tomorrow_lunar}"
        if tomorrow_solar_term:
            tomorrow_line += f" | {tomorrow_solar_term}"
        lines.append(tomorrow_line)
        
        # 4. 简洁提示
        lines.append("")
        lines.append("提示: 以上是完整的日期信息，如果可以用于回答用户关于日期、星期、节假日、农历、节气的问题，就无需调用工具搜索日期。")
        lines.append("")
        
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"[DatePerception] 构建注入内容失败: {e}")
        # 降级方案：返回简单的日期信息
        now = datetime.now()
        simple_info = f"\n当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        return simple_info


# ==================== EventHandler 组件 ====================

class DateInjectEventHandler(BaseEventHandler):
    """日期信息注入事件处理器
    
    在 LLM 调用前自动注入完整的日期信息到 prompt，包括：
    - 当前时间和时间段
    - 三天日期信息（昨天、今天、明天）
    - 节假日状态
    - 农历信息（如果 lunarcalendar 可用）
    - 节气信息（如果 lunarcalendar 可用）
    """
    
    event_type: EventType = EventType.POST_LLM
    handler_name: str = "date_inject_handler"
    handler_description: str = "在 LLM 调用前自动注入完整的日期信息到 prompt"
    weight: int = 10
    intercept_message: bool = True
    
    async def execute(
        self, message
    ) -> Tuple[bool, bool, Optional[str], None, None]:
        """
        执行日期注入
        
        Returns:
            (continue, success, description, custom_result, modified_message)
        """
        try:
            # 早退策略：message 不存在时跳过
            if not message:
                return True, True, "无消息对象", None, None
            
            # 早退策略：llm_prompt 不存在时跳过
            if not hasattr(message, "llm_prompt") or not message.llm_prompt:
                return True, True, "无 LLM prompt", None, None
            
            # 构建完整的注入内容
            inject_content = await build_injection_content()
            
            # 修改 prompt（注入到末尾）
            message.modify_llm_prompt(
                message.llm_prompt + "\n" + inject_content,
                suppress_warning=True
            )
            
            # 记录注入的内容（用于调试）
            logger.info(f"[DatePerception] 已注入日期信息到 LLM prompt")
            logger.debug(f"[DatePerception] 注入内容:\n{inject_content}")
            
            return True, True, "日期信息已注入", None, message
        except Exception as e:
            logger.error(f"[DatePerception] 日期注入失败: {e}")
            logger.exception(f"[DatePerception] 异常详情: {e}")
            # 注入失败不阻止消息处理
            return True, False, f"注入失败: {str(e)}", None, message


# ==================== Command 组件 ====================

class DateCommand(BaseCommand):
    """日期查询命令
    
    用户可以使用 /date 命令手动查询日期信息。
    输出内容基于自动注入的内容，但移除了提示信息，更简洁易读。
    
    支持 LLM 扩展模式：
    - enable_llm_expand = false（默认）：输出结构化日期信息（简洁版）
    - enable_llm_expand = true：使用 LLM 将日期信息转换为自然语言
    
    注意：LLM 扩展仅对此命令有效，不影响自动注入和 Tool 工具。
    """
    
    command_name: str = "date_query"
    command_description: str = "查询昨天、今天、明天的日期信息"
    command_pattern: str = r"^/date$"
    
    async def execute(self) -> Tuple[bool, Optional[str], bool]:
        """
        执行日期查询命令
        
        Returns:
            (success, description, block_further_processing)
        """
        try:
            # 使用和注入相同的内容构建函数
            date_info = await build_injection_content()
            
            # 移除最后的提示信息（提示信息只在注入时需要，用户查询时不需要）
            lines = date_info.split('\n')
            # 移除空行和提示行
            filtered_lines = []
            skip_next = False
            for line in lines:
                if line.startswith("提示:"):
                    skip_next = True
                    continue
                if skip_next and line.strip() == "":
                    skip_next = False
                    continue
                filtered_lines.append(line)
            
            # 移除末尾的空行
            while filtered_lines and filtered_lines[-1].strip() == "":
                filtered_lines.pop()
            
            date_info = '\n'.join(filtered_lines)
            
            # 检查是否启用 LLM 扩展
            enable_llm_expand = self.get_config("llm.enable_llm_expand", False)
            
            if enable_llm_expand:
                # 使用 LLM 扩展
                llm_model = self.get_config("llm.llm_model", "replyer")
                date_info = await expand_with_llm(date_info, llm_model)
            
            # 发送结果
            await self.send_text(date_info)
            
            return True, "日期查询成功", True
        except Exception as e:
            logger.error(f"[DatePerception] DateCommand 执行失败: {e}")
            await self.send_text(f"查询失败: {str(e)}")
            return False, f"查询失败: {str(e)}", True


# ==================== 插件注册（必须放在最后） ====================
# ⚠️ 重要：@register_plugin 装饰的插件类必须放在文件最后
# 原因：装饰器执行时会引用 get_plugin_components() 返回的类
# 如果类定义在插件类之后，会导致 NameError

@register_plugin
class QuickDatePerceptionPlugin(BasePlugin):
    """
    quick-date-perception 插件主类
    
    提供日期感知功能，包括：
    - 时间、日期、星期识别
    - 节假日和调休识别（多数据源降级策略）
    - 农历日期转换
    - 二十四节气计算
    - LLM Prompt 自动注入
    - Tool 和 Command 查询接口
    """
    
    # ==================== 基本属性 ====================
    plugin_name: str = "quick_date_perception"
    enable_plugin: bool = True
    dependencies: List[str] = []
    python_dependencies: List[str] = [
        "chinese-calendar>=1.8.0 (可选)",
        "lunarcalendar>=0.0.9 (可选)",
        "aiohttp>=3.8.0 (可选)"
    ]
    config_file_name: str = "config.toml"
    
    # ==================== 配置定义 ====================
    config_schema: dict = {
        "plugin": {
            "enabled": ConfigField(
                type=bool,
                default=True,
                description="是否启用插件"
            ),
            "config_version": ConfigField(
                type=str,
                default="1.0.0",
                description="配置版本"
            ),
        },
        "perception": {
            "timezone": ConfigField(
                type=str,
                default="Asia/Shanghai",
                description="时区设置（IANA 时区标识符）"
            ),
            "enable_holiday": ConfigField(
                type=bool,
                default=True,
                description="是否启用节假日感知"
            ),
            "enable_lunar": ConfigField(
                type=bool,
                default=True,
                description="是否启用农历感知（需要 lunarcalendar 库）"
            ),
            "enable_solar_term": ConfigField(
                type=bool,
                default=True,
                description="是否启用节气感知（需要 lunarcalendar 库）"
            ),
        },
        "components": {
            "enable_event_handler": ConfigField(
                type=bool,
                default=True,
                description="是否启用自动注入（推荐开启）"
            ),
            "enable_tool": ConfigField(
                type=bool,
                default=False,
                description="是否启用 Tool 工具接口（LLM 可主动调用查询日期，不推荐开启）"
            ),
            "enable_command": ConfigField(
                type=bool,
                default=True,
                description="是否启用 /date 命令"
            ),
        },
        "llm": {
            "enable_llm_expand": ConfigField(
                type=bool,
                default=False,
                description="是否使用 LLM 将 /date 命令的输出转换为自然语言（仅对 /date 命令有效，不影响自动注入和 Tool 工具）"
            ),
            "llm_model": ConfigField(
                type=str,
                default="replyer",
                description="LLM 模型名称（用于 /date 命令的自然语言扩展）"
            ),
        },
    }
    
    config_section_descriptions: dict = {
        "plugin": "插件基本信息",
        "perception": "感知功能配置",
        "components": "组件开关",
        "llm": "LLM 扩展配置（仅对 /date 命令有效）",
    }
    
    # ==================== 组件注册 ====================
    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """
        返回插件包含的所有组件
        
        根据配置决定注册哪些组件：
        - enable_event_handler: 注册 DateInjectEventHandler
        - enable_tool: 注册 DateTool
        - enable_command: 注册 DateCommand
        
        Returns:
            组件列表，每个元素为 (ComponentInfo, Type) 元组
        """
        components = []
        
        # 读取配置
        enable_event_handler = self.get_config("components.enable_event_handler", True)
        enable_tool = self.get_config("components.enable_tool", True)
        enable_command = self.get_config("components.enable_command", True)
        
        # 条件注册组件
        if enable_event_handler:
            components.append((DateInjectEventHandler.get_handler_info(), DateInjectEventHandler))
            logger.info("[DatePerception] 已注册 EventHandler 组件")
        
        if enable_tool:
            components.append((DateTool.get_tool_info(), DateTool))
            logger.info("[DatePerception] 已注册 Tool 组件")
        
        if enable_command:
            components.append((DateCommand.get_command_info(), DateCommand))
            logger.info("[DatePerception] 已注册 Command 组件")
        
        # 记录依赖库状态
        logger.info(f"[DatePerception] 依赖库状态: "
                   f"chinese-calendar={'可用' if CHINESE_CALENDAR_AVAILABLE else '不可用'}, "
                   f"lunarcalendar={'可用' if LUNARCALENDAR_AVAILABLE else '不可用'}, "
                   f"aiohttp={'可用' if AIOHTTP_AVAILABLE else '不可用'}")
        
        # 记录时区配置
        timezone_name = self.get_config("perception.timezone", "Asia/Shanghai")
        try:
            timezone = ZoneInfo(timezone_name)
            logger.info(f"[DatePerception] 时区配置: {timezone_name}")
        except Exception as e:
            logger.error(f"[DatePerception] 时区配置无效: {timezone_name}，使用默认时区 Asia/Shanghai")
        
        logger.info("[DatePerception] 插件初始化完成")
        
        return components
