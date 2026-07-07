"""
ContributionAgent — AI-driven mentorship and contribution discovery.

This agent consumes RepositoryContext, GitHubContext, and ArchitectureAnalysis,
and uses Gemini (via ADK + genai client) to propose structured, high-value
contribution tasks.

It uses a two-step generation flow:
1. Brainstorm a large candidate set of ideas across 15 categories.
2. Filter, rank, and format the best ~15 ideas (Beginner, Intermediate, Advanced)
   into a structured ContributionCandidateList, explicitly evaluating duplicate
   risks against existing issues and PRs.
"""

from __future__ import annotations

import sys
import os
from typing import Any

from google.adk import Agent
from google.genai import Client, types
from pydantic import ValidationError

from models.architecture_context import ArchitectureAnalysis
from models.contribution_context import ContributionCandidateList, ContributionRecommendation
from models.github_context import GitHubContext
from models.repository_context import RepositoryContext
from .retry import with_retry


class ContributionAgent:
    """
    ContributionAgent acts as the mentoring engine of RepoBuddy.

    Responsibilities:
    - Analyze repository code structure, GitHub activity, and architecture.
    - Evaluate opportunities across 15 standard categories.
    - Generate actionable, scored contribution tasks.
    - Provide customized learning paths and mentor advice.
    """

    def __init__(self, model_name: str | None = None) -> None:
        """
        Initializes the ContributionAgent and configures its underlying
        ADK Agent structure.
        """
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.client = Client()

        self.adk_agent = Agent(
            name="ContributionAgent",
            instruction=(
                "You are an empathetic, expert open-source mentor. Your goal is to guide developers "
                "by suggesting realistic, highly-structured contribution tasks. "
                "Always evaluate opportunities across these categories where applicable: "
                "Documentation, Testing, Bug Fixes, Refactoring, Performance, Security, "
                "Accessibility, Developer Experience, CI/CD, Code Quality, Features, "
                "Architecture, Dependencies, Examples/Tutorials, and DevOps.\n\n"
                "You must ensure each recommendation includes clear mentor advice, "
                "why the contribution matters, and the expected learning outcome. "
                "Learning paths should reference actual repository files. "
                "Estimate duplicate risk by carefully considering existing open issues, "
                "pull requests, and repository activity."
            ),
        )

    @with_retry()
    def identify_contributions(
        self,
        repo_ctx: RepositoryContext,
        github_ctx: GitHubContext,
        arch_analysis: ArchitectureAnalysis,
    ) -> list[ContributionRecommendation]:
        """
        Scans code features, architecture, and external GitHub telemetry to
        propose mentor-guided contribution ideas using a two-step LLM flow.

        Args:
            repo_ctx (RepositoryContext): Local analysis data.
            github_ctx (GitHubContext): GitHub API data.
            arch_analysis (ArchitectureAnalysis): Architectural insights.

        Returns:
            list[ContributionRecommendation]: Balanced list of ~15 scored contributions.
        """
        print(f"[ContributionAgent] Brainstorming contributions for {github_ctx.full_name}...", file=sys.stderr)

        prompt = self._build_contribution_prompt(repo_ctx, github_ctx, arch_analysis)

        # Step 1: Brainstorming (Text output)
        brainstorm_instruction = (
            str(self.adk_agent.instruction) + "\n\n"
            "STEP 1: BRAINSTORMING.\n"
            "Based on the provided repository context, generate a large, raw list of "
            "potential contribution ideas across all applicable categories. "
            "Do not restrict yourself to 15 items yet. Explore ideas for testing, refactoring, "
            "documentation, CI/CD, and features. Consider the current open issues and PRs "
            "to identify what is already being worked on (to avoid) and what is needed. "
            "Output this as a detailed brainstormed list."
        )

        brainstorm_response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=brainstorm_instruction,
                temperature=0.4,
            ),
        )
        candidates_text = brainstorm_response.text

        # Step 2: Filtering & Formatting (Structured JSON output)
        print("[ContributionAgent] Filtering and structuring recommendations...", file=sys.stderr)
        
        filter_instruction = (
            str(self.adk_agent.instruction) + "\n\n"
            "STEP 2: FILTERING, RANKING, AND FORMATTING.\n"
            "You have brainstormed a large set of candidate ideas. Now, you must filter, "
            "rank, and select the highest-quality, most balanced recommendations. "
            "Select approximately 15 recommendations total, aiming for a balance of "
            "Beginner, Intermediate, and Advanced difficulties.\n"
            "Remove redundant ideas and strictly evaluate 'duplicate_risk' by cross-referencing "
            "the selected ideas with the provided Open Issues and Pull Requests. If an idea "
            "is heavily discussed in an open issue, mark duplicate_risk as High.\n"
            "Return the final selected list matching the ContributionCandidateList schema."
        )

        final_prompt = (
            "Here is the context of the repository:\n\n" + prompt +
            "\n\nHere is your initial brainstormed list of ideas:\n" + (candidates_text or "") +
            "\n\nPlease select the best ~15 balanced recommendations and output them as JSON."
        )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=final_prompt,
            config=types.GenerateContentConfig(
                system_instruction=filter_instruction,
                response_mime_type="application/json",
                response_schema=ContributionCandidateList,
                temperature=0.2,
            ),
        )

        try:
            raw_text = response.text or "{}"
            candidate_list = ContributionCandidateList.model_validate_json(raw_text)
            print(f"[ContributionAgent] Successfully generated {len(candidate_list.recommendations)} recommendations.", file=sys.stderr)
            return candidate_list.recommendations
        except ValidationError as e:
            print(f"[ContributionAgent] Failed to parse structured output: {e}", file=sys.stderr)
            raise RuntimeError("Gemini returned invalid JSON for ContributionCandidateList.") from e

    def _build_contribution_prompt(
        self,
        repo_ctx: RepositoryContext,
        github_ctx: GitHubContext,
        arch_analysis: ArchitectureAnalysis,
    ) -> str:
        """
        Summarizes the relevant context into a prompt string for the LLM.
        """
        lines = [
            f"Repository: {github_ctx.full_name}",
            f"Description: {github_ctx.description or 'None'}",
            f"Primary Language: {repo_ctx.primary_language}",
            f"Architecture Style: {arch_analysis.architecture_style}",
            f"Primary Framework: {arch_analysis.primary_framework or 'None'}",
            "",
            "--- ARCHITECTURE SUMMARY ---",
            f"Testing Strategy: {arch_analysis.testing_strategy}",
            f"Maintainability: {arch_analysis.maintainability_notes}",
            f"Potential Improvements: {'; '.join(arch_analysis.potential_improvements)}",
            "",
            "--- GITHUB ACTIVITY ---",
            f"Health Level: {github_ctx.repository_health.level} (Score: {github_ctx.repository_health.score})",
            f"Commit Frequency: {github_ctx.repository_health.commit_frequency}",
            "",
            "--- OPEN ISSUES (Sample) ---",
        ]

        for issue in github_ctx.open_issues[:30]:
            lines.append(f"- Issue #{issue.number}: {issue.title} [Labels: {', '.join(issue.labels)}]")

        lines.extend(["", "--- OPEN PULL REQUESTS (Sample) ---"])
        for pr in github_ctx.open_pull_requests[:20]:
            lines.append(f"- PR #{pr.number}: {pr.title} [Labels: {', '.join(pr.labels)}]")

        lines.extend(["", "--- REPOSITORY TREE (Sample) ---"])
        for node in repo_ctx.repo_tree[:150]:
            lines.append(f"- {node.path}")

        return "\n".join(lines)
