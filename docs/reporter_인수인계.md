# reporter 인수인계 문서

> 이 파일 하나만 읽고도 이어서 작업할 수 있게 정리한 문서다.
> 작업 대상: `src/reporter.py` (브랜치 `feat/reporter`)
> 최종 갱신: 단위 4 완료 시점

---

## 0. 작업자 규칙 (반드시 지킬 것)

이 프로젝트는 **코디세이 AI 네이티브 과정의 평가 대상 미션**이다. 평가는 코드 완성도가 아니라
**"기술 선택 근거와 핵심 원리를 학습자 본인의 언어로 설명할 수 있는가"**를 무작위 동료 3인이
대면 인터뷰로 검증하는 방식이다. 단순 바이브코딩은 과정 규정상 불허된다.

- **의뢰인은 비개발자다.** 개발 지식이 전혀 없다고 전제하고, 용어를 처음 쓸 때는 반드시 한 줄로 풀어 준다.
- **완성품을 통째로 만들어 주지 말 것.** 의뢰인이 이해하고 손댈 수 있는 초안까지만 만든다.
  **의뢰인이 설명하지 못하는 코드가 레포에 남으면 그 작업은 실패로 간주한다.**
- **한 번에 한 단위만 작업한다.** 단위가 끝나면 멈추고 확인을 요청한다. 확인 없이 다음 단위로 넘어가지 않는다.
- **선택지가 갈리는 지점**(라이브러리, 자료구조, 차트 형태)에서는 단일 추천을 밀지 말고
  2~3개 대안과 트레이드오프를 "무엇이 쉬워지고 무엇이 어려워지는지"로 제시한다. 최종 결정은 의뢰인이 한다.
- **Pull Request는 절대 직접 생성하지 않는다.** 브랜치 생성·작업·커밋까지만 수행한다. 제출 시점은 의뢰인이 판단한다.
- 매 단위마다 **설계 의도·기술 선택 근거 메모 / README 조각 / 핵심 코드 라인별 해설** 3종을 함께 갱신한다.
  → 이 프로젝트에서는 `docs/reporter_설계메모.md` 한 파일에 세 가지를 모두 담고 있다.
- 응답은 한국어, 서론 없이 본론부터. 각 단위 종료 시 마지막 줄에 `다음 단위: ___ / 확인 필요: ___`.

---

## 1. 미션 개요

**[Project C] AI 기반 고객 리뷰 감정 분석 대시보드** (AI 활용 학습 / Term Project / 40시간)

CSV·Excel 리뷰 파일을 읽어 → AI로 감정 분석 → 차트 PNG와 리포트 파일을 생성하는
**CLI 기반 Python 애플리케이션**. 실시간 웹 대시보드와 쇼핑몰 크롤링은 구현 범위에서 제외된다.

필수 서브커맨드 9개: `import` `clean` `analyze` `extract` `list` `show` `stats` `dashboard` `export`

전체 요건은 레포 밖 `미션체크리스트.md` 참조. **이 문서가 다루는 것은 아래 4개 요건뿐이다.**

| 요건 | 상태 |
|---|---|
| matplotlib 차트 3종 이상 | ✅ **4종 완료** |
| 한글 폰트 적용 + PNG 저장 | ✅ 완료 (Windows·Linux 양쪽 실행 검증) |
| 품질 지표 2개 이상 **계산** | ✅ **3종 완료** (`calc_stats`) |
| 리포트에 품질 지표 + TOP N 집계 1개 이상 + AI 추출 결과 **표시** | ✅ 완료 (AI 구역은 D가 `insights`를 넘기면 채워짐) |
| 리포트 콘솔 출력 및 파일(TXT/MD) 저장 | ✅ 완료 (TXT·MD 둘 다) |

---

## 2. 팀 구성과 담당 (4인 협업)

| 담당 | 브랜치 | 파일 | 범위 |
|---|---|---|---|
| A · 데이터/DB | `feat/storage` | `src/storage.py`, `src/importer.py` | import, clean, list, show, 샘플 데이터 |
| B · AI 분석 | `feat/analyzer` | `analyzer/sentiment.py`, `analyzer/extractor.py` | analyze, extract |
| **C · 통계/대시보드** | **`feat/reporter`** | **`src/reporter.py`** | **stats, dashboard, export** ← 이 문서의 담당 |
| D · CLI/통합 | `feat/cli` | `main.py`, `config.py` | argparse, 전체 연결, 테스트, README |

