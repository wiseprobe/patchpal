---
name: review
description: Perform a thorough code review of recent changes
---

# Code Review Checklist

Conduct a comprehensive code review by examining:

## 1. What Changed
- Use `git_diff` to see all modifications
- Use `git_log` to understand the commit history and context
- Identify the scope and purpose of changes

## 2. Code Quality
Review each changed file for:
- **Correctness**: Does the code do what it's supposed to do?
- **Clarity**: Is the code readable and well-structured?
- **Edge cases**: Are error conditions handled properly?
- **Performance**: Are there any obvious performance issues?
- **Security**: Check for common vulnerabilities (injection, XSS, auth issues)

## 3. Best Practices
Check for:
- Consistent code style
- Proper error handling
- Appropriate use of language features
- No commented-out code or debug statements
- Meaningful variable and function names

## 4. Testing
- Are there tests for the new functionality?
- Do existing tests still pass?
- Use `grep_code` to find related test files
- Use `run_shell` to execute tests if needed

## 5. Documentation
- Are complex parts commented?
- Is README or documentation updated if needed?
- Are function/class docstrings present?

## Output Format
Provide feedback as:
1. **Summary**: Brief overview of changes
2. **Positives**: What's done well
3. **Issues**: Problems that must be fixed (if any)
4. **Suggestions**: Optional improvements
5. **Verdict**: APPROVE / REQUEST CHANGES / COMMENT
