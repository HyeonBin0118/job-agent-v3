from fastapi import FastAPI ## FastAPI 앱 객체 생성. 
from app.routers import analyze, resume,  job_agent

app = FastAPI(title="Job Agent")

app.include_router(analyze.router, prefix="/api")
app.include_router(resume.router, prefix="/api")
app.include_router(job_agent.router, prefix="/api")

@app.get("/") ##  서버 주소 들어갔을 때 잘 돌아가는지 화긴
def root():
    return {"status": "running"}