**철칙: 남의 파일은 열지 않는다.** 문제가 있으면 직접 고치지 말고 담당자에게 알린다.

레포: `https://github.com/gudwls3805-dev/Term-Project-2` (Public)
로컬: `C:\Users\my\workspaces\Term-Project-2`

---

## 3. 핵심 설계 결정 (확정, 변경하지 말 것)

### 3-1. reporter는 저장소를 직접 열지 않는다 ★가장 중요

`src/reporter.py`의 모든 공개 함수는 **리뷰 목록(딕셔너리 리스트)을 인자로 받는다.**
SQLite에 접속하지 않고, A의 저장 방식을 전혀 모른다.

```python
chart_sentiment_distribution(reviews) -> str | None   # PNG 경로 반환
```

- **얻은 것**: A의 작업을 기다리지 않고 독립적으로 개발·테스트 가능. A가 SQLite→JSONL로 바꿔도 이 파일은 안 바뀜.
- **대가**: D가 `main.py`에서 "저장소에서 꺼내 → reporter에 넘기기" 연결선을 한 줄 더 씀.
- 이 원칙을 깨고 reporter 안에서 `sqlite3`를 import하는 순간 위 이점이 전부 사라진다. **금지.**

### 3-2. 한글 폰트는 OS를 감지해 자동 선택

Windows→`Malgun Gothic`, macOS→`AppleGothic`, Linux→`NanumGothic`/`Noto Sans CJK`.
**2단계 탐색**을 쓴다: 후보 목록을 돌며 실제 설치 여부를 확인하고, 하나도 없으면 경고만 남기고 계속 진행한다
(폰트가 없다고 프로그램이 죽으면 안 된다).

`axes.unicode_minus = False`도 함께 설정한다 — 이게 없으면 음수 부호가 한글 폰트에서 네모로 깨진다.

**버린 대안**: 코드에 `Malgun Gothic` 한 줄 고정(→ Mac·Linux 팀원 환경에서 깨짐),
폰트 `.ttf` 파일 레포 동봉(→ 용량·라이선스 부담).

### 3-3. 감정 표시 규칙은 한 곳에서만 관리

`SENTIMENT_ORDER` / `SENTIMENT_KO` / `SENTIMENT_COLOR` / `SENTIMENT_INK` 상수로 파일 상단에 모아 둠.
차트마다 색과 순서가 달라지면 읽는 사람이 매번 범례를 다시 봐야 하므로, 전 차트가 이 상수를 공유한다.
**새 차트를 추가할 때도 반드시 이 상수를 쓴다.**

### 3-4. 차트별 형태 선택 근거

| 차트 | 형태 | 버린 대안과 이유 |
|---|---|---|
| ① 감정 분포 | 가로 막대 | 파이차트 — 조각 각도 비교가 부정확, 한글 라벨이 조각 밖으로 밀림 |
| ② 별점별 감정 분포 | 세로 누적 막대 | 그룹 막대(막대 15개로 늘어 안 읽힘), 100% 비율 막대(건수가 사라져 신뢰도 판단 불가) |
| ④ 부정 비율 추이 | 이동 평균 선 | 10건씩 구간 묶기 — 50건이면 점이 5개뿐이라 추이라 부르기 어려움 |
| ⑤ 리뷰 길이 분포 | 점 흩뿌리기 | 평균 막대(분포가 통째로 사라짐), 상자 그림(사분위수 개념 설명 부담) |

### 3-5. 무작위(random)를 쓰지 않는다

차트 ⑤에서 점이 겹치지 않게 흩을 때 `random`이 아니라 **순번을 5로 나눈 나머지**를 쓴다.
무작위면 실행할 때마다 그림이 미묘하게 달라져서, 제출한 PNG와 평가자가 재실행한 PNG가 달라진다.
**"제3자 재현 가능"이 실제 평가 항목이므로 이 원칙을 지킨다.**

---

## 4. 현재 데이터 현황

### 4-1. 샘플 CSV (A 제공)

`naver_reviews_sample50.csv` — **50건**, 칸은 `rating`, `review` **두 개뿐**.
파일 앞에 BOM이 붙어 있어 **`encoding="utf-8-sig"`로 읽어야** 첫 칸 이름이 `rating`으로 나온다.

