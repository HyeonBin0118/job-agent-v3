import json
import httpx
import re
from bs4 import BeautifulSoup
from openai import OpenAI
import os
from dotenv import load_dotenv
import fitz

load_dotenv()
client = OpenAI()


def crawl_job_posting(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    response = httpx.get(url, headers=headers, follow_redirects=True, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe", "noscript"]):
        tag.decompose()
    for tag in soup.find_all(class_=re.compile(r"(ad|banner|menu|nav|popup|cookie|sns|share|recommend)", re.I)):
        tag.decompose()
    text = soup.get_text(separator="\n")
    text = re.sub(r"[^\w\s가-힣.,·\-/()%+]", " ", text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    seen = set()
    cleaned = []
    for line in lines:
        if line not in seen and len(line) > 1:
            seen.add(line)
            cleaned.append(line)
    return "\n".join(cleaned)


def parse_resume(path: str) -> str:
    doc = fitz.open(path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text.strip()


def match_resume_to_job(resume_text: str, job_info: dict) -> dict:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"""
이력서와 채용공고를 비교해서 JSON으로 반환해줘.
- matched_skills, missing_skills, score(0~100), summary
채용공고: {json.dumps(job_info, ensure_ascii=False)}
이력서: {resume_text[:3000]}
JSON만 반환해.
"""}],
        temperature=0
    )
    result = response.choices[0].message.content.replace("```json", "").replace("```", "").strip()
    return json.loads(result)


def generate_cover_letter_A(resume_text: str, job_info: dict, match_result: dict) -> dict:
    """프롬프트 A: 기본 프롬프트"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"""
이력서, 채용공고, 매칭 결과를 바탕으로 자소서 초안을 작성해줘.
항목: motivation(지원동기), experience(직무경험), goal(입사후포부)
각 항목 500자 내외로 작성해줘.
채용공고: {json.dumps(job_info, ensure_ascii=False)}
매칭결과: {json.dumps(match_result, ensure_ascii=False)}
이력서: {resume_text[:3000]}
JSON만 반환해.
"""}],
        temperature=0.7
    )
    result = response.choices[0].message.content.replace("```json", "").replace("```", "").strip()
    return json.loads(result)


def generate_cover_letter_B(resume_text: str, job_info: dict, match_result: dict) -> dict:
    """프롬프트 B: STAR 기법 적용"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"""
이력서, 채용공고, 매칭 결과를 바탕으로 자소서 초안을 STAR 기법으로 작성해줘.
STAR 기법: Situation(상황) - Task(과제) - Action(행동) - Result(결과) 구조로 작성.
항목: motivation(지원동기), experience(직무경험), goal(입사후포부)
각 항목 500자 내외로 작성하되, experience 항목은 반드시 STAR 구조를 따라줘.
채용공고: {json.dumps(job_info, ensure_ascii=False)}
매칭결과: {json.dumps(match_result, ensure_ascii=False)}
이력서: {resume_text[:3000]}
JSON만 반환해.
"""}],
        temperature=0.7
    )
    result = response.choices[0].message.content.replace("```json", "").replace("```", "").strip()
    return json.loads(result)


def evaluate_cover_letter(cover_letter: dict, job_info: dict) -> dict:
    """GPT로 자소서 품질 평가"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"""
아래 자소서를 채용공고 기준으로 평가해줘.
평가 항목:
- specificity: 구체성 (0~10) - 구체적인 경험/수치가 포함되어 있는가
- relevance: 직무 연관성 (0~10) - 공고 요구사항과 얼마나 관련있는가
- structure: 구조/논리성 (0~10) - 글의 흐름이 자연스럽고 논리적인가
- total: 총점 (0~30)
- feedback: 한 줄 피드백

채용공고: {json.dumps(job_info, ensure_ascii=False)}
자소서: {json.dumps(cover_letter, ensure_ascii=False)}
JSON만 반환해.
"""}],
        temperature=0
    )
    result = response.choices[0].message.content.replace("```json", "").replace("```", "").strip()
    return json.loads(result)


if __name__ == "__main__":
    JOB_URL = "https://www.wanted.co.kr/wd/353354"
    RESUME_HIGH = "TESTResume_100.pdf"

    print("공고 크롤링 중...")
    job_content = crawl_job_posting(JOB_URL)

    job_info_response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"""
아래 채용공고 텍스트에서 다음 항목을 JSON으로 추출해줘.
- company, position, required_skills, preferred_skills, experience, summary
불필요한 메뉴, 광고, 버튼 텍스트는 무시하고 실제 공고 내용만 분석해줘.
텍스트: {job_content}
JSON만 반환해.
"""}],
        temperature=0
    )
    job_info = json.loads(job_info_response.choices[0].message.content.replace("```json", "").replace("```", "").strip())
    resume_text = parse_resume(RESUME_HIGH)
    match_result = match_resume_to_job(resume_text, job_info)

    print("\n자소서 생성 중...")
    cover_A = generate_cover_letter_A(resume_text, job_info, match_result)
    cover_B = generate_cover_letter_B(resume_text, job_info, match_result)

    print("\n자소서 품질 평가 중...")
    eval_A = evaluate_cover_letter(cover_A, job_info)
    eval_B = evaluate_cover_letter(cover_B, job_info)

    print("\n=== 프롬프트 A (기본) ===")
    print(f"구체성:       {eval_A.get('specificity')}/10")
    print(f"직무 연관성:  {eval_A.get('relevance')}/10")
    print(f"구조/논리성:  {eval_A.get('structure')}/10")
    print(f"총점:         {eval_A.get('total')}/30")
    print(f"피드백:       {eval_A.get('feedback')}")

    print("\n=== 프롬프트 B (STAR 기법) ===")
    print(f"구체성:       {eval_B.get('specificity')}/10")
    print(f"직무 연관성:  {eval_B.get('relevance')}/10")
    print(f"구조/논리성:  {eval_B.get('structure')}/10")
    print(f"총점:         {eval_B.get('total')}/30")
    print(f"피드백:       {eval_B.get('feedback')}")

    print(f"\n=== 비교 결과 ===")
    print(f"총점 차이: B가 A보다 {eval_B.get('total', 0) - eval_A.get('total', 0)}점 높음")