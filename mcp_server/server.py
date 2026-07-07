import sys
from mcp.server.fastmcp import FastMCP

from .tools_repository import (
    clone_repository,
    list_directory,
    read_file,
    detect_languages,
    search_files,
)
from .tools_github import (
    get_repository_metadata,
    get_open_issues,
    get_pull_requests,
    get_labels,
    get_recent_commits,
    get_contributors,
    get_repository_languages,
    get_repository_topics,
    get_repository_license,
    get_latest_release,
    get_default_branch,
)
from .tools_report import save_markdown

def create_server() -> FastMCP:
    """
    Creates and configures the RepoBuddy MCP server, registering all tool endpoints.
    """
    mcp = FastMCP("RepoBuddy MCP Server")

    # Register Repository & Filesystem tools
    mcp.tool()(clone_repository)
    mcp.tool()(list_directory)
    mcp.tool()(read_file)
    mcp.tool()(detect_languages)
    mcp.tool()(search_files)

    # Register GitHub integration tools
    mcp.tool()(get_repository_metadata)
    mcp.tool()(get_open_issues)
    mcp.tool()(get_pull_requests)
    mcp.tool()(get_labels)
    mcp.tool()(get_recent_commits)
    mcp.tool()(get_contributors)
    mcp.tool()(get_repository_languages)
    mcp.tool()(get_repository_topics)
    mcp.tool()(get_repository_license)
    mcp.tool()(get_latest_release)
    mcp.tool()(get_default_branch)

    # Register Report saving tools
    mcp.tool()(save_markdown)

    return mcp

if __name__ == "__main__":
    # Stdout should be reserved for JSON-RPC communications only.
    # All logging should go to stderr.
    print("Initializing RepoBuddy FastMCP Server...", file=sys.stderr)
    server = create_server()
    server.run(transport="stdio")
