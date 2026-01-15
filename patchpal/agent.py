import os
from smolagents import ToolCallingAgent, LiteLLMModel, tool
from patchpal.tools import read_file, list_files, apply_patch, run_shell


def create_agent(model_id="anthropic/claude-sonnet-4-5"):
    """Create and configure the PatchPal agent.

    Args:
        model_id: LiteLLM model identifier (default: anthropic/claude-sonnet-4-5)
    """
    tools = [
        tool(read_file),
        tool(list_files),
        tool(apply_patch),
        tool(run_shell),
    ]

    model = LiteLLMModel(
        model_id=model_id,
    )

    agent = ToolCallingAgent(
        model=model,
        tools=tools,
        instructions="""You are a senior software engineer working inside a repository.

Available tools:
- read_file: Read the contents of any file
- list_files: List all files in the repository
- apply_patch: Modify a file by providing the complete new content
- run_shell: Run safe shell commands (no rm, mv, sudo, etc.)

Instructions:
1. Start by listing or reading files to understand the codebase
2. Make minimal, focused changes to accomplish the task
3. Use apply_patch to update files with the complete new content
4. Test your changes if appropriate using run_shell
5. Explain what you're doing at each step

Stop when the task is complete.""",
    )

    return agent
