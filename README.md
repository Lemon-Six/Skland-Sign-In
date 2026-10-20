# Skland-Sign-In

森空岛自动签到青龙脚本，用于实现森空岛平台下《明日方舟》与《终末地》的每日自动签到。  
支持多账号管理及多种消息推送渠道。

上游项目：https://github.com/kafuneri/Skland-Sign-In

> ![Python](https://img.shields.io/badge/Python-3.7+-blue?logo=python&logoColor=white)
> ![Platform](https://img.shields.io/badge/Platform-青龙面板-blue?logo=linux)

## 获取 Token

1. 登录 [森空岛](https://www.skland.com/)

2. 登录成功后再访问：https://web-api.skland.com/account/info/hg

   接口会返回如下数据：

   ```json
   {
       "code": 0,
       "data": {
           "content": "token"
       },
       "msg": "接口会返回您的鹰角网络通行证账号的登录凭证，此凭证可以用于鹰角网络账号系统校验您登录的有效性。泄露登录凭证属于极度危险操作，为了您的账号安全，请勿将此凭证以任何形式告知他人！"
   }
   ```

   其中 `data.content` 中的字符串即为 `token`

## 使用指南

青龙面板创建订阅

链接: `https://github.com/devnakx/skyland_auto_checkin.git`

定时规则: `4 5 * * *`

## 添加环境变量

青龙 →「环境变量」，添加：

| 变量名              | 值                                        |
| ------------------- | ----------------------------------------- |
| `SKLAND_TOKEN`      | 森空岛 Token；多个账号用英文分号 `;` 分隔 |
| `WECHAT_CORP_ID`    | 企业微信企业 ID                           |
| `WECHAT_APP_SECRET` | 自建应用 Secret                           |
| `WECHAT_AGENT_ID`   | 自建应用 AgentId                          |
| `WECHAT_TO_USER`    | 通讯录成员 UserID                         |

我用的企业微信应用通知，不搞通知只需要添加森空岛token变量就行

## 运行截图  

<img width="366" height="295" alt="image" src="https://github.com/user-attachments/assets/55ee4bbc-3f3a-4e63-8746-3dcbc059ff90" />

## 感谢以下项目

* 本项目的核心 API 交互逻辑（`skland_api.py`）提取自 AstrBot 的开源插件 [astrbot_plugin_skland](https://github.com/Azincc/astrbot_plugin_skland)
