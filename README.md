# Banking Transaction Analysis System

A local analytics and demonstration application for synthetic banking transactions. It does not connect to real bank accounts, move money, or establish that a flagged transaction is fraud.

## Stage A: project foundation

The Flask application currently provides a process health endpoint at `GET /health`. It does not contact MySQL. Database configuration and transaction features will be added in later stages.

### Requirements

- Python 3.10 or newer
- Git

Install the pinned project dependencies in a virtual environment:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If the `py` launcher is unavailable, use an installed Python executable to create the virtual environment.

### Run the application

```powershell
python app.py
```

Open `http://127.0.0.1:5000/health`. A successful response is `{"status":"ok"}`.

Optional settings are read from the process environment. `.env.example` documents the supported names; no dotenv package is used. Set values in PowerShell, for example:

```powershell
$env:APP_ENV = "development"
$env:APP_DEBUG = "0"
```

### Run checks

```powershell
pytest
```

## File purpose inventory

- `app.py` — starts the local Flask development server.
- `app/__init__.py` — creates the Flask application and defines the database-independent health route.
- `app/config.py` — reads the safe default environment settings used by the app factory.
- `tests/test_health.py` — checks the health endpoint response using Flask's in-process test client.
- `requirements.txt` — pins Flask for the application and pytest for the test suite.
- `.env.example` — documents safe optional environment settings; it contains no secrets.
- `.gitignore` — excludes environment files, virtual environments, caches, and editor or OS metadata.
- `README.md` — explains scope, setup, startup, tests, and file responsibilities.

## Git and GitHub

`git init` creates a local repository. `git add` selects files for the next snapshot, and `git commit` records that snapshot locally. A GitHub repository is a separate remote copy: `git remote add origin <URL>` connects it, and `git push -u origin main` uploads the local commit and sets the upstream branch. Do not push until the GitHub repository has been created and the remote URL has been verified.
