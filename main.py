#!/usr/bin/env python3
# cron: 0 1 * * *
# 青龙定时任务：每天北京时间 01:00（请确认青龙/容器时区）
"""QingLong adapter for kafuneri/Skland-Sign-In.

Uses the upstream skland_api.py unchanged. No config.yaml and no notification
provider are required. Set SKLAND_TOKEN in QingLong environment variables.
Multiple tokens may be separated by semicolons or newlines.
"""
import asyncio
import logging
import os
import random
import sys
from typing import List, Tuple

from skland_api import SklandAPI

LOG_LEVEL = os.getenv("SKLAND_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("SklandQingLong")


def load_accounts() -> List[Tuple[str, str]]:
    """Return (display_name, token) pairs without printing tokens."""
    raw = os.getenv("SKLAND_TOKEN", "").strip()
    if not raw:
        raw = os.getenv("SKLAND_TOKENS", "").strip()
    if not raw:
        raise ValueError(
            "未设置 SKLAND_TOKEN。请在青龙「环境变量」中新建 SKLAND_TOKEN。"
        )

    # Support semicolon or newline separators; avoid comma because token formats
    # should not be assumed comma-free forever.
    tokens = [x.strip() for line in raw.splitlines() for x in line.split(";") if x.strip()]
    names_raw = os.getenv("SKLAND_NICKNAMES", "").strip()
    names = [x.strip() for line in names_raw.splitlines() for x in line.split(";") if x.strip()]

    accounts = []
    for idx, token in enumerate(tokens, 1):
        name = names[idx - 1] if idx <= len(names) and names[idx - 1] else f"账号{idx}"
        accounts.append((name, token))
    return accounts


def is_already_signed(error: str) -> bool:
    text = (error or "").lower()
    return any(word in text for word in ("已签到", "请勿重复", "重复签到", "already", "签到过", "今日已"))


async def run() -> int:
    try:
        accounts = load_accounts()
    except ValueError as exc:
        logger.error("%s", exc)
        return 2

    logger.info("森空岛青龙签到开始，共 %d 个账号；签到范围：明日方舟 + 终末地", len(accounts))
    api = SklandAPI(max_retries=3)
    failures = 0

    try:
        # Initialise the device fingerprint with bounded retries, as in the
        # upstream project's intended startup flow.
        did_retries = max(1, min(5, int(os.getenv("SKLAND_DID_RETRIES", "3"))))
        did_ok = False
        for attempt in range(1, did_retries + 1):
            try:
                await api.get_device_id()
                did_ok = True
                logger.info("设备指纹初始化成功")
                break
            except Exception as exc:
                logger.warning("设备指纹初始化失败（%d/%d）：%s", attempt, did_retries, exc)
                if attempt < did_retries:
                    await asyncio.sleep(min(30, 10 * attempt))
        if not did_ok:
            logger.error("设备指纹连续初始化失败，本次任务终止")
            return 1

        # Small random startup delay to avoid all scheduled clients firing at
        # exactly the same second. Set SKLAND_START_DELAY_MAX=0 to disable.
        delay_max = max(0, min(120, int(os.getenv("SKLAND_START_DELAY_MAX", "8"))))
        if delay_max:
            delay = random.randint(1, delay_max)
            logger.info("随机等待 %d 秒后开始签到", delay)
            await asyncio.sleep(delay)

        for index, (nickname, token) in enumerate(accounts, 1):
            logger.info("开始处理 %s（%d/%d）", nickname, index, len(accounts))
            try:
                # Upstream SklandAPI handles both games in this call.
                results, official_nickname = await api.do_full_sign_in(token)
                if official_nickname:
                    logger.info("%s：识别到森空岛角色「%s」", nickname, official_nickname)
                if not results:
                    logger.error("%s：未找到明日方舟或终末地绑定角色", nickname)
                    failures += 1
                else:
                    account_failed = False
                    for result in results:
                        if result.success:
                            award_text = f"（奖励：{', '.join(result.awards)}）" if result.awards else ""
                            logger.info("✅ %s / %s：签到成功%s", nickname, result.game, award_text)
                        elif is_already_signed(getattr(result, "error", "")):
                            logger.info("✅ %s / %s：今日已签到", nickname, result.game)
                        else:
                            logger.error("❌ %s / %s：签到失败：%s", nickname, result.game, result.error)
                            account_failed = True
                    if account_failed:
                        failures += 1
            except Exception as exc:
                failures += 1
                logger.exception("%s：处理账号时发生异常：%s", nickname, exc)

            # Pause between accounts to avoid sending requests back-to-back.
            if index < len(accounts):
                await asyncio.sleep(max(0, min(60, int(os.getenv("SKLAND_ACCOUNT_INTERVAL", "3")))))

    finally:
        await api.close()

    if failures:
        logger.warning("签到任务结束，存在 %d 个账号/角色处理失败，请检查上方日志", failures)
        return 1
    logger.info("所有账号处理完成")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(run()))
    except KeyboardInterrupt:
        logger.warning("任务被手动中断")
        sys.exit(130)
