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
import logging
import platform
import statistics
from collections import Counter

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
    """비율을 사람이 읽을 글자로 바꾼다. 셀 수 없었으면 '—'."""
    return "—" if value is None else f"{value}%"


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

    # 단위 3에서 만든 통계·품질 지표를 눈으로 확인한다.
    # ※ 아래 숫자 중 '별점-감정 일치율'은 지금 100%로 나오는 게 정상이다.
    #   단독 실행 모드의 감정값이 별점으로 매긴 임시값이라 어긋날 수가 없기 때문이다.
    #   B의 AI 분석이 붙어야 이 지표에 의미가 생긴다.
    stats = calc_stats(reviews)
    match = stats["match"]

    print("\n[통계·품질 지표]")
    print(f"  전체 {stats['total']}건 · 감정 분석 완료 {stats['analyzed']}건 "
          f"· 미분석 {stats['unanalyzed']}건")
    for sentiment in SENTIMENT_ORDER:
        print(f"    {SENTIMENT_KO[sentiment]} {stats['sentiment_counts'][sentiment]}건")
    print(f"  ① 긍정 비율        : {_pct_text(stats['positive_ratio'])}")
    print(f"  ② 평균 별점        : {stats['avg_rating']}점 (별점 있는 {stats['rated']}건 기준)")
    print(f"  ③ 별점-감정 일치율 : {_pct_text(match['match_rate'])} "
          f"(판정 {match['compared']}건 중 어긋남 {match['mismatched']}건)")
    print(f"       별점 4~5인데 부정: {match['high_rating_negative']}건")
    print(f"       별점 1~2인데 긍정: {match['low_rating_positive']}건")
