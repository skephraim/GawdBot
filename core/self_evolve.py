"""
Self-evolution — GawdBot improves its own source code.

Workflow:
1. Create a git branch
2. Run the agent with access to all tools + its own source
3. Agent reads CLAUDE.md, reads relevant files, makes changes, commits
4. Either auto-merge or push + create a PR for human review
"""

from __future__ import annotations
import json

import config
from core import llm, memory
from core.agent import TOOLS, _execute_tool
from tools import git_tools

EVOLVE_SYSTEM_PROMPT = """You are GawdBot performing a self-improvement cycle.

You have been given a specific improvement request. Your job:
1. Read CLAUDE.md first to understand the architecture
2. Read the source files relevant to the improvement
3. Make minimal, targeted changes using write_file
4. Test if possible with run_command (e.g., python -m py_compile <file>)
5. Commit changes to the current branch (already created for you)
6. Return a clear summary: what you changed, why, and what the expected improvement is

Rules:
- Only change what's needed for the improvement. Don't refactor unrelated code.
- Never modify .env or .git
- Commit to the current branch only — never checkout main
- If something is unclear, make your best decision and note it in the summary
"""


async def propose_improvement(request: str, interface: str = "chat") -> str:
    """
    Run a self-improvement cycle for the given request.
    Returns a status message to send back to the user.
    """
    if not config.SELF_EVOLVE_ENABLED:
        return "Self-evolution is disabled. Set SELF_EVOLVE_ENABLED=true in .env to enable."

    # Create evolve branch
    branch = git_tools.generate_evolve_branch()
    branch_result = git_tools.create_branch(branch)
    print(f"[Self-evolve] {branch_result}")

    messages = [
        {"role": "system", "content": EVOLVE_SYSTEM_PROMPT},
        {"role": "user", "content": f"Improvement request: {request}"},
    ]

    summary = "Self-improvement cycle completed."
    for _ in range(20):
        msg = await llm.chat(messages, tools=TOOLS)

        if not msg.tool_calls:
            summary = msg.content or summary
            break

        messages.append(msg)

        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            result = await _execute_tool(tc.function.name, args, interface)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })
    else:
        summary = "Reached iteration limit during self-improvement."

    await memory.save_memory(
        f"Self-improvement: {request}\nSummary: {summary}",
        category="self-improvement",
        source="self_evolve",
    )

    if config.SELF_EVOLVE_AUTO_MERGE:
        merge = git_tools.merge_to_main(branch)
        return f"Self-improvement auto-merged to main.\n\n{summary}\n\nMerge: {merge}"

    push = git_tools.push(branch)

    if config.GITHUB_REPO and config.GITHUB_TOKEN:
        pr = await git_tools.create_pr(
            title=f"[GawdBot] Self-improvement: {request[:60]}",
            body=f"## What changed\n\n{summary}\n\n## Request\n\n{request}",
            head=branch,
            base="main",
        )
        return f"Self-improvement complete. Review before merging.\n\n{summary}\n\n{pr}"

    return (
        f"Self-improvement complete on branch `{branch}`.\n"
        f"Review with `git diff main..{branch}` then merge manually.\n\n"
        f"{summary}"
    )
