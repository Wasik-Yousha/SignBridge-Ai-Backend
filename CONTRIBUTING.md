# Contributing

Thanks for your interest in improving SignBridge AI Backend.

## Development Setup

```bash
make run
```

Or manually:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Contribution Guidelines

- Keep pull requests focused and small.
- Add clear commit messages in imperative mood.
- Update `README.md` when behavior or API changes.
- Preserve backward compatibility unless the pull request clearly documents a breaking change.

## Before Opening a Pull Request

- Run static checks:

```bash
source backend/.venv/bin/activate
ruff check backend/app
python -m compileall backend/app
```

- Verify endpoints in local docs: `http://localhost:8000/docs`.
- Confirm no secrets or local credentials are committed.

## Pull Request Checklist

- Code compiles and checks pass.
- New behavior is documented.
- Request/response changes are reflected in API examples.
- Temporary or generated files are excluded from git.
