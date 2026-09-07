"""
reporter.py — 통계 집계 · 차트 생성 · 리포트 출력
담당: C (통계/대시보드) · 브랜치: feat/reporter
관련 요구사항: ⑥ stats, ⑦ 대시보드 시각화, ⑧ 리포트 생성, ⑨ export

설계 원칙: 이 파일은 저장소(SQLite)를 직접 열지 않는다.
           리뷰 목록(딕셔너리 리스트)을 인자로 받아 그림과 글자만 만든다.
           → A의 저장 방식이 바뀌어도 이 파일은 고칠 필요가 없다.
"""

from __future__ import annotations

import os
import sys
import logging
import platform
import statistics
import unicodedata
from collections import Counter
from datetime import datetime

import matplotlib

matplotlib.use("Agg")  # 화면(GUI) 없는 환경에서도 PNG 저장이 되게 한다

import matplotlib.pyplot as plt
from matplotlib import font_manager

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 표시 규칙 — 감정 이름·색·순서를 여기 한 곳에서만 관리한다
# ─────────────────────────────────────────────────────────────

SENTIMENT_ORDER = ["positive", "neutral", "negative"]

SENTIMENT_KO = {
    "positive": "긍정",
    "neutral": "중립",
    "negative": "부정",
}

# 긍정=파랑, 중립=회색, 부정=빨강
# 초록/빨강 대신 파랑/빨강을 쓴 이유는 아래 '설계메모'에 적어두었다.
SENTIMENT_COLOR = {
    "positive": "#2a78d6",
    "neutral": "#898781",
    "negative": "#e34948",
}

# 막대 '안쪽'에 숫자를 쓸 때의 글자색.
# 파랑·빨강 위에는 흰 글씨가 잘 보이지만, 회색 위에서는 흰 글씨가 흐려진다.
SENTIMENT_INK = {
    "positive": "#ffffff",
    "neutral": "#0b0b0b",
    "negative": "#ffffff",
}

SURFACE = "#fcfcfb"  # 차트 배경색
INK = "#0b0b0b"  # 글자색
MUTED = "#898781"  # 흐린 글자색
GRID = "#e1e0d9"  # 눈금선 색

RATING_RANGE = [1, 2, 3, 4, 5]  # 별점은 항상 1~5를 모두 표시한다


# ─────────────────────────────────────────────────────────────
# 1. 한글 폰트 자동 설정
# ─────────────────────────────────────────────────────────────

FONT_CANDIDATES = {
    "Windows": ["Malgun Gothic", "NanumGothic", "Gulim"],
    "Darwin": ["AppleGothic", "Apple SD Gothic Neo", "NanumGothic"],
    "Linux": ["NanumGothic", "NanumBarunGothic", "Noto Sans KR", "Noto Sans CJK KR"],
}

# 위 목록에 정확히 일치하는 게 없을 때, 이름에 이 조각이 들어간 폰트를 찾아본다.
# (리눅스는 배포판마다 폰트 이름이 제각각이라 정확한 이름만으로는 자주 실패한다)
FONT_KEYWORDS = ["Nanum", "Noto Sans CJK", "Noto Sans KR", "Malgun", "AppleGothic"]


def setup_korean_font() -> str | None:
    """실행 중인 운영체제에 맞는 한글 폰트를 찾아 matplotlib에 등록한다.

    1) 운영체제별 대표 폰트 이름을 순서대로 찾아본다
    2) 없으면 이름에 한글 폰트 키워드가 들어간 폰트를 찾아본다
    찾으면 폰트 이름을, 끝내 못 찾으면 None을 돌려준다.
    """
    system = platform.system()
    installed = {f.name for f in font_manager.fontManager.ttflist}

    candidates = FONT_CANDIDATES.get(system, [])
    for name in candidates:
        if name in installed:
            return _apply_font(name, system)

    for keyword in FONT_KEYWORDS:
        matched = sorted(n for n in installed if keyword in n)
        if matched:
            return _apply_font(matched[0], system)

    plt.rcParams["axes.unicode_minus"] = False
    logger.warning(
        "한글 폰트를 찾지 못했습니다 (%s). 차트의 한글이 □□□로 깨집니다. 찾아본 이름: %s",
        system,
        ", ".join(candidates) or "(없음)",
    )
    return None


def _apply_font(name: str, system: str) -> str:
    plt.rcParams["font.family"] = name
    # 폰트를 바꾸면 음수 부호(−)가 네모로 깨진다. 아래 한 줄이 그걸 막는다.
    plt.rcParams["axes.unicode_minus"] = False
    logger.info("한글 폰트 적용: %s (%s)", name, system)
    return name


# ─────────────────────────────────────────────────────────────
# 2. 차트 ① 감정 분포
# ─────────────────────────────────────────────────────────────


