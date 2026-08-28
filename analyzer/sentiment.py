from typing import TypedDict, Literal
import os
import json
import logging
from urllib import response

from dotenv import load_dotenv
from openai import OpenAI


class SentimentResult(TypedDict):
    sentiment: Literal["positive", "negative", "neutral"]
    confidence: float


load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def analyze_sentiment(text: str) -> SentimentResult | None:
    prompt = f"""
다음 고객 리뷰의 감정을 분석하세요.

감정은 반드시 다음 세 가지 중 하나로 분류하세요.
- positive: 긍정
- negative: 부정
- neutral: 중립

confidence는 해당 감정 분류에 대한 신뢰도를
0.0 이상 1.0 이하의 숫자로 작성하세요.

고객 리뷰:
{text}

반드시 다음 JSON 형식으로만 답변하세요.
설명이나 다른 문장은 추가하지 마세요.

{{
    "sentiment": "positive",
    "confidence": 0.95
}}
"""

    try:
        response = client.responses.create(
            model="gpt-5.6-luna",
            input=prompt,
        )

        result = json.loads(response.output_text)

        sentiment = result["sentiment"]
        confidence = float(result["confidence"])

        if sentiment not in ("positive", "negative", "neutral"):
            raise ValueError(f"잘못된 감정 값: {sentiment}")

        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"신뢰도 범위 오류: {confidence}")

        return {
            "sentiment": sentiment,
            "confidence": confidence,
        }

    except Exception as e:
        logging.error("감정 분석 API 호출 실패: %s", e)
        return None
