"""
Report writing tools for MCP server. Used to export mentor results.
"""

def save_markdown(file_path: str, content: str) -> bool:
    """
    Saves generated markdown text cleanly to the filesystem.

    Args:
        file_path (str): Target output file path (e.g. reports/ProjectAnalysis.md).
        content (str): The raw markdown string to write.

    Returns:
        bool: True if writing succeeded, False otherwise.
    """
    import os
    print(f"[MCP TOOL] Saving markdown content to {file_path}...")
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"[MCP TOOL ERROR] Failed to save {file_path}: {e}")
        return False