def chart_sentiment_distribution(
    reviews: list[dict],
    out_dir: str = "output",
    filename: str = "sentiment_distribution.png",
) -> str | None:
    """긍정/중립/부정이 각각 몇 건인지 가로 막대로 그려 PNG로 저장한다.

    reviews : 'sentiment' 키를 가진 딕셔너리들의 목록
    반환값  : 저장된 파일 경로 (그릴 게 없으면 None)
    """
    counts = Counter(r["sentiment"] for r in reviews if r.get("sentiment"))
    total = sum(counts.values())

    if total == 0:
        logger.warning("분석된 리뷰가 없어 감정 분포 차트를 건너뜁니다.")
        return None

    labels = [SENTIMENT_KO[s] for s in SENTIMENT_ORDER]
    values = [counts.get(s, 0) for s in SENTIMENT_ORDER]
    colors = [SENTIMENT_COLOR[s] for s in SENTIMENT_ORDER]

    fig, ax = plt.subplots(figsize=(7.0, 3.0), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)

    bars = ax.barh(labels, values, color=colors, height=0.55)
    ax.invert_yaxis()  # 긍정이 맨 위로 오게 뒤집는다

    # 막대 끝에 "89건 (62.7%)" 형태로 직접 표기
    for bar, value in zip(bars, values):
        pct = value / total * 100
        ax.text(
            bar.get_width() + total * 0.015,
            bar.get_y() + bar.get_height() / 2,
            f"{value}건 ({pct:.1f}%)",
            va="center",
            fontsize=10.5,
            color=INK,
        )

    ax.set_xlim(0, max(values) * 1.30)
    ax.set_title(
        f"감정 분포 (분석 완료 {total}건)",
        fontsize=13,
        color=INK,
        pad=14,
        loc="left",
    )

    # 눈금선·테두리를 지워 데이터만 남긴다
    ax.get_xaxis().set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=11.5, colors=INK)
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_visible(False)

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)

    logger.info("차트 저장: %s", path)
    return path


# ─────────────────────────────────────────────────────────────
# 3. 차트 ② 별점별 감정 분포
# ─────────────────────────────────────────────────────────────


def chart_rating_sentiment(
    reviews: list[dict],
    out_dir: str = "output",
    filename: str = "rating_sentiment.png",
) -> str | None:
    """별점 1~5 각각에서 감정이 어떻게 갈리는지 누적 막대로 그린다.

    "별점은 5점인데 내용은 부정" 같은 어긋난 조합을 눈으로 찾기 위한 차트다.
    """
    # {별점: {감정: 건수}} 표를 만든다. 별점 1~5는 데이터에 없어도 칸을 만들어 둔다.
    table = {rating: Counter() for rating in RATING_RANGE}

    for review in reviews:
        rating = review.get("rating")
        sentiment = review.get("sentiment")
        if rating in table and sentiment:
            table[rating][sentiment] += 1

    totals = [sum(table[rating].values()) for rating in RATING_RANGE]

    if sum(totals) == 0:
        logger.warning("분석된 리뷰가 없어 별점별 감정 분포 차트를 건너뜁니다.")
        return None

    fig, ax = plt.subplots(figsize=(7.2, 4.2), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)

    labels = [f"{rating}점" for rating in RATING_RANGE]
    bottom = [0] * len(RATING_RANGE)  # 지금까지 쌓인 높이

    for sentiment in SENTIMENT_ORDER:
        values = [table[rating][sentiment] for rating in RATING_RANGE]

        ax.bar(
            labels,
            values,
            bottom=bottom,
            width=0.58,
            color=SENTIMENT_COLOR[sentiment],
            label=SENTIMENT_KO[sentiment],
            edgecolor=SURFACE,  # 배경색으로 테두리를 그려 조각 사이를 벌린다
            linewidth=1.6,
        )

        # 조각이 충분히 클 때만 안쪽에 건수를 쓴다 (작은 조각에 쓰면 글자가 삐져나온다)
        for index, (value, base) in enumerate(zip(values, bottom)):
            if value >= 3:
                ax.text(
                    index,
                    base + value / 2,
                    str(value),
                    ha="center",
                    va="center",
                    fontsize=10,
                    color=SENTIMENT_INK[sentiment],
                )

        bottom = [base + value for base, value in zip(bottom, values)]

    # 막대 위에 그 별점의 총 건수
    headroom = max(totals) * 0.04
    for index, total in enumerate(totals):
        if total > 0:
            ax.text(index, total + headroom, f"{total}건",
                    ha="center", fontsize=10, color=MUTED)

    ax.set_ylim(0, max(totals) * 1.18)
    ax.set_title("별점별 감정 분포", fontsize=13, color=INK, pad=14, loc="left")
    ax.set_ylabel("리뷰 수", fontsize=10, color=MUTED)

    ax.tick_params(axis="x", length=0, labelsize=11.5, colors=INK)
    ax.tick_params(axis="y", length=0, labelsize=9.5, colors=MUTED)
    ax.set_axisbelow(True)  # 눈금선을 막대 뒤로 보낸다
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.xaxis.grid(False)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)

    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.08),
        ncol=3,
        frameon=False,
        fontsize=10.5,
        labelcolor=INK,
    )

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)

    logger.info("차트 저장: %s", path)
    return path


# ─────────────────────────────────────────────────────────────
# 4. 차트 ④ 수집 순번별 부정 비율 추이 (이동 평균)
# ─────────────────────────────────────────────────────────────


