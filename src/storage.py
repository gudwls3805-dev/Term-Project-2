"""
storage.py — 데이터 저장소 (SQLite)
담당: A (데이터/DB) · 브랜치: feat/storage
관련 요구사항: ② 수집(raw 저장), ③ 정제(clean 저장), ⑪ 영구 저장소
"""

import sqlite3
import logging

DB_PATH = "review.db"
logger = logging.getLogger(__name__)


def get_conn(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # row["review_text"] 처럼 컬럼명으로 접근
    return conn


def init_db(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS raw_reviews (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            review_text TEXT,
            rating      INTEGER,
            date        TEXT,
            product     TEXT,
            imported_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS clean_reviews (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            review_text TEXT NOT NULL,
            rating      INTEGER,
            date        TEXT,
            product     TEXT,
            sentiment   TEXT,
            score       REAL,
            text_hash   TEXT UNIQUE,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );
        """
    )
    conn.commit()
    logger.info("DB 초기화 완료 (raw_reviews, clean_reviews)")


def insert_raw(conn, review_text, rating=None, date=None, product=None):
    conn.execute(
        "INSERT INTO raw_reviews (review_text, rating, date, product) VALUES (?,?,?,?)",
        (review_text, rating, date, product),
    )


def insert_clean(conn, review_text, rating, date, product, text_hash, policy="skip"):
    row = conn.execute(
        "SELECT id FROM clean_reviews WHERE text_hash=?", (text_hash,)
    ).fetchone()

    if row is None:
        conn.execute(
            "INSERT INTO clean_reviews (review_text, rating, date, product, text_hash) "
            "VALUES (?,?,?,?,?)",
            (review_text, rating, date, product, text_hash),
        )
        return "inserted"

    if policy == "upsert":
        conn.execute(
            "UPDATE clean_reviews SET review_text=?, rating=?, date=?, product=? "
            "WHERE text_hash=?",
            (review_text, rating, date, product, text_hash),
        )
        return "updated"

    return "skipped"


def update_sentiment(conn, review_id, sentiment, score):
    conn.execute(
        "UPDATE clean_reviews SET sentiment=?, score=? WHERE id=?",
        (sentiment, score, review_id),
    )
    conn.commit()


def query_reviews(conn, sentiment=None, rating=None,
                  date_from=None, date_to=None,
                  only_unanalyzed=False, limit=None, offset=0):
    sql = "SELECT * FROM clean_reviews WHERE 1=1"
    params = []
    if sentiment:
        sql += " AND sentiment=?"; params.append(sentiment)
    if rating:
        sql += " AND rating=?"; params.append(rating)
    if date_from:
        sql += " AND date>=?"; params.append(date_from)
    if date_to:
        sql += " AND date<=?"; params.append(date_to)
    if only_unanalyzed:
        sql += " AND sentiment IS NULL"
    sql += " ORDER BY id"
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"; params += [limit, offset]
    return conn.execute(sql, params).fetchall()


def get_review(conn, review_id):
    return conn.execute(
        "SELECT * FROM clean_reviews WHERE id=?", (review_id,)
    ).fetchone()


def count_reviews(conn, **filters):
    filters.pop("limit", None)
    filters.pop("offset", None)
    return len(query_reviews(conn, **filters))