"""Sentiment statistics for a task."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from bili_analyzer.constants import EmotionLabel, MembershipFilter
from bili_analyzer.models import Comment, User, task_comments
from bili_analyzer.utils.mid_mask import mask_mid

TRANSITION_KEYS = [
    f"{EmotionLabel.POSITIVE.value}→{EmotionLabel.NEGATIVE.value}",
    f"{EmotionLabel.POSITIVE.value}→{EmotionLabel.NEUTRAL.value}",
    f"{EmotionLabel.NEGATIVE.value}→{EmotionLabel.POSITIVE.value}",
    f"{EmotionLabel.NEGATIVE.value}→{EmotionLabel.NEUTRAL.value}",
    f"{EmotionLabel.NEUTRAL.value}→{EmotionLabel.POSITIVE.value}",
    f"{EmotionLabel.NEUTRAL.value}→{EmotionLabel.NEGATIVE.value}",
]


class StatisticsService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def compute_overview(
        self, task_id: int, membership: str = MembershipFilter.ALL.value
    ) -> dict[str, Any]:
        df = self._task_df(task_id)
        df = self._filter_membership(df, membership)
        by_comment = self._label_distribution(df["emotion_label"])
        by_user = self._user_label_distribution(df)
        return {
            "filter": membership,
            "total_comments": int(len(df)),
            "total_users": int(df["mid"].nunique()),
            "by_comment": by_comment,
            "by_user": by_user,
        }

    def compute_transition(
        self, task_id: int, membership: str = MembershipFilter.ALL.value
    ) -> dict[str, Any]:
        df = self._task_df(task_id)
        df = self._filter_membership(df, membership)
        total_users = int(df["mid"].nunique())

        transition_counts: dict[str, int] = {key: 0 for key in TRANSITION_KEYS}
        multiple = 0
        final_tendency: Counter[str] = Counter()
        eligible_users = 0

        for _, group in df.groupby("mid"):
            if len(group) < 2:
                continue
            eligible_users += 1
            labels = group.sort_values("ctime")["emotion_label"].tolist()
            trajectory = self._compress_trajectory(labels)
            if len(trajectory) == 2:
                key = f"{trajectory[0]}→{trajectory[1]}"
                transition_counts[key] += 1
            elif len(trajectory) > 2:
                multiple += 1
                final_tendency[trajectory[-1]] += 1

        return {
            "filter": membership,
            "total_users": total_users,
            "eligible_users": eligible_users,
            "eligible_ratio": (eligible_users / total_users) if total_users else 0.0,
            "six_transitions": transition_counts,
            "multiple_conversions": multiple,
            "final_tendency": dict(final_tendency),
        }

    def compute_extremes(
        self,
        task_id: int,
        membership: str = MembershipFilter.ALL.value,
        top_n: int = 10,
    ) -> dict[str, Any]:
        df = self._task_df(task_id)
        df = self._filter_membership(df, membership)
        always_positive: list[dict[str, Any]] = []
        always_negative: list[dict[str, Any]] = []

        for mid, group in df.groupby("mid"):
            labels = group["emotion_label"].tolist()
            if len(labels) < 2:
                continue
            confidence = group["confidence"].mean()
            item = {
                "mid": int(mid),
                "masked_mid": mask_mid(mid),
                "comment_count": int(len(group)),
                "avg_confidence": round(float(confidence), 4),
            }
            if all(label == EmotionLabel.POSITIVE.value for label in labels):
                always_positive.append(item)
            elif all(label == EmotionLabel.NEGATIVE.value for label in labels):
                always_negative.append(item)

        always_positive.sort(key=lambda x: (-x["comment_count"], -x["avg_confidence"]))
        always_negative.sort(key=lambda x: (-x["comment_count"], -x["avg_confidence"]))
        return {
            "filter": membership,
            "always_positive": always_positive[:top_n],
            "always_negative": always_negative[:top_n],
        }

    def _task_df(self, task_id: int) -> pd.DataFrame:
        with self.session_factory() as session:
            stmt = (
                select(
                    Comment.id,
                    Comment.mid,
                    Comment.emotion_label,
                    Comment.confidence,
                    Comment.ctime,
                    User.vip_status,
                )
                .join(task_comments, task_comments.c.comment_id == Comment.id)
                .outerjoin(User, User.mid == Comment.mid)
                .where(task_comments.c.task_id == task_id)
            )
            rows = session.execute(stmt).all()
        df = pd.DataFrame(
            rows,
            columns=["id", "mid", "emotion_label", "confidence", "ctime", "vip_status"],
        )
        if df.empty:
            return df
        df = df.dropna(subset=["emotion_label"])
        df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce").fillna(0.5)
        return df

    @staticmethod
    def _filter_membership(df: pd.DataFrame, membership: str) -> pd.DataFrame:
        if membership == MembershipFilter.MEMBER.value:
            return df[df["vip_status"] == 1]
        if membership == MembershipFilter.NON_MEMBER.value:
            return df[df["vip_status"] == 0]
        if membership == MembershipFilter.UNKNOWN.value:
            return df[df["vip_status"].isna()]
        return df

    @staticmethod
    def _label_distribution(series: pd.Series) -> dict[str, dict[str, Any]]:
        total = int(series.count())
        result: dict[str, dict[str, Any]] = {}
        for label in [EmotionLabel.POSITIVE.value, EmotionLabel.NEGATIVE.value, EmotionLabel.NEUTRAL.value]:
            count = int((series == label).sum())
            result[label] = {
                "count": count,
                "ratio": round(count / total, 4) if total else 0.0,
            }
        return result

    @staticmethod
    def _user_label_distribution(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
        user_labels: dict[int, str] = {}
        for mid, group in df.groupby("mid"):
            ordered = group.sort_values("ctime")
            counter = Counter(ordered["emotion_label"])
            max_count = max(counter.values())
            top_labels = [label for label, count in counter.items() if count == max_count]
            if len(top_labels) == 1:
                user_labels[int(mid)] = top_labels[0]
            else:
                user_labels[int(mid)] = ordered.iloc[-1]["emotion_label"]
        total = len(user_labels)
        result: dict[str, dict[str, Any]] = {}
        for label in [EmotionLabel.POSITIVE.value, EmotionLabel.NEGATIVE.value, EmotionLabel.NEUTRAL.value]:
            count = sum(1 for value in user_labels.values() if value == label)
            result[label] = {
                "count": count,
                "ratio": round(count / total, 4) if total else 0.0,
            }
        return result

    @staticmethod
    def _compress_trajectory(labels: list[str]) -> list[str]:
        compressed: list[str] = []
        for label in labels:
            if not compressed or compressed[-1] != label:
                compressed.append(label)
        return compressed