def chart_negative_trend(
    reviews: list[dict],
    out_dir: str = "output",
    filename: str = "negative_trend.png",
    window: int = 10,
) -> str | None:
    """리뷰를 수집된 순서대로 놓고, 부정 비율이 어떻게 움직이는지 그린다.

    데이터에 작성일이 없어 '시간별 추이' 대신 '수집 순번별 추이'로 만든다.
    window=10 이면 "직전 10건 중 부정이 몇 %인가"를 한 건씩 밀며 계산한다.
    """
    # 감정이 매겨진 리뷰만, 원래 순서 그대로 뽑는다
    sequence = [r["sentiment"] for r in reviews if r.get("sentiment")]

    if len(sequence) < window:
        logger.warning(
            "분석된 리뷰가 %d건뿐이라 %d건 단위 추이를 그릴 수 없습니다.",
            len(sequence), window,
        )
        return None

    # 창(window)을 한 칸씩 밀면서 그 구간의 부정 비율을 구한다
    x_values, y_values = [], []
    for end in range(window, len(sequence) + 1):
        chunk = sequence[end - window : end]  # end 바로 앞 window개
        y_values.append(chunk.count("negative") / window * 100)
        x_values.append(end)  # 그 창의 마지막 리뷰 번호

    overall = sequence.count("negative") / len(sequence) * 100

    fig, ax = plt.subplots(figsize=(7.8, 3.9), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)

    # 전체 평균보다 높은 구간만 옅게 칠해서 '나빠진 구간'을 눈에 띄게 한다
    ax.fill_between(
        x_values, y_values, overall,
        where=[y >= overall for y in y_values],
        color=SENTIMENT_COLOR["negative"], alpha=0.13, linewidth=0,
    )
    ax.plot(x_values, y_values,
            color=SENTIMENT_COLOR["negative"], linewidth=2.3, solid_capstyle="round")

    # 전체 평균 기준선
    ax.axhline(overall, color=MUTED, linewidth=1, linestyle=(0, (4, 4)))
    ax.text(x_values[0], overall + 3, f"전체 평균 {overall:.1f}%",
            fontsize=9.5, color=MUTED, va="bottom")

    ax.set_ylim(-4, 104)
    ax.set_xlim(x_values[0] - 0.5, x_values[-1] + 0.5)
    ax.set_title(f"부정 비율 추이 (직전 {window}건 기준)",
                 fontsize=13, color=INK, pad=14, loc="left")
    ax.set_xlabel("리뷰 수집 순번", fontsize=10, color=MUTED)
    ax.set_ylabel("부정 비율 (%)", fontsize=10, color=MUTED)

    ax.tick_params(axis="both", length=0, labelsize=9.5, colors=MUTED)
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.xaxis.grid(False)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)

    logger.info("차트 저장: %s", path)
    return path


# ─────────────────────────────────────────────────────────────
# 5. 차트 ⑤ 리뷰 길이 vs 감정
# ─────────────────────────────────────────────────────────────


def chart_length_by_sentiment(
    reviews: list[dict],
    out_dir: str = "output",
    filename: str = "length_by_sentiment.png",
) -> str | None:
    """감정별로 리뷰 글자 수가 어떻게 퍼져 있는지 점으로 찍는다.

    점 하나 = 리뷰 한 건. 평균 막대로 뭉개지 않고 분포를 그대로 보여준다.
    """
    groups: dict[str, list[int]] = {s: [] for s in SENTIMENT_ORDER}

    for review in reviews:
        sentiment = review.get("sentiment")
        text = review.get("review_text") or ""
        if sentiment in groups and text:
            groups[sentiment].append(len(text))

    if not any(groups.values()):
        logger.warning("분석된 리뷰가 없어 리뷰 길이 차트를 건너뜁니다.")
        return None

    fig, ax = plt.subplots(figsize=(7.8, 3.9), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)

    for row, sentiment in enumerate(SENTIMENT_ORDER):
        lengths = groups[sentiment]
        if not lengths:
            continue

        # 같은 글자 수 리뷰가 겹쳐 한 점처럼 보이지 않게 위아래로 조금씩 흩는다.
        # 무작위가 아니라 순번을 5로 나눈 나머지로 정한다 → 실행할 때마다 그림이 같다.
        y_positions = [row + ((i % 5) - 2) * 0.05 for i in range(len(lengths))]

        ax.scatter(lengths, y_positions, s=44,
                   color=SENTIMENT_COLOR[sentiment], alpha=0.55, linewidths=0)

        # 중앙값(길이 순으로 줄 세웠을 때 한가운데 값) 표시
        median = statistics.median(lengths)
        ax.plot([median, median], [row - 0.26, row + 0.26],
                color=SENTIMENT_COLOR[sentiment], linewidth=2.6, solid_capstyle="round")
        ax.text(median, row - 0.36, f"중앙값 {median:.0f}자",
                fontsize=9.5, color=INK, ha="center")

    ax.set_yticks(range(len(SENTIMENT_ORDER)))
    ax.set_yticklabels([SENTIMENT_KO[s] for s in SENTIMENT_ORDER])
    ax.set_ylim(len(SENTIMENT_ORDER) - 0.45, -0.55)  # 위아래 뒤집어 긍정을 맨 위로
    ax.set_xlim(left=0)

    ax.set_title("리뷰 길이 분포 (점 1개 = 리뷰 1건)",
                 fontsize=13, color=INK, pad=14, loc="left")
    ax.set_xlabel("리뷰 글자 수", fontsize=10, color=MUTED)

    ax.tick_params(axis="y", length=0, labelsize=11.5, colors=INK)
    ax.tick_params(axis="x", length=0, labelsize=9.5, colors=MUTED)
    ax.set_axisbelow(True)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.yaxis.grid(False)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)

    logger.info("차트 저장: %s", path)
    return path


