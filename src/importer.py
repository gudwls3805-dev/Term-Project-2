"""
importer.py — 리뷰 수집(import) + 정제(clean)
담당: A (데이터/DB) · 브랜치: feat/storage
관련 요구사항: ② 데이터 수집(CSV/Excel → raw), ③ 데이터 정제(→ clean, 중복 처리)
"""

import re
import hashlib
import logging

import pandas as pd

from src import storage

logger = logging.getLogger(__name__)

MIN_LEN = 5  # 이보다 짧은 리뷰는 버린다


def run_import(file_path, db_path=storage.DB_PATH):
    if file_path.lower().endswith(".csv"):
        df = pd.read_csv(file_path, encoding="utf-8-sig")
    else:
        df = pd.read_excel(file_path)

    logger.info("파일 로드: %s (총 %d행)", file_path, len(df))

    text_col = _find_column(df, ["review_text", "review", "리뷰", "내용", "content"])
    rating_col = _find_column(df, ["rating", "별점", "평점", "star"])
    date_col = _find_column(df, ["date", "작성일", "날짜"])
    product_col = _find_column(df, ["product", "제품", "상품", "product_name"])

    if text_col is None:
        raise ValueError("리뷰 텍스트 컬럼을 찾을 수 없습니다.")

    conn = storage.get_conn(db_path)
    storage.init_db(conn)

    saved = 0
    for _, row in df.iterrows():
        text = row.get(text_col)
        if pd.isna(text):
            continue
        rating = _to_int(row.get(rating_col)) if rating_col else None
        date = _cell_or_none(row.get(date_col)) if date_col else None
        product = _cell_or_none(row.get(product_col)) if product_col else None
        storage.insert_raw(conn, str(text), rating, date, product)
        saved += 1

    conn.commit()
    conn.close()
    logger.info("raw 저장소에 저장 완료: %d건", saved)
    print(f"[INFO] 파일 로드: {file_path}")
    print(f"[INFO] raw 저장소에 {saved}건 저장 완료")
    return saved


def run_clean(db_path=storage.DB_PATH, policy="skip"):
    conn = storage.get_conn(db_path)
    storage.init_db(conn)

    raws = conn.execute("SELECT * FROM raw_reviews").fetchall()
    total = len(raws)
    inserted = updated = skipped = dropped = 0

    for r in raws:
        text = _normalize_text(r["review_text"])
        if not text:
            dropped += 1
            continue
        if len(text) < MIN_LEN:
            dropped += 1
            continue

        rating = r["rating"]
        if rating is not None and not (1 <= rating <= 5):
            rating = None

        date = _normalize_date(r["date"])
        text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()

        result = storage.insert_clean(
            conn, text, rating, date, r["product"], text_hash, policy
        )
        if result == "inserted":
            inserted += 1
        elif result == "updated":
            updated += 1
        else:
            skipped += 1

    conn.commit()
    conn.close()
    logger.info(
        "정제 완료 total=%d inserted=%d updated=%d skipped=%d dropped=%d",
        total, inserted, updated, skipped, dropped,
    )
    print(f"[INFO] 정제 대상: {total}건")
    print(f"[INFO] 저장 {inserted}건, 갱신 {updated}건, "
          f"중복 스킵 {skipped}건, 규칙 제외 {dropped}건")
    return {"total": total, "inserted": inserted, "updated": updated,
            "skipped": skipped, "dropped": dropped}


def _find_column(df, candidates):
    for cand in candidates:
        for col in df.columns:
            norm = str(col).strip().lstrip("\ufeff").lower()
            if norm == cand.lower():
                return col
    return None


def _normalize_text(text):
    if text is None:
        return ""
    text = str(text).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _normalize_date(value):
    s = _cell_or_none(value)
    if s is None:
        return None
    s = s.replace("/", "-").replace(".", "-").strip()
    if re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", s):
        return s
    return None


def _cell_or_none(value):
    if value is None:
        return None
    if pd.isna(value):
        return None
    s = str(value).strip()
    return s if s and s.lower() != "nan" else None


def _to_int(value):
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None