별점 분포: 1점 13건 / 2점 13건 / **3점 0건** / 4점 13건 / 5점 11건
리뷰 길이: 최소 7자 / 평균 46.2자 / 최대 139자

### 4-2. A의 DB 스키마 (`clean_reviews` 테이블)

```
id, review_text, rating, date, product, sentiment, score, text_hash, created_at
```

reporter는 이 중 `id`, `review_text`, `rating`, `sentiment`, `score`를 읽는다.
**`date`와 `product`는 CSV에 원본 데이터가 없어 항상 비어 있다.**

### 4-3. 임시 감정값에 대한 경고 ★오해 금지

현재 `src/reporter.py`의 단독 실행 모드는 **별점으로 감정을 매긴 임시값**을 쓴다
(4~5점→긍정, 3점→중립, 1~2점→부정). `_rating_to_sentiment()` 함수가 그것이다.

**이건 AI 분석 결과가 아니다.** 차트 코드가 도는지 확인하는 용도일 뿐이며,
실제 리포트에는 B의 `analyze_sentiment()` 결과를 쓴다.
지금 차트가 밋밋하게(막대마다 단색으로) 보이는 것은 이 때문이며, 코드 문제가 아니다.

---

## 5. 팀 인터페이스 (A·B가 만든 것 — 읽기만 할 것)

### A · `src/storage.py`
```python
query_reviews(conn, sentiment=None, rating=None, date_from=None, date_to=None,
              only_unanalyzed=False, limit=None, offset=0) -> list[sqlite3.Row]
get_review(conn, review_id) -> sqlite3.Row
count_reviews(conn, **filters) -> int
update_sentiment(conn, review_id, sentiment, score)
```
`sqlite3.Row`는 `row["rating"]`처럼 칸 이름으로 접근된다. `dict(row)`로 바꿔서 reporter에 넘기면 된다.

### B · `analyzer/sentiment.py`
```python
analyze_sentiment(text: str) -> {"sentiment": "positive"|"negative"|"neutral",
                                 "confidence": float} | None
```

### B · `analyzer/extractor.py`
```python
extract_insights(reviews: list[str]) -> {"positive_keywords": list[str],   # 최대 5개
                                         "negative_keywords": list[str],   # 최대 5개
                                         "summary": str,
                                         "improvements": list[str]} | None
```
→ **TOP N 집계와 "AI 추출 결과 포함" 요건은 이 함수의 반환값을 받아 표시하면 된다.**
   reporter가 직접 호출하지 않는다. D가 `main.py`에서 호출해 결과를 넘겨준다.

---

## 6. 미해결 이슈 (팀에 전달 필요, C 혼자 해결 불가)

| # | 내용 | 영향 | 담당 |
|---|---|---|---|
| 1 | **CSV에 날짜 칸이 없다** | 미션 필수 차트인 "시간별 추이"를 만들 수 없다. `list --date-from/to` 필터도 불가 | A |
| 2 | **CSV에 제품명 칸이 없다** | 제품별 비교(보너스) 불가 | A |
| 3 | **CSV가 별점 순으로 정렬되어 있다** | 수집 순번이 실제 수집 순서가 아님 → 차트 ④가 계단 모양으로 나와 무의미 | A |
| 4 | **별점 3점 리뷰가 0건** | "중립" 감정 분류를 한 번도 검증할 수 없다 | A |
| 5 | **B의 반환값은 `confidence`, A의 DB 칸은 `score`** | 이름이 달라 그대로 넣으면 값이 안 들어간다. 어딘가에서 변환 필요 | D |
| 6 | **폴더 구조 불일치** — storage는 `src/`, analyzer는 최상위 `analyzer/` | main으로 합칠 때 import 경로 충돌 | D |
| 7 | **줄바꿈 형식(CRLF/LF) 혼재** | 손대지 않은 파일이 "591줄 변경"으로 뜬다. 레포 루트에 `.gitattributes`(`* text=auto eol=lf`) 필요 | D |
| 8 | **`REDEME.md`는 오타** (`README.md`가 맞다) | GitHub 첫 화면에 내용이 안 뜬다 | D |

**주의**: 6~8번은 레포 전체에 영향을 주는 공용 설정이라 **C가 임의로 고치면 안 된다.** PR 본문에 적어 D에게 넘긴다.

---

## 7. 완료된 작업 (단위 1~4)