# ─────────────────────────────────────────────────────────────
# 6. 통계·품질 지표 계산
# ─────────────────────────────────────────────────────────────

# "별점은 높은데 감정은 부정" / "별점은 낮은데 감정은 긍정" — 어긋남을 판정할 기준.
# 중립(별점 3점, 감정 neutral)은 판정에서 통째로 뺀다. 이유는 설계메모 1-6에 적어두었다.
HIGH_RATINGS = (4, 5)
LOW_RATINGS = (1, 2)


def _percent(part: int, whole: int) -> float | None:
    """비율(%)을 구한다. 분모가 0이면 0.0이 아니라 None을 돌려준다.

    0.0으로 돌려주면 "긍정이 0%"로 잘못 읽힌다.
    실제 뜻은 "셀 수 있는 리뷰가 아예 없다"이므로 둘을 구분한다.
    """
    if whole == 0:
        return None
    return round(part / whole * 100, 1)


def _pct_text(value: float | None) -> str:
    """비율을 사람이 읽을 글자로 바꾼다. 셀 수 없었으면 '-'.

    em dash(—)가 아니라 보통 하이픈을 쓰는 이유: 윈도우 기본 콘솔(cp949)에는
    em dash 글자가 없어서, 그대로 찍으면 프로그램이 거기서 멈춘다.
    """
    return "-" if value is None else f"{value}%"


def calc_stats(reviews: list[dict]) -> dict:
    """리뷰 목록에서 통계·품질 지표를 계산해 딕셔너리로 돌려준다.

    reviews : 'rating', 'sentiment' 키를 가진 딕셔너리들의 목록
    반환값  : 아래 3종 지표를 담은 딕셔너리 (데이터가 비어도 None이 아니라 딕셔너리)

      ① 긍정 비율        positive_ratio
      ② 평균 별점        avg_rating
      ③ 별점-감정 일치율 match.match_rate   ← 이 프로젝트의 차별화 지표

    차트 함수들과 달리 데이터가 비어도 None을 돌려주지 않는다.
    리포트(단위 4)가 이 값을 받아 쓰는데, None이면 쓰는 쪽에서 매번 검사해야 하기 때문이다.
    대신 계산이 불가능한 비율 항목만 None으로 두어 "0%"와 "셀 수 없음"을 구분한다.
    """
    total = len(reviews)

    # ── ① 감정 집계 ──────────────────────────────────────────
    # 아직 분석 전(sentiment 없음)인 리뷰는 분모에서 뺀다.
    # 분모에 넣으면 분석을 돌릴 때마다 '긍정 비율'이 진행률에 따라 흔들린다.
    sentiments = [r.get("sentiment") for r in reviews]
    counts = Counter(s for s in sentiments if s in SENTIMENT_KO)
    analyzed = sum(counts.values())
    sentiment_counts = {s: counts.get(s, 0) for s in SENTIMENT_ORDER}

    # ── ② 별점 집계 ──────────────────────────────────────────
    # 1~5 범위를 벗어난 값·빈 칸은 평균을 왜곡하므로 걸러낸다.
    ratings = [
        r.get("rating") for r in reviews
        if isinstance(r.get("rating"), int) and r.get("rating") in RATING_RANGE
    ]
    rating_counts = {value: 0 for value in RATING_RANGE}
    for value in ratings:
        rating_counts[value] += 1
    avg_rating = round(statistics.mean(ratings), 2) if ratings else None

    # ── ③ 별점-감정 일치율 ───────────────────────────────────
    # 별점 4~5는 '긍정'이, 1~2는 '부정'이 정상. 그 반대가 나오면 어긋남이다.
    # 별점 3점이거나 감정이 중립인 리뷰는 어느 쪽으로도 세지 않고 건너뛴다.
    matched = 0
    high_rating_negative = 0  # 별점 4~5인데 감정은 부정 (= 별점만 보면 놓치는 불만)
    low_rating_positive = 0   # 별점 1~2인데 감정은 긍정 (= 오탈자·오해 가능성)

    for review in reviews:
        rating = review.get("rating")
        sentiment = review.get("sentiment")

        if rating in HIGH_RATINGS:
            if sentiment == "positive":
                matched += 1
            elif sentiment == "negative":
                high_rating_negative += 1
        elif rating in LOW_RATINGS:
            if sentiment == "negative":
                matched += 1
            elif sentiment == "positive":
                low_rating_positive += 1

    mismatched = high_rating_negative + low_rating_positive
    compared = matched + mismatched  # 실제로 판정한 건수 (중립·미분석 제외)

    if analyzed == 0:
        logger.warning("감정이 분석된 리뷰가 0건입니다. 비율 지표는 None으로 둡니다.")

    return {
        "total": total,
        "analyzed": analyzed,
        "unanalyzed": total - analyzed,
        "sentiment_counts": sentiment_counts,
        "positive_ratio": _percent(sentiment_counts["positive"], analyzed),
        "negative_ratio": _percent(sentiment_counts["negative"], analyzed),
        "rated": len(ratings),
        "rating_counts": rating_counts,
        "avg_rating": avg_rating,
        "match": {
            "compared": compared,
            "matched": matched,
            "mismatched": mismatched,
            "match_rate": _percent(matched, compared),
            "mismatch_rate": _percent(mismatched, compared),
            "high_rating_negative": high_rating_negative,
            "low_rating_positive": low_rating_positive,
        },
    }


