from typing import TypedDict
import os
import json
import logging

from dotenv import load_dotenv
from google import genai


class ExtractionResult(TypedDict):
    positive_keywords: list[str]
    negative_keywords: list[str]
    summary: str
    improvements: list[str]

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def extract_insights(reviews: list[str]) -> ExtractionResult | None:
    if not reviews:
        logging.warning("분석할 리뷰가 없습니다.")
        return None

    review_text = "\n".join(
        f"{index + 1}. {review}"
        for index, review in enumerate(reviews)
    )

    prompt = f"""
다음은 고객 리뷰 목록입니다.
전체 리뷰를 종합하여 비즈니스 관점에서 분석하세요.

다음 항목을 반드시 추출하세요.

1. positive_keywords
- 고객이 긍정적으로 평가한 주요 키워드를 추출하세요.
- 최대 5개까지 작성하세요.

2. negative_keywords
- 고객의 불만이나 부정적인 평가와 관련된 주요 키워드를 추출하세요.
- 최대 5개까지 작성하세요.

3. summary
- 전체 리뷰의 주요 내용을 2~3문장으로 요약하세요.

4. improvements
- 리뷰를 바탕으로 제품 또는 서비스의 개선 제안을 작성하세요.
- 최대 3개까지 작성하세요.

반드시 다음 JSON 형식으로만 답변하세요.
설명이나 다른 문장은 추가하지 마세요.

{{
    "positive_keywords": ["키워드1", "키워드2"],
    "negative_keywords": ["키워드1", "키워드2"],
    "summary": "전체 리뷰 요약",
    "improvements": ["개선 제안1", "개선 제안2"]
}}

고객 리뷰:
{review_text}
"""

    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
        )

        result = json.loads(response.text)

    except Exception as e:
        logging.error("키워드/요약 분석 API 호출 실패: %s", e)
        return None

    required_keys = {
        "positive_keywords",
        "negative_keywords",
        "summary",
        "improvements",
    }

    if not required_keys.issubset(result):
        logging.error("키워드/요약 분석 결과에 필요한 항목이 없습니다.")
        return None

    return {
        "positive_keywords": result["positive_keywords"],
        "negative_keywords": result["negative_keywords"],
        "summary": result["summary"],
        "improvements": result["improvements"],
    }

