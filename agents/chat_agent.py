import os
import sys
import json
from google.genai import Client, types
from agents.retry import with_retry

class ChatAgent:
    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.client = Client()

    @with_retry()
    def chat(self, repo_url: str, opportunity: dict, plan: dict | None, messages: list[dict], new_message: str) -> str:
        print(f"[ChatAgent] Handling chat for '{opportunity.get('title')}'...", file=sys.stderr)
        
        system_instruction = (
            "You are an expert, empathetic open-source mentor. "
            "Your goal is to guide a developer working on a specific contribution opportunity. "
            "You have context on the repository, the opportunity details, and the generated implementation plan. "
            "Answer their questions practically, referencing the plan steps or codebase where appropriate. "
            "Be encouraging but concise."
        )

        plan_context = json.dumps(plan, indent=2) if plan else "Plan generation failed or not available yet."
        opp_context = json.dumps(opportunity, indent=2)
        
        context_msg = (
            f"--- MENTORSHIP CONTEXT ---\n"
            f"Repository: {repo_url}\n"
            f"Opportunity Details:\n{opp_context}\n\n"
            f"Implementation Plan:\n{plan_context}\n"
            f"---------------------------\n"
            f"The developer is asking a question about the above context. "
            f"Please answer their questions based on this."
        )

        # Build Gemini history
        history = [
            types.Content(role="user", parts=[types.Part.from_text(text=context_msg)]),
            types.Content(role="model", parts=[types.Part.from_text(text="I understand the context. I'm ready to help!")])
        ]
        
        for msg in messages:
            # gemini roles are 'user' and 'model'
            role = "user" if msg["role"] == "user" else "model"
            history.append(types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])]))
            
        history.append(types.Content(role="user", parts=[types.Part.from_text(text=new_message)]))

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=history,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.4,
            ),
        )
        return response.text