# ─────────────────────────────────────────────────────────────
# 7. 리포트 생성 (콘솔 · TXT · MD)
# ─────────────────────────────────────────────────────────────

REPORT_TITLE = "고객 리뷰 감정 분석 리포트"
LINE_WIDTH = 64  # 콘솔·TXT에서 제목 줄(===)의 길이


def _width(text: str) -> int:
    """글자가 화면에서 차지하는 칸 수를 센다.

    파이썬 len("긍정")은 2를 돌려주지만, 화면에서 한글 한 글자는 두 칸을 먹는다.
    len()으로 표를 맞추면 한글이 섞이는 순간 열이 어긋난다.
    east_asian_width가 'W'(넓음)/'F'(전각)이면 두 칸으로 센다.
    """
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _pad(text: str, width: int, align: str = "l") -> str:
    """글자 뒤(또는 앞)에 공백을 채워 폭을 맞춘다. align이 'r'이면 오른쪽 정렬."""
    gap = max(0, width - _width(text))
    return (" " * gap + text) if align == "r" else (text + " " * gap)


def _bar(value: int, largest: int, width: int = 14) -> str:
    """건수를 막대 글자로 바꾼다. 가장 큰 값이 width칸을 채운다.

    0건이면 빈 글자, 1건이라도 있으면 최소 한 칸은 그린다.
    (반올림해서 0칸이 되면 '있는데 없어 보이는' 막대가 되기 때문)
    """
    if largest <= 0 or value <= 0:
        return ""
    return "■" * max(1, round(value / largest * width))


def _shorten(text: str | None, limit: int = 38) -> str:
    """리뷰를 표 한 칸에 들어갈 길이로 줄인다. 줄바꿈·연속 공백은 한 칸으로 편다."""
    flat = " ".join((text or "").split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def _as_text_list(value) -> list[str]:
    """AI가 돌려준 값을 '글자 목록'으로 맞춘다.

    B의 extract_insights()는 네 항목이 '있는지'만 확인하고 '무엇인지'는 확인하지 않는다.
    AI가 형식을 어겨 목록 대신 글자 하나를 돌려줘도 그대로 통과한다.
    그런데 ", ".join("배송")은 오류를 내지 않고 "배, 송"을 만든다.
    오류가 안 나니 아무도 모르고, 틀린 글자가 리포트에 멀쩡한 표로 실린다.
    그래서 리포트에 넣기 전에 여기서 모양을 맞춘다.
    """
    if value is None:
        return []
    if isinstance(value, str):  # 글자 하나로 왔으면 한 칸짜리 목록으로 감싼다
        return [value.strip()] if value.strip() else []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value)]  # 숫자 등 뜻밖의 값도 일단 글자로 바꿔 보여준다


def _longest_negative_reviews(reviews: list[dict], top_n: int = 5) -> list[dict]:
    """부정 리뷰를 글자 수가 많은 순으로 상위 N건 뽑는다. (TOP N 집계)

    단위 2에서 찾은 사실 — 부정 리뷰 중앙값 45자 vs 긍정 22자 — 을 행동으로 옮기는 집계다.
    리뷰를 다 읽을 수 없을 때 '긴 부정 리뷰부터' 읽으면 구체적인 불만을 가장 빨리 잡는다.

    길이가 같을 때는 id 순으로 줄 세운다. 기준이 하나뿐이면 같은 길이끼리 순서가
    실행할 때마다 달라질 수 있고, 그러면 제출한 리포트와 평가자가 뽑은 리포트가 달라진다.
    """
    negatives = [r for r in reviews if r.get("sentiment") == "negative"]
    negatives.sort(key=lambda r: (-len(r.get("review_text") or ""), r.get("id") or 0))
    return negatives[:top_n]


