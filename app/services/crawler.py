import httpx
from bs4 import BeautifulSoup


def crawl_job_posting(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    # URL에 요청 보내서 HTML 가져옴
    response = httpx.get(url, headers=headers, follow_redirects=True, timeout=10) 
    soup = BeautifulSoup(response.text, "html.parser")
            #HTML에서 텍스트만 추출

    # 스크립트, 스타일 태그 제거
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    text = soup.get_text(separator="\n")

    # 빈 줄 제거
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)