`src/reporter.py` — 약 960줄. 구성:

| 구역 | 내용 |
|---|---|
| 표시 규칙 상수 | `SENTIMENT_ORDER/KO/COLOR/INK`, `SURFACE/INK/MUTED/GRID`, `RATING_RANGE` |
| `setup_korean_font()` | OS 감지 → 후보 폰트 실전 탐색 → 적용. 없으면 경고만 남기고 진행 |
| `chart_sentiment_distribution()` | 차트 ① 감정 분포 (가로 막대) |
| `chart_rating_sentiment()` | 차트 ② 별점별 감정 분포 (세로 누적 막대) |
| `chart_negative_trend()` | 차트 ④ 부정 비율 추이 (이동 평균, `window=10`) |
| `chart_length_by_sentiment()` | 차트 ⑤ 리뷰 길이 분포 (점 흩뿌리기 + 중앙값) |
| `calc_stats()` | 통계·품질 지표 3종 계산. 항상 딕셔너리 반환 |
| `_percent()` / `_pct_text()` | 비율 계산(분모 0이면 `None`) · 화면 표기(`None`→`—`) |
| `render_report()` | 리포트를 글자로 만든다. `style="text"` / `"markdown"` |
| `print_report()` | 콘솔 출력. cp949가 못 찍는 글자는 `?`로 바꿔서라도 출력 |
| `save_report()` | `output/report.txt` · `output/report.md` 저장, 경로 반환 |
| `_report_blocks()` | 리포트 **내용**만 블록 목록으로 만든다 (모양은 입히지 않음) |
| `_render_text()` / `_render_markdown()` | 블록 목록에 **모양**을 입힌다 |
| `_longest_negative_reviews()` | TOP N 집계 — 가장 긴 부정 리뷰 5건 |
| `_width()` / `_pad()` / `_bar()` / `_shorten()` | 한글 폭 계산 · 정렬 · 막대 · 말줄임 |
| `_load_demo_reviews()` | 단독 실행용. CSV 있으면 읽고, 없으면 내장 가짜 데이터 30건 |

모든 차트 함수는 **데이터가 비면 `None`을 반환하고 경고 로그만 남긴다.** 예외를 던져 프로그램을 죽이지 않는다.
**`calc_stats()`만 예외**로, 비어 있어도 항상 딕셔너리를 반환한다(리포트가 받아 쓰는 재료이기 때문. 설계메모 1-7).

`docs/reporter_설계메모.md` — 약 400줄. 설계 근거 + 코드 라인별 해설 + README 조각 + 팀 전달사항.

### 단독 실행 확인
```
python src/reporter.py
```
→ `output/` 폴더에 PNG 4개 + `report.txt` + `report.md` 생성. 리포트가 콘솔에도 출력된다.

### 검증 완료 사항
- Windows(`Malgun Gothic`)와 Linux(`Noto Sans CJK JP`) 양쪽에서 한글 깨짐 없이 동일하게 출력됨
- 중립 0건 상황에서도 멈추지 않고 "0건 (0.0%)"으로 정상 출력 (`counts.get(s, 0)` 안전장치 작동 확인)
- 단위 3 실행 결과(샘플 50건): 긍정 비율 48.0% / 평균 별점 2.92점 / 일치율 100.0%(판정 50건, 어긋남 0건)
  → 일치율 100%는 **임시 감정값이 별점에서 나왔기 때문에 당연한 결과**다. 코드가 맞는지는 이 숫자로 판단할 수 없다.
- 단위 4 검증: 빈 리뷰 목록 / `insights` 없음 / `insights` 있음 / 마크다운 표에 `|`가 섞인 리뷰 /
  잘못된 `style` 값 / cp949가 못 찍는 이모지 — 여섯 경우 모두 확인. 이모지는 화면만 `?`, 파일은 원본 유지.
- 한글(2칸)과 영문(1칸)이 섞인 표에서 열이 어긋나지 않는 것 확인 (`_width()` 작동)

### 실제로 얻은 발견
**부정 리뷰 중앙값 45자 vs 긍정 22자 — 부정 리뷰가 2배 길다.**
글자 수와 별점은 진짜 데이터이므로 이건 유효한 발견이다.
실무 함의: 리뷰를 다 못 읽을 때는 **긴 것부터 읽으면 불만을 먼저 잡을 수 있다.**

---

## 8. 다음에 할 일