def _report_blocks(reviews: list[dict], insights: dict | None = None) -> list[tuple]:
    """리포트에 들어갈 내용을 '블록' 목록으로 만든다. 서식(모양)은 아직 입히지 않는다.

    블록 종류는 다섯 가지뿐이다.
      ("h1", 제목) ("h2", 소제목) ("text", 한 줄) ("list", [항목들])
      ("table", [머리글], [[칸들]], [정렬])
    내용과 모양을 나눈 이유는 설계메모 1-8에 적어두었다.
    """
    stats = calc_stats(reviews)
    match = stats["match"]
    blocks: list[tuple] = [
        ("h1", REPORT_TITLE),
        ("text", f"생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}"),
    ]

    # ── 1. 요약 ───────────────────────────────────────────────
    avg_text = (
        f"{stats['avg_rating']}점 (별점 있는 {stats['rated']}건 기준)"
        if stats["avg_rating"] is not None
        else "-"
    )
    blocks += [
        ("h2", "1. 요약"),
        ("table", ["지표", "값"], [
            ["분석한 리뷰", f"{stats['analyzed']}건 "
                          f"(전체 {stats['total']}건 · 미분석 {stats['unanalyzed']}건)"],
            ["긍정 비율", _pct_text(stats["positive_ratio"])],
            ["평균 별점", avg_text],
            ["별점-감정 일치율", f"{_pct_text(match['match_rate'])} "
                              f"(판정 {match['compared']}건 중 어긋남 {match['mismatched']}건)"],
        ], ["l", "l"]),
    ]

    # ── 2. 감정 분포 ──────────────────────────────────────────
    counts = stats["sentiment_counts"]
    largest = max(counts.values())
    blocks += [
        ("h2", "2. 감정 분포"),
        ("table", ["감정", "건수", "비율", ""], [
            [
                SENTIMENT_KO[sentiment],
                f"{counts[sentiment]}건",
                _pct_text(_percent(counts[sentiment], stats["analyzed"])),
                _bar(counts[sentiment], largest),
            ]
            for sentiment in SENTIMENT_ORDER
        ], ["l", "r", "r", "l"]),
    ]

    # ── 3. 별점 분포 ──────────────────────────────────────────
    rating_counts = stats["rating_counts"]
    largest = max(rating_counts.values())
    blocks += [
        ("h2", "3. 별점 분포"),
        ("table", ["별점", "건수", "비율", ""], [
            [
                f"{rating}점",
                f"{rating_counts[rating]}건",
                _pct_text(_percent(rating_counts[rating], stats["rated"])),
                _bar(rating_counts[rating], largest),
            ]
            for rating in RATING_RANGE
        ], ["l", "r", "r", "l"]),
    ]

    # ── 4. 품질 지표 ──────────────────────────────────────────
    blocks += [
        ("h2", "4. 품질 지표 - 별점만 봐서는 놓치는 것"),
        ("table", ["항목", "값"], [
            ["판정 대상", f"{match['compared']}건 (별점 3점 · 감정 중립 · 미분석은 제외)"],
            ["일치", f"{match['matched']}건"],
            ["어긋남", f"{match['mismatched']}건 ({_pct_text(match['mismatch_rate'])})"],
            ["└ 별점 4~5인데 부정",
             f"{match['high_rating_negative']}건 - 별점만 보면 놓치는 불만"],
            ["└ 별점 1~2인데 긍정",
             f"{match['low_rating_positive']}건 - AI 분석 품질을 의심할 신호"],
        ], ["l", "l"]),
    ]

    # ── 5. 먼저 읽어야 할 부정 리뷰 TOP N ─────────────────────
    top_negative = _longest_negative_reviews(reviews)
    blocks.append(("h2", f"5. 먼저 읽어야 할 부정 리뷰 TOP {len(top_negative) or 5}"))
    if top_negative:
        blocks += [
            ("text",
             "부정 리뷰는 긍정보다 평균 2배 길다. 길수록 불만이 구체적이라 먼저 읽을 값어치가 있다."),
            ("table", ["순위", "별점", "길이", "리뷰"], [
                [
                    str(rank),
                    f"{review.get('rating')}점",
                    f"{len(review.get('review_text') or '')}자",
                    _shorten(review.get("review_text")),
                ]
                for rank, review in enumerate(top_negative, start=1)
            ], ["r", "r", "r", "l"]),
        ]
    else:
        blocks.append(("text", "부정으로 분류된 리뷰가 없습니다."))

    # ── 6~8. AI 추출 결과 (B의 extract_insights 결과를 D가 넘겨준다) ──
    missing = "AI 추출 결과가 전달되지 않았습니다. analyze → extract 를 실행한 뒤 다시 만드세요."
    positive_keywords = _as_text_list((insights or {}).get("positive_keywords"))
    negative_keywords = _as_text_list((insights or {}).get("negative_keywords"))

    blocks.append(("h2", "6. AI 키워드 TOP N"))
    if not insights:
        blocks.append(("text", missing))
    else:
        blocks.append(("table", ["구분", "키워드"], [
            [f"긍정 TOP {len(positive_keywords)}", ", ".join(positive_keywords) or "-"],
            [f"부정 TOP {len(negative_keywords)}", ", ".join(negative_keywords) or "-"],
        ], ["l", "l"]))

    summary = (insights or {}).get("summary")
    blocks += [("h2", "7. AI 요약"), ("text", str(summary).strip() if summary else "-")]

    improvements = _as_text_list((insights or {}).get("improvements"))
    blocks.append(("h2", "8. 개선 제안"))
    blocks.append(("list", improvements) if improvements else ("text", "-"))

    return blocks


