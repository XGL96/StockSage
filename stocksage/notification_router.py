# -*- coding: utf-8 -*-
"""
通知路由器 - 统一管理所有通知渠道。

将 daily_stock_analysis 的 12 个通知渠道与新增的 WxPusher 渠道整合为统一的发送接口。
"""
from __future__ import annotations

import logging
from typing import Any

from stocksage.config_bridge import ConfigBridge

logger = logging.getLogger(__name__)


class NotificationRouter:
    """统一通知路由：DSA NotificationService（12渠道）+ WxPusher。"""

    def __init__(self, bridge: ConfigBridge) -> None:
        self._bridge = bridge
        self._dsa_service: Any = None
        self._wxpusher_sender: Any = None

        # 初始化 DSA NotificationService（延迟导入，因为需要 sys.path 已配置）
        try:
            from src.notification import NotificationService  # type: ignore[import-untyped]
            self._dsa_service = NotificationService()
            channels = self._dsa_service.get_channel_names() if hasattr(self._dsa_service, "get_channel_names") else "unknown"
            logger.info("DSA 通知服务已初始化，渠道: %s", channels)
        except Exception as e:
            logger.warning("DSA 通知服务初始化失败（将仅使用 WxPusher）: %s", e)

        # 初始化 WxPusher
        wx_cfg = bridge.get_wxpusher_config()
        if wx_cfg.get("app_token") and (wx_cfg.get("uids") or wx_cfg.get("topic_ids")):
            try:
                from stocksage.wxpusher_sender import WxPusherSender
                self._wxpusher_sender = WxPusherSender(
                    app_token=wx_cfg["app_token"],
                    uids=wx_cfg.get("uids", []),
                    topic_ids=wx_cfg.get("topic_ids", []),
                    content_type=wx_cfg.get("content_type", 3),
                )
                logger.info("WxPusher 已初始化")
            except Exception as e:
                logger.warning("WxPusher 初始化失败: %s", e)

    def is_available(self) -> bool:
        """是否有至少一个通知渠道可用。"""
        dsa_available = self._dsa_service is not None
        if dsa_available and hasattr(self._dsa_service, "is_available"):
            dsa_available = self._dsa_service.is_available()
        return dsa_available or self._wxpusher_sender is not None

    def send(self, content: str) -> bool:
        """向所有已配置的渠道发送通知。

        Returns:
            True 如果至少一个渠道发送成功。
        """
        any_success = False

        # DSA 通知渠道（12个）
        if self._dsa_service is not None:
            try:
                result = self._dsa_service.send(content)
                if result:
                    any_success = True
                    logger.info("DSA 通知渠道发送成功")
                else:
                    logger.warning("DSA 通知渠道发送失败")
            except Exception as e:
                logger.error("DSA 通知渠道发送异常: %s", e)

        # WxPusher
        if self._wxpusher_sender is not None:
            try:
                result = self._wxpusher_sender.send(content)
                if result:
                    any_success = True
                    logger.info("WxPusher 发送成功")
                else:
                    logger.warning("WxPusher 发送失败")
            except Exception as e:
                logger.error("WxPusher 发送异常: %s", e)

        if not any_success:
            logger.warning("所有通知渠道均发送失败")

        return any_success

    def save_report(self, content: str) -> str | None:
        """通过 DSA 服务保存报告到本地文件。"""
        if self._dsa_service is not None and hasattr(self._dsa_service, "save_report_to_file"):
            try:
                return self._dsa_service.save_report_to_file(content)
            except Exception as e:
                logger.warning("保存报告失败: %s", e)
        return None
