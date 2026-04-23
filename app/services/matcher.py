from openai import OpenAI
from dotenv import load_dotenv
import json

load_dotenv()

client = OpenAI()


def match_resume_to_job(resume_text: str, job_info: dict) -> dict:
    prompt = f"""
아래는 지원자의 이력서와 채용공고 분석 결과야.
이력서를 채용공고와 비교해서 다음 항목을 JSON으로 반환해줘.

- matched_skills: 이력서에 있는 스킬 중 공고 요구사항과 일치하는 것
- missing_skills: 공고에서 요구하는데 이력서에 없는 스킬
- score: 매칭 점수 0~100
- summary: 한 줄 평가

채용공고:
{json.dumps(job_info, ensure_ascii=False)}

이력서:
{resume_text[:3000]}

JSON만 반환하고 다른 말은 하지 마.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    result = response.choices[0].message.content
    result = result.replace("```json", "").replace("```", "").strip()
    return json.loads(result)