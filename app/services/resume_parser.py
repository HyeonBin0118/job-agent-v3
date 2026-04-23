import fitz
from dotenv import load_dotenv

load_dotenv()


def parse_resume(file_path: str) -> str:
    doc = fitz.open(file_path)
    text = ""
    for page in doc:
        text += page.get_text() # 각 페이지에서 텍스트만 추출(레이아웃 무시)
    doc.close()
    return text.strip()