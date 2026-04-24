import streamlit as st
import httpx
from bs4 import BeautifulSoup
from openai import OpenAI
import fitz
import json
import os
from dotenv import load_dotenv
import re

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    try:
        api_key = st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass
client = OpenAI(api_key=api_key)



"""
    채용공고 URL에서 텍스트를 추출하고
    광고/배너 클래스 제거, 특수문자 정리, 중복 줄 제거를 통해
    GPT에 넘기는 입력 텍스트 품질을 높인다.
    """
def crawl_job_posting(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    response = httpx.get(url, headers=headers, follow_redirects=True, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")

    # 불필요한 태그 제거 
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe", "noscript"]):
        tag.decompose()

    # 노이즈 제거를 위한 전처리 
    for tag in soup.find_all(class_=re.compile(r"(ad|banner|menu|nav|popup|cookie|sns|share|recommend)", re.I)):
        tag.decompose()

    text = soup.get_text(separator="\n")

    # 특수문자 정리
    text = re.sub(r"[^\w\s가-힣.,·\-/()%+]", " ", text)

    # 반복 공백 및 빈 줄 제거
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # 중복 줄 제거
    seen = set()
    cleaned = []
    for line in lines:
        if line not in seen and len(line) > 1:
            seen.add(line)
            cleaned.append(line)

    return "\n".join(cleaned)


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

def evaluate_cover_letter(cover_letter: dict, job_info: dict) -> dict:
    """
    생성된 자소서를 GPT로 자동 평가하고,
    구체성, 직무 연관성, 구조/논리성 세 가지 지표로 점수를 산출한다.
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"""
아래 자소서를 채용공고 기준으로 평가해줘.
평가 항목:
- specificity: 구체성 (0~10)
- relevance: 직무 연관성 (0~10)
- structure: 구조/논리성 (0~10)
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


st.set_page_config(page_title="Job Agent v3", layout="wide")
st.title("🤖 Job Agent v3")
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

def generate_interview_questions(resume_text: str, job_info: dict, match_result: dict) -> list:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"""
아래 정보를 바탕으로 면접 예상 질문 8개와 각 모범 답안을 생성해줘.
질문 구성:
- 보유 스킬 기반 심화 질문 3개 (실제로 어떻게 활용했는지 검증하는 질문)
- 부족 스킬 관련 질문 2개 (약점을 어떻게 극복할지 묻는 질문)
- 직무/회사 관련 질문 2개 (지원동기, 커리어 방향 등)
- 인성/경험 질문 1개

각 항목은 아래 JSON 배열 형태로 반환해줘:
[
  {{
    "category": "보유 스킬",
    "question": "질문 내용",
    "answer": "모범 답안 (200자 내외)",
    "tip": "답변 시 주의할 점 한 줄",
    "difficulty": 3
    "specificity": 3               
  }},
  ...
]

difficulty 기준:
1 = 매우 쉬움 (단순 지식 확인)
2 = 쉬움 (기본 개념 이해)
3 = 보통 (적용 경험 필요)
4 = 어려움 (심화 이해 및 트레이드오프 판단)
5 = 매우 어려움 (설계/아키텍처 수준)
                   
specificity 기준:
1 = 매우 추상적 (경험 없어도 답변 가능)
2 = 추상적
3 = 보통
4 = 구체적 (프로젝트/수치 언급 필요)
5 = 매우 구체적 (상세 설계/트레이드오프 설명 필요)

채용공고: {json.dumps(job_info, ensure_ascii=False)}
보유 스킬: {match_result.get("matched_skills", [])}
부족 스킬: {match_result.get("missing_skills", [])}
이력서: {resume_text[:2000]}
JSON 배열만 반환해.
"""}],
        temperature=0.7
    )
    content = response.choices[0].message.content
    content = content.replace("```json", "").replace("```", "").strip()
    return json.loads(content)


def score_specificity(question: str, resume_text: str) -> int:
    """
    질문 텍스트와 이력서를 비교해서
    이력서 기반 구체적 키워드(기술명, 수치, 프로젝트명)가
    질문에 얼마나 반영됐는지로 구체성을 측정한다.
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"""
아래 면접 질문이 이력서의 구체적인 내용(기술명, 프로젝트명, 수치, 경험)을 얼마나 반영하고 있는지 점수를 매겨줘.

