from nonebot import MessageSegment
import random
import datetime
from loguru import logger
from PIL import Image
from .constant import PIG_HUB_PATH, PIGINFO_PATH, TODAY_PATH
from .util import async_fetch_pig_data, find_image_file, load_json, save_json
from hoshino import Service
from hoshino.util import pic2b64
from hoshino.typing import CQEvent, HoshinoBot

HELP = """
今日小猪 - 抽取今天属于你的小猪
随机小猪 - 从PigHub随机获取一张猪猪图
找猪 + 关键词 - 从PigHub中搜索
关键词相关的猪猪图片并发送（最多8张）
"""
sv = Service(
    "今天是什么小猪",
    enable_on_default=False,
    help_=HELP.strip(),
)
# 载入小猪信息
PIG_LIST = load_json(PIGINFO_PATH, [])
# —— 烤群友专用：排除人类 + 稀有度权重 ——  
# 稀有猪（低权重，数字越小越稀有）  
RARE_PIG_WEIGHTS = {  
    "pig_god": 1,  
    "chained_crown_pig": 1,  
    "pearl-pig": 2,  
    "jewelry-pig": 2,  
    "vangogh_pig": 3,  
}  
DEFAULT_PIG_WEIGHT = 10  # 普通猪默认权重  
  
def roll_a_pig():  
    # 排除 human  
    pool = [p for p in PIG_LIST if p.get("id") != "human"]  
    if not pool:  
        return None  
    weights = [RARE_PIG_WEIGHTS.get(p.get("id"), DEFAULT_PIG_WEIGHT) for p in pool]  
    return random.choices(pool, weights=weights, k=1)[0]
if not PIG_LIST:
    logger.error("猪圈空荡荡，请检查资源文件！")


@sv.scheduled_job("cron", hour="0", minute="0")
async def auto_refresh_pig_data():
    try:
        data = await async_fetch_pig_data("https://pighub.top/api/all-images")
        if data and data.get("images"):
            save_json(PIG_HUB_PATH, data)
            logger.success(f"成功从 PigHub 刷新 {len(data['images'])} 头猪猪")
        else:
            logger.warning("PigHub 中找不到猪猪，未能刷新数据。")
    except Exception as e:
        logger.error(f"从PigHub中获取猪猪失败: {e}")


@sv.on_fullmatch("今日小猪帮助")
async def send_help(bot: HoshinoBot, ev: CQEvent):
    await bot.send(ev, HELP.strip())


@sv.on_fullmatch("刷新小猪")
async def refresh_pig_data(bot: HoshinoBot, ev: CQEvent):
    try:
        data = await async_fetch_pig_data("https://pighub.top/api/all-images")
        if data and data.get("images"):
            save_json(PIG_HUB_PATH, data)
            msg = f"成功从 PigHub 刷新 {len(data['images'])} 头猪猪"
        else:
            msg = "刷新失败，PigHub 中找不到猪猪。"
        await bot.send(ev, msg)
    except Exception as e:
        await bot.send(ev, f"刷新失败，无法从PigHub获取数据。{e}")


@sv.on_fullmatch("随机小猪")
async def send_random_pig(bot: HoshinoBot, ev: CQEvent):
    data = load_json(PIG_HUB_PATH, {})
    pig_images = data["images"]
    pig = random.choice(pig_images)
    image_url = "https://pighub.top/data/" + pig["thumbnail"].split("/")[-1]
    await bot.send(ev, MessageSegment.image(image_url))


# 主函数
@sv.on_fullmatch("今日小猪")
async def send_today_pig(bot: HoshinoBot, ev: CQEvent):
    today_str = datetime.date.today().isoformat()
    user_id = str(ev.user_id)

    # 读取今日缓存
    today_cache = load_json(TODAY_PATH, {"date": "", "records": {}})

    # 检查日期，如果不是今天，则清空记录
    if today_cache.get("date") != today_str:
        today_cache = {"date": today_str, "records": {}}

    user_records = today_cache["records"]

    # 如果用户今天已经抽过，直接发送结果
    if user_id in user_records:
        pig = user_records[user_id]
    else:
        pig = random.choice(PIG_LIST)
        user_records[user_id] = pig
        save_json(TODAY_PATH, today_cache)
    msg = (
        "今日你是："
        + pig["name"]
        + MessageSegment.image(pic2b64(Image.open(find_image_file(pig["id"]))))
        + "\n"
        + pig["description"]
        + "\n分析："
        + pig["analysis"]
    )

    await bot.send(ev, msg)


@sv.on_prefix("找猪")
async def find_pig(bot: HoshinoBot, ev: CQEvent):
    data = load_json(PIG_HUB_PATH, {})
    pig_images = data["images"]
    if not pig_images:
        await bot.finish("猪圈空荡荡...")
        return

    keyword = ev.message.extract_plain_text().strip()
    found_pigs = [pig for pig in pig_images if keyword.lower() in pig["title"].lower()]

    if not found_pigs:
        await bot.finish(ev, "你要找的猪仔离家出走了~")

    messages = []
    count = min(len(found_pigs), 8)
    for i in range(count):
        pig = found_pigs[i]
        image_url = "https://pighub.top/data/" + pig["thumbnail"].split("/")[-1]
        messages.append(str(pig["title"] + MessageSegment.image(image_url)))
    await bot.send(ev, "\n".join(messages))

