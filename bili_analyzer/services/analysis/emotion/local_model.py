"""Default local Chinese sentiment analyzer.

This is a lightweight, dependency-free lexicon model. It is intentionally
pluggable: replace it with a transformer model or another provider by
implementing :class:`EmotionAnalyzer`.
"""

from __future__ import annotations

from bili_analyzer.constants import EmotionLabel
from bili_analyzer.services.analysis.emotion.base import (
    EmotionAnalyzer,
    EmotionResult,
    map_score_to_emotion,
)

POSITIVE_WORDS = (
    "好", "赞", "喜欢", "优秀", "支持", "棒", "厉害", "好看", "感谢", "加油",
    "期待", "精彩", "爱了", "神作", "不错", "太棒", "完美", "推荐", "顶",
    "牛", "真香", "舒服", "好听", "感动", "收藏", "三连", "有用",
)

NEGATIVE_WORDS = (
    "差", "烂", "垃圾", "讨厌", "恶心", "失望", "不好", "难看", "无聊",
    "浪费时间", "骗", "离谱", "太差", "差评", "拉胯", "无语", "尴尬",
    "翻车", "踩", "不值", "难受", "难听", "烂片",
)


class LocalLexiconAnalyzer(EmotionAnalyzer):
    def __init__(
        self,
        positive_threshold: float = 0.6,
        negative_threshold: float = 0.4,
    ) -> None:
        self.positive_threshold = positive_threshold
        self.negative_threshold = negative_threshold

    def analyze(self, text: str) -> EmotionResult:
        normalized = (text or "").strip()
        positive = sum(normalized.count(word) for word in POSITIVE_WORDS)
        negative = sum(normalized.count(word) for word in NEGATIVE_WORDS)

        if positive == 0 and negative == 0:
            return EmotionResult(EmotionLabel.NEUTRAL.value, 0.5)

        score = positive / (positive + negative)
        return map_score_to_emotion(
            score,
            positive_threshold=self.positive_threshold,
            negative_threshold=self.negative_threshold,
        )

