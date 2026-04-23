import json
import httpx
from bs4 import BeautifulSoup
from openai import OpenAI
import os
from dotenv import load_dotenv
import fitz

load_dotenv()
client = OpenAI()


def crawl_job_posting_v2(url: str) -> str:
    # v2 전처리 (광고 클래스 제거, 특수문자 정리 없음)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    response = httpx.get(url, headers=headers, follow_redirects=True, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    lines = [line.strip() for line in soup.get_text(separator="\n").splitlines() if line.strip()]
    return "\n".join(lines)


def extract_job_info(content: str) -> dict:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"""
아래 채용공고 텍스트에서 다음 항목을 JSON으로 추출해줘.
- company, position, required_skills, preferred_skills, experience, summary
텍스트: {content}
JSON만 반환해.
"""}],
        temperature=0
    )
    result = response.choices[0].message.content.replace("```json", "").replace("```", "").strip()
    return json.loads(result)


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


def run_evaluation(job_url: str, resume_path: str, n: int = 10):
    print(f"공고 크롤링 중...")
    job_content = crawl_job_posting_v2(job_url)
    job_info = extract_job_info(job_content)
    resume_text = parse_resume(resume_path)

    print(f"총 {n}회 매칭 테스트 시작...\n")
    scores = []
    for i in range(n):
        result = match_resume_to_job(resume_text, job_info)
        score = result.get("score", 0)
        scores.append(score)
        print(f"  {i+1}회: {score}점")

    print(f"\n--- 결과 ---")
    print(f"최소: {min(scores)}")
    print(f"최대: {max(scores)}")
    print(f"평균: {sum(scores)/len(scores):.1f}")
    print(f"편차: {max(scores) - min(scores)}")

    return scores


if __name__ == "__main__":
    JOB_URL = "https://www.jobkorea.co.kr/Recruit/GI_Read/49008149"
    RESUME_LOW = "TESTResume_50.pdf"
    RESUME_HIGH = "TESTResume_100.pdf"

    print("=== [v2 전처리] 낮은 적합도 이력서 (50점 예상)===")
    scores_low = run_evaluation(JOB_URL, RESUME_LOW, n=10)

    print("\n=== [v2 전처리] 높은 적합도 이력서 (100점 예상)===")
    scores_high = run_evaluation(JOB_URL, RESUME_HIGH, n=10)