import os
import sys
import traceback
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Ensure local project modules can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents import OrchestratorAgent

# Load environment variables
load_dotenv()

app = FastAPI(
    title="RepoBuddy API",
    description="Backend HTTP API server for RepoBuddy Open Source Mentor Agent",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    repo_url: str

@app.get("/api/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "message": "RepoBuddy API server is running"}

@app.post("/api/analyze")
def analyze_repository(request: AnalyzeRequest):
    """
    Triggers the OrchestratorAgent mentorship flow for the given repository URL,
    and returns the contents of ProjectAnalysis.md and ContributionRoadmap.md.
    """
    repo_url = request.repo_url.strip()
    if not repo_url:
        raise HTTPException(status_code=400, detail="Repository URL cannot be empty.")
    
    if not repo_url.startswith("http://") and not repo_url.startswith("https://"):
        raise HTTPException(status_code=400, detail="Invalid URL format. Please provide a valid GitHub URL (e.g. https://github.com/owner/repo).")

    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY is missing from environment variables (.env)."
        )

    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
    os.makedirs(output_dir, exist_ok=True)

    try:
        orchestrator = OrchestratorAgent()
        results = orchestrator.run_mentorship_flow(repo_url=repo_url, output_dir=output_dir)

        pa_path = results.get("project_analysis_path")
        cr_path = results.get("contribution_roadmap_path")

        project_analysis_content = ""
        contribution_roadmap_content = ""

        if pa_path and os.path.exists(pa_path):
            with open(pa_path, "r", encoding="utf-8") as f:
                project_analysis_content = f.read()

        if cr_path and os.path.exists(cr_path):
            with open(cr_path, "r", encoding="utf-8") as f:
                contribution_roadmap_content = f.read()

        return {
            "status": "success",
            "repo_url": repo_url,
            "project_analysis": project_analysis_content,
            "contribution_roadmap": contribution_roadmap_content
        }

    except Exception as e:
        error_msg = str(e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Mentorship analysis failed: {error_msg}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
