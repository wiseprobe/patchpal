#!/usr/bin/env python3
"""
multi_phase_todo_api_example.py - Chain multiple autopilot loops for complex projects

This example shows how to break down large projects into sequential phases,
with each phase running as its own autopilot loop. Each phase must complete
before the next one begins.

Usage:
    python multi_phase_todo_api_example.py

    # Or customize the phases by editing this file
"""

import sys

try:
    from patchpal.autopilot import autopilot_loop
except ImportError:
    # Fallback for running from examples directory before installation
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from patchpal.autopilot import autopilot_loop


def multi_phase_build():
    """Run multiple autopilot phases sequentially to build a complete application."""

    phases = [
        {
            "name": "Phase 1: Data Models",
            "prompt": """
Build data models and database schema for a Todo application.

Requirements:
- User model (id, username, email, password_hash)
- Todo model (id, title, description, completed, user_id)
- Tag model (id, name)
- TodoTag association table (many-to-many relationship)
- Use SQLAlchemy ORM
- Create database migrations (Alembic)
- Write unit tests for all models
- Tests must pass with pytest

Process:
1. Create models.py with all models
2. Create database.py with database setup
3. Create alembic migrations
4. Write tests in test_models.py
5. Run tests: run_shell("pytest test_models.py -v")
6. Fix any failures
7. Repeat until all tests pass

Success Criteria:
- All models defined with proper relationships
- Database migrations work
- All tests passing
- No SQLAlchemy warnings

Output: <promise>PHASE1_DONE</promise> when complete.
            """,
            "completion_promise": "PHASE1_DONE",
            "max_iterations": 20,
        },
        {
            "name": "Phase 2: API Endpoints",
            "prompt": """
Build REST API endpoints for the Todo application.

Requirements:
- Flask app with blueprints
- CRUD endpoints for Todos (/api/todos)
- CRUD endpoints for Tags (/api/tags)
- Request validation (Flask-Marshmallow)
- Error handling (400, 404, 500)
- API documentation (docstrings)
- Integration tests
- All tests must pass

Process:
1. Create app.py with Flask app
2. Create routes/todos.py with Todo endpoints
3. Create routes/tags.py with Tag endpoints
4. Create schemas.py with Marshmallow schemas
5. Write tests in test_api.py
6. Run tests: run_shell("pytest test_api.py -v")
7. Fix any failures
8. Repeat until all tests pass

Success Criteria:
- All CRUD operations work for Todos and Tags
- Input validation works
- Error handling works
- All integration tests pass
- API responds correctly to valid/invalid requests

Output: <promise>PHASE2_DONE</promise> when complete.
            """,
            "completion_promise": "PHASE2_DONE",
            "max_iterations": 25,
        },
        {
            "name": "Phase 3: Authentication",
            "prompt": """
Add JWT authentication to the API.

Requirements:
- /api/auth/register endpoint (create user)
- /api/auth/login endpoint (return JWT token)
- JWT token generation and validation (PyJWT)
- Protected routes (require authentication)
- Password hashing (bcrypt)
- Auth middleware/decorator
- Auth tests
- All tests must pass

Process:
1. Create auth.py with register/login logic
2. Add JWT utilities (generate_token, verify_token)
3. Add @require_auth decorator for protected routes
4. Update Todo routes to require authentication
5. Write tests in test_auth.py
6. Run all tests: run_shell("pytest -v")
7. Fix any failures
8. Repeat until all tests pass

Success Criteria:
- Users can register and login
- JWT tokens work correctly
- Protected routes require valid token
- Invalid tokens are rejected
- All tests pass (models, API, auth)

Output: <promise>PHASE3_DONE</promise> when complete.
            """,
            "completion_promise": "PHASE3_DONE",
            "max_iterations": 20,
        },
    ]

    print("\n" + "=" * 80)
    print("🚀 Multi-Phase Autopilot Build")
    print("=" * 80)
    print(f"Total phases: {len(phases)}")
    print("Each phase must complete before the next begins.")
    print("=" * 80 + "\n")

    for i, phase in enumerate(phases, 1):
        print(f"\n{'=' * 80}")
        print(f"🎯 Starting {phase['name']} ({i}/{len(phases)})")
        print(f"{'=' * 80}\n")

        result = autopilot_loop(
            prompt=phase["prompt"],
            completion_promise=phase["completion_promise"],
            max_iterations=phase["max_iterations"],
        )

        if not result:
            print(f"\n❌ {phase['name']} failed to complete!")
            print("Multi-phase build aborted.")
            return False

        print(f"\n✅ {phase['name']} completed successfully!")

    print("\n" + "=" * 80)
    print("🎉 All phases completed successfully!")
    print("=" * 80)
    print("\nYour Todo API is ready with:")
    print("  ✓ Data models and database")
    print("  ✓ REST API endpoints")
    print("  ✓ JWT authentication")
    print("  ✓ Comprehensive test coverage")
    print("=" * 80 + "\n")
    return True


if __name__ == "__main__":
    try:
        success = multi_phase_build()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Multi-phase build interrupted by user (Ctrl-C)")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
