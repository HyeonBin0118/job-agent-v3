from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
client = OpenAI()

# 크롤링한 텍스트를 GPT한테 넘겨서 필요한 정보만 뽑아내는 함수
def extract_job_info(content: str) -> dict:
    prompt = f"""
아래는 채용공고 페이지에서 추출한 텍스트야.
다음 항목을 JSON 형식으로 추출해줘.

- company: 회사명
- position: 직무명
- required_skills: 필수 스킬 리스트
- preferred_skills: 우대 스킬 리스트
- experience: 경력 요건
- summary: 공고 한 줄 요약

텍스트:
{content}

JSON만 반환하고 다른 말은 하지 마.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0 # 일관된 답변을 위해 0으로 설정
    )

    import json
    result = response.choices[0].message.content
    result = result.replace("```json", "").replace("```", "").strip()
    return json.loads(result) # JSON 앞뒤에 마크다운 코드블록을 붙여서 반환하는 경우를 방지