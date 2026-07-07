"""
ArchitectureAgent — AI-driven architectural analysis.

This agent consumes deterministic context (from RepositoryAgent and GitHubAgent)
and uses Gemini (via ADK + genai client) to generate a structured
``ArchitectureAnalysis`` model.
"""

from __future__ import annotations

import sys
import os
from typing import Any

from google.adk import Agent
from google.genai import Client, types
from pydantic import ValidationError

from models.architecture_context import ArchitectureAnalysis
from models.github_context import GitHubContext
from models.repository_context import RepositoryContext
from .retry import with_retry


class ArchitectureAgent:
    """
    ArchitectureAgent analyzes the structural architecture and frameworks
    of the repository.

    Responsibilities:
    - Identify code pattern styles (e.g., MVC, Clean Architecture, Monolith).
    - Classify major libraries and frameworks.
    - Outline component relationships and dependency hierarchies.
    - Produce a structured ArchitectureAnalysis model.
    """

    def __init__(self, model_name: str | None = None) -> None:
        """
        Initializes the ArchitectureAgent and configures its underlying
        ADK Agent structure.
        """
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.client = Client()

        # ADK Agent instantiated with clear instructions
        self.adk_agent = Agent(
            name="ArchitectureAgent",
            instruction=(
                "You are an expert software architect analyzing a codebase. "
                "Your goal is to review the provided repository metadata, file tree, "
                "and dependencies to identify major architecture styles (e.g., MVC, "
                "Monolith, Layered, SPA, Microservice), classify the primary frameworks, "
                "and map out the major logical components of the system.\n\n"
                "Provide detailed insights into the dependency management strategy, "
                "build process, testing strategy, and any deployment indicators "
                "(e.g., Docker, GitHub Actions).\n"
                "Finally, critique the architecture by outlining design patterns, "
                "strengths, potential improvements, and scalability/maintainability notes."
            ),
        )

    @with_retry()
    def classify_architecture(
        self, repo_ctx: RepositoryContext, github_ctx: GitHubContext
    ) -> ArchitectureAnalysis:
        """
        Synthesizes files, directories, and configuration settings to deduce
        structural patterns using an LLM.

        Args:
            repo_ctx (RepositoryContext): Deterministic repository metadata.
            github_ctx (GitHubContext): Deterministic GitHub metadata.

        Returns:
            ArchitectureAnalysis: Structured architectural insights.
        """
        print(f"[ArchitectureAgent] Analyzing architecture for {github_ctx.full_name}...", file=sys.stderr)

        prompt = self._build_architecture_prompt(repo_ctx, github_ctx)

        print("[ArchitectureAgent] Requesting structured generation from Gemini...", file=sys.stderr)
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=self.adk_agent.instruction,
                response_mime_type="application/json",
                response_schema=ArchitectureAnalysis,
                temperature=0.2,
            ),
        )

        try:
            raw_text = response.text or "{}"
            analysis = ArchitectureAnalysis.model_validate_json(raw_text)
            print("[ArchitectureAgent] Architecture analysis successfully generated.", file=sys.stderr)
            return analysis
        except ValidationError as e:
            print(f"[ArchitectureAgent] Failed to parse structured output: {e}", file=sys.stderr)
            raise RuntimeError("Gemini returned invalid JSON for ArchitectureAnalysis.") from e

    def _build_architecture_prompt(
        self, repo_ctx: RepositoryContext, github_ctx: GitHubContext
    ) -> str:
        """
        Summarizes the relevant context into a prompt string, avoiding massive
        JSON dumps to the LLM.
        """
        lines = [
            f"Repository: {github_ctx.full_name}",
            f"Description: {github_ctx.description or 'None'}",
            f"Primary Language: {repo_ctx.primary_language}",
            f"Detected Frameworks: {', '.join(repo_ctx.frameworks) or 'None'}",
            "",
            "--- PACKAGE MANAGERS ---",
        ]
        for pm in repo_ctx.package_managers:
            lines.append(f"- {pm.name} (config: {pm.config_file})")

        lines.extend(["", "--- BUILD SYSTEMS ---"])
        for bs in repo_ctx.build_systems:
            lines.append(f"- {bs.name} (config: {bs.config_file})")

        lines.extend(["", "--- ENTRY POINTS ---"])
        for ep in repo_ctx.entry_points:
            lines.append(f"- {ep.path} (type: {ep.entry_type})")

        lines.extend(["", "--- REPOSITORY TREE SUMMARY (max 200 nodes) ---"])
        for node in repo_ctx.repo_tree[:200]:
            lines.append(f"- {node.path} {'(DIR)' if node.node_type == 'directory' else ''}")

        lines.extend([
            "",
            "Please analyze the provided context and return a valid JSON object matching "
            "the required ArchitectureAnalysis schema.",
        ])

        return "\n".join(lines)
