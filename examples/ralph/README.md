# Ralph Wiggum Technique for PatchPal

> "I'm learnding!" - Ralph Wiggum

The **Ralph Wiggum technique** is an iterative AI development methodology where an agent repeatedly works on a task until completion. Named after The Simpsons character, it embodies the philosophy of persistent iteration despite setbacks.

---

⚠️ **SAFETY FIRST**: Ralph runs autonomously with permissions disabled. **Always use in sandboxed/isolated environments** (Docker containers, dedicated VMs, or test machines). See [Safety Considerations](#safety-considerations) before running.

---

## What is Ralph?

Ralph is fundamentally about **iteration over perfection**. Instead of trying to build everything perfectly in one shot, you let the agent try, fail, learn, and try again - automatically.

### Key Principles

1. **Iteration > Perfection**: Don't aim for perfect on first try. Let the loop refine the work.
2. **Failures Are Data**: Deterministically bad means failures are predictable and informative.
3. **Operator Skill Matters**: Success depends on writing good prompts, not just having a good model.
4. **Persistence Wins**: Keep trying until success. The loop handles retry logic automatically.

### The Core Mechanism: Stop Hook

The "stop hook" is what makes Ralph special:

```
1. Agent works on task
2. Agent tries to exit
3. Stop hook intercepts ← Key insight!
4. Same prompt fed back
5. Agent sees previous work in history
6. Agent adjusts approach
7. Repeat until completion promise found
```

The agent never actually "completes" until it outputs the completion promise. This forces it to review its own work, notice failures, and try different approaches.

## PatchPal Implementation

PatchPal's Python API enables **true Ralph** with a proper stop hook by leveraging the agent's conversation history.

After `pip install patchpal`, autopilot is immediately available:

```bash
# As a command
python -m patchpal autopilot \
  --prompt "Build a REST API with tests" \
  --completion-promise "COMPLETE" \
  --max-iterations 30

# As a Python library
from patchpal.autopilot import autopilot_loop

autopilot_loop(
    prompt="Build a REST API with tests",
    completion_promise="COMPLETE",
    max_iterations=30
)
```

The key mechanism: Check for completion, or feed prompt back:

```python
# The stop hook: Check for completion, or feed prompt back
for iteration in range(max_iterations):
    response = agent.run(prompt)  # Same prompt every time!

    if completion_promise in response:
        return response  # Done!

    # No completion - agent will see its previous work and try again
```

The agent's `messages` list preserves all previous work, so each iteration builds on the last.

## Quick Start

⚠️ **IMPORTANT**: Always run autopilot in isolated environments (Docker containers, VMs, throwaway projects). See [Safety Considerations](#safety-considerations) below for detailed guidance.

### Basic Usage

After `pip install patchpal`, autopilot is available immediately:

```bash
# Simple autopilot loop (recommended: use python -m)
python -m patchpal autopilot \
  --prompt "Build a REST API with tests" \
  --completion-promise "COMPLETE" \
  --max-iterations 30

# Alternative: Direct command
patchpal-autopilot \
  --prompt "Build a REST API with tests" \
  --completion-promise "COMPLETE" \
  --max-iterations 30

# Using a prompt file
python -m patchpal autopilot \
  --prompt-file prompts/todo_api.md \
  --completion-promise "COMPLETE" \
  --max-iterations 50

# With local model (zero API cost)
python -m patchpal autopilot \
  --model hosted_vllm/openai/gpt-oss-20b \
  --prompt-file prompts/fix_tests.md \
  --completion-promise "DONE"
```

### Multi-Phase Projects

For complex projects, break them into phases:

```bash
# Example: Builds a complete Todo API in 3 sequential phases
python multi_phase_todo_api_example.py
```

## Files in This Example

```
examples/ralph/
├── README.md                           # This file - comprehensive autopilot guide
├── simple_autopilot_example.py         # Simple example using autopilot as Python library
├── multi_phase_todo_api_example.py     # Multi-phase example (sequential phases)
└── prompts/                            # Example prompt templates
    ├── todo_api.md                     # Build a REST API
    ├── fix_tests.md                    # Fix failing tests
    └── refactor.md                     # Refactor code
```

Note: After `pip install patchpal`, autopilot is available as:
- `python -m patchpal autopilot` (recommended)
- `patchpal-autopilot` (direct command)
- `from patchpal.autopilot import autopilot_loop` (Python library)

## Writing Effective Ralph Prompts

Good prompts are critical to Ralph's success. Here's what works:

### ✅ Good Prompt Structure

```markdown
# Task: [Clear, specific goal]

## Requirements
- Specific requirement 1
- Specific requirement 2
- Measurable success criteria

## Process
1. Step-by-step instructions
2. How to verify each step
3. What to do if step fails
4. Run tests: run_shell("pytest -v")
5. Fix failures and retry

## Success Criteria
- All tests pass
- Coverage >80%
- No linter errors

## Escape Hatch
After N iterations if not complete:
- Document blocking issues
- List attempted approaches

When complete, output: <promise>COMPLETE</promise>
```

### ❌ Bad Prompts (Too Vague)

```markdown
Build a todo API and make it good.
```

### ✅ Good Prompts (Clear & Specific)

```markdown
Build a REST API for todos.

Requirements:
- Flask app with CRUD endpoints (GET, POST, PUT, DELETE)
- Input validation (title required, max 200 chars)
- Unit tests with pytest
- All tests passing (>80% coverage)
- README with API docs

Process:
1. Create app.py with routes
2. Write tests in test_app.py
3. Run tests: run_shell("pytest test_app.py -v")
4. If any fail, debug and fix
5. Repeat until all green

Output: <promise>COMPLETE</promise> when done.
```

### Key Elements

1. **Clear Completion Criteria**: What does "done" look like?
   - All tests passing
   - Specific coverage target
   - No linter errors
   - README complete

2. **Incremental Goals**: Break into phases
   - Phase 1: Core functionality
   - Phase 2: Error handling
   - Phase 3: Tests

3. **Self-Correction Pattern**: Built-in feedback loop
   - Write code
   - Run tests
   - If fail → debug and fix
   - Repeat until pass

4. **Escape Hatches**: Handle impossible tasks
   - After N iterations, document issues
   - List attempted approaches
   - Suggest alternatives

5. **Explicit Completion Promise**: Make it unmistakable
   - `<promise>COMPLETE</promise>`
   - `<promise>DONE</promise>`
   - Use a unique string that won't appear accidentally

## Safety Considerations

⚠️ **CRITICAL SECURITY WARNING**: Ralph disables PatchPal's permission system for autonomous operation (`PATCHPAL_REQUIRE_PERMISSION=false`). This means:

- **No permission prompts** - Agent can modify any file and run any shell command
- **No sandboxing** - Agent has full user account access
- **Autonomous execution** - Multiple iterations without human oversight
- **Potential for damage** - Mistakes can delete files, break systems, or corrupt data

### 🔒 Recommended: Run Ralph in Isolated Environments

**Option 1: Dedicated Sandboxed Machine (BEST)**
```bash
# Use a separate VM, EC2 instance, or physical machine
# - No access to production systems
# - No valuable data
# - Easy to wipe and recreate
# - Network-isolated if possible

ssh ralph-sandbox-machine
cd /workspace/throwaway-project
python ralph.py --prompt-file task.md --completion-promise "DONE"
```

**Option 2: Docker/Podman Container (GOOD)**

```bash
# Create a Dockerfile for autopilot environment
cat > Dockerfile.autopilot <<EOF
FROM python:3.11-slim
RUN pip install patchpal
WORKDIR /workspace
EOF

# Build container (use 'docker' or 'podman')
docker build -f Dockerfile.autopilot -t autopilot-env .

# Run autopilot in isolated container
docker run -it --rm \
  -v $(pwd):/workspace \
  --memory="2g" \
  --cpus="2" \
  --network=none \
  autopilot-env \
  python -m patchpal autopilot --prompt-file task.md --completion-promise "DONE"

# With network (if agent needs to install packages)
docker run -it --rm \
  -v $(pwd):/workspace \
  --memory="2g" \
  --cpus="2" \
  autopilot-env \
  python -m patchpal autopilot --prompt-file task.md --completion-promise "DONE"
```

**Option 3: Git Worktree Isolation (MINIMAL)**
```bash
# Creates isolated branch for autopilot experiments
git worktree add ../autopilot-sandbox -b autopilot-experiment
cd ../autopilot-sandbox

# Run autopilot in isolated branch
python -m patchpal autopilot --prompt-file task.md --completion-promise "DONE"

# Review changes
git diff main

# Merge if good, or delete if bad
cd ..
git worktree remove autopilot-sandbox --force
```

### Safety Best Practices

**1. Always Use Version Control**
```bash
# Commit before running autopilot
git add -A
git commit -m "Before autopilot: baseline"

# Run autopilot
python -m patchpal autopilot --prompt-file task.md --completion-promise "DONE"

# Review changes
git diff HEAD
git status

# Rollback if needed
git reset --hard HEAD
```

**2. Test with Read-Only Mode First**
```bash
# Test prompt safely without any file modifications
export PATCHPAL_READ_ONLY=true
python -m patchpal autopilot --prompt-file test.md --completion-promise "DONE" --max-iterations 5

# If behavior looks good, then run with write access
unset PATCHPAL_READ_ONLY
python -m patchpal autopilot --prompt-file test.md --completion-promise "DONE" --max-iterations 30
```

**3. Start with Low Max Iterations**
```bash
# Validate prompt behavior with limited iterations
python -m patchpal autopilot --prompt "..." --completion-promise "DONE" --max-iterations 5

# Gradually increase if working correctly: 10, 20, 50, etc.
python -m patchpal autopilot --prompt "..." --completion-promise "DONE" --max-iterations 20
```

**4. Add Explicit Constraints in Prompt**
```markdown
# In your PROMPT.md, add safety constraints:

## Safety Constraints
- ONLY modify files in src/ and tests/ directories
- DO NOT modify: package.json, Dockerfile, .env, config files
- DO NOT run: sudo, rm -rf, git push, curl to external APIs
- DO NOT install packages without explicit approval
- DO NOT access files outside project directory
- If you need to do any of the above, document why in BLOCKED.md and stop
```

**5. Monitor Ralph Activity**
```bash
# Watch file changes in another terminal
watch -n 2 'git status --short'

# Monitor system resources
htop  # or top

# Check Ralph output continuously
tail -f ralph_session.log
```

**6. Limit Resource Usage (Docker)**
```bash
# Prevent resource exhaustion
docker run -it --rm \
  -v $(pwd):/workspace \
  --memory="2g" \
  --cpus="2" \
  --pids-limit=100 \
  autopilot-env \
  python -m patchpal autopilot --prompt-file task.md --completion-promise "DONE"
```

**7. Use Audit Logs**
```bash
# PatchPal logs all operations to audit log
tail -f ~/.patchpal/<repo-name>/audit.log

# Review what Ralph did
cat ~/.patchpal/<repo-name>/audit.log | grep "USER_PROMPT\|TOOL_CALL"
```

### What Can Go Wrong Without Sandboxing?

**Ralph with disabled permissions can:**

- ❌ **Delete important files** - `rm -rf` mistakes, accidental overwrites
- ❌ **Corrupt configuration** - Break package.json, docker files, CI/CD configs
- ❌ **Push to remote** - `git push` broken code to production branches
- ❌ **Install malware** - `pip install` packages from untrusted sources
- ❌ **External API calls** - Leak data, make unauthorized requests
- ❌ **Resource exhaustion** - Infinite loops, memory leaks, fork bombs
- ❌ **Escape repository** - Modify files in parent directories or system files
- ❌ **Network attacks** - If compromised, could scan/attack other systems

**Ralph Does NOT Have:**
- ❌ Sandboxing (full user permissions)
- ❌ File access restrictions (can modify anything)
- ❌ Network restrictions (can make external requests)
- ❌ Command filtering (can run any shell command)
- ❌ Automatic rollback (no undo mechanism)
- ❌ Resource limits (unless using Docker)

### Safer Semi-Autonomous Alternative

If you can't use sandboxing, keep permissions enabled for critical operations:

```python
# safe_ralph.py - Semi-autonomous Ralph with permission prompts
def safe_ralph_loop(prompt: str, completion_promise: str, max_iterations: int = 100):
    """Ralph that still prompts for destructive operations."""
    # KEEP permissions enabled (do not disable)
    # Agent will ask before modifying files or running commands

    agent = create_agent()  # Permissions enabled by default

    for iteration in range(max_iterations):
        print(f"Iteration {iteration + 1}/{max_iterations}")
        response = agent.run(prompt)

        if completion_promise in response:
            return response

    return None
```

This trades full autonomy for safety - you'll need to approve operations, but catastrophic mistakes are prevented.

### Comparison: Ralph Safety Modes

| Mode | Safety | Autonomy | Use Case |
|------|--------|----------|----------|
| **Full Ralph (permissions off)** | ⚠️ Low | ✅ Full | Sandboxed environments only |
| **Safe Ralph (permissions on)** | ✅ High | ⚠️ Semi | Production repositories |
| **Read-only testing** | ✅ Very High | ❌ None | Prompt validation |
| **Docker container** | ✅ High | ✅ Full | Isolated projects |
| **Sandboxed machine** | ✅ Very High | ✅ Full | Long-running experiments |

## When to Use Ralph

### ✅ Safe Use Cases

- **Sandboxed/isolated environments** (dedicated VM, container, test machine)
- **Throwaway projects** you can recreate easily
- **Git repositories** with committed baseline (easy rollback)
- **Well-defined tasks** with clear success criteria
- **Iterative refinement** (getting tests to pass)
- **Greenfield projects** with no valuable data
- **Test environments** where mistakes are acceptable

### ❌ Unsafe Without Sandboxing

- **Production codebases** on your main development machine
- **Shared repositories** without isolation
- **Systems with valuable data** without backups
- **Critical infrastructure** files (configs, deployments)
- **Repositories with uncommitted work**
- **Production debugging** (use targeted debugging instead)
- **Overnight/weekend runs** on your daily-use laptop
- **Any environment you can't afford to lose**

### ✅ Overnight/Weekend Development - Done Safely

The articles mention running Ralph overnight while you sleep. **This should ONLY be done in isolated environments:**

```bash
# ✅ SAFE: Dedicated sandbox machine
ssh autopilot-sandbox
cd /workspace/experiment
nohup python -m patchpal autopilot --prompt-file task.md --completion-promise "DONE" --max-iterations 100 > autopilot.log 2>&1 &
# Leave running, check in the morning

# ✅ SAFE: Docker container on dedicated server
ssh autopilot-server
docker run -d --name autopilot-overnight \
  -v $(pwd):/workspace \
  --memory="4g" --cpus="4" \
  autopilot-env \
  python -m patchpal autopilot --prompt-file task.md --completion-promise "DONE" --max-iterations 100

# ❌ UNSAFE: Your daily laptop
# python -m patchpal autopilot --prompt-file task.md --completion-promise "DONE" --max-iterations 100 &
# (Agent could damage your system, corrupt data, or worse)
```

## Real-World Results

The Ralph technique has been used successfully for:

- **6 repos at Y Combinator hackathon** - Successfully generated 6 repositories overnight [[source](https://github.com/repomirrorhq/repomirror/blob/main/repomirror.md)]
- **$50k contract for $297 in API costs** - One contract worth $50k USD was completed, tested, and reviewed for just $297 in API costs [[source](https://ghuntley.com/ralph/)]
- **CURSED programming language** - Created an entire programming language over 3 months using this approach [[source](https://cursed-lang.org/)]
- **Test-driven development** - Excellent for TDD workflows where tests guide development [[source](https://mcpmarket.com/tools/skills/ralph-wiggum-autonomous-tdd-loop)]

## Advanced Patterns

### Parallel Ralph Loops (Git Worktrees)

Run multiple autopilot loops simultaneously on different branches:

```bash
# Create isolated worktrees
git worktree add ../project-auth -b feature/auth
git worktree add ../project-api -b feature/api

# Terminal 1: Auth feature
cd ../project-auth
python -m patchpal autopilot --prompt-file auth.md --completion-promise "AUTH_DONE"

# Terminal 2: API feature (simultaneously!)
cd ../project-api
python -m patchpal autopilot --prompt-file api.md --completion-promise "API_DONE"
```

### Overnight Batch Processing

Queue up work to run while you sleep:

```bash
#!/bin/bash
# overnight_autopilot.sh

cd /path/to/project1
python -m patchpal autopilot --prompt-file task1.md --completion-promise "DONE" --max-iterations 50

cd /path/to/project2
python -m patchpal autopilot --prompt-file task2.md --completion-promise "DONE" --max-iterations 50

# Run before bed
chmod +x overnight_autopilot.sh
./overnight_autopilot.sh > autopilot_session.log 2>&1
```

### Prompt Tuning Technique

Iteratively improve your prompts based on failures:

1. **Start with no guardrails**: Let Ralph build the playground first
2. **Add signs when Ralph fails**: When Ralph falls off the slide, add a sign saying "SLIDE DOWN, DON'T JUMP"
3. **Iterate on failures**: Each failure teaches you what guardrails to add
4. **Eventually get a new Ralph**: Once prompts are tuned, the defects disappear

Example evolution:

```markdown
# Version 1 (fails after 10 iterations)
Build a REST API.

# Version 2 (add tests requirement)
Build a REST API. Write tests. Run pytest.

# Version 3 (add explicit success criteria)
Build a REST API.
- Write tests in test_app.py
- Run: run_shell("pytest test_app.py -v")
- Fix failures until all pass
- Output: COMPLETE when pytest succeeds

# Version 4 (add escape hatch for infinite loops)
Build a REST API.
- Write tests in test_app.py
- Run: run_shell("pytest test_app.py -v")
- Fix failures until all pass
- If stuck after 10 iterations, document issue in BLOCKED.md
- Output: COMPLETE when pytest succeeds
```

## Cost Optimization

Autopilot can run for many iterations, so cost management matters:

### Use Local Models (Zero API Cost)

```bash
# vLLM (recommended)
export HOSTED_VLLM_API_BASE=http://localhost:8000
export HOSTED_VLLM_API_KEY=token-abc123
python -m patchpal autopilot --model hosted_vllm/openai/gpt-oss-20b \
  --prompt-file prompts/todo_api.md \
  --completion-promise "COMPLETE"
```

### Monitor Costs During Development

The autopilot mode shows cost tracking:

```
✅ COMPLETION DETECTED after 12 iterations!
Total LLM calls: 47
Total tokens: 156,234
Total cost: $2.34
```

### Tips for Cost Control

1. **Test with small max-iterations first** (e.g., 5-10) to validate your prompt
2. **Use cheaper models for simple tasks** (e.g., `claude-3-7-sonnet` instead of `claude-sonnet-4-5`)
3. **Break large tasks into phases** to avoid context explosion
4. **Use local models** (vLLM/Ollama) for development and iteration

## Comparison: Autopilot vs Other Approaches

| Approach | Stop Hook | History Preserved | Cost | Control | Best For |
|----------|-----------|-------------------|------|---------|----------|
| **PatchPal Autopilot (Python API)** | ✅ Yes | ✅ Full history | Track | ✅ Full | Iterative development |
| **Bash Loop (`while :; do`)** | ❌ No | ❌ Starts fresh | ? | Limited | Not recommended |
| **Claude Code Plugin** | ✅ Yes | ✅ Yes | ? | ❌ Opaque | Claude Code only |
| **Manual Iteration** | ❌ No | ❌ Lost | High | ✅ Full | One-shot tasks |

## Troubleshooting

### Autopilot Never Completes

**Problem**: Reaches max iterations without outputting completion promise.

**Solutions**:
1. Check if completion promise is too generic (might appear in logs/output accidentally)
2. Make success criteria more specific and achievable
3. Add intermediate checkpoints (Phase 1, Phase 2, etc.)
4. Review the agent's work - is it stuck on an impossible task?
5. Increase max iterations if it's making progress

### Autopilot Repeats The Same Mistake

**Problem**: Agent makes the same error every iteration.

**Solutions**:
1. Add explicit instructions about the failure pattern
2. Include self-correction steps in prompt: "If X fails, try Y instead"
3. Add escape hatch: "After 3 failures on same test, document issue and move on"
4. Refine prompt with more specific guidance
5. Consider if task is actually achievable

### Context Window Fills Up

**Problem**: Agent hits context limit mid-autopilot.

**Solutions**:
1. PatchPal has auto-compaction - should handle this automatically
2. Break task into smaller phases
3. Increase compaction threshold: `export PATCHPAL_COMPACT_THRESHOLD=0.60`
4. Use more aggressive pruning: `export PATCHPAL_PRUNE_PROTECT=20000`

### High API Costs

**Problem**: Autopilot uses too many tokens.

**Solutions**:
1. **Use local model** (vLLM) for zero API cost
2. Test with low max-iterations first (5-10)
3. Use cheaper models for validation
4. Break into phases to reduce iterations per task
5. Refine prompts to reduce trial-and-error

## Related Resources

- **Ralph Technique Explained**: [Ralph Wiggum as a "Software Engineer"](https://ghuntley.com/ralph/) - Geoffrey Huntley's comprehensive guide to the Ralph technique, philosophy, and real-world applications
- **Original Concept**: [A Brief History of Ralph](https://www.humanlayer.dev/blog/brief-history-of-ralph) - Comprehensive history and philosophy behind Ralph
- **Technique Guide**: [Ralph Wiggum - Awesome Claude](https://awesomeclaude.ai/ralph-wiggum) - Detailed guide with prompt templates and patterns
- **Creator's Blog**: [Geoffrey Huntley's Blog](https://github.com/ghuntley/ralph) - Original creator Geoff Huntley's Ralph resources
- **Video Tutorial**: [Matt Pocock's Ralph Overview](https://www.youtube.com/watch?v=_IK18goX4X8) - "Ship working code while you sleep" - practical walkthrough with bash scripts, PRDs, and TypeScript/tests
- **CURSED Language**: [cursed-lang.org](https://cursed-lang.org) - Programming language built with Ralph over 3 months
- **Deep Dive Podcast**: [AI That Works - Ralph Under the Hood](https://www.youtube.com/watch?v=fOPvAPdqgPo) - 75-minute discussion on context windows, control loops, and applications with Geoff Huntley
- **Curated Resources**: [Awesome Ralph](https://github.com/snwfdhmp/awesome-ralph) - Community-curated list of Ralph resources, tutorials, and examples

## Example Session Output

```bash
$ python -m patchpal autopilot --prompt-file prompts/todo_api.md --completion-promise "COMPLETE" --max-iterations 20

⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️
  PATCHPAL AUTOPILOT MODE - AUTONOMOUS OPERATION
⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️

Autopilot disables PatchPal's permission system for autonomous operation.

🔒 RECOMMENDED: Run in isolated environments only:
   • Docker/Podman containers (see Safety Considerations section below)
   • Dedicated VMs or test machines
   • Throwaway projects with version control

❌ DO NOT RUN on production systems or your main development machine.

This implements the 'Ralph Wiggum technique' - see examples/ralph/README.md

Continue with autopilot mode? (yes/no): yes

================================================================================
✈️  PatchPal Autopilot Mode Starting
================================================================================
Prompt: # Task: Build a Todo REST API...
Completion promise: 'COMPLETE'
Max iterations: 20
Model: anthropic/claude-sonnet-4-5
================================================================================

================================================================================
🔄 Autopilot Iteration 1/20
================================================================================

🤔 Thinking...
[Agent creates app.py and test_app.py]

================================================================================
📝 Agent Response:
================================================================================
I've created the Flask app and tests. Let me run them...
[Tests fail - 2 failures]

⚠️  No completion promise detected. Continuing...
   (Messages in history: 8)
   (Context usage: 12%)

================================================================================
🔄 Autopilot Iteration 2/20
================================================================================

🤔 Thinking...
[Agent fixes bugs based on test output]

================================================================================
📝 Agent Response:
================================================================================
Fixed the validation bug. Running tests again...
[Tests fail - 1 failure]

⚠️  No completion promise detected. Continuing...
   (Messages in history: 14)
   (Context usage: 18%)

================================================================================
🔄 Autopilot Iteration 3/20
================================================================================

🤔 Thinking...
[Agent fixes last bug]

================================================================================
📝 Agent Response:
================================================================================
All tests passing! Coverage: 87%. README created.

<promise>COMPLETE</promise>

================================================================================
✅ COMPLETION DETECTED after 3 iterations!
================================================================================
Agent found completion promise in response.
Total LLM calls: 12
Total tokens: 45,678
Total cost: $0.68

✅ Autopilot completed successfully!
```

## Contributing

Have improvements to the Ralph implementation or better prompt templates? PRs welcome!

## License

This example is part of PatchPal and follows the same license.
