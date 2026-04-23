import streamlit as st
import httpx
from bs4 import BeautifulSoup
from openai import OpenAI
import fitz
import json
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    try:
        api_key = st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass
client = OpenAI(api_key=api_key)


def crawl_job_posting(url: str) -> str:
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
불필요한 메뉴, 광고, 버튼 텍스트는 무시하고 실제 공고 내용만 분석해줘.
텍스트: {content}
JSON만 반환해.
"""}],
        temperature=0
    )
    result = response.choices[0].message.content.replace("```json", "").replace("```", "").strip()
    return json.loads(result)


def parse_resume(file) -> str:
    doc = fitz.open(stream=file.read(), filetype="pdf")
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


def generate_cover_letter(resume_text: str, job_info: dict, match_result: dict, length: int, custom_format: str) -> dict:
    if custom_format:
        format_guide = f"""
아래 자소서 형식에 맞게 작성해줘. 각 항목명을 JSON 키로 그대로 사용해줘. 번호는 제거해줘.
예를 들어 "1. 성장과정"은 "성장과정", "2. 지원동기"는 "지원동기" 이런 식으로.
형식:
{custom_format}
"""
    else:
        format_guide = "항목: motivation(지원동기), experience(직무경험), goal(입사후포부)"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"""
이력서, 채용공고, 매칭 결과를 바탕으로 자소서 초안을 작성해줘.
{format_guide}
각 항목 {length}자 내외로 작성해줘.
채용공고: {json.dumps(job_info, ensure_ascii=False)}
매칭결과: {json.dumps(match_result, ensure_ascii=False)}
이력서: {resume_text[:3000]}
JSON만 반환해.
"""}],
        temperature=0.7
    )
    result = response.choices[0].message.content.replace("```json", "").replace("```", "").strip()
    return json.loads(result)


st.set_page_config(page_title="Job Agent v2", layout="wide")
st.title("🤖 Job Agent v2")
st.caption("채용공고 분석 · 이력서 매칭 · 자소서 생성 자동화")

with st.sidebar:
    st.header("📥 입력 정보")
    job_url = st.text_input("채용공고 URL")
    resume_file = st.file_uploader("이력서 PDF", type=["pdf"])

    st.divider()
    st.header("✍️ 자소서 설정")
    cover_length = st.slider("자소서 길이 (자)", min_value=200, max_value=1000, value=500, step=100)
    custom_format = st.text_area(
        "자소서 포맷 입력 (선택)",
        placeholder="예시:\n1. 지원동기\n2. 직무 관련 경험\n3. 성격 장단점\n4. 입사 후 포부",
        height=120
    )

    if st.button("분석 시작", type="primary"):
        if not job_url or not resume_file:
            st.warning("URL과 이력서를 모두 입력해주세요")
        else:
            with st.spinner("분석 중... (30초 정도 걸려요)"):
                try:
                    job_content = crawl_job_posting(job_url)
                    job_info = extract_job_info(job_content)
                    resume_text = parse_resume(resume_file)
                    match_result = match_resume_to_job(resume_text, job_info)
                    cover_letter = generate_cover_letter(
                        resume_text, job_info, match_result, cover_length, custom_format
                    )
                    st.session_state["result"] = {
                        "job_info": job_info,
                        "match_result": match_result,
                        "cover_letter": cover_letter,
                        "resume_text": resume_text
                    }
                    st.success("분석 완료")
                except Exception as e:
                    st.error(f"분석 실패: {e}")

result = st.session_state.get("result", None)
tab1, tab2, tab3, tab4 = st.tabs(["📋 공고 분석", "📊 이력서 매칭", "✍️ 자소서 생성", "💬 AI 상담"])

with tab1:
    st.subheader("채용공고 분석")
    if not result:
        st.info("사이드바에서 URL과 이력서를 입력하고 분석을 시작하세요.")
    else:
        data = result["job_info"]
        col1, col2 = st.columns(2)
        with col1:
            st.metric("회사", data.get("company", "-"))
            st.metric("직무", data.get("position", "-"))
            st.metric("경력", data.get("experience", "-"))
        with col2:
            st.write("**필수 스킬**")
            for skill in data.get("required_skills", []):
                st.badge(skill)
            st.write("**우대 스킬**")
            for skill in data.get("preferred_skills", []):
                st.badge(skill)
        st.info(data.get("summary", ""))

with tab2:
    st.subheader("이력서 매칭 분석")
    if not result:
        st.info("사이드바에서 URL과 이력서를 입력하고 분석을 시작하세요.")
    else:
        match = result["match_result"]
        st.metric("매칭 점수", f"{match.get('score', 0)} / 100")
        st.info(match.get("summary", ""))
        col1, col2 = st.columns(2)
        with col1:
            st.write("**✅ 보유 스킬**")
            for skill in match.get("matched_skills", []):
                st.badge(skill)
        with col2:
            st.write("**❌ 부족한 스킬**")
            for skill in match.get("missing_skills", []):
                st.badge(skill)

with tab3:
    st.subheader("자소서 초안")
    if not result:
        st.info("사이드바에서 URL과 이력서를 입력하고 분석을 시작하세요.")
    else:
        cover = result["cover_letter"]
        for key, value in cover.items():
            st.subheader(key)
            st.write(value)

with tab4:
    st.subheader("💬 결과 기반 AI 상담")
    if not result:
        st.info("먼저 사이드바에서 분석을 완료해주세요.")
    else:
        if "chat_history" not in st.session_state:
            st.session_state["chat_history"] = []

        for msg in st.session_state["chat_history"]:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        user_input = st.chat_input("분석 결과에 대해 질문하세요. 자소서 수정 요청도 가능합니다.")
        if user_input:
            st.session_state["chat_history"].append({"role": "user", "content": user_input})
            context = f"""
회사: {result['job_info'].get('company')}
직무: {result['job_info'].get('position')}
필수 스킬: {result['job_info'].get('required_skills')}
매칭 점수: {result['match_result'].get('score')}
부족한 스킬: {result['match_result'].get('missing_skills')}
현재 자소서:
- 지원동기: {result['cover_letter'].get('motivation')}
- 직무경험: {result['cover_letter'].get('experience')}
- 입사후포부: {result['cover_letter'].get('goal')}
"""
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": f"너는 취업 컨설턴트야. 아래 분석 결과와 자소서를 바탕으로 답변하고, 자소서 수정 요청이 오면 수정된 내용을 바로 제공해줘.\n{context}"},
                    *[{"role": m["role"], "content": m["content"]} for m in st.session_state["chat_history"]]
                ]
            )
            reply = response.choices[0].message.content
            st.session_state["chat_history"].append({"role": "assistant", "content": reply})
            st.rerun()