def _render_text(blocks: list[tuple]) -> str:
    """블록 목록을 콘솔·TXT용 글자로 바꾼다."""
    lines: list[str] = []

    for block in blocks:
        kind = block[0]
        if kind == "h1":
            lines += ["=" * LINE_WIDTH, f"  {block[1]}", "=" * LINE_WIDTH]
        elif kind == "h2":
            lines += ["", block[1], "-" * _width(block[1])]
        elif kind == "text":
            lines.append(block[1])
        elif kind == "list":
            lines += [f"  {number}. {item}" for number, item in enumerate(block[1], start=1)]
        elif kind == "table":
            lines += _text_table(block[1], block[2], block[3])

    return "\n".join(lines) + "\n"


def _text_table(headers: list[str], rows: list[list[str]], aligns: list[str]) -> list[str]:
    """공백으로 열을 맞춘 표를 만든다. 세로줄(|) 없이 여백만으로 열을 나눈다."""
    # 열마다 '머리글과 그 열의 모든 칸' 중 가장 넓은 것을 그 열의 폭으로 삼는다
    widths = [
        max([_width(headers[index])] + [_width(row[index]) for row in rows])
        for index in range(len(headers))
    ]

    def draw(cells: list[str]) -> str:
        joined = "  ".join(_pad(cell, widths[i], aligns[i]) for i, cell in enumerate(cells))
        return ("  " + joined).rstrip()  # 오른쪽 끝에 남는 공백은 지운다

    # 머리글이 빈 열(막대 그래프 칸)에는 밑줄을 긋지 않는다. 떠 있는 줄처럼 보인다.
    divider = draw(["-" * widths[i] if headers[i] else "" for i in range(len(headers))])
    return [draw(headers), divider] + [draw(row) for row in rows]


def _render_markdown(blocks: list[tuple]) -> str:
    """블록 목록을 마크다운(.md)으로 바꾼다."""
    chunks: list[str] = []

    for block in blocks:
        kind = block[0]
        if kind == "h1":
            chunks.append(f"# {block[1]}")
        elif kind == "h2":
            chunks.append(f"## {block[1]}")
        elif kind == "text":
            chunks.append(block[1])
        elif kind == "list":
            chunks.append("\n".join(f"{n}. {item}" for n, item in enumerate(block[1], start=1)))
        elif kind == "table":
            chunks.append(_markdown_table(block[1], block[2], block[3]))

    return "\n\n".join(chunks) + "\n"


def _markdown_table(headers: list[str], rows: list[list[str]], aligns: list[str]) -> str:
    """마크다운 표를 만든다. 폭은 맞출 필요가 없고, 정렬은 구분선에 적는다."""

    def cells(values: list[str]) -> str:
        # 리뷰 본문에 세로줄이 들어 있으면 표의 칸 구분자로 오해되므로 막아 준다
        return "| " + " | ".join(value.replace("|", "\\|") for value in values) + " |"

    divider = "| " + " | ".join("---:" if align == "r" else "---" for align in aligns) + " |"
    return "\n".join([cells(headers), divider] + [cells(row) for row in rows])


def render_report(reviews: list[dict], insights: dict | None = None,
                  style: str = "text") -> str:
    """리포트를 글자로 만들어 돌려준다. 화면에 찍지도, 파일로 저장하지도 않는다.

    reviews  : 'rating', 'sentiment', 'review_text' 키를 가진 딕셔너리들의 목록
    insights : B의 extract_insights() 결과. D가 넘겨준다.
               없으면 해당 구역만 안내문으로 채우고 리포트는 정상으로 만든다
    style    : "text"(콘솔·TXT) 또는 "markdown"(MD)
    """
    blocks = _report_blocks(reviews, insights)

    if style == "text":
        return _render_text(blocks)
    if style == "markdown":
        return _render_markdown(blocks)

    # 데이터가 비는 것과 달리 이건 부르는 쪽의 오타다.
    # 조용히 넘기면 엉뚱한 형식의 파일이 만들어지므로 여기서는 멈춘다.
    raise ValueError(f"style은 'text' 또는 'markdown'이어야 합니다. 받은 값: {style!r}")


def print_report(reviews: list[dict], insights: dict | None = None) -> str:
    """리포트를 콘솔에 출력하고, 출력한 글자를 그대로 돌려준다.

    윈도우 기본 콘솔은 UTF-8이 아니라 cp949를 쓴다. 리뷰에 이모지처럼
    cp949에 없는 글자가 하나라도 섞이면 print가 실패하며 프로그램이 멈춘다.
    화면에 못 찍는 글자 하나 때문에 리포트 전체를 못 보는 건 말이 안 되므로,
    그럴 때는 그 글자만 '?'로 바꿔서라도 출력한다.
    파일(UTF-8)에는 원래 글자가 그대로 들어가므로 내용이 손상되지 않는다.
    """
    text = render_report(reviews, insights, style="text")

    try:
        print(text)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        print(text.encode(encoding, errors="replace").decode(encoding))
        logger.warning(
            "콘솔(%s)이 표시할 수 없는 글자가 있어 화면에서만 '?'로 바꿔 출력했습니다. "
            "저장된 리포트 파일에는 원래 글자가 그대로 들어 있습니다.",
            encoding,
        )

    return text


