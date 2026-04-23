import shutil
import os
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.resume_parser import parse_resume
from app.agent.graph import build_graph

router = APIRouter()


@router.post("/agent/run")
def run_agent(job_url: str, file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다")

    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        resume_text = parse_resume(temp_path)
        graph = build_graph()
        result = graph.invoke({
            "job_url": job_url,
            "resume_text": resume_text,
            "job_content": "",
            "job_info": {},
            "match_result": {},
            "cover_letter": {}
        })
        return {
            "job_info": result["job_info"],
            "match_result": result["match_result"],
            "cover_letter": result["cover_letter"],
            "status": "Agent 실행 완료"
        }
    finally:
        os.remove(temp_path)