**C 담당(stats · dashboard · export)의 필수 요건은 단위 1~4로 모두 채워졌다.**
남은 것은 D와의 연결, 그리고 B의 AI 분석이 붙은 뒤의 선택 작업이다.

### 8-1. D에게 넘길 연결 지점 (내가 하는 일 아님)

`main.py`에서 아래처럼 부르면 된다. reporter는 저장소도, AI도 직접 부르지 않는다.

```python
from src.reporter import (setup_korean_font, calc_stats, print_report, save_report,
                          chart_sentiment_distribution, chart_rating_sentiment,
                          chart_negative_trend, chart_length_by_sentiment)

setup_korean_font()                      # 프로그램 시작 시 한 번
reviews  = [dict(row) for row in query_reviews(conn)]   # A의 함수
insights = extract_insights([r["review_text"] for r in reviews])  # B의 함수

print_report(reviews, insights)          # stats / dashboard 서브커맨드
save_report(reviews, insights)           # export 서브커맨드
```

- `insights`를 안 넘겨도 리포트는 정상 생성된다(6~8번 구역만 안내문).
- `export` 서브커맨드가 CSV/JSON도 요구하면 그건 A의 저장소 쪽이 맞다. 확인 필요.

### 8-2. B의 감정 분석이 붙은 뒤 (선택)

- 차트 ③ 키워드 TOP N — `insights["positive_keywords"]` / `negative_keywords` 사용
- 차트 ⑥ 감정별 신뢰도 분포 — B의 `confidence` 값 사용
- **별점–감정 일치율이 처음으로 의미를 갖는 시점이다.** 지금은 임시 감정값이라 항상 100%다.
  실제 AI 결과에서 이 숫자가 몇 %로 나오는지가 이 프로젝트의 핵심 발견이 된다.

### 8-3. 단위 3~4에서 확정된 규칙 (앞으로도 지킬 것)

- **일치율은 중립을 판정에서 뺀다.** 비율만 쓰지 말고 `match.compared`(판정 건수)를 항상 함께 표시한다.
- **어긋남은 두 방향을 나눠 본다.** `high_rating_negative`는 *고객*을 보는 지표,
  `low_rating_positive`는 *AI 분석 품질*을 의심하는 지표다. 합쳐서 쓰지 않는다.
- **리포트에 새 항목을 넣을 때는 `_report_blocks()` 한 곳만 고친다.**
  `_render_text()` / `_render_markdown()`을 직접 손대면 TXT와 MD의 내용이 어긋난다.
- **리포트에 들어가는 글자에 이모지·em dash 같은 특수문자를 쓰지 않는다.** 윈도우 콘솔(cp949)에 없다.

---

## 9. 작업 시 주의사항

### Git
```
git checkout main && git pull && git checkout feat/reporter   # 작업 시작 전
git add src/reporter.py docs/                                  # 내 파일만
git commit -m "무엇을 왜 바꿨는지 한 줄"
git push
```
- **`naver_reviews_sample50.csv`는 커밋하지 않는다.** A의 브랜치에 이미 있어 중복된다. 테스트용으로만 둔다.
- **`output/` 폴더는 `.gitignore`에 있다.** 차트 PNG는 코드가 아니라 생성물이라 올리지 않는다.
- 손대지 않은 파일이 "수정됨"으로 뜨면 줄바꿈 형식 문제다(이슈 7번). `git restore <파일>`로 되돌리고 커밋하지 않는다.
- **PR은 만들지 않는다.** 의뢰인이 판단한다.

### 코드
- 새 차트를 추가할 때도 `SENTIMENT_*` 상수를 쓴다. 색·순서를 따로 정하지 않는다.
- 데이터가 비어 있을 가능성을 항상 처리한다(`return None` + `logger.warning`).
- 새 라이브러리는 설명 없이 추가하지 않는다. 현재 의존성은 `matplotlib`뿐이다.

### 인터뷰 대비
의뢰인이 답해야 할 4가지 중 C가 담당하는 것은 **"감정 분석 결과를 집계하고 matplotlib으로
다양한 차트를 생성하는 과정"**과 **"분석 결과를 비즈니스 관점에서 해석해 인사이트를 도출하는 방법"**이다.
코드를 추가할 때마다 **"왜 이렇게 동작하는지"**를 비개발자 언어로 설계메모에 남긴다.
