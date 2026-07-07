"""
Domain models for RepoBuddy.

This package contains Pydantic v2 models representing structured analysis
outputs. Any agent or tool can import from here without coupling to the
analysis implementation details.
"""

from .repository_context import (
    BuildSystemInfo,
    ComplexityLevel,
    ComplexityMetrics,
    DocumentationInfo,
    EntryPoint,
    LanguageStat,
    PackageManagerInfo,
    RepositoryContext,
    TreeNode,
)
from .github_context import (
    CommitRecord,
    ContributorRecord,
    GitHubContext,
    HealthLevel,
    IssueRecord,
    LabelRecord,
    PullRequestRecord,
    ReleaseRecord,
    RepositoryHealth,
)
from .architecture_context import (
    ArchitectureAnalysis,
    ComponentDescription,
)
from .contribution_context import (
    ContributionCandidateList,
    ContributionRecommendation,
    DifficultyLevel,
    ImpactLevel,
    LearningPath,
    LearningStep,
    RiskLevel,
)

__all__ = [
    # RepositoryContext models
    "BuildSystemInfo",
    "ComplexityLevel",
    "ComplexityMetrics",
    "DocumentationInfo",
    "EntryPoint",
    "LanguageStat",
    "PackageManagerInfo",
    "RepositoryContext",
    "TreeNode",
    # GitHubContext models
    "CommitRecord",
    "ContributorRecord",
    "GitHubContext",
    "HealthLevel",
    "IssueRecord",
    "LabelRecord",
    "PullRequestRecord",
    "ReleaseRecord",
    "RepositoryHealth",
    # ArchitectureContext models
    "ArchitectureAnalysis",
    "ComponentDescription",
    # ContributionContext models
    "ContributionCandidateList",
    "ContributionRecommendation",
    "DifficultyLevel",
    "ImpactLevel",
    "LearningPath",
    "LearningStep",
    "RiskLevel",
]
