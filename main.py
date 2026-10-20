#!/usr/bin/env python3
# cron: 0 1 * * *
"""QingLong adapter for kafuneri/Skland-Sign-In with WeCom self-built app notifications.

Required:
  SKLAND_TOKEN
Optional notification settings:
  WECHAT_CORP_ID, WECHAT_APP_SECRET, WECHAT_AGENT_ID, WECHAT_TO_USER
Keep the upstream skland_api.py unchanged and in the same directory.
"""
import asyncio
import logging
import os
import random
import sys
from datetime import datetime
from typing import List, Tuple

from skland_api import SklandAPI
from notifier import send_wecom_app

LOG_LEVEL = os.getenv("SKLAND_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("SklandQingLong")


def load_accounts() -> List[Tuple[str, str]]:
    raw = os.getenv("SKLAND_TOKEN", "").strip() or os.getenv("SKLAND_TOKENS", "").strip()
    if not raw:
        raise ValueError("未设置 SKLAND_TOKEN，请在青龙「环境变量」中配置。")
    tokens = [part.strip() for line in raw.splitlines() for part in line.split(";") if part.strip()]
    raw_names = os.getenv("SKLAND_NICKNAMES", "").strip()
    names = [part.strip() for line in raw_names.splitlines() for part in line.split(";") if part.strip()]
    return [(names[i] if i < len(names) and names[i] else f"账号{i + 1}", token)
            for i, token in enumerate(tokens)]


def already_signed(error: str) -> bool:
    text = (error or "").lower()
    return any(word in text for word in ("已签到", "请勿重复", "重复签到", "already", "签到过", "今日已"))


async def main() -> int:
    summary = []
    failures = 0
    return_code = 0

    try:
        accounts = load_accounts()
    except ValueError as exc:
        logger.error("%s", exc)
        try:
            await send_wecom_app(
                f"森空岛签到任务配置错误\n{exc}\n时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        except Exception as notify_exc:
            logger.error("企业微信应用通知失败：%s", notify_exc)
        return 2

    logger.info("森空岛签到开始，共 %d 个账号；目标：明日方舟 + 终末地", len(accounts))
    api = SklandAPI(max_retries=3)
    try:
        retries = max(1, min(5, int(os.getenv("SKLAND_DID_RETRIES", "3"))))
        did_ok = False
        for attempt in range(1, retries + 1):
            try:
                await api.get_device_id()
                did_ok = True
                logger.info("设备指纹初始化成功")
                break
            except Exception as exc:
                logger.warning("设备指纹初始化失败（%d/%d）：%s", attempt, retries, exc)
                if attempt < retries:
                    await asyncio.sleep(min(30, attempt * 10))

        if not did_ok:
            failures += 1
            summary.append("设备指纹初始化失败，签到未执行")
            return_code = 1
        else:
            delay_max = max(0, min(120, int(os.getenv("SKLAND_START_DELAY_MAX", "8"))))
            if delay_max:
                delay = random.randint(1, delay_max)
                logger.info("随机等待 %d 秒后开始签到", delay)
                await asyncio.sleep(delay)

            for idx, (nickname, token) in enumerate(accounts, 1):
                logger.info("开始处理 %s（%d/%d）", nickname, idx, len(accounts))
                lines = [f"{nickname}："]
                try:
                    results, official_nickname = await api.do_full_sign_in(token)
                    if official_nickname:
                        logger.info("%s：识别到角色「%s」", nickname, official_nickname)
                    if not results:
                        lines.append("  - 未找到明日方舟或终末地绑定角色")
                        failures += 1
                    else:
                        account_failed = False
                        for result in results:
                            game = str(getattr(result, "game", "游戏"))
                            if getattr(result, "success", False):
                                awards = getattr(result, "awards", []) or []
                                award_text = f"；奖励：{', '.join(map(str, awards))}" if awards else ""
                                lines.append(f"  - {game}：签到成功{award_text}")
                                logger.info("%s / %s：签到成功%s", nickname, game, award_text)
                            elif already_signed(getattr(result, "error", "")):
                                lines.append(f"  - {game}：今日已签到")
                                logger.info("%s / %s：今日已签到", nickname, game)
                            else:
                                err = str(getattr(result, "error", "未知错误"))[:160]
                                lines.append(f"  - {game}：签到失败（{err}）")
                                logger.error("%s / %s：签到失败：%s", nickname, game, err)
                                account_failed = True
                        if account_failed:
                            failures += 1
                except Exception as exc:
                    failures += 1
                    logger.exception("%s：处理账号异常", nickname)
                    lines.append(f"  - 处理异常：{str(exc)[:160]}")
                summary.extend(lines)
                if idx < len(accounts):
                    await asyncio.sleep(max(0, min(60, int(os.getenv("SKLAND_ACCOUNT_INTERVAL", "3")))))
            return_code = 1 if failures else 0

    except Exception as exc:
        failures += 1
        return_code = 1
        logger.exception("签到任务异常")
        summary.append(f"任务异常：{str(exc)[:200]}")
    finally:
        try:
            await api.close()
        except Exception as exc:
            logger.warning("关闭 API 客户端失败：%s", exc)

    status = "存在失败" if failures else "执行完成"
    message = (
        "森空岛签到结果\n"
        f"状态：{status}\n"
        f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        + "\n".join(summary or ["无签到明细"])
    )
    try:
        await send_wecom_app(message)
    except Exception as exc:
        logger.error("企业微信应用通知失败：%s", exc)
        if return_code == 0:
            return_code = 1
    logger.info("签到任务结束，失败计数：%d", failures)
    return return_code


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        logger.warning("任务被手动中断")
        sys.exit(130)
