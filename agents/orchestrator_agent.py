"""
OrchestratorAgent — Coordinates the entire codebase analysis and mentoring workflow.
"""

from __future__ import annotations

import sys
import os
import tempfile
import shutil
import urllib.parse
from pathlib import Path

from google.adk import Agent

from .repository_agent import RepositoryAgent
from .architecture_agent import ArchitectureAgent
from .contribution_agent import ContributionAgent
from .github_agent import GitHubAgent
from .report_agent import ReportAgent
from mcp_server.tools_repository import clone_repository


class OrchestratorAgent:
    """
    OrchestratorAgent manages the sequential execution of all RepoBuddy agents.
    """

    def __init__(self, model_name: str | None = None) -> None:
        """
        Initializes the OrchestratorAgent and its sub-agents.
        """
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.repository_agent = RepositoryAgent()
        self.github_agent = GitHubAgent()
        self.architecture_agent = ArchitectureAgent(model_name=self.model_name)
        self.contribution_agent = ContributionAgent(model_name=self.model_name)
        self.report_agent = ReportAgent()

        self.adk_agent = Agent(
            name="OrchestratorAgent",
            instruction=(
                "You are the orchestrator that manages codebase mentoring. You coordinate "
                "sub-agents to perform local analysis, gather GitHub activity, synthesize "
                "architecture designs, score contribution guidelines, and compile markdown reports."
            ),
        )

    def run_mentorship_flow(self, repo_url: str, output_dir: str = "reports") -> dict[str, str]:
        """
        Runs the full analysis flow step-by-step.

        Args:
            repo_url (str): The URL of the public GitHub repository to analyze.
            output_dir (str): The output folder path for storing reports.

        Returns:
            dict: Path references to ProjectAnalysis.md and ContributionRoadmap.md.
        """
        print(f"\n[ORCHESTRATOR] Starting mentorship flow for: {repo_url}", file=sys.stderr)
        
        # Validate URL
        try:
            parsed = urllib.parse.urlparse(repo_url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError(f"Invalid URL format: {repo_url}")
        except Exception as e:
            print(f"[ORCHESTRATOR] URL Validation Error: {e}", file=sys.stderr)
            raise

        clone_dir = tempfile.mkdtemp(prefix="repobuddy_")
        print(f"[ORCHESTRATOR] Created temporary workspace: {clone_dir}", file=sys.stderr)

        try:
            # 1. Clone repository
            print("[ORCHESTRATOR] Step 1: Cloning repository...", file=sys.stderr)
            if not clone_repository(repo_url, clone_dir):
                raise RuntimeError(f"Failed to clone repository from {repo_url}")
                
            repo_ctx = self.repository_agent.analyze_repository(clone_dir)

            # 2. GitHub Intelligence
            print("[ORCHESTRATOR] Step 2: Fetching GitHub intelligence...", file=sys.stderr)
            github_ctx = self.github_agent.analyze_repository(repo_url)

            # 3. Architecture Reasoning
            print("[ORCHESTRATOR] Step 3: Performing architectural reasoning...", file=sys.stderr)
            arch_analysis = self.architecture_agent.classify_architecture(repo_ctx, github_ctx)

            # 4. Save Project Analysis immediately
            print("[ORCHESTRATOR] Step 4: Generating ProjectAnalysis.md...", file=sys.stderr)
            pa_path = self.report_agent.save_project_analysis(
                repo_ctx=repo_ctx,
                github_ctx=github_ctx,
                arch_analysis=arch_analysis,
                output_dir=output_dir
            )

            # 5. Contribution Reasoning (Fault-tolerant)
            print("[ORCHESTRATOR] Step 5: Discovering contribution opportunities...", file=sys.stderr)
            contributions = []
            try:
                contributions = self.contribution_agent.identify_contributions(repo_ctx, github_ctx, arch_analysis)
                
                # 6. Save Contribution Roadmap
                print("[ORCHESTRATOR] Step 6: Generating ContributionRoadmap.md...", file=sys.stderr)
                cr_path = self.report_agent.save_contribution_roadmap(
                    github_ctx=github_ctx,
                    contributions=contributions,
                    output_dir=output_dir
                )
            except Exception as contrib_err:
                print(f"[ORCHESTRATOR] Warning: Contribution discovery failed: {contrib_err}", file=sys.stderr)
                
                cr_path = self.report_agent.save_fallback_contribution_roadmap(
                    github_ctx=github_ctx,
                    output_dir=output_dir,
                    error_message="Contribution recommendations could not be generated because the Gemini model was temporarily unavailable or under high demand. The repository analysis completed successfully. Please retry the analysis later."
                )

            print("[ORCHESTRATOR] Mentorship flow completed.", file=sys.stderr)
            return {
                "project_analysis_path": pa_path,
                "contribution_roadmap_path": cr_path,
                "contributions": contributions,
            }

        except Exception as e:
            print(f"\n[ORCHESTRATOR] Flow failed: {e}", file=sys.stderr)
            raise

        finally:
            # Cleanup
            print(f"[ORCHESTRATOR] Cleaning up temporary workspace: {clone_dir}", file=sys.stderr)
            try:
                # Resolve permissions issues on Windows (readonly files in .git)
                def onerror(func, path, exc_info):
                    import stat, os
                    if not os.access(path, os.W_OK):
                        os.chmod(path, stat.S_IWUSR)
                        func(path)
                    else:
                        raise
                shutil.rmtree(clone_dir, onexc=onerror)
            except Exception as cleanup_err:
                print(f"[ORCHESTRATOR] Cleanup warning: {cleanup_err}", file=sys.stderr)
