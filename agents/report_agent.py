"""
ReportAgent — Formats deterministic and AI-reasoned context into professional markdown reports.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

from mcp_server.tools_report import save_markdown
from models.architecture_context import ArchitectureAnalysis
from models.contribution_context import ContributionRecommendation
from models.github_context import GitHubContext
from models.repository_context import RepositoryContext


class ReportAgent:
    """
    ReportAgent formats and builds polished, mentor-centric markdown reports.
    """

    def __init__(self) -> None:
        """
        Initializes the ReportAgent. (Formatting is deterministic, no LLM required).
        """
        pass

    def save_project_analysis(
        self,
        repo_ctx: RepositoryContext,
        github_ctx: GitHubContext,
        arch_analysis: ArchitectureAnalysis,
        output_dir: str,
    ) -> str:
        """Saves the ProjectAnalysis.md report."""
        print(f"[ReportAgent] Generating ProjectAnalysis in '{output_dir}'...", file=sys.stderr)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        text = self._build_project_analysis(repo_ctx, github_ctx, arch_analysis, now_str)
        pa_path = str(Path(output_dir) / "ProjectAnalysis.md")
        saved = save_markdown(pa_path, text)
        
        if not saved:
            print(f"[ReportAgent] Warning: Failed to save {pa_path}.", file=sys.stderr)
        
        return pa_path

    def save_contribution_roadmap(
        self,
        github_ctx: GitHubContext,
        contributions: list[ContributionRecommendation],
        output_dir: str,
    ) -> str:
        """Saves the ContributionRoadmap.md report."""
        print(f"[ReportAgent] Generating ContributionRoadmap in '{output_dir}'...", file=sys.stderr)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        text = self._build_contribution_roadmap(github_ctx, contributions, now_str)
        cr_path = str(Path(output_dir) / "ContributionRoadmap.md")
        saved = save_markdown(cr_path, text)
        
        if not saved:
            print(f"[ReportAgent] Warning: Failed to save {cr_path}.", file=sys.stderr)
            
        return cr_path

    def save_fallback_contribution_roadmap(
        self,
        github_ctx: GitHubContext,
        output_dir: str,
        error_message: str
    ) -> str:
        """Saves a partial fallback ContributionRoadmap.md if AI generation fails."""
        print(f"[ReportAgent] Generating Fallback ContributionRoadmap in '{output_dir}'...", file=sys.stderr)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        lines = [
            f"# Contribution Roadmap: {github_ctx.full_name}",
            "",
            f"**Generated:** {now_str}  ",
            f"**Repository:** [{github_ctx.full_name}](https://github.com/{github_ctx.full_name})",
            "",
            "> [!WARNING]",
            f"> {error_message}",
            "",
            "Please try running the orchestration flow again later."
        ]
        
        cr_path = str(Path(output_dir) / "ContributionRoadmap.md")
        saved = save_markdown(cr_path, "\n".join(lines))
        
        if not saved:
            print(f"[ReportAgent] Warning: Failed to save {cr_path}.", file=sys.stderr)
            
        return cr_path

    def _build_project_analysis(
        self,
        repo_ctx: RepositoryContext,
        github_ctx: GitHubContext,
        arch_analysis: ArchitectureAnalysis,
        timestamp: str,
    ) -> str:
        """Builds the ProjectAnalysis.md content."""
        lines = [
            f"# Project Analysis: {github_ctx.full_name}",
            "",
            f"**Generated:** {timestamp}  ",
            f"**Repository:** [{github_ctx.full_name}](https://github.com/{github_ctx.full_name})  ",
            f"**Stars:** {github_ctx.stars} | **Forks:** {github_ctx.forks} | **Open Issues:** {github_ctx.open_issue_count} | **License:** {github_ctx.license or 'None'}  ",
            "",
            "## Table of Contents",
            "- [Repository Overview](#repository-overview)",
            "- [Technologies](#technologies)",
            "- [Architecture](#architecture)",
            "- [Components](#components)",
            "- [Build Process](#build-process)",
            "- [Testing](#testing)",
            "- [Strengths](#strengths)",
            "- [Potential Improvements](#potential-improvements)",
            "",
            "---",
            "",
            "## Repository Overview",
            "",
            f"{github_ctx.description or 'No description provided.'}",
            "",
            "**Repository Health**:",
            f"- **Level**: {github_ctx.repository_health.level} (Score: {github_ctx.repository_health.score}/100)",
            f"- **Commit Frequency**: {github_ctx.repository_health.commit_frequency}",
            f"- **Maintainer Responsiveness**: {github_ctx.repository_health.maintainer_responsiveness or 'Unknown'}",
            "",
            "---",
            "",
            "## Technologies",
            "",
            f"- **Primary Language:** {repo_ctx.primary_language}",
            f"- **All Languages:** {', '.join(repo_ctx.languages) or 'None'}",
            f"- **Package Managers:** {', '.join(pm.name for pm in repo_ctx.package_managers) or 'None'}",
            f"- **Detected Frameworks (Local):** {', '.join(repo_ctx.frameworks) or 'None'}",
            "",
            "---",
            "",
            "## Architecture",
            "",
            f"- **Project Type:** {arch_analysis.project_type}",
            f"- **Architecture Style:** {arch_analysis.architecture_style}",
            f"- **Primary Framework:** {arch_analysis.primary_framework or 'None'}",
            f"- **Backend Framework:** {arch_analysis.backend_framework or 'None'}",
            f"- **Frontend Framework:** {arch_analysis.frontend_framework or 'None'}",
            "",
            "**Design Patterns Detected**:",
            "\n".join(f"- {pattern}" for pattern in arch_analysis.design_patterns) if arch_analysis.design_patterns else "None",
            "",
            "---",
            "",
            "## Components",
            "",
        ]

        if arch_analysis.major_components:
            for comp in arch_analysis.major_components:
                lines.append(f"### {comp.name}")
                lines.append(f"{comp.description}")
                if comp.key_files:
                    lines.append("\n**Key Files**:")
                    for kf in comp.key_files:
                        lines.append(f"- `{kf}`")
                lines.append("")
        else:
            lines.append("No major components identified.")

        lines.extend([
            "---",
            "",
            "## Build Process",
            "",
            f"{arch_analysis.build_process}",
            "",
            "**Deployment Indicators**:",
            f"{arch_analysis.deployment_indicators}",
            "",
            "---",
            "",
            "## Testing",
            "",
            f"{arch_analysis.testing_strategy}",
            "",
            "---",
            "",
            "## Strengths",
            "",
            "\n".join(f"- {s}" for s in arch_analysis.strengths) if arch_analysis.strengths else "None",
            "",
            "---",
            "",
            "## Potential Improvements",
            "",
            "\n".join(f"- {pi}" for pi in arch_analysis.potential_improvements) if arch_analysis.potential_improvements else "None",
            "",
            "**Scalability Notes**:  ",
            f"{arch_analysis.scalability_notes}",
            "",
            "**Maintainability Notes**:  ",
            f"{arch_analysis.maintainability_notes}",
            "",
        ])

        return "\n".join(lines)

    def _build_contribution_roadmap(
        self,
        github_ctx: GitHubContext,
        contributions: list[ContributionRecommendation],
        timestamp: str,
    ) -> str:
        """Builds the ContributionRoadmap.md content."""
        grouped_contributions: dict[str, list[ContributionRecommendation]] = defaultdict(list)
        for rec in contributions:
            grouped_contributions[rec.difficulty].append(rec)

        lines = [
            f"# Contribution Roadmap: {github_ctx.full_name}",
            "",
            f"**Generated:** {timestamp}  ",
            f"**Repository:** [{github_ctx.full_name}](https://github.com/{github_ctx.full_name})",
            "",
            "This roadmap outlines high-value contribution opportunities tailored to the project's current architecture and GitHub activity.",
            "",
        ]

        for difficulty in ["Beginner", "Intermediate", "Advanced"]:
            recs = grouped_contributions.get(difficulty, [])
            if not recs:
                continue

            lines.extend([
                "---",
                "",
                f"## {difficulty} Contributions",
                "",
            ])

            for rec in recs:
                lines.extend([
                    f"### {rec.title}",
                    "",
                    f"**Category:** {rec.category} | **Tags:** {', '.join(rec.tags) or 'None'}",
                    "",
                    f"{rec.description}",
                    "",
                    "| Metric | Value |",
                    "|---|---|",
                    f"| **Estimated Time** | {rec.estimated_time} |",
                    f"| **Impact** | {rec.impact} |",
                    f"| **Confidence** | {rec.confidence:.2f} |",
                    f"| **Duplicate Risk** | {rec.duplicate_risk} |",
                    "",
                    "**Duplicate Risk Reasoning:**",
                    f"{rec.duplicate_risk_reasoning}",
                    "",
                    "**Suggested Files:**",
                    "\n".join(f"- `{f}`" for f in rec.suggested_files) if rec.suggested_files else "None",
                    "",
                    "**Why this matters:**",
                    f"{rec.why_this_matters}",
                    "",
                    "**Expected learning outcome:**",
                    f"{rec.expected_learning_outcome}",
                    "",
                    "#### Learning Path",
                    f"*(Estimated learning time: {rec.learning_path.estimated_learning_time})*",
                    "",
                ])
                
                for step in rec.learning_path.steps:
                    lines.append(f"1. {step.instruction}")
                
                lines.extend([
                    "",
                    "#### Mentor Advice",
                    "",
                    "\n".join(f"- {a}" for a in rec.mentor_advice) if rec.mentor_advice else "None",
                    "",
                ])

        return "\n".join(lines)
