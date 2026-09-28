"""Pluggable emotion analysis."""

from bili_analyzer.services.analysis.emotion.api_model import ApiEmotionAnalyzer
from bili_analyzer.services.analysis.emotion.base import (
    EmotionAnalyzer,
    EmotionResult,
    map_score_to_emotion,
)
from bili_analyzer.services.analysis.emotion.local_model import LocalLexiconAnalyzer
from bili_analyzer.services.analysis.emotion.service import EmotionService

__all__ = [
    "ApiEmotionAnalyzer",
    "EmotionAnalyzer",
    "EmotionResult",
    "EmotionService",
    "LocalLexiconAnalyzer",
    "map_score_to_emotion",
]

