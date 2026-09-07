# AI 기반 고객 리뷰 감정 분석 대시보드

고객 리뷰(CSV)를 수집·정제하고, AI(Google Gemini API)로 감정을 분석한 뒤,
키워드·요약을 추출하고 차트와 리포트로 시각화하는 CLI 기반 Python 애플리케이션입니다.

단순 감정 분류에 그치지 않고 감정 분포, 별점-감정 상관관계, 주요 불만/칭찬 키워드,
개선 제안 등 비즈니스 의사결정에 활용 가능한 인사이트를 도출합니다.

---

## 팀 구성 및 역할

| 담당 | 역할 | 주요 파일 |
|------|------|-----------|
| A | 데이터/DB (수집·정제·저장) | `src/storage.py`, `src/importer.py` |
| B | AI 분석 (감정 분석·키워드 추출) | `analyzer/sentiment.py`, `analyzer/extractor.py` |
| C | 통계/대시보드 (집계·차트·리포트) | `src/reporter.py` |
| D | CLI/통합 (전체 연결·설정·실행) | `main.py`, `config.json` |

---

## 프로젝트 구조

```
Term-Project-2/
├── main.py                      # CLI 진입점 (argparse, 전체 연결)
├── config.json                  # 설정 파일 (API 키 이름, 중복 정책 등)
├── naver_reviews_sample50.csv   # 테스트용 샘플 리뷰 데이터 (50건)
├── src/
│   ├── storage.py               # 데이터 저장/조회 (SQLite)
│   ├── importer.py              # CSV 수집 및 정제
│   └── reporter.py              # 통계 집계, 차트 생성, 리포트
└── analyzer/
    ├── sentiment.py             # AI 감정 분석
    └── extractor.py             # AI 키워드/요약 추출
```

---

## 개발 환경 및 설치

- Python 3.10 이상
- AI API: Google Gemini API

### 1. 패키지 설치

```bash
pip install pandas openpyxl matplotlib google-genai python-dotenv
```

### 2. API 키 설정

API 키는 코드에 직접 작성하지 않고 환경변수로 관리합니다.
프로젝트 루트에 `.env` 파일을 만들고 아래 한 줄을 작성하세요.

```
GEMINI_API_KEY=발급받은_API_키
```

> Gemini API 키는 https://aistudio.google.com/api-keys 에서 발급받을 수 있습니다.
> `.env` 파일은 `.gitignore`에 포함되어 저장소에 올라가지 않습니다.

---

## 사용법

각 명령은 아래 순서대로 실행합니다.

```bash
# 1. 리뷰 데이터 가져오기 (raw 저장)
python main.py import --file naver_reviews_sample50.csv

# 2. 데이터 정제 (clean 저장, 중복 skip/upsert)
python main.py clean

# 3. AI 감정 분석 (긍정/부정/중립 + 신뢰도)
python main.py analyze --unanalyzed --limit 50

# 4. AI 키워드/요약 추출
python main.py extract

# 5. 리뷰 조회
python main.py list --sentiment negative --page 1 --size 5
python main.py show --id 1

# 6. 통계 요약
python main.py stats

# 7. 대시보드 (차트 PNG + 종합 리포트 TXT/MD)
python main.py dashboard

# 8. 데이터 내보내기 (CSV / JSONL / Excel)
python main.py export --format csv
python main.py export --format xlsx
```

---

## 주요 기능

### CLI 서브커맨드 (9종)

| 커맨드 | 설명 | 주요 옵션 |
|--------|------|-----------|
| `import` | CSV 리뷰 데이터 수집 → raw 저장 | `--file` |
| `clean` | 정제 후 clean 저장 (중복/짧은 리뷰 처리) | |
| `analyze` | AI 감정 분석 (긍정/부정/중립 + 신뢰도) | `--all`, `--id`, `--unanalyzed`, `--limit` |
| `extract` | AI 키워드/요약/개선제안 추출 | `--sentiment`, `--date-from/to` |
| `list` | 리뷰 목록 조회 (필터·페이지네이션) | `--sentiment`, `--rating`, `--page`, `--size` |
| `show` | 리뷰 상세 조회 | `--id` |
| `stats` | 전체 통계 요약 | |
| `dashboard` | 차트 생성 + 종합 리포트 | |
| `export` | 데이터 내보내기 | `--format`, `--sentiment`, `--rating-min` |

### 데이터 처리
- CSV에서 리뷰 텍스트·별점·작성일을 읽어 raw 저장소(SQLite)에 저장
- 정제: 필수 필드 검증, 텍스트 정규화, 별점 범위 검증, 짧은 리뷰 필터링
- 중복 처리 정책(skip/upsert) 적용, clean 저장소에 별도 저장

### AI 감정 분석
- Gemini API로 감정(긍정/부정/중립)과 신뢰도 점수(0.0~1.0) 분석
- 분석 대상 선택(`--all`, `--id`, `--unanalyzed`), API 실패 시 로깅 후 스킵

### AI 키워드/요약 추출
- 긍정/부정 키워드, 빈출 칭찬/불만, 전체 요약, 개선 제안 추출
- 추출 결과를 저장하여 대시보드 리포트에 활용

### 시각화 및 리포트
- matplotlib 차트 (감정 분포, 별점별 감정 분포, 부정 비율 추이, 리뷰 길이 분포)
- 한글 폰트 적용, PNG 저장
- 품질 지표(별점-감정 불일치 분석), 부정 리뷰 TOP N, AI 인사이트를 포함한
  종합 리포트를 콘솔 출력 및 TXT/MD 파일로 저장

### 데이터 저장 및 설정
- 영구 저장소로 SQLite 사용
- `config.json`으로 설정 관리, `logging`으로 INFO/WARNING/ERROR 로그 기록

---

## 참고 사항

- 무료 Gemini API는 모델별 일일 호출 한도가 있어, 대량 분석 시 나누어 실행할 수 있습니다.
- 실시간 웹 대시보드나 쇼핑몰 크롤링은 구현 범위에 포함되지 않으며,
  파일 기반 입력과 정적 차트·파일 리포트로 구성됩니다.
