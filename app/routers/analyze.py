from fastapi import APIRouter, HTTPException
from app.services.crawler import crawl_job_posting
from app.services.analyzer import extract_job_info

router = APIRouter()


@router.get("/analyze")
def analyze_job(url: str):
    try:
        content = crawl_job_posting(url)
        job_info = extract_job_info(content)
        return {
            "url": url,
            "job_info": job_info,
            "status": "분석 완료"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))