채점 기준:
1 = 이력서와 무관한 일반적 질문 (예: "팀워크 경험이 있나요?")
2 = 직무 관련이지만 이력서 내용 미반영
3 = 이력서 기술 스택 언급은 있으나 구체적 경험 미반영
4 = 이력서의 특정 프로젝트나 기술을 구체적으로 언급
5 = 이력서의 수치/성과/설계까지 구체적으로 파고드는 질문

이력서: {resume_text[:1500]}
질문: {question}

숫자 하나만 반환해. 다른 텍스트 없이.
"""}],
        temperature=0
    )
    try:
        return int(response.choices[0].message.content.strip())
    except:
        return 3

result = st.session_state.get("result", None)
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📋 공고 분석", "📊 이력서 매칭", "✍️ 자소서 생성", "💬 AI 상담", "🔀 공고 비교", "🎯 면접 준비"])
with tab1:#📋 공고 분석
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

with tab2: # 📊 이력서 매칭
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
        key_labels = {
            "motivation": "지원동기",
            "experience": "직무 관련 경험",
            "goal": "입사 후 포부"
        }
        for key, value in cover.items():
            st.subheader(key_labels.get(key, key))
            st.write(value)

        st.divider()
        st.subheader("📊 자소서 품질 자동 평가")
        if st.button("품질 평가 시작"):
            with st.spinner("평가 중..."):
                try:
                    eval_result = evaluate_cover_letter(cover, result["job_info"])
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("구체성", f"{eval_result.get('specificity')}/10")
                    with col2:
                        st.metric("직무 연관성", f"{eval_result.get('relevance')}/10")
                    with col3:
                        st.metric("구조/논리성", f"{eval_result.get('structure')}/10")
                    with col4:
                        st.metric("총점", f"{eval_result.get('total')}/30")
                    st.info(f"💬 {eval_result.get('feedback')}")
                except Exception as e:
                    st.error(f"평가 실패: {e}")

with tab4:#💬 AI 상담
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


with tab5:# 🔀 공고 비교
    st.subheader("🔀 다중 공고 비교")
    st.caption("여러 공고를 동시에 분석해서 이력서와 가장 잘 맞는 공고를 찾아줍니다.")

    if not result:
        st.info("먼저 사이드바에서 이력서를 업로드하고 분석을 완료해주세요.")
    else:
        st.write("**추가 채용공고 URL 입력 (최대 3개)**")
        url1 = st.text_input("공고 URL 1", key="compare_url1")
        url2 = st.text_input("공고 URL 2", key="compare_url2")
        url3 = st.text_input("공고 URL 3", key="compare_url3")

        if st.button("공고 비교 시작", type="primary"):
            urls = [u for u in [url1, url2, url3] if u.strip()]
            if not urls:
                st.warning("URL을 최소 1개 입력해주세요.")
            else:
                resume_text = result["resume_text"]
                compare_results = []

                with st.spinner(f"총 {len(urls)}개 공고 분석 중..."):
                    for i, url in enumerate(urls):
                        try:
                            job_content = crawl_job_posting(url)
                            job_info = extract_job_info(job_content)
                            match = match_resume_to_job(resume_text, job_info)
                            compare_results.append({
                                "url": url,
                                "company": job_info.get("company", "-"),
                                "position": job_info.get("position", "-"),
                                "score": match.get("score", 0),
                                "matched": match.get("matched_skills", []),
                                "missing": match.get("missing_skills", [])
                            })
                        except Exception as e:
                            st.error(f"URL {i+1} 분석 실패: {e}")

                if compare_results:
                    compare_results.sort(key=lambda x: x["score"], reverse=True)
                    st.subheader("📊 비교 결과")
                    for idx, r in enumerate(compare_results):
                        medal = ["🥇", "🥈", "🥉"][idx] if idx < 3 else "  "
                        with st.expander(f"{medal} {r['company']} — {r['position']} ({r['score']}점)", expanded=idx==0):
                            st.metric("매칭 점수", f"{r['score']} / 100")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write("**✅ 보유 스킬**")
                                for skill in r["matched"]:
                                    st.badge(skill)
                            with col2:
                                st.write("**❌ 부족한 스킬**")
                                for skill in r["missing"]:
                                    st.badge(skill)

with tab6:  # 🎯 면접 준비
    st.subheader("🎯 면접 예상 질문 & 모범 답안")
    if not result:
        st.info("사이드바에서 URL과 이력서를 입력하고 분석을 완료해주세요.")
    else:
        category_colors = {
            "보유 스킬": "🟢",
            "부족 스킬": "🔴",
            "직무/회사": "🔵",
            "인성/경험": "🟡"
        }
        st.caption("🟢 보유 스킬  🔴 부족 스킬  🔵 직무/회사  🟡 인성/경험")
        if st.button("면접 질문 생성", type="primary"):
            with st.spinner("면접 질문 생성 중..."):
                try:
                    questions = generate_interview_questions(
                        result["resume_text"],
                        result["job_info"],
                        result["match_result"]
                    )
                    st.session_state["interview_questions"] = questions
                except Exception as e:
                    st.error(f"생성 실패: {e}")

        questions = st.session_state.get("interview_questions", [])
        if questions:
            for i, q in enumerate(questions):
                category = q.get("category", "기타")
                icon = category_colors.get(category, "⚪")
                with st.expander(f"{icon} Q{i+1}. {q.get('question')}", expanded=i == 0):
                    st.caption(f"카테고리: {category}")
                    st.write("**📝 모범 답안**")
                    st.write(q.get("answer", ""))
                    st.info(f"💡 {q.get('tip', '')}")

            st.divider()
            st.subheader("📐 가설 검증: 보유/부족 스킬별 난이도 적절성")

            보유 = [q for q in questions if q.get("category") == "보유 스킬"]
            부족 = [q for q in questions if q.get("category") == "부족 스킬"]

            if 보유 and 부족:
                avg_보유 = sum(q.get("difficulty", 3) for q in 보유) / len(보유)
                avg_부족 = sum(q.get("difficulty", 3) for q in 부족) / len(부족)

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("🟢 보유 스킬 평균 난이도", f"{avg_보유:.1f} / 5")
                with col2:
                    st.metric("🔴 부족 스킬 평균 난이도", f"{avg_부족:.1f} / 5")

                if avg_보유 > avg_부족:
                    st.success("✅ 가설 1 검증: 보유 스킬 질문이 더 높은 난이도로 생성됨 (심화 검증 경향)")
                elif avg_보유 < avg_부족:
                    st.warning("⚠️ 가설 1 반증: 부족 스킬 질문 난이도가 더 높게 나타남")
                else:
                    st.info("➖ 가설 1 중립: 보유/부족 스킬 난이도 차이 없음")
            else:
                st.info("보유 스킬 또는 부족 스킬 질문이 충분하지 않습니다.")

            st.divider()
            st.subheader("📐 가설 검증 2: 이력서 품질별 질문 구체성 비교")
        

            if st.button("구체성 측정 시작"):
                with st.spinner("질문 구체성 분석 중..."):
                    scores = []
                    for q in questions:
                        s = score_specificity(q.get("question", ""), result["resume_text"])
                        scores.append(s)
                    st.session_state["specificity_scores"] = scores

            scores = st.session_state.get("specificity_scores", [])
            if scores:
                avg_specificity = sum(scores) / len(scores)
                match_score = result["match_result"].get("score", 0)

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("현재 이력서 매칭 점수", f"{match_score} / 100")
                with col2:
                    st.metric("질문 평균 구체성", f"{avg_specificity:.1f} / 5")

                st.write("**질문별 구체성 점수**")
                for i, (q, s) in enumerate(zip(questions, scores)):
                    bar = "🟦" * s + "⬜" * (5 - s)
                    st.caption(f"Q{i+1}. {q.get('question', '')[:40]}...  {bar} ({s}/5)")

                if match_score >= 70:
                    st.success("✅ 고득점 이력서 기반 — 구체성 점수 확인")
                else:
                    st.warning("⚠️ 저득점 이력서 기반 — 구체성 점수 확인")