# AGENTS.md

This file defines how a software development agent should operate in this repository.

## Read First
Before making changes, read these project documents:
- `ARCHITECTURE.md` to understand file layout, component boundaries, and runtime flow.
- `API.md` to understand the HTTP contract and preserve API compatibility.

## Mission
Build high-quality, readable, and maintainable software with predictable behavior and low regression risk.

## Core Principles
- Prefer simple, clear solutions over clever or complex ones.
- Optimize for long-term maintainability and ease of onboarding.
- Keep changes small, focused, and easy to review.
- Make behavior explicit and deterministic.
- Preserve backward compatibility unless a change is intentionally breaking.

## Engineering Standards
- Write code that is easy to read first, do not optimize. 
- Use descriptive names and clear module boundaries.
- Follow existing project conventions and architecture.
- Add or update documentation/comments when behavior is non-obvious.
- Avoid dead code, speculative abstractions, and unnecessary dependencies.

## Required Development Workflow (TDD)
For every feature, bug fix, or behavior change:

1. **Write a failing test first**
   - Add or update tests that capture the desired behavior.
   - Run tests to confirm the new/changed test fails for the expected reason.

2. **Implement the minimal code change**
   - Write only enough production code to make the failing test pass.
   - Keep implementation straightforward and aligned with project patterns.

3. **Refactor safely**
   - Improve clarity and design while preserving behavior.
   - Keep tests green throughout refactoring.

## Test and Regression Policy
- Run relevant tests during development for quick feedback.
- After implementation, run the appropriate broader test suite to detect regressions.
- Do not consider work complete unless tests pass.
- If tests are flaky or failing for unrelated reasons, document the issue and scope clearly.

## Change Quality Checklist
Before finalizing any task, ensure:
- New behavior is covered by tests.
- Existing tests still pass.
- Code is readable and maintainable.
- No obvious duplication or unnecessary complexity was introduced.
- Error handling and edge cases are addressed.
- Any user-visible or developer-impacting changes are documented.

## Scope and Safety
- Do not make unrelated refactors in the same change unless explicitly requested.
- Highlight assumptions, risks, and tradeoffs when they matter.
- Prefer reversible, incremental changes over sweeping rewrites.

## Completion Criteria
A task is complete only when:
- Tests were written first (TDD flow followed).
- Implementation satisfies the test expectations.
- Regression checks were run and passed.
- The final diff is clean, focused, and understandable.

## Version Control
Follow best practices for Git when developing new features.
- Build and test new features on feature branches.
- Commit changes with descriptive commit messages.
- Merge feature branches when feature is complete and tested.
