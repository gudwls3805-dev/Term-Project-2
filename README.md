# AI 기반 고객 리뷰 감정 분석 대시보드

고객 리뷰(CSV)를 수집·정제하고, AI(Google Gemini API)로 감정을 분석한 뒤,
키워드·요약을 추출하고 차트와 리포트로 시각화하는 CLI 기반 Python 애플리케이션입니다.

단순 감정 분류에 그치지 않고 감정 분포, 별점-감정 상관관계, 주요 불만/칭찬 키워드,
개선 제안 등 비즈니스 의사결정에 활용 가능한 인사이트를 도출합니다.

> 본 문서는 프로젝트 개요·설치/실행·설정·**DB 스키마·설계 근거·기능별 실행 증빙**을
> 하나로 통합한 문서입니다.

---

# 목차

- [1. 팀 구성 및 역할](#1-팀-구성-및-역할)
- [2. 프로젝트 구조](#2-프로젝트-구조)
- [3. 설치 및 실행](#3-설치-및-실행)
- [4. 커맨드 실행 흐름](#4-커맨드-실행-흐름)
- [5. 모듈 아키텍처 (책임·의존 관계)](#5-모듈-아키텍처-책임의존-관계)
- [6. raw / clean 저장소 분리 설계](#6-raw--clean-저장소-분리-설계)
- [7. DB 스키마 (테이블·컬럼 명세)](#7-db-스키마-테이블컬럼-명세)
- [8. AI 감정 분석 프롬프트 설계](#8-ai-감정-분석-프롬프트-설계)
- [9. 감정 점수(0.0~1.0)의 저장 목적과 활용](#9-감정-점수0010의-저장-목적과-활용)
- [10. 차트 데이터 집계 및 전처리 로직](#10-차트-데이터-집계-및-전처리-로직)
- [11. 데이터 정제 규칙 상세](#11-데이터-정제-규칙-상세)
- [12. 기능별 실행 결과 및 정상 작동 증빙](#12-기능별-실행-결과-및-정상-작동-증빙)

---

## 1. 팀 구성 및 역할

| 담당 | 역할 | 주요 파일 |
|------|------|-----------|
| A | 데이터/DB (수집·정제·저장) | `src/storage.py`, `src/importer.py` |
| B | AI 분석 (감정 분석·키워드 추출) | `analyzer/sentiment.py`, `analyzer/extractor.py` |
| C | 통계/대시보드 (집계·차트·리포트) | `src/reporter.py` |
| D | CLI/통합 (전체 연결·설정·실행) | `main.py`, `config.json` |

---

## 2. 프로젝트 구조

```
Term-Project-2/
├── main.py                      # CLI 진입점 (argparse, 전체 연결)
├── config.json                  # 설정 파일 (API 키 이름, 중복 정책 등)
├── naver_reviews_sample50.csv   # 테스트용 샘플 리뷰 데이터 (50건)
├── src/
│   ├── storage.py               # 데이터 저장/조회 (SQLite)
│   ├── importer.py              # CSV 수집 및 정제
│   └── reporter.py              # 통계 집계, 차트 생성, 리포트
├── analyzer/
│   ├── sentiment.py             # AI 감정 분석
│   └── extractor.py             # AI 키워드/요약 추출
└── images/                      # 실행 증빙 이미지 (차트·화면 캡처)
```

---

## 3. 설치 및 실행

### 개발 환경
- Python 3.10 이상
- AI API: Google Gemini API

### 패키지 설치
```bash
pip install pandas openpyxl matplotlib google-genai python-dotenv
```

### API 키 설정
API 키는 코드에 직접 작성하지 않고 환경변수로 관리합니다.
프로젝트 루트에 `.env` 파일을 만들고 아래 한 줄을 작성하세요.

```
GEMINI_API_KEY=발급받은_API_키
```

> Gemini API 키는 https://aistudio.google.com/api-keys 에서 발급받습니다.
> `.env`는 `.gitignore`에 포함되어 저장소에 올라가지 않습니다.

### 설정 파일 (config.json)
DB 경로·중복 정책·시각화 옵션·API 키 환경변수명을 관리합니다.
실제 프로젝트의 `config.json` 전체 내용은 다음과 같습니다.

```json
{
  "db_path": "review.db",
  "dedup_policy": "skip",
  "min_review_length": 5,
  "ai": { "api_key_env": "GEMINI_API_KEY" },
  "visualization": { "output_dir": "output", "font": "NanumGothic", "dpi": 120 },
  "logging": { "level": "INFO" }
}
```

**각 설정 항목의 의미:**

| 키 | 타입 | 기본값 | 설명 |
|----|------|--------|------|
| `db_path` | string | `"review.db"` | SQLite DB 파일 경로 |
| `dedup_policy` | string | `"skip"` | 중복 리뷰 처리 정책. `skip`=중복 무시, `upsert`=기존 갱신 |
| `min_review_length` | int | `5` | 이 길이 미만의 리뷰는 정제 단계에서 제외 |
| `ai.api_key_env` | string | `"GEMINI_API_KEY"` | API 키를 읽어올 환경변수 이름 (키 값 자체는 `.env`에 보관) |
| `visualization.output_dir` | string | `"output"` | 차트·리포트 저장 폴더 |
| `visualization.font` | string | `"NanumGothic"` | 차트 한글 폰트(미설치 시 OS 기본 한글 폰트로 대체) |
| `visualization.dpi` | int | `120` | 차트 이미지 해상도 |
| `logging.level` | string | `"INFO"` | 로그 출력 레벨(INFO/WARNING/ERROR) |

> **설계 의도:** API 키 값을 config에 직접 넣지 않고 `api_key_env`로 **환경변수 이름만**
> 지정합니다. 이렇게 하면 config.json은 저장소에 커밋해도 안전하며, 실제 키는 `.gitignore`로
> 제외된 `.env`에만 존재합니다. 중복 정책·최소 길이 등 정책성 값을 코드가 아닌 설정 파일로
> 분리해, 코드 수정 없이 동작을 바꿀 수 있게 했습니다.

### 실행 (전체 순서)
```bash
python main.py import --file naver_reviews_sample50.csv   # 수집
python main.py clean                                       # 정제
python main.py analyze --unanalyzed --limit 50             # 감정 분석
python main.py extract                                     # 키워드/요약
python main.py list --sentiment negative --page 1 --size 5 # 조회
python main.py show --id 1                                  # 상세
python main.py stats                                       # 통계
python main.py dashboard                                    # 차트+리포트
python main.py export --format csv                          # 내보내기
python main.py export --format xlsx
```

### CLI 서브커맨드 (9종)

| 커맨드 | 설명 | 주요 옵션 |
|--------|------|-----------|
| `import` | CSV 수집 → raw 저장 | `--file` |
| `clean` | 정제 후 clean 저장 | |
| `analyze` | AI 감정 분석 | `--all`, `--id`, `--unanalyzed`, `--limit` |
| `extract` | AI 키워드/요약 추출 | `--sentiment`, `--date-from/to` |
| `list` | 목록 조회(필터·페이지네이션) | `--sentiment`, `--rating`, `--page`, `--size` |
| `show` | 상세 조회 | `--id` |
| `stats` | 통계 요약 | |
| `dashboard` | 차트 + 종합 리포트 | |
| `export` | 내보내기 | `--format`, `--sentiment`, `--rating-min` |

---

## 4. 커맨드 실행 흐름

```
import ─→ raw_reviews 적재
  │
clean  ─→ 정규화·검증·중복제거 ─→ clean_reviews
  │
analyze ─→ 미분석 리뷰를 Gemini로 감정 분석 ─→ clean_reviews.sentiment/score UPDATE
  │
extract ─→ 리뷰 종합 → 키워드/요약 추출 ─→ extractions 저장
  │
stats / list / show ─→ 집계·조회
  │
dashboard ─→ 차트 4종 PNG + 종합 리포트(TXT/MD)
  │
export ─→ CSV / Excel 내보내기
```

각 단계는 앞 단계의 저장 결과를 입력으로 사용하며, 영구 저장소(SQLite)를 통해 단계 간
데이터가 전달되므로 명령을 나누어 실행하거나 재실행해도 상태가 유지됩니다.

---

## 5. 모듈 아키텍처 (책임·의존 관계)

기능을 역할별로 6개 모듈로 분리했습니다. 단일 파일 구성은 수정 시 영향 범위가 크고 팀
병렬 작업이 불가능하므로, 각 모듈이 하나의 책임만 갖도록 설계했습니다(단일 책임 원칙).

| 모듈 | 책임 | 의존 대상 |
|------|------|-----------|
| `main.py` (D) | CLI 진입점. argparse 파싱 후 알맞은 모듈 함수 호출(조립). 비즈니스 로직 없음 | importer, storage, sentiment, extractor, reporter |
| `src/importer.py` (A) | CSV 수집·정제. 컬럼 매핑, 정규화, 중복 해시 | storage |
| `src/storage.py` (A) | SQLite 저장·조회. 테이블 생성, insert/query, 감정 UPDATE | (없음, 최하위) |
| `analyzer/sentiment.py` (B) | AI 감정 분석. 프롬프트 구성, Gemini 호출, 검증 | Gemini API |
| `analyzer/extractor.py` (B) | AI 키워드/요약 추출 | Gemini API |
| `src/reporter.py` (C) | 통계 집계, 차트, 리포트 | 입력 dict 리스트만 |

### 의존 방향
```
main.py  (최상위 · 조립만 담당)
   ├──► importer.py ──► storage.py
   ├──► sentiment.py / extractor.py  (Gemini API)
   ├──► storage.py   (조회)
   └──► reporter.py  (집계·시각화)

storage.py 는 어떤 모듈에도 의존하지 않는 최하위 계층이다.
```

**설계 의도:** 의존을 상위(main) → 하위(storage) 한 방향으로만 흐르게 하여 순환 의존을
제거했습니다. `reporter.py`는 DB를 직접 다루지 않고 **dict 리스트만 입력**받도록 하여
데이터 출처가 바뀌어도 시각화 코드를 재사용할 수 있고, `main.py`는 로직 없이 연결만
담당하므로 한 기능 수정이 다른 모듈로 전파되지 않습니다.

---

## 6. raw / clean 저장소 분리 설계

원본(`raw_reviews`)과 정제 데이터(`clean_reviews`)를 물리적으로 다른 테이블로 분리했습니다.

| 구분 | raw_reviews | clean_reviews |
|------|-------------|---------------|
| 저장 시점 | `import` 시 (원본 그대로) | `clean` 시 (정제 통과분만) |
| 가공 | 없음 (원본 보존) | 정규화·검증·중복제거 완료 |
| 용도 | 감사·재처리 소스 | 분석·시각화 대상 |

**분리한 이유:**
1. **원본 불변성(재현성):** 정제 규칙은 개발 중 계속 바뀝니다(예: 최소 길이 기준). 원본을
   보존하면 규칙을 바꿔도 raw에서 다시 정제할 수 있습니다. 덮어쓰기 방식은 복구가 불가합니다.
2. **문제 추적:** 결과가 이상할 때 raw와 clean을 비교해 어느 단계에서 데이터가 걸러졌는지
   (짧은 리뷰/중복/별점 오류) 추적할 수 있습니다.
3. **책임 분리:** 수집(무손실 적재)과 정제(품질 보장)는 목적이 다른 단계이므로 저장소를
   나누어 각 단계가 독립적으로 검증되게 했습니다.

---

## 7. DB 스키마 (테이블·컬럼 명세)

영구 저장소로 **SQLite**를 사용하며 3개 테이블로 구성됩니다.

### 7-1. `raw_reviews` — 수집 원본
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK AUTOINCREMENT | 고유 ID |
| review_text | TEXT | 리뷰 원문 |
| rating | INTEGER | 별점(1~5), 없으면 NULL |
| date | TEXT | 작성일 |
| product | TEXT | 제품명(선택) |
| imported_at | TEXT | 수집 시각(기본값 현재시각) |

### 7-2. `clean_reviews` — 정제·분석 결과
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK AUTOINCREMENT | 고유 ID |
| review_text | TEXT NOT NULL | 정규화된 리뷰 |
| rating | INTEGER | 검증된 별점(1~5) |
| date | TEXT | 통일된 날짜 |
| product | TEXT | 제품명 |
| **sentiment** | TEXT | 감정(positive/negative/neutral), 분석 전 NULL |
| **score** | REAL | 신뢰도 0.0~1.0, 분석 전 NULL |
| text_hash | TEXT UNIQUE | 본문 MD5 해시(중복 판별 키) |
| created_at | TEXT | 정제 시각 |

> 감정 결과는 별도 테이블이 아니라 **clean_reviews의 `sentiment`, `score` 컬럼에 UPDATE**로
> 저장합니다. 리뷰와 감정이 1:1 관계이므로 같은 행에 두어 조인 없이 조회 가능하게
> 설계했고, 미분석 리뷰는 `sentiment IS NULL`로 판별하여 `--unanalyzed`가 이를 활용합니다.

### 7-3. `extractions` — AI 키워드/요약 결과
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK AUTOINCREMENT | 고유 ID |
| scope | TEXT | 추출 범위 |
| keywords_pos | TEXT | 긍정 키워드 |
| keywords_neg | TEXT | 부정 키워드 |
| summary | TEXT | 전체 요약 |
| suggestions | TEXT | 개선 제안 |
| created_at | TEXT | 추출 시각 |

---

## 8. AI 감정 분석 프롬프트 설계

### 8-1. 실제 사용 프롬프트 (원문)
```
다음 고객 리뷰의 감정을 분석하세요.

감정은 반드시 다음 세 가지 중 하나로 분류하세요.
- positive: 긍정
- negative: 부정
- neutral: 중립

confidence는 해당 감정 분류에 대한 신뢰도를
0.0 이상 1.0 이하의 숫자로 작성하세요.

고객 리뷰:
{리뷰 텍스트}

반드시 다음 JSON 형식으로만 답변하세요.
설명이나 다른 문장은 추가하지 마세요.

{
    "sentiment": "positive",
    "confidence": 0.95
}
```

### 8-2. 설계 원리
- **라벨 고정(폐쇄형 분류):** positive/negative/neutral 3개로 라벨을 한정하여 모델이 임의
  표현("만족" 등)을 반환하지 못하게 했습니다. 후처리에서 이 3개 외 값은 `ValueError`로
  걸러 저장하지 않습니다.
- **출력 형식 강제(JSON):** "반드시 JSON으로만, 설명 없이"를 명시해 파싱 가능한 구조화
  출력을 유도했고, `json.loads`로 파싱하며 형식 오류 시 예외 처리 후 스킵합니다.
- **점수 정의 명시:** confidence를 "분류 신뢰도(0.0~1.0)"로 정의하고 후처리에서
  `0.0 <= score <= 1.0` 범위를 검증하여 이상치를 배제합니다.
- **예시 제공(one-shot):** 원하는 출력 JSON 예시를 함께 제시해 형식 준수율을 높였습니다.

### 8-3. 키워드/요약 프롬프트 (extractor)
다건 리뷰를 번호 목록으로 합쳐 한 번에 요청하고, `positive_keywords`, `negative_keywords`,
`frequent_praises`, `frequent_complaints`, `summary`, `improvements` 6개 항목을 JSON으로
반환하도록 지시했습니다. 각 항목 최대 개수(키워드 5개, 개선안 3개 등)를 명시해 분량을
제어했습니다.

---

## 9. 감정 점수(0.0~1.0)의 저장 목적과 활용

### score의 정확한 의미

`score`는 **감정의 세기(강도)가 아니라, AI가 내린 감정 분류 결과에 대한 신뢰도
(confidence)**입니다. 즉 "얼마나 긍정적인가"가 아니라 "이 분류(positive/negative/neutral)를
얼마나 확신하는가"를 나타냅니다.

- `0.0`에 가까울수록: AI가 분류를 확신하지 못함 (모호한 리뷰)
- `1.0`에 가까울수록: AI가 분류를 강하게 확신함 (명확한 리뷰)

예를 들어 "배송 최악"은 부정이 명확하여 score가 높게(예: 0.99), "그냥 무난해요"처럼
긍정·중립이 섞인 모호한 리뷰는 score가 낮게 나오는 경향이 있습니다.

### 활용 방안

1. **분석 신뢰도 판별 → 재검수 트리거:** 점수가 낮은(예: 0.5 미만) 리뷰는 AI가 확신하지
   못한 경우이므로 사람이 재확인해야 할 대상으로 분류할 수 있습니다.
   여기서 **0.5는 절대적인 통계적 임계값이 아니라, 사람이 재검수할 후보를 선별하기 위한
   초기 운영 기준(휴리스틱)**입니다. 신뢰도가 절반에 못 미치면 자동 분석 결과를 그대로
   신뢰하기보다 검토 대상으로 돌린다는 의미이며, 실제 운영 데이터가 쌓이면 오분류율을
   보고 임계치를 조정할 수 있습니다.
2. **별점-감정 불일치 탐지(품질 지표):** 리포트 "품질 지표"에서 별점은 높은데(4~5) 감정이
   부정이거나 그 반대인 리뷰를 집계합니다. 별점만으로 놓치는 숨은 불만, 또는 AI 오분류
   가능성을 드러내는 신호입니다.
3. **상관관계 분석:** 별점(정량)과 감정 점수(AI 정성)를 함께 저장해 둘의 상관관계를 비교할
   수 있으며, 별점-감정 일치율이 그 예입니다.

> 확장: 임계치(예: 0.5)를 config로 두어 임계치 미만 리뷰를 상담사 재검수 큐로 자동 분류하는
> 운영 연계가 가능합니다.

---

## 10. 차트 데이터 집계 및 전처리 로직

모든 차트는 `clean_reviews`의 dict 리스트를 입력받아 `collections.Counter`로 집계하며,
**감정 미분석(sentiment=NULL) 리뷰는 집계에서 제외**하여 결측을 처리합니다.

| 차트 | 집계 단위 | 결측/이상치 처리 |
|------|-----------|------------------|
| 감정 분포 | 감정별 건수 | sentiment 없는 행 제외, 전체 0건이면 생략 |
| 별점별 감정 분포 | (별점 × 감정) 교차, 별점 1~5 고정 | 별점 없는 행 제외, 0건 구간도 축 유지 |
| 부정 비율 추이 | 수집순 이동평균(직전 10건) 부정 비율 | 10건 미만이면 생략(구간 부족) |
| 리뷰 길이 분포 | 감정별 글자 수 분포 + 중앙값 | 감정 없는 행 제외, 감정별 그룹핑 |

**설계 의도:** 별점 축(1~5)은 데이터에 없는 값(예: 3점 0건)도 항상 표시해 빈 구간이
드러나게 했고, 추이 차트는 표본이 부족하면(10건 미만) 왜곡된 추세를 그리지 않도록
생략 처리했습니다. 한글 깨짐 방지를 위해 OS별 폰트(Windows: Malgun Gothic)를 자동 적용합니다.

### 집계 과정 예시 — 별점별 감정 분포

실제 코드(`chart_rating_sentiment`)가 데이터를 처리하는 단계는 다음과 같습니다.

```
입력:
  clean_reviews (dict 리스트)

필터(결측 처리):
  rating IS NOT NULL  AND  sentiment IS NOT NULL
  → 별점 또는 감정이 없는 행은 집계에서 제외

Grouping(교차 집계):
  (rating, sentiment) 조합별로 그룹핑
  코드: table = {rating: Counter() for rating in 1..5}
        table[rating][sentiment] += 1

Aggregation:
  각 (별점, 감정) 조합의 COUNT(*)

결과 예시 (실제 50건 기준):
  1점 → 긍정 1  / 중립 0 / 부정 12
  2점 → 긍정 1  / 중립 1 / 부정 11
  3점 → (0건, 축은 유지)
  4점 → 긍정 6  / 중립 3 / 부정 4
  5점 → 긍정 11 / 중립 0 / 부정 0
```

이 교차 집계 결과를 감정별로 누적(stacked)하여 막대에 쌓아, "별점 4~5인데 부정" 같은
어긋난 조합을 시각적으로 드러냅니다. 별점 1~5는 데이터에 없어도 축을 유지하여(3점 0건도
표시) 분포의 공백이 보이도록 했습니다.

---

## 11. 데이터 정제 규칙 상세 (importer.py)

- **컬럼 자동 매핑:** `rating/별점/평점/star`, `review/리뷰/내용/content` 등 후보명으로 다양한
  CSV 헤더 인식 (BOM·대소문자·공백 처리 포함).
- **텍스트 정규화:** 앞뒤 공백 제거, 연속 공백 정리.
- **짧은 리뷰 필터:** 정규화 후 길이 5자 미만 제외(`MIN_LEN=5`).
- **별점 검증:** 1~5 범위를 벗어나면 NULL 처리.
- **날짜 통일:** `/`, `.` 구분자를 `-`로 통일.
- **중복 처리:** 본문 MD5 해시(`text_hash`)를 UNIQUE 키로 사용, 정책(skip/upsert)에 따라
  중복을 건너뛰거나 갱신.

---

## 12. 기능별 실행 결과 및 정상 작동 증빙

아래는 실제 프로그램을 Windows 환경에서 Gemini API로 구동한 결과입니다.
(테스트 데이터: `naver_reviews_sample50.csv` 50건)

### 검증 요약표

| # | 기능 | 실행 결과 | 정상 |
|---|------|-----------|:---:|
| 1 | import | 50건 로드·저장 | ✅ |
| 2 | clean | 50건 정제 완료 | ✅ |
| 3 | analyze | 50건 분석(긍정/부정/중립 + 신뢰도) | ✅ |
| 4 | extract | 6개 항목 추출 | ✅ |
| 5 | list/show | 필터·페이지네이션·상세 | ✅ |
| 6 | stats | 통계 출력 | ✅ |
| 7 | dashboard | 차트 4종 + 리포트 | ✅ |
| 8 | export | CSV·Excel 50건 | ✅ |
| 9 | API 실패 처리 | 429 시 로깅 후 스킵 | ✅ |

### 12-1. 감정 분석 (analyze)
```
$ python main.py analyze --unanalyzed --limit 5
[INFO] 분석 대상: 5건
[INFO] HTTP Request: POST .../gemini-3.5-flash:generateContent "HTTP/1.1 200 OK"
[INFO] [1/5] ID=18 분석 완료: positive (0.80)
[INFO] [2/5] ID=19 분석 완료: negative (0.99)
[INFO] [3/5] ID=20 분석 완료: neutral (0.85)
[INFO] 분석 완료: 5건 성공, 0건 실패
```
→ 실제 API 호출(HTTP 200), 긍정·부정·중립 3종 분류 + 신뢰도 저장 확인.

### 12-2. 통계 (stats)
![stats 실행 결과](images/screen_stats_dashboard.png)

### 12-3. 생성된 차트 4종 (dashboard)
**① 감정 분포**
![감정 분포](images/sentiment_distribution.png)

**② 별점별 감정 분포**
![별점별 감정 분포](images/rating_sentiment.png)

**③ 부정 비율 추이**
![부정 비율 추이](images/negative_trend.png)

**④ 리뷰 길이 분포**
![리뷰 길이 분포](images/length_by_sentiment.png)

→ 요구 3종을 초과하는 차트 4종, 한글 폰트 정상 적용, PNG 저장 확인.

### 12-4. 종합 리포트 (dashboard)
![리포트 요약·감정분포·별점분포·품질지표](images/screen_report_1.png)

![부정 TOP5·AI 키워드·AI 요약·개선제안·export](images/screen_report_2.png)

→ 품질 지표(별점-감정 불일치), 부정 TOP 5, AI 키워드/요약/개선제안 포함.
콘솔 출력 및 TXT/MD 저장 동작.

### 12-5. API 실패 처리
```
[INFO] HTTP Request: POST .../generateContent "HTTP/1.1 429 Too Many Requests"
[ERROR] 감정 분석 API 호출 실패: 429 RESOURCE_EXHAUSTED. (...quota...)
[ERROR] [4/5] ID=22 분석 실패 → 스킵
[INFO] 분석 완료: 3건 성공, 2건 실패
```
→ API 실패 시 에러를 로깅하고 해당 건만 스킵, 프로그램은 계속 진행하며 성공/실패 집계.

---

## 종합 결론

CLI 서브커맨드 9종이 모두 정상 작동하며, 실제 Gemini API를 통한 감정 분석·키워드 추출,
matplotlib 차트 4종, 품질 지표·TOP N·AI 인사이트를 포함한 종합 리포트, 다중 포맷 내보내기,
예외 처리까지 기능 요구사항을 충족합니다. 아울러 모듈 아키텍처·저장소 분리·DB 스키마·
프롬프트 설계·감정 점수 활용·차트 집계 로직 등 설계 근거를 본 문서에 기술하였습니다.
