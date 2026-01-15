import os
from smolagents import ToolCallingAgent, LiteLLMModel, tool
from patchpal.tools import read_file, list_files, apply_patch, run_shell


def _is_bedrock_arn(model_id: str) -> bool:
    """Check if a model ID is a Bedrock ARN."""
    return (
        model_id.startswith('arn:aws') and
        ':bedrock:' in model_id and
        ':inference-profile/' in model_id
    )


def _normalize_bedrock_model_id(model_id: str) -> str:
    """Normalize Bedrock model ID to ensure it has the bedrock/ prefix.

    Args:
        model_id: Model identifier, may or may not have bedrock/ prefix

    Returns:
        Model ID with bedrock/ prefix if it's a Bedrock model
    """
    # If it already has bedrock/ prefix, return as-is
    if model_id.startswith('bedrock/'):
        return model_id

    # If it looks like a Bedrock ARN, add the prefix
    if _is_bedrock_arn(model_id):
        return f'bedrock/{model_id}'

    # If it's a standard Bedrock model ID (e.g., anthropic.claude-v2)
    # Check if it looks like a Bedrock model format
    if '.' in model_id and any(provider in model_id for provider in ['anthropic', 'amazon', 'meta', 'cohere', 'ai21']):
        return f'bedrock/{model_id}'

    return model_id


def _setup_bedrock_env():
    """Set up Bedrock-specific environment variables for LiteLLM.

    Configures custom region and endpoint URL for AWS Bedrock (including GovCloud and VPC endpoints).
    Maps PatchPal's environment variables to LiteLLM's expected format.
    """
    # Set custom region (e.g., us-gov-east-1 for GovCloud)
    bedrock_region = os.getenv('AWS_BEDROCK_REGION')
    if bedrock_region and not os.getenv('AWS_REGION_NAME'):
        os.environ['AWS_REGION_NAME'] = bedrock_region

    # Set custom endpoint URL (e.g., VPC endpoint or GovCloud endpoint)
    bedrock_endpoint = os.getenv('AWS_BEDROCK_ENDPOINT')
    if bedrock_endpoint and not os.getenv('AWS_BEDROCK_RUNTIME_ENDPOINT'):
        os.environ['AWS_BEDROCK_RUNTIME_ENDPOINT'] = bedrock_endpoint


def create_agent(model_id="anthropic/claude-sonnet-4-5"):
    """Create and configure the PatchPal agent.

    Args:
        model_id: LiteLLM model identifier (default: anthropic/claude-sonnet-4-5)

                  For AWS Bedrock, you can use:
                    - Standard model ID: "anthropic.claude-sonnet-4-5-20250929-v1:0"
                    - With bedrock/ prefix: "bedrock/anthropic.claude-sonnet-4-5-20250929-v1:0"
                    - Full ARN (auto-detected): "arn:aws-us-gov:bedrock:us-gov-east-1:012345678901:inference-profile/..."

                  Note: bedrock/ prefix is automatically added for Bedrock ARNs and model IDs

                  Configure via environment variables:
                    - AWS_ACCESS_KEY_ID: AWS access key
                    - AWS_SECRET_ACCESS_KEY: AWS secret key
                    - AWS_BEDROCK_REGION: Custom region (e.g., us-gov-east-1)
                    - AWS_BEDROCK_ENDPOINT: Custom endpoint URL (e.g., VPC endpoint)
    """
    # Normalize model ID (auto-add bedrock/ prefix if needed)
    model_id = _normalize_bedrock_model_id(model_id)

    # Set up Bedrock environment if using Bedrock models
    if model_id.startswith('bedrock/'):
        _setup_bedrock_env()

    tools = [
        tool(read_file),
        tool(list_files),
        tool(apply_patch),
        tool(run_shell),
    ]

    # Configure model with Bedrock-specific settings if needed
    model_kwargs = {}
    if model_id.startswith('bedrock/'):
        # Enable drop_params for Bedrock to handle unsupported OpenAI params
        model_kwargs['drop_params'] = True

    model = LiteLLMModel(
        model_id=model_id,
        **model_kwargs,
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
