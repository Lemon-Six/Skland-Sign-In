"""WeCom self-built application message sender.

Environment variables:
  WECHAT_CORP_ID
  WECHAT_APP_SECRET
  WECHAT_AGENT_ID
  WECHAT_TO_USER (one or more UserIDs separated by |; defaults to @all only if explicitly set)
"""
import logging
import os
import time
from typing import Optional

import httpx

logger = logging.getLogger("SklandQingLong")
API_BASE = "https://qyapi.weixin.qq.com/cgi-bin"


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"未配置环境变量 {name}")
    return value


async def send_wecom_app(message: str) -> None:
    corp_id = os.getenv("WECHAT_CORP_ID", "").strip()
    secret = os.getenv("WECHAT_APP_SECRET", "").strip()
    agent_id = os.getenv("WECHAT_AGENT_ID", "").strip()
    to_user = os.getenv("WECHAT_TO_USER", "").strip()

    # Optional notifications: if no WeCom app variables are configured, don't fail sign-in.
    if not any((corp_id, secret, agent_id, to_user)):
        logger.info("未配置企业微信自建应用环境变量，跳过通知")
        return

    corp_id = _required_env("WECHAT_CORP_ID")
    secret = _required_env("WECHAT_APP_SECRET")
    agent_id = _required_env("WECHAT_AGENT_ID")
    to_user = _required_env("WECHAT_TO_USER")

    try:
        agent_id_int = int(agent_id)
    except ValueError as exc:
        raise ValueError("WECHAT_AGENT_ID 必须是数字") from exc

    # Avoid logging credentials or the access_token.
    async with httpx.AsyncClient(timeout=15) as client:
        token_resp = await client.get(
            f"{API_BASE}/gettoken",
            params={"corpid": corp_id, "corpsecret": secret},
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()
        if token_data.get("errcode") != 0 or not token_data.get("access_token"):
            raise RuntimeError(
                f"获取企业微信 access_token 失败：errcode={token_data.get('errcode')}，"
                f"errmsg={token_data.get('errmsg', '未知错误')}"
            )
        access_token = token_data["access_token"]

        response = await client.post(
            f"{API_BASE}/message/send",
            params={"access_token": access_token},
            json={
                "touser": to_user,
                "msgtype": "text",
                "agentid": agent_id_int,
                "text": {"content": message[:2000]},
                "safe": 0,
                "enable_duplicate_check": 1,
                "duplicate_check_interval": 1800,
            },
        )
        response.raise_for_status()
        result = response.json()

    if result.get("errcode") != 0:
        raise RuntimeError(
            f"企业微信应用消息发送失败：errcode={result.get('errcode')}，"
            f"errmsg={result.get('errmsg', '未知错误')}；请检查应用可见范围和接收人 UserID"
        )
    logger.info("企业微信自建应用通知发送成功")


async def send_wecom(message: str) -> None:
    """Compatibility alias for callers using the older helper name."""
    await send_wecom_app(message)
