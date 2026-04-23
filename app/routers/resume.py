import os
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.resume_parser import parse_resume
from app.services.matcher import match_resume_to_job
from app.services.analyzer import extract_job_info
from app.services.crawler import crawl_job_posting
from app.services.cover_letter import generate_cover_letter

router = APIRouter()


@router.post("/resume")
def upload_resume(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다")

    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        text = parse_resume(temp_path)
        return {"filename": file.filename, "content": text[:500], "status": "파싱 완료"}
    finally:
        os.remove(temp_path)


@router.post("/match")
def match_job(job_url: str, file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다")

    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        resume_text = parse_resume(temp_path)
        job_content = crawl_job_posting(job_url)
        job_info = extract_job_info(job_content)
        match_result = match_resume_to_job(resume_text, job_info)
        return {
            "job_info": job_info,
            "match_result": match_result,
            "status": "매칭 완료"
        }
    finally:
        os.remove(temp_path)


@router.post("/cover-letter")
def create_cover_letter(job_url: str, file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다")

    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        resume_text = parse_resume(temp_path)
        job_content = crawl_job_posting(job_url)
        job_info = extract_job_info(job_content)
        match_result = match_resume_to_job(resume_text, job_info)
        cover_letter = generate_cover_letter(resume_text, job_info, match_result)
        return {
            "job_info": job_info,
            "match_result": match_result,
            "cover_letter": cover_letter,
            "status": "자소서 생성 완료"
        }
    finally:
        os.remove(temp_path)