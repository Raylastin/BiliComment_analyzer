"""Matplotlib chart generation for analysis results."""

from __future__ import annotations

from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _configure_chinese_font() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def overview_figure(overview: dict[str, Any]):
    """Return a Figure with comment pie chart and user bar chart."""
    _configure_chinese_font()
    labels = list(overview["by_comment"].keys())
    comment_values = [item["count"] for item in overview["by_comment"].values()]
    user_values = [item["count"] for item in overview["by_user"].values()]

    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    axes[0].pie(
        comment_values,
        labels=labels,
        autopct="%1.1f%%",
        startangle=90,
    )
    axes[0].set_title("按评论数统计")

    axes[1].bar(labels, user_values, color=["#4CAF50", "#F44336", "#9E9E9E"])
    axes[1].set_title("按用户数统计")
    axes[1].set_ylabel("用户数")

    fig.suptitle("情感倾向分布")
    fig.tight_layout()
    return fig


def transition_figure(transition: dict[str, Any]):
    """Return a Figure for six single transitions and multiple conversions."""
    _configure_chinese_font()
    six = transition["six_transitions"]
    labels = list(six.keys())
    values = list(six.values())

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(labels, values, color="#2196F3")
    ax.set_title(
        f"单次转化统计（多次转化 {transition['multiple_conversions']} 人）"
    )
    ax.set_ylabel("用户数")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    return fig


def extremes_figure(extremes: dict[str, Any]):
    """Return a Figure comparing always-positive and always-negative users."""
    _configure_chinese_font()
    positive = extremes["always_positive"][:10]
    negative = extremes["always_negative"][:10]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.axis("off")
    rows = [
        ["类型", "用户(mid)", "评论数", "平均置信度"],
    ]
    for item in positive:
        rows.append(["一直正面", item["masked_mid"], item["comment_count"], item["avg_confidence"]])
    for item in negative:
        rows.append(["一直负面", item["masked_mid"], item["comment_count"], item["avg_confidence"]])

    table = ax.table(cellText=rows, loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.5)
    fig.tight_layout()
    return fig

