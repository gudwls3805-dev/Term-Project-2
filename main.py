"""
[Project C] AI 기반 고객 리뷰 감정 분석 대시보드
D · CLI / 통합 (feat/cli)

A(feat/storage), B(feat/analyzer)의 실제 구현에 맞춰 통합.
  - storage/importer : 함수가 conn을 인자로 받음, 리뷰 텍스트 키 = review_text
  - sentiment/extractor : Gemini SDK, 반환은 dict(None on fail), 키 = confidence/improvements
C(reporter)는 미구현 → stats/dashboard/export는 lazy import로 안내 후 스킵.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger("reviewcli")

DEFAULT_CONFIG = {
    "db_path": "review.db",
    "dedup_policy": "skip",           # skip | upsert
    "min_review_length": 5,
    "ai": {"api_key_env": "GEMINI_API_KEY"},  # B가 쓰는 환경변수명
    "visualization": {"output_dir": "output", "font": "NanumGothic", "dpi": 120},
    "logging": {"level": "INFO"},
}


# ---------------------------------------------------------------------------
# 설정 / 로깅
# ---------------------------------------------------------------------------
def load_config(path="config.json"):
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    p = Path(path)
    if p.exists():
        try:
            _deep_update(cfg, json.loads(p.read_text(encoding="utf-8")))
        except json.JSONDecodeError as e:
            print(f"[ERROR] config.json 파싱 실패: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        logging.getLogger().warning("config.json 없음 → 기본 설정 사용")
    return cfg


def _deep_update(base, override):
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_update(base[k], v)
        else:
            base[k] = v


def setup_logging(cfg):
    level = getattr(logging, cfg.get("logging", {}).get("level", "INFO"))
    logging.basicConfig(level=level, format="[%(levelname)s] %(message)s")


def check_api_key(cfg):
    env = cfg["ai"]["api_key_env"]
    if not os.environ.get(env):
        logger.error("환경변수 %s 가 설정되지 않았습니다. AI 분석에 필요합니다.", env)
        logger.error("예: export %s=your_key  (또는 .env 파일에 작성)", env)
        return False
    return True


# ---------------------------------------------------------------------------
# storage 어댑터: conn 관리 + Row → dict 변환 (D가 흡수하는 계층)
# ---------------------------------------------------------------------------
def _with_conn(fn):
    """storage 함수 호출용 conn 컨텍스트."""
    from src import storage
    conn = storage.get_conn(cfg_global["db_path"])
    storage.init_db(conn)
    try:
        return fn(conn)
    finally:
        conn.commit()
        conn.close()


def _row_to_dict(row):
    """sqlite3.Row → 표준 dict. review_text → text 로 정규화."""
    d = dict(row)
    d["text"] = d.get("review_text", "")
    return d


cfg_global = {}  # setup 후 채워짐


# ---------------------------------------------------------------------------
# 서브커맨드 핸들러
# ---------------------------------------------------------------------------
def cmd_import(args, cfg):
    from src import importer
    importer.run_import(args.file, db_path=cfg["db_path"])


def cmd_clean(args, cfg):
    from src import importer
    importer.run_clean(db_path=cfg["db_path"], policy=cfg["dedup_policy"])


def cmd_analyze(args, cfg):
    if not check_api_key(cfg):
        sys.exit(2)
    from src import storage
    from analyzer import sentiment

    def fetch(conn):
        if args.id is not None:
            row = storage.get_review(conn, args.id)
            return [row] if row else []
        return storage.query_reviews(
            conn, only_unanalyzed=(args.scope != "all"), limit=args.limit
        )

    targets = _with_conn(fetch)
    logger.info("분석 대상: %d건", len(targets))
    ok = fail = 0
    for i, row in enumerate(targets, 1):
        rid = row["id"]
        result = sentiment.analyze_sentiment(row["review_text"])  # dict | None
        if result is None:
            logger.error("[%d/%d] ID=%s 분석 실패 → 스킵", i, len(targets), rid)
            fail += 1
            continue
        s, score = result["sentiment"], result["confidence"]
        _with_conn(lambda c, rid=rid, s=s, score=score:
                   storage.update_sentiment(c, rid, s, score))
        logger.info("[%d/%d] ID=%s 분석 완료: %s (%.2f)",
                    i, len(targets), rid, s, score)
        ok += 1
    logger.info("분석 완료: %d건 성공, %d건 실패", ok, fail)


def cmd_extract(args, cfg):
    if not check_api_key(cfg):
        sys.exit(2)
    from src import storage
    from analyzer import extractor

    rows = _with_conn(lambda c: storage.query_reviews(
        c, sentiment=args.sentiment, date_from=args.date_from,
        date_to=args.date_to, limit=args.limit))
    texts = [r["review_text"] for r in rows]
    logger.info("추출 대상: %d건", len(texts))
    logger.info("AI 분석 요청 중...")

    result = extractor.extract_insights(texts)  # dict | None
    if result is None:
        logger.error("추출 실패 (리뷰 없음 또는 API 오류)")
        return

    scope = args.sentiment or "all"
    _with_conn(lambda c: storage.save_extraction(
        c, scope,
        keywords_pos=", ".join(result["positive_keywords"]),
        keywords_neg=", ".join(result["negative_keywords"]),
        summary=result["summary"],
        suggestions=" | ".join(result["improvements"]),
    ))
    logger.info("추출 완료")
    _print_extraction(result)


def _print_extraction(r):
    print("\n=== 키워드 분석 ===")
    print("[긍정 키워드]", ", ".join(r["positive_keywords"]))
    print("[부정 키워드]", ", ".join(r["negative_keywords"]))
    if r.get("frequent_complaints"):
        print("[빈출 불만]", ", ".join(r["frequent_complaints"]))
    print("\n[요약]\n" + r["summary"])
    print("\n[개선 제안]")
    for s in r["improvements"]:
        print(f"- {s}")


def cmd_list(args, cfg):
    from src import storage
    offset = (args.page - 1) * args.size

    def fetch(conn):
        rows = storage.query_reviews(
            conn, sentiment=args.sentiment, rating=args.rating,
            date_from=args.date_from, date_to=args.date_to,
            limit=args.size, offset=offset)
        total = storage.count_reviews(
            conn, sentiment=args.sentiment, rating=args.rating,
            date_from=args.date_from, date_to=args.date_to)
        return rows, total

    rows, total = _with_conn(fetch)
    total_pages = max(1, (total + args.size - 1) // args.size)
    print(f"=== 리뷰 목록 (감정: {args.sentiment or '전체'}, "
          f"{args.page}/{total_pages} 페이지) ===")
    for r in rows:
        d = _row_to_dict(r)
        stars = "★" * (d.get("rating") or 0) + "☆" * (5 - (d.get("rating") or 0))
        senti = d.get("sentiment") or "-"
        score = d.get("score")
        score_str = f"({score:.2f})" if score is not None else ""
        print(f"[{d['id']}] {stars} | {d.get('date') or '-'} | "
              f"{d['text'][:20]}... | {senti} {score_str}")


def cmd_show(args, cfg):
    from src import storage
    row = _with_conn(lambda c: storage.get_review(c, args.id))
    if not row:
        print(f"[WARN] ID={args.id} 리뷰를 찾을 수 없음")
        return
    d = _row_to_dict(row)
    print(f"=== 리뷰 상세 [{d['id']}] ===")
    print(f"별점   : {d.get('rating', '-')}")
    print(f"작성일 : {d.get('date', '-')}")
    print(f"제품   : {d.get('product', '-')}")
    print(f"감정   : {d.get('sentiment', '-')} "
          f"({d.get('score') if d.get('score') is not None else '-'})")
    print(f"원문   :\n{d['text']}")


def _load_reviews(**filters):
    """조회 → dict 리스트. C·reporter는 원본 키(review_text 등)를 그대로 기대하므로
    dict(row) 그대로 넘긴다 (text 정규화 키도 함께 붙여둠)."""
    from src import storage
    rows = _with_conn(lambda c: storage.query_reviews(c, **filters))
    return [_row_to_dict(r) for r in rows]


def _load_insights(scope="all"):
    """A의 extractions 테이블(문자열 저장)에서 B의 insights dict를 복원해 C에 넘긴다."""
    from src import storage
    rows = _with_conn(lambda c: storage.get_extractions(c, scope=scope))
    if not rows:
        return None
    r = dict(rows[0])  # 최신 1건
    return {
        "positive_keywords": [k.strip() for k in (r.get("keywords_pos") or "").split(",") if k.strip()],
        "negative_keywords": [k.strip() for k in (r.get("keywords_neg") or "").split(",") if k.strip()],
        "summary": r.get("summary") or "",
        "improvements": [s.strip() for s in (r.get("suggestions") or "").split("|") if s.strip()],
    }


def cmd_stats(args, cfg):
    from src import reporter
    reviews = _load_reviews()
    stats = reporter.calc_stats(reviews)
    # C의 리포트에서 요약 부분만 활용해 통계 출력
    print("=== 리뷰 분석 통계 ===")
    print(f"총 리뷰 수: {stats['total']}건")
    print(f"분석 완료: {stats['analyzed']}건 "
          f"(미분석 {stats['unanalyzed']}건)")
    print("\n[감정 분포]")
    for s in ["positive", "neutral", "negative"]:
        cnt = stats["sentiment_counts"][s]
        ko = {"positive": "긍정", "neutral": "중립", "negative": "부정"}[s]
        print(f"- {ko}: {cnt}건")
    print("\n[별점 분포]")
    for r in [5, 4, 3, 2, 1]:
        print(f"- {'★'*r}{'☆'*(5-r)}: {stats['rating_counts'][r]}건")
    if stats["avg_rating"] is not None:
        print(f"\n평균 별점: {stats['avg_rating']}")
    print(f"별점-감정 일치율: {reporter._pct_text(stats['match']['match_rate'])}")


def cmd_dashboard(args, cfg):
    from src import reporter
    reviews = _load_reviews()
    insights = _load_insights("all") or _load_insights("negative")
    out_dir = cfg["visualization"]["output_dir"]

    # 1) 차트 4종 생성 (요구사항: 최소 3종)
    reporter.setup_korean_font()
    charts = []
    for fn in (reporter.chart_sentiment_distribution,
               reporter.chart_rating_sentiment,
               reporter.chart_negative_trend,
               reporter.chart_length_by_sentiment):
        path = fn(reviews, out_dir=out_dir)
        if path:
            charts.append(path)
            logger.info("차트 생성: %s", path)

    # 2) 종합 리포트 콘솔 출력 + 파일 저장(TXT/MD)
    reporter.print_report(reviews, insights)
    if not args.no_save:
        paths = reporter.save_report(reviews, insights, out_dir=out_dir)
        logger.info("리포트 저장: %s, %s", paths["txt"], paths["md"])


def cmd_export(args, cfg):
    """C에 export가 없어 D가 구현 (CSV/JSONL/Excel). 요구사항: 최소 2개 포맷."""
    import csv
    import json as _json
    reviews = _load_reviews(sentiment=args.sentiment)
    if args.rating_min is not None:
        reviews = [r for r in reviews if (r.get("rating") or 0) >= args.rating_min]

    out_dir = cfg["visualization"]["output_dir"]
    os.makedirs(out_dir, exist_ok=True)
    fields = ["id", "review_text", "rating", "date", "product", "sentiment", "score"]
    path = args.output or os.path.join(out_dir, f"reviews_export.{args.format}")

    if args.format == "csv":
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(reviews)
    elif args.format == "jsonl":
        with open(path, "w", encoding="utf-8") as f:
            for r in reviews:
                f.write(_json.dumps({k: r.get(k) for k in fields}, ensure_ascii=False) + "\n")
    elif args.format == "xlsx":
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(fields)
        for r in reviews:
            ws.append([r.get(k) for k in fields])
        wb.save(path)

    logger.info("내보내기 완료: %s (%d건)", path, len(reviews))


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------
def build_parser():
    parser = argparse.ArgumentParser(prog="main.py",
                                     description="AI 기반 고객 리뷰 감정 분석 대시보드")
    parser.add_argument("--config", default="config.json")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("import", help="리뷰 데이터 가져오기")
    p.add_argument("--file", required=True)
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("clean", help="데이터 정제")
    p.set_defaults(func=cmd_clean)

    p = sub.add_parser("analyze", help="AI 감정 분석")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--all", dest="scope", action="store_const", const="all")
    g.add_argument("--unanalyzed", dest="scope", action="store_const", const="unanalyzed")
    g.add_argument("--id", type=int)
    p.add_argument("--limit", type=int, default=None)
    p.set_defaults(func=cmd_analyze, scope="unanalyzed", id=None)

    p = sub.add_parser("extract", help="AI 키워드/요약 추출")
    p.add_argument("--sentiment", choices=["positive", "negative", "neutral"])
    p.add_argument("--date-from", dest="date_from")
    p.add_argument("--date-to", dest="date_to")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("list", help="리뷰 목록 조회")
    p.add_argument("--sentiment", choices=["positive", "negative", "neutral"])
    p.add_argument("--rating", type=int, choices=range(1, 6))
    p.add_argument("--date-from", dest="date_from")
    p.add_argument("--date-to", dest="date_to")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--size", type=int, default=10)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="리뷰 상세 조회")
    p.add_argument("--id", type=int, required=True)
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("stats", help="통계 요약")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("dashboard", help="차트 생성 및 종합 리포트")
    p.add_argument("--no-save", dest="no_save", action="store_true",
                   help="리포트 파일 저장 생략 (콘솔 출력만)")
    p.set_defaults(func=cmd_dashboard)

    p = sub.add_parser("export", help="데이터 내보내기")
    p.add_argument("--format", choices=["csv", "jsonl", "xlsx"], default="csv")
    p.add_argument("--output")
    p.add_argument("--sentiment", choices=["positive", "negative", "neutral"])
    p.add_argument("--rating-min", dest="rating_min", type=int)
    p.set_defaults(func=cmd_export)

    return parser


def main(argv=None):
    global cfg_global
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    cfg_global = cfg
    setup_logging(cfg)
    try:
        args.func(args, cfg)
    except ModuleNotFoundError as e:
        logger.error("아직 구현되지 않은 모듈: %s (C·reporter 담당 대기 중)", e.name)
        sys.exit(2)
    except FileNotFoundError as e:
        logger.error("파일을 찾을 수 없음: %s", e)
        sys.exit(1)
    except Exception as e:
        logger.error("실행 중 오류: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()