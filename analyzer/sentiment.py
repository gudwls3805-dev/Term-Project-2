from typing import TypedDict, Literal

import os

from dotenv import load_dotenv
from google import genai


class SentimentResult(TypedDict):
    sentiment: Literal["positive", "negative", "neutral"]
    confidence: float


load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def analyze_sentiment(text: str) -> SentimentResult:
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

다음 형식으로만 답변하세요.
sentiment: positive
confidence: 0.95
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt,
    )

    print(response.text)

if __name__ == "__main__":
    analyze_sentiment("배송이 빠르고 제품 품질도 정말 좋아요.")