# -*- coding: utf-8 -*-
"""
WxPusher notification sender.

Sends messages via the WxPusher API with automatic retry and chunking
for large content.
"""
from __future__ import annotations

import logging
import time

import requests

logger = logging.getLogger(__name__)

_WXPUSHER_API_URL = "https://wxpusher.zjiecode.com/api/send/message"
_MAX_CONTENT_BYTES = 48 * 1024  # 48 KB
_MAX_RETRIES = 3
_RETRY_DELAYS = (2, 4, 8)


class WxPusherSender:
    """Send notifications through WxPusher."""

    def __init__(
        self,
        app_token: str,
        uids: list[str],
        topic_ids: list[str],
        content_type: int = 3,
    ) -> None:
        """Initialize WxPusher sender.

        Args:
            app_token: WxPusher application token.
            uids: List of user UIDs to send to.
            topic_ids: List of topic IDs to send to.
            content_type: Message format — 1=text, 2=html, 3=markdown.
        """
        self._app_token = app_token
        self._uids = uids
        self._topic_ids = topic_ids
        self._content_type = content_type

    def send(self, content: str, summary: str | None = None) -> bool:
        """Send a message via WxPusher.

        Args:
            content: Message body.
            summary: Optional short summary (max 100 chars). Falls back to
                the first 100 characters of *content*.

        Returns:
            True if the message was sent successfully, False otherwise.
        """
        if summary is None:
            summary = content[:100]

        content_bytes = len(content.encode("utf-8"))
        if content_bytes > _MAX_CONTENT_BYTES:
            logger.info(
                "WxPusher content exceeds 48 KB (%d bytes), sending in chunks",
                content_bytes,
            )
            return self._send_chunked(content, summary)

        return self._send_with_retry(content, summary)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_payload(self, content: str, summary: str) -> dict[str, object]:
        """Build the JSON payload for the WxPusher API."""
        return {
            "appToken": self._app_token,
            "content": content,
            "summary": summary,
            "contentType": self._content_type,
            "uids": self._uids,
            "topicIds": self._topic_ids,
        }

    def _send_once(self, content: str, summary: str) -> bool:
        """Attempt a single POST to WxPusher. Returns True on success."""
        payload = self._build_payload(content, summary)
        response = requests.post(_WXPUSHER_API_URL, json=payload, timeout=10)

        if response.status_code != 200:
            logger.error("WxPusher HTTP error: %d", response.status_code)
            return False

        result: dict[str, object] = response.json()
        if result.get("success") is True or result.get("code") == 1000:
            logger.info("WxPusher message sent successfully")
            return True

        logger.error("WxPusher API error: %s", result.get("msg", "unknown"))
        return False

    def _send_with_retry(self, content: str, summary: str) -> bool:
        """Send with up to 3 retries using exponential back-off."""
        for attempt in range(_MAX_RETRIES):
            try:
                if self._send_once(content, summary):
                    return True
            except Exception:
                logger.exception(
                    "WxPusher request failed (attempt %d/%d)",
                    attempt + 1,
                    _MAX_RETRIES,
                )

            if attempt < _MAX_RETRIES - 1:
                delay = _RETRY_DELAYS[attempt]
                logger.info("Retrying WxPusher in %d seconds …", delay)
                time.sleep(delay)

        logger.error("WxPusher send failed after %d attempts", _MAX_RETRIES)
        return False

    def _send_chunked(self, content: str, summary: str) -> bool:
        """Split content at paragraph boundaries and send each chunk."""
        chunks = _split_paragraphs(content, _MAX_CONTENT_BYTES)
        total = len(chunks)
        success_count = 0

        logger.info("WxPusher chunked send: %d chunk(s)", total)

        for idx, chunk in enumerate(chunks):
            chunk_summary = f"{summary} ({idx + 1}/{total})" if total > 1 else summary
            if self._send_with_retry(chunk, chunk_summary):
                success_count += 1
                logger.info("WxPusher chunk %d/%d sent", idx + 1, total)
            else:
                logger.error("WxPusher chunk %d/%d failed", idx + 1, total)

            if idx < total - 1:
                time.sleep(1)

        return success_count == total


def _split_paragraphs(text: str, max_bytes: int) -> list[str]:
    """Split *text* into chunks that each fit within *max_bytes* UTF-8.

    Splits are made at paragraph boundaries (double newline) when possible,
    falling back to single newline, then to the byte limit.
    """
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current: list[str] = []
    current_size = 0

    for para in paragraphs:
        para_bytes = len(para.encode("utf-8"))
        # Separator cost: "\n\n" = 2 bytes when joining
        sep_cost = 2 if current else 0

        if current_size + sep_cost + para_bytes > max_bytes and current:
            chunks.append("\n\n".join(current))
            current = []
            current_size = 0
            sep_cost = 0

        if para_bytes > max_bytes:
            # Paragraph itself exceeds limit — flush current first, then split by lines
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_size = 0
            for line in para.split("\n"):
                line_bytes = len(line.encode("utf-8"))
                line_sep = 1 if current else 0
                if current_size + line_sep + line_bytes > max_bytes and current:
                    chunks.append("\n".join(current))
                    current = []
                    current_size = 0
                current.append(line)
                current_size += (1 if current_size else 0) + line_bytes
            # Flush line-split content before resuming paragraph-level joins
            if current:
                chunks.append("\n".join(current))
                current = []
                current_size = 0
        else:
            current.append(para)
            current_size += sep_cost + para_bytes

    if current:
        chunks.append("\n\n".join(current))

    return chunks if chunks else [text]
