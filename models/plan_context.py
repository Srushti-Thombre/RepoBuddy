from __future__ import annotations
from pydantic import BaseModel, Field

class PlanRelevantFile(BaseModel):
    path: str = Field(..., description="Path to the file relative to repository root.")
    reason: str = Field(..., description="Why this file is relevant to the opportunity.")

class PlanStep(BaseModel):
    step_number: int = Field(..., description="Ordered step number starting from 1.")
    title: str = Field(..., description="A short, clear title for this implementation step.")
    description: str = Field(..., description="Clear instructions on what needs to be done.")
    files_to_modify: list[str] = Field(default_factory=list, description="File paths to modify in this step.")
    acceptance_criteria: str = Field(..., description="How to know this step is completed successfully.")

class PlanTestingGuidance(BaseModel):
    detected_framework: str = Field(..., description="e.g. 'pytest', 'jest', 'go test', 'unknown'")
    suggested_commands: list[str] = Field(..., description="Exact commands the user should run.")
    how_to_verify: str = Field(..., description="Short explanation of what success looks like.")
    common_failures: list[str] = Field(default_factory=list, description="Optional tips on common failures.")

class PlanGitPRGuidance(BaseModel):
    suggested_branch_name: str = Field(..., description="e.g. 'fix/add-validation-opp-3'")
    commit_message: str = Field(..., description="Conventional commit style preferred.")
    pr_title: str = Field(..., description="The title of the PR.")
    pr_body: str = Field(..., description="Markdown-ready PR description referencing the opportunity and plan.")
    commands: list[str] = Field(..., description="Step-by-step git / gh commands the user can copy.")

class ImplementationPlan(BaseModel):
    summary: str = Field(..., description="1-3 sentence overview of what needs to be done.")
    relevant_files: list[PlanRelevantFile] = Field(default_factory=list, description="List of all relevant files and reasons.")
    steps: list[PlanStep] = Field(default_factory=list, description="Ordered implementation steps.")
    estimated_time: str = Field(..., description="Estimated time (e.g. '1-2 hours').")
    potential_pitfalls: list[str] = Field(default_factory=list, description="Common mistakes or gotchas to avoid.")
    testing: PlanTestingGuidance = Field(..., description="Guidance on how to test the changes.")
    git_pr: PlanGitPRGuidance = Field(..., description="Guidance on committing, pushing, and creating a PR.")
