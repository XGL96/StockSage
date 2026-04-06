# -*- coding: utf-8 -*-
"""Tests for NotificationRouter."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from stocksage.config_bridge import ConfigBridge


def _make_bridge(tmp_config_yaml: Path) -> ConfigBridge:
    return ConfigBridge(tmp_config_yaml)


class TestNotificationRouter:
    """Tests for NotificationRouter with mocked dependencies."""

    def _build_router(self, tmp_config_yaml: Path, dsa_service: MagicMock | None, wxpusher: MagicMock | None):
        """Build a NotificationRouter with injected mocks."""
        from stocksage.notification_router import NotificationRouter

        bridge = _make_bridge(tmp_config_yaml)

        # Patch imports inside __init__
        with patch.dict("sys.modules", {"src.notification": MagicMock()}):
            with patch.object(NotificationRouter, "__init__", lambda self, b: None):
                router = NotificationRouter.__new__(NotificationRouter)
                router._bridge = bridge
                router._dsa_service = dsa_service
                router._wxpusher_sender = wxpusher
        return router

    def test_send_both_channels(self, tmp_config_yaml: Path) -> None:
        dsa = MagicMock()
        dsa.send.return_value = True
        wx = MagicMock()
        wx.send.return_value = True

        router = self._build_router(tmp_config_yaml, dsa, wx)
        assert router.send("report content") is True
        dsa.send.assert_called_once_with("report content")
        wx.send.assert_called_once_with("report content")

    def test_send_wxpusher_only(self, tmp_config_yaml: Path) -> None:
        wx = MagicMock()
        wx.send.return_value = True

        router = self._build_router(tmp_config_yaml, dsa_service=None, wxpusher=wx)
        assert router.send("report content") is True
        wx.send.assert_called_once()

    def test_all_fail(self, tmp_config_yaml: Path) -> None:
        dsa = MagicMock()
        dsa.send.return_value = False
        wx = MagicMock()
        wx.send.return_value = False

        router = self._build_router(tmp_config_yaml, dsa, wx)
        assert router.send("report content") is False

    def test_is_available(self, tmp_config_yaml: Path) -> None:
        # WxPusher available, DSA unavailable
        router = self._build_router(tmp_config_yaml, dsa_service=None, wxpusher=MagicMock())
        assert router.is_available() is True

        # Neither available
        router2 = self._build_router(tmp_config_yaml, dsa_service=None, wxpusher=None)
        assert router2.is_available() is False
