
# Autopilot Mode

**Autopilot mode** enables autonomous iterative development where the agent repeatedly works on a task until completion. Based on the ["Ralph Wiggum technique"](https://ghuntley.com/ralph/) pioneered by Geoffrey Huntley, it embodies persistent iteration over perfection.

⚠️ **CRITICAL SAFETY WARNING**: Autopilot disables PatchPal's permission system. **ONLY use in isolated environments** (Docker containers, VMs, throwaway projects). See [examples/ralph/](https://github.com/wiseprobe/patchpal/tree/main/examples/ralph) for comprehensive safety guidelines.

### Quick Start

```bash
# After pip install patchpal, autopilot is available immediately

# Option 1: Use python -m (recommended)
python -m patchpal autopilot \
  --prompt "Build a REST API with tests" \
  --completion-promise "COMPLETE" \
  --max-iterations 30

# Option 2: Direct command (if preferred)
patchpal-autopilot \
  --prompt-file task.md \
  --completion-promise "DONE" \
  --max-iterations 50

# Option 3: Use as a Python library
python -c "
from patchpal.autopilot import autopilot_loop
autopilot_loop(
    prompt='Build a calculator with tests',
    completion_promise='COMPLETE',
    max_iterations=20
)
"
```

### How It Works

The key insight: The agent sees its previous work in conversation history and can adjust its approach, notice failures, and try different solutions automatically.

```
1. Agent works on task
2. Agent tries to exit
3. Stop hook intercepts ← Key mechanism!
4. Same prompt fed back
5. Agent sees previous work in history
6. Agent adjusts approach
7. Repeat until completion promise found
```

The agent never actually "completes" until it outputs the completion promise string.

### Key Principles

- **Iteration > Perfection**: Let the loop refine the work, don't aim for perfect first try
- **Failures Are Data**: Deterministically bad means failures are predictable and informative
- **Operator Skill Matters**: Success depends on writing good prompts, not just having a good model
- **Persistence Wins**: Keep trying until success—the loop handles retry logic automatically

### Writing Effective Prompts

Good autopilot prompts have:

**1. Clear Completion Criteria**
```markdown
# Success Criteria
- All tests pass (pytest -v shows green)
- Coverage >80%
- No linter errors
- README with API documentation

When complete, output: <promise>COMPLETE</promise>
```

**2. Self-Correction Pattern**
```markdown
# Process
1. Write code in app.py
2. Write tests in test_app.py
3. Run tests: run_shell("pytest test_app.py -v")
4. If any fail, debug and fix
5. Repeat until all pass
```

**3. Incremental Goals**
```markdown
# Requirements
Phase 1: Core CRUD operations
Phase 2: Input validation
Phase 3: Error handling
Phase 4: Tests (>80% coverage)
```

**4. Escape Hatch**
```markdown
# If Stuck
After 10 iterations without progress:
- Document blocking issues in BLOCKED.md
- List attempted approaches
- Suggest alternatives
```

### Real-World Examples

See [examples/ralph/](https://github.com/wiseprobe/patchpal/tree/main/examples/ralph) for complete examples:
- **simple_autopilot_example.py**: Basic calculator task
- **multi_phase_todo_api_example.py**: Multi-phase API build (3 sequential phases)
- **prompts/**: Example prompt templates for different task types

### Using as a Python Library

```python
from patchpal.autopilot import autopilot_loop

result = autopilot_loop(
    prompt="""
Build a REST API for todos.

Requirements:
- Flask app with CRUD endpoints
- Input validation (title required, max 200 chars)
- Unit tests with pytest (>80% coverage)
- All tests passing

Process:
1. Create app.py with routes
2. Write tests in test_app.py
3. Run: run_shell("pytest test_app.py -v")
4. Fix failures and retry

Output: <promise>COMPLETE</promise> when done.
    """,
    completion_promise="COMPLETE",
    max_iterations=30,
    model="anthropic/claude-sonnet-4-5"  # optional
)

if result:
    print("✅ Task completed successfully!")
else:
    print("⚠️ Did not complete within max iterations")
```

### Safety: Sandboxed Environments Only

**Why Isolation Is Critical:**

Autopilot runs with `PATCHPAL_REQUIRE_PERMISSION=false`:
- No permission prompts for file modifications
- No permission prompts for shell commands
- Multiple iterations without human oversight
- Potential for catastrophic mistakes

**Recommended Isolation:**

**Option 1: Docker/Podman Container** (Good)
```bash
# Create and run in isolated container
docker run -it --rm \
  -v $(pwd):/workspace \
  --memory="2g" --cpus="2" \
  python:3.11-slim bash

# Inside container
pip install patchpal
python -m patchpal autopilot --prompt-file task.md --completion-promise "DONE"
```

**Option 2: Dedicated VM/Server** (Best)
```bash
# Use a separate machine/VM with no access to production
ssh autopilot-sandbox
cd /workspace/throwaway-project
python -m patchpal autopilot --prompt-file task.md --completion-promise "DONE"
```

**Option 3: Git Worktree** (Minimal)
```bash
# Isolate in a separate branch
git worktree add ../autopilot-sandbox -b autopilot-experiment
cd ../autopilot-sandbox
python -m patchpal autopilot --prompt-file task.md --completion-promise "DONE"

# Review and merge, or discard
git worktree remove --force ../autopilot-sandbox
```

### Best Practices

**Always:**
- ✅ Use version control (commit before running)
- ✅ Run in isolated environments
- ✅ Start with low max-iterations (5-10) to validate prompts
- ✅ Monitor with `git status` or `watch -n 2 'git status --short'`
- ✅ Review all changes before committing

**Never:**
- ❌ Run on codebases in production
- ❌ Run on your main development machine without container
- ❌ Leave running unattended on important systems

### Real-World Results

The Ralph Wiggum technique has been successfully used for:
- **6 repos at Y Combinator hackathon** - Generated overnight
- **$50k contract for $297 in API costs** - Complete tested project
- **CURSED programming language** - Built over 3 months
- **Test-driven development** - Excellent for TDD workflows

See [examples/ralph/](https://github.com/wiseprobe/patchpal/blob/main/examples/ralph/) for comprehensive documentation, safety guidelines, and more examples.

### Learn More

- **Comprehensive Guide**: [examples/ralph/](https://github.com/wiseprobe/patchpal/tree/main/examples/ralph) - Safety, prompts, patterns, troubleshooting
- **Ralph Wiggum Technique Origins**:
  - https://www.humanlayer.dev/blog/brief-history-of-ralph
  - https://awesomeclaude.ai/ralph-wiggum
  - https://github.com/ghuntley/ralph
