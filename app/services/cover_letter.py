from openai import OpenAI
from dotenv import load_dotenv
import json

load_dotenv()

client = OpenAI()


def generate_cover_letter(resume_text: str, job_info: dict, match_result: dict) -> dict:
    prompt = f"""
아래는 지원자의 이력서, 채용공고 정보, 매칭 분석 결과야.
이 정보를 바탕으로 자기소개서 초안을 작성해줘.

항목:
1. 지원동기
2. 직무 관련 경험
3. 입사 후 포부

각 항목은 200자 내외로 작성하고 다음 JSON 형식으로 반환해줘.

{{
  "motivation": "지원동기 내용",
  "experience": "직무 관련 경험 내용",
  "goal": "입사 후 포부 내용"
}}

채용공고:
{json.dumps(job_info, ensure_ascii=False)}

매칭 분석:
{json.dumps(match_result, ensure_ascii=False)}

이력서:
{resume_text[:3000]}

JSON만 반환하고 다른 말은 하지 마.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7 # 매칭 분석은 일관성이 중요해서 0으로 설정, 자소서는 자연스러운 문장이 필요해서 0.7로 값 설정.
    )

    result = response.choices[0].message.content
    result = result.replace("```json", "").replace("```", "").strip()
    return json.loads(result)