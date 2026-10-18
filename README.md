# Banking Transaction Analysis System

A local analytics and demonstration application for synthetic banking transactions. It does not connect to real bank accounts, move money, or establish that a flagged transaction is fraud.

## Current implementation

The Flask application provides a process health endpoint at `GET /health`; it does not contact MySQL. The database layer defines synthetic accounts and transactions, and includes a deterministic seed command. Seed records are synthetic, dated in January 2025, denominated in USD, and contain no personal information.

### Requirements

- Python 3.10 or newer
- Git
- MySQL 8.0.16 or newer for enforcing the schema's `CHECK` constraints and running the seed command (database tests use SQLite and need no server)

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

Settings are read from the process environment. `.env.example` documents the supported names; it is a template and is not loaded automatically. No dotenv package is used. Set values in PowerShell, for example:

```powershell
$env:APP_ENV = "development"
$env:APP_DEBUG = "0"
$env:DATABASE_URL = "mysql+pymysql://bank_demo:replace_me@127.0.0.1:3306/bank_analysis"
```

Create the empty MySQL database first, then run `python -m app.seed` once to create the tables and insert sample data. Replace the example connection values with your local MySQL username and password; set real credentials in your shell environment and never commit them. `.env` files are ignored by Git, but this project does not load them automatically. The seed command refuses to mix sample data into a database that already contains accounts or transactions. `create_all` creates missing tables but does not migrate existing schemas.

The schema stores each transaction as one event. `amount` is a positive `DECIMAL(12, 2)` value and is not a net balance or profit. Deposits have a destination account, withdrawals have a source account, and transfers/payments have both. A transfer is not duplicated into two transaction rows. Timestamp values are stored in UTC. The sample data uses USD only; future analytics must group by currency before summing.

## Dependencies

- Flask — HTTP application and the database-independent health route.
- SQLAlchemy — ORM mappings, schema constraints, and parameterized database access.
- PyMySQL — Python MySQL driver used by the `mysql+pymysql` SQLAlchemy URL.
- pytest — automated checks for the health route, schema constraints, and synthetic seed behavior.

Flask's supporting packages and pytest's supporting packages are installed transitively by pip. Pandas and NumPy are postponed until the analytics stage needs them.

### Run checks

```powershell
pytest
```

## File purpose inventory

- `app.py` — starts the local Flask development server.
- `app/__init__.py` — creates the Flask application and defines the database-independent health route.
- `app/config.py` — reads the safe default environment settings used by the app factory.
- `app/database.py` — declares the SQLAlchemy base, creates engines, and creates missing model tables; imports do not open a database connection.
- `app/models.py` — defines account and transaction fields, relationships, indexes, and database constraints.
- `app/seed.py` — generates deterministic, PII-free sample data and exposes `python -m app.seed`.
- `tests/test_health.py` — checks the health endpoint response using Flask's in-process test client.
- `tests/test_database.py` — verifies seed behavior and schema constraints with an in-memory SQLite database.
- `requirements.txt` — pins Flask, SQLAlchemy, PyMySQL, and pytest.
- `.env.example` — documents safe optional environment settings; it contains no secrets.
- `.gitignore` — excludes environment files, virtual environments, caches, and editor or OS metadata.
- `README.md` — explains scope, setup, startup, tests, and file responsibilities.

## Git and GitHub

`git init` creates a local repository. `git add` selects files for the next snapshot, and `git commit` records that snapshot locally. A GitHub repository is a separate remote copy: `git remote add origin <URL>` connects it, and `git push -u origin main` uploads the local commit and sets the upstream branch. Do not push until the GitHub repository has been created and the remote URL has been verified.