@sv.on_prefix("烤群友")  
async def roast_member(bot: HoshinoBot, ev: CQEvent):  
    text = ev.message.extract_plain_text().strip()  
  
    force_keywords = {"打点后厨", "偷换烤架", "贿赂主厨", "加急生火"}  
    super_force_keyword = "强行点火"  
  
    # 1) 解析后门口令  
    force_mode = None  
    if super_force_keyword in text:  
        force_mode = "super"  
    elif any(k in text for k in force_keywords):  
        force_mode = "normal"  
  
    # 2) 解析目标：优先回复，其次 @  
    target_id = None  
    target_name = "群友"  
  
    reply = getattr(ev, "reply", None)  
    if reply:  
        try:  
            target_id = str(reply.sender.user_id)  
            target_name = reply.sender.card or reply.sender.nickname  
        except Exception:  
            target_id = None  
  
    if not target_id:  
        for seg in ev.message:  
            if seg.type == "at":  
                target_id = str(seg.data["qq"])  
                target_name = "对方"  
                break  
  
    if not target_id:  
        await bot.finish(ev, "请 @ 或回复你要烤的群友！")  
        return  
  
    if target_id == str(ev.user_id):  
        await bot.finish(ev, "对自己好一点，别自焚。请发送「今日烤猪」。")  
        return  
  
    # 3) 读取今日抽猪缓存  
    today_str = datetime.date.today().isoformat()  
    today_cache = load_json(TODAY_PATH, {"date": "", "records": {}})  
  
    if today_cache.get("date") != today_str:  
        today_cache = {"date": today_str, "records": {}}  
  
    records = today_cache["records"]  
  
    attacker_pig = records.get(str(ev.user_id))  
    target_pig = records.get(target_id)  
  
    # 4) 目标资格检查  
    #    对方今天还没抽过 → 当场帮他抽一个今日小猪并写入缓存  
    if not target_pig:  
        if not PIG_LIST:  
            await bot.finish(ev, "猪图鉴为空，请先检查资源文件。")  
            return  
        target_pig = random.choice(PIG_LIST)  
        records[target_id] = target_pig  
        today_cache["date"] = today_str          # 确保日期字段正确  
        save_json(TODAY_PATH, today_cache)
  
    target_pig_id = target_pig.get("id", "")  
    if target_pig_id == "human":  
        await bot.finish(ev, f"【{target_name}】今天是人类形态，烤架拒绝处理。")  
        return  
  
    # 5) 基础 60% 成功 / 30% 逃脱 / 10% 反噬  
    roll = 1 if force_mode in {"normal", "super"} else random.randint(1, 100)  
  
    # —— 按双方猪种调整概率（force 模式下 roll=1 会强制成功，不受影响）——  
    success_line = 60   # <= success_line 判成功  
    escape_line = 90    # <= escape_line 判逃脱，其余为反噬  
  
    target_id_str = target_pig.get("id", "")  
    attacker_id_str = attacker_pig.get("id", "") if attacker_pig else ""  
  
    # 目标好烤的猪 → 提高成功率  
    EASY_TARGETS = {"roasted-pig", "bacon", "char-siu"}  
    # 目标难烤的猪 → 降低成功率  
    HARD_TARGETS = {"wild-boar", "pig_god", "chained_crown_pig"}  
  
    if target_id_str in EASY_TARGETS:  
        success_line += 20  
    elif target_id_str in HARD_TARGETS:  
        success_line -= 25  
  
    # 发起者是神/王 → 降低反噬概率（抬高逃脱线）  
    if attacker_id_str in {"pig_god", "chained_crown_pig"}:  
        escape_line += 5  
  
    # 保证阈值合法且不交叉  
    success_line = max(0, min(success_line, 100))  
    escape_line = max(success_line, min(escape_line, 100))  
  
    # 6) 判定结果  
    if roll <= success_line:  
        food = roll_a_pig()  
        if not food:  
            await bot.finish(ev, "猪图鉴为空，请先检查资源文件。")  
            return  
  
        image = find_image_file(food["id"])  
  
        msg = f"【{target_name}】被烤成了【{food['name']}】\n{food['description']}\n分析：{food['analysis']}"  
        if image:  
            with Image.open(image) as img:  
                msg += MessageSegment.image(pic2b64(img))  
  
        await bot.send(ev, msg)  
        return  
  
    if roll <= escape_line:  
        await bot.finish(ev, f"【{target_name}】机灵地逃掉了，这次没烤到。")  
        return  
  
    backfire_food = roll_a_pig()  
    if not backfire_food:  
        await bot.finish(ev, "猪图鉴为空，请先检查资源文件。")  
        return  
  
    image = find_image_file(backfire_food["id"])  
  
    msg = (  
        f"烤架反噬了发起者，你自己变成了【{backfire_food['name']}】\n"  
        f"{backfire_food['description']}\n分析：{backfire_food['analysis']}"  
    )  
    if image:  
        with Image.open(image) as img:  
            msg += MessageSegment.image(pic2b64(img))  
  
    await bot.send(ev, msg)