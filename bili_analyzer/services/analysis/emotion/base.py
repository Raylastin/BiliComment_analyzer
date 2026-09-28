"""Emotion analyzer interface and threshold mapping."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from bili_analyzer.constants import EmotionLabel


@dataclass(frozen=True)
class EmotionResult:
    label: str
    confidence: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "confidence", _clamp(self.confidence))


class EmotionAnalyzer(ABC):
    @abstractmethod
    def analyze(self, text: str) -> EmotionResult:
        """Return emotion label and confidence for one comment text."""


def map_score_to_emotion(
    score: float,
    positive_threshold: float = 0.6,
    negative_threshold: float = 0.4,
) -> EmotionResult:
    """Map a continuous 0..1 score to three labels.

    Higher score means more positive. Confidence follows the chosen label:
    positive -> score, negative -> 1 - score, neutral -> distance to 0.5.
    """
    score = _clamp(score)
    if score > positive_threshold:
        return EmotionResult(EmotionLabel.POSITIVE.value, score)
    if score < negative_threshold:
        return EmotionResult(EmotionLabel.NEGATIVE.value, 1 - score)
    return EmotionResult(EmotionLabel.NEUTRAL.value, 1 - 2 * abs(score - 0.5))


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))

