import httpx
import re
from bs4 import BeautifulSoup

JOB_URL = "https://www.jobkorea.co.kr/Recruit/GI_Read/49008149"

NOISE_KEYWORDS = [
    "로그인", "회원가입", "추천 공고", "광고", "배너", "공고 더보기",
    "스크랩", "지원하기", "관심기업", "채용달력", "이전", "다음", "공유"
]


def crawl_v2(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    response = httpx.get(url, headers=headers, follow_redirects=True, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    lines = [line.strip() for line in soup.get_text(separator="\n").splitlines() if line.strip()]
    return "\n".join(lines)


def crawl_v3(url: str) -> str:
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


def analyze(text: str, label: str):
    lines = text.splitlines()
    total_chars = len(text)
    total_lines = len(lines)
    noise_count = sum(1 for line in lines if any(kw in line for kw in NOISE_KEYWORDS))
    noise_ratio = noise_count / total_lines * 100 if total_lines > 0 else 0

    print(f"\n--- {label} ---")
    print(f"총 문자 수:       {total_chars:,}")
    print(f"총 줄 수:         {total_lines}")
    print(f"노이즈 줄 수:     {noise_count}")
    print(f"노이즈 비율:      {noise_ratio:.1f}%")


if __name__ == "__main__":
    print("크롤링 중...")
    text_v2 = crawl_v2(JOB_URL)
    text_v3 = crawl_v3(JOB_URL)

    analyze(text_v2, "v2 전처리")
    analyze(text_v3, "v3 전처리")

    print(f"\n--- 비교 ---")
    print(f"문자 수 감소:     {len(text_v2) - len(text_v3):,}자 감소")
    print(f"줄 수 감소:       {len(text_v2.splitlines()) - len(text_v3.splitlines())}줄 감소")