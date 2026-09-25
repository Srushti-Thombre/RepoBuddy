import os
import sys
from google.genai import Client, types
from models.plan_context import ImplementationPlan
from agents.retry import with_retry
from pydantic import ValidationError

class PlanAgent:
    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.client = Client()

    @with_retry()
    def generate_plan(self, repo_url: str, opportunity: dict) -> dict:
        print(f"[PlanAgent] Generating plan for opportunity '{opportunity.get('title')}' in {repo_url}...", file=sys.stderr)
        
        system_instruction = (
            "You are an expert open-source maintainer and software engineer. "
            "Your task is to generate a concrete, actionable implementation plan "
            "for a given contribution opportunity. "
            "Ensure the plan is realistic, references actual file paths if provided, "
            "and warns of common pitfalls. "
            "Also include specific testing guidance (commands, framework) and git/PR workflow guidance "
            "(branch name, commit message, PR body, and git commands). "
            "Return the output exactly matching the ImplementationPlan JSON schema."
        )

        prompt_text = (
            f"Repository: {repo_url}\n\n"
            f"--- Opportunity ---\n"
            f"Title: {opportunity.get('title')}\n"
            f"Difficulty: {opportunity.get('difficulty')}\n"
            f"Category: {opportunity.get('category')}\n"
            f"Description: {opportunity.get('description')}\n"
            f"Learning Path:\n{opportunity.get('learning_path')}\n"
            f"Relevant Files: {', '.join(opportunity.get('relevant_files', []))}\n"
            f"Estimated Effort: {opportunity.get('estimated_effort')}\n\n"
            f"Please generate a detailed implementation plan."
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt_text,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=ImplementationPlan,
                    temperature=0.2,
                ),
            )
            raw_text = response.text or "{}"
            plan = ImplementationPlan.model_validate_json(raw_text)
            return plan.model_dump()
        except ValidationError as e:
            print(f"[PlanAgent] Failed to parse structured output: {e}", file=sys.stderr)
            raise RuntimeError("Gemini returned invalid JSON for ImplementationPlan.") from e