def save_report(reviews: list[dict], insights: dict | None = None,
                out_dir: str = "output", basename: str = "report") -> dict:
    """리포트를 TXT와 MD 두 파일로 저장하고 {"txt": 경로, "md": 경로}를 돌려준다.

    줄바꿈은 운영체제 기본값을 그대로 쓴다(윈도우 CRLF / 리눅스 LF).
    output/ 폴더는 .gitignore에 있어 레포에 올라가지 않으므로,
    형식을 통일하는 것보다 윈도우 메모장에서 줄이 제대로 보이는 쪽이 낫다.
    """
    os.makedirs(out_dir, exist_ok=True)
    paths = {}

    for style, extension in (("text", "txt"), ("markdown", "md")):
        path = os.path.join(out_dir, f"{basename}.{extension}")
        with open(path, "w", encoding="utf-8") as f:
            f.write(render_report(reviews, insights, style=style))
        paths[extension] = path
        logger.info("리포트 저장: %s", path)

    return paths


# ─────────────────────────────────────────────────────────────
# 9. 혼자 확인해 보는 용도 —  python src/reporter.py
# ─────────────────────────────────────────────────────────────

DEMO_CSV = "naver_reviews_sample50.csv"


def _rating_to_sentiment(rating: int) -> str:
    """별점만 보고 감정을 임시로 정한다.

    ※ 이건 AI 분석이 아니다. B의 감정 분석이 붙기 전까지 차트가 제대로
      그려지는지 확인하려고 쓰는 임시 규칙일 뿐이다.
      실제 리포트에는 절대 이 값을 쓰지 않는다.
    """
    if rating >= 4:
        return "positive"
    if rating == 3:
        return "neutral"
    return "negative"


def _load_demo_reviews(csv_path: str = DEMO_CSV) -> list[dict]:
    """확인용 리뷰 목록을 만든다.

    샘플 CSV가 옆에 있으면 그걸 읽고(감정은 별점으로 임시 부여),
    없으면 내장된 가짜 데이터 30건을 쓴다.
    """
    if os.path.exists(csv_path):
        import csv

        # utf-8-sig : 파일 맨 앞에 붙은 보이지 않는 표식(BOM)을 걷어내고 읽는다.
        #             이걸 안 쓰면 첫 칸 이름이 'rating'이 아니라 '﻿rating'이 된다.
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))

        reviews = []
        for index, row in enumerate(rows, start=1):
            rating = int(row["rating"])
            reviews.append(
                {
                    "id": index,
                    "review_text": row["review"],
                    "rating": rating,
                    "sentiment": _rating_to_sentiment(rating),  # ← 임시값
                    "score": None,
                }
            )
        logger.info("샘플 CSV %d건 로드 (감정은 별점 기준 임시값)", len(reviews))
        return reviews

    logger.info("샘플 CSV(%s)가 없어 내장 가짜 데이터 30건을 사용합니다.", csv_path)
    plan = [("positive", 17), ("neutral", 6), ("negative", 7)]
    reviews = []
    review_id = 1
    for sentiment, count in plan:
        for _ in range(count):
            reviews.append(
                {
                    "id": review_id,
                    "review_text": f"테스트 리뷰 {review_id}",
                    "rating": 5 if sentiment == "positive" else (3 if sentiment == "neutral" else 1),
                    "sentiment": sentiment,
                    "score": None,
                }
            )
            review_id += 1
    return reviews


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    font = setup_korean_font()
    print(f"사용 폰트: {font}")

    reviews = _load_demo_reviews()
    print(f"리뷰 건수: {len(reviews)}건")

    charts = [
        chart_sentiment_distribution(reviews),
        chart_rating_sentiment(reviews),
        chart_negative_trend(reviews),
        chart_length_by_sentiment(reviews),
    ]
    print("저장된 차트:")
    for path in charts:
        print(f"  - {path}")

    # 단위 4 — 리포트를 콘솔에 찍고 TXT·MD 두 파일로 저장한다.
    # ※ 여기서는 insights를 넘기지 않는다. B의 extract_insights() 결과는
    #   D가 main.py에서 호출해 넘겨주기로 한 값이라, 단독 실행에서는 알 수 없다.
    #   그래서 리포트의 6~8번 구역은 안내문으로 채워진 채 정상 생성된다.
    # ※ '별점-감정 일치율'이 100%로 나오는 것도 정상이다.
    #   단독 실행 모드의 감정값이 별점으로 매긴 임시값이라 어긋날 수가 없다.
    print()
    print_report(reviews)

    paths = save_report(reviews)
    print("저장된 리포트:")
    for extension, path in paths.items():
        print(f"  - {path}")
