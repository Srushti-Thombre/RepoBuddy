import os
import sys
import traceback
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Ensure local project modules can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents import OrchestratorAgent, PlanAgent, ChatAgent

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

class PlanRequest(BaseModel):
    repo_url: str
    opportunity: dict

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    repo_url: str
    opportunity: dict
    plan: dict | None = None
    messages: list[ChatMessage] = []
    new_message: str


def _contributions_to_opportunities(contributions) -> list[dict]:
    """
    Converts a list of ContributionRecommendation Pydantic objects into
    simplified opportunity dicts for the frontend.
    """
    opportunities = []
    for idx, rec in enumerate(contributions, start=1):
        # Flatten learning path steps into a readable string
        learning_steps = []
        if hasattr(rec, 'learning_path') and rec.learning_path:
            for step in rec.learning_path.steps:
                learning_steps.append(step.instruction)
            if rec.learning_path.estimated_learning_time:
                learning_steps.append(f"Estimated learning time: {rec.learning_path.estimated_learning_time}")

        opportunities.append({
            "id": f"opp-{idx}",
            "title": rec.title,
            "category": rec.category,
            "difficulty": rec.difficulty,
            "description": rec.description,
            "learning_path": "\n".join(learning_steps) if learning_steps else "",
            "relevant_files": rec.suggested_files if rec.suggested_files else [],
            "estimated_effort": rec.estimated_time if hasattr(rec, 'estimated_time') else "",
        })
    return opportunities


@app.get("/api/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "message": "RepoBuddy API server is running"}

@app.post("/api/analyze")
def analyze_repository(request: AnalyzeRequest):
    """
    Triggers the OrchestratorAgent mentorship flow for the given repository URL,
    and returns the contents of ProjectAnalysis.md, ContributionRoadmap.md,
    and a structured opportunities array.
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
        contributions = results.get("contributions", [])

        project_analysis_content = ""
        contribution_roadmap_content = ""

        if pa_path and os.path.exists(pa_path):
            with open(pa_path, "r", encoding="utf-8") as f:
                project_analysis_content = f.read()

        if cr_path and os.path.exists(cr_path):
            with open(cr_path, "r", encoding="utf-8") as f:
                contribution_roadmap_content = f.read()

        opportunities = _contributions_to_opportunities(contributions)

        return {
            "status": "success",
            "repo_url": repo_url,
            "project_analysis": project_analysis_content,
            "contribution_roadmap": contribution_roadmap_content,
            "opportunities": opportunities
        }

    except Exception as e:
        error_msg = str(e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Mentorship analysis failed: {error_msg}")

@app.post("/api/plan")
def generate_plan(request: PlanRequest):
    """
    Generates a concrete implementation plan for a selected opportunity.
    """
    repo_url = request.repo_url.strip()
    if not repo_url:
        raise HTTPException(status_code=400, detail="Repository URL cannot be empty.")
    if not request.opportunity:
        raise HTTPException(status_code=400, detail="Opportunity data cannot be empty.")
        
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY is missing from environment variables (.env)."
        )

    try:
        plan_agent = PlanAgent()
        plan = plan_agent.generate_plan(repo_url=repo_url, opportunity=request.opportunity)
        return {
            "status": "success",
            "plan": plan
        }
    except Exception as e:
        error_msg = str(e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Plan generation failed: {error_msg}")

@app.post("/api/chat")
def chat_with_mentor(request: ChatRequest):
    """
    Continues a mentoring conversation about a specific opportunity.
    """
    repo_url = request.repo_url.strip()
    if not repo_url:
        raise HTTPException(status_code=400, detail="Repository URL cannot be empty.")
    if not request.opportunity:
        raise HTTPException(status_code=400, detail="Opportunity data cannot be empty.")
    if not request.new_message.strip():
        raise HTTPException(status_code=400, detail="New message cannot be empty.")

    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY is missing from environment variables (.env)."
        )

    try:
        chat_agent = ChatAgent()
        messages_dict = [{"role": msg.role, "content": msg.content} for msg in request.messages]
        reply = chat_agent.chat(
            repo_url=repo_url,
            opportunity=request.opportunity,
            plan=request.plan,
            messages=messages_dict,
            new_message=request.new_message.strip()
        )
        return {
            "status": "success",
            "reply": reply
        }
    except Exception as e:
        error_msg = str(e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Chat failed: {error_msg}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)

