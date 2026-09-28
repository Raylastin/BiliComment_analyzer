"""Optional remote emotion analyzer."""

from __future__ import annotations

from typing import Any

import httpx

from bili_analyzer.constants import EmotionLabel
from bili_analyzer.services.analysis.emotion.base import EmotionAnalyzer, EmotionResult


class ApiEmotionAnalyzer(EmotionAnalyzer):
    def __init__(
        self,
        url: str,
        api_key: str | None = None,
        timeout: float = 10.0,
        label_map: dict[str, str] | None = None,
    ) -> None:
        self.url = url
        self.api_key = api_key
        self.timeout = timeout
        self.label_map = label_map or {
            "positive": EmotionLabel.POSITIVE.value,
            "negative": EmotionLabel.NEGATIVE.value,
            "neutral": EmotionLabel.NEUTRAL.value,
            "正面": EmotionLabel.POSITIVE.value,
            "负面": EmotionLabel.NEGATIVE.value,
            "中立": EmotionLabel.NEUTRAL.value,
        }

    def analyze(self, text: str) -> EmotionResult:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload: dict[str, Any] = {"text": text}
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(self.url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        label = self.label_map.get(str(data.get("label", "").lower()), EmotionLabel.NEUTRAL.value)
        confidence = _as_float(data.get("confidence"), 0.5)
        return EmotionResult(label, confidence)


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

