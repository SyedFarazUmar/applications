# Calculator Service — Code Reference Guide

The calculator is a **Python Flask** REST API that connects to MongoDB to compute on-call shift statistics. It has no HTML templates — it returns JSON responses only. This document explains every code construct used in this service.

---

## Table of Contents

- [Python / Flask (app.py)](#python--flask-apppy)
  - [Imports](#imports)
  - [Flask Application Object](#flask-application-object)
  - [Logging](#logging)
  - [Environment Variables with os.environ](#environment-variables-with-osenviron)
  - [MongoDB Connection (PyMongo)](#mongodb-connection-pymongo)
  - [Functions (def)](#functions-def)
  - [Type Hints](#type-hints)
  - [Route Decorators (@app.route)](#route-decorators-approute)
  - [URL Parameters](#url-parameters)
  - [Query Parameters (request.args)](#query-parameters-requestargs)
  - [jsonify](#jsonify)
  - [List Comprehensions and Generator Expressions](#list-comprehensions-and-generator-expressions)
  - [try / except (Error Handling)](#try--except-error-handling)
  - [if \_\_name\_\_ == "\_\_main\_\_"](#if-__name__--__main__)
  - [app.run()](#apprun)
- [Dockerfile](#dockerfile)
- [Gunicorn (WSGI Server)](#gunicorn-wsgi-server)
- [requirements.txt](#requirementstxt)

---

## Python / Flask (app.py)

### Imports

```python
import os
import logging
from datetime import datetime

from flask import Flask, jsonify, request
from pymongo import MongoClient
```

| Statement | What it does |
|-----------|-------------|
| `import os` | Access OS-level features like environment variables |
| `import logging` | Python's built-in structured logging framework |
| `from datetime import datetime` | Import the `datetime` class for date parsing and comparison |
| `from flask import Flask, jsonify, request` | Flask web framework — `jsonify` for JSON responses, `request` for reading query parameters |
| `from pymongo import MongoClient` | MongoDB driver for Python |

**Difference from frontend:** The calculator does NOT import `render_template`, `session`, `redirect`, `flash`, `url_for` (no HTML pages), `requests` (no outbound HTTP calls), or `werkzeug.security` (no password handling).

---

### Flask Application Object

```python
app = Flask(__name__)
```

- Creates the Flask application instance.
- `__name__` is a Python built-in variable containing the module name (here, `"app"`).
- Flask uses this to locate resources relative to the module.
- No `secret_key` needed because this service doesn't use sessions or flash messages.

---

### Logging

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("calculator")
```

- `logging.basicConfig()` configures the root logger once.
- `level=logging.INFO` means messages at INFO level and above (INFO, WARNING, ERROR, CRITICAL) are shown; DEBUG is hidden.
- `format` defines the log line structure:

| Placeholder | Output |
|-------------|--------|
| `%(asctime)s` | Timestamp like `2026-03-31 14:30:00,123` |
| `%(levelname)s` | Level like `INFO`, `WARNING`, `ERROR` |
| `%(name)s` | Logger name (`"calculator"`) |
| `%(message)s` | The actual log message |

**Usage:**
```python
logger.info("Found %d total entries for user %s", len(entries), username)
logger.warning("Unparseable date: %s", date_str)
```

The `%s` and `%d` are lazy formatting placeholders — the string is only formatted if the log level is actually enabled.

---

### Environment Variables with os.environ

```python
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://mongodb:27017")
DB_NAME = os.environ.get("DB_NAME", "oncall_db")
```

- `os.environ` is a dictionary of all environment variables set in the system/container.
- `.get("KEY", "default")` returns the value if set, or the default string if not.
- This pattern makes the app configurable without changing code — set variables in `docker-compose.yaml`, Kubernetes Deployment, or the shell.

**Example:** In the Helm chart, `MONGO_URI` is set to `mongodb://mongodb:27017` via the Deployment environment section.

---

### MongoDB Connection (PyMongo)

```python
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client[DB_NAME]
oncall_col = db["oncall_entries"]
```

| Object | What it is |
|--------|-----------|
| `MongoClient(uri, ...)` | Creates a connection pool to the MongoDB server |
| `client[DB_NAME]` | Selects the `oncall_db` database |
| `db["oncall_entries"]` | Selects the `oncall_entries` collection |
| `serverSelectionTimeoutMS=5000` | Timeout: fail if MongoDB is unreachable for 5 seconds |

**Operations used in this service:**
```python
oncall_col.find({"username": "admin"})   # Returns a cursor over all matching documents
list(cursor)                              # Convert cursor to a Python list
client.admin.command("ping")              # Ping MongoDB to check if it's alive
```

---

### Functions (def)

```python
def _in_year(date_str: str, year: int) -> bool:
    """Return True if a YYYY-MM-DD date string falls within the given year."""
    if not date_str:
        return False
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.year == year
    except ValueError:
        logger.warning("Unparseable date: %s", date_str)
        return False
```

| Element | Explanation |
|---------|-------------|
| `def _in_year(...)` | Defines a function. The `_` prefix is a Python convention meaning "private / internal use" |
| `date_str: str` | Type hint — the parameter should be a string |
| `year: int` | Type hint — the parameter should be an integer |
| `-> bool` | Type hint — the function returns a boolean (`True` or `False`) |
| `"""..."""` | Docstring — documentation for the function |
| `if not date_str` | Checks for empty or `None` string |
| `datetime.strptime(...)` | Parses a string into a `datetime` object using a format pattern |
| `"%Y-%m-%d"` | Format: 4-digit year, 2-digit month, 2-digit day (e.g., `2026-04-07`) |
| `dt.year == year` | Compares the parsed year to the target year |
| `except ValueError` | Catches invalid date strings (e.g., `"not-a-date"`) |

---

### Type Hints

```python
def _in_year(date_str: str, year: int) -> bool:
```

- Type hints are optional annotations that document expected types.
- They do NOT enforce types at runtime — Python still allows any type to be passed.
- They help with code readability and IDE autocompletion.

| Syntax | Meaning |
|--------|---------|
| `param: str` | Parameter should be a string |
| `param: int` | Parameter should be an integer |
| `-> bool` | Function returns a boolean |
| `-> None` | Function returns nothing |

---

### Route Decorators (@app.route)

```python
@app.route("/api/calculate/<username>", methods=["GET"])
def calculate_oncall(username):
    ...

@app.route("/api/health", methods=["GET"])
def health():
    ...
```

- `@app.route(path, methods=[...])` registers a function as a URL handler.
- `methods=["GET"]` means only HTTP GET requests are accepted.
- When someone visits `/api/calculate/admin`, Flask calls `calculate_oncall("admin")`.

| Route | Function | Purpose |
|-------|----------|---------|
| `/api/calculate/<username>` | `calculate_oncall(username)` | Calculate on-call statistics for a user |
| `/api/health` | `health()` | Health check — tests MongoDB connectivity |

---

### URL Parameters

```python
@app.route("/api/calculate/<username>", methods=["GET"])
def calculate_oncall(username):
    ...
```

- `<username>` in the route path is a **variable segment**.
- Flask extracts the value from the URL and passes it as a function argument.
- Examples:
  - `/api/calculate/admin` → `username = "admin"`
  - `/api/calculate/jdoe` → `username = "jdoe"`

**Typed URL parameters:**
```python
@app.route("/users/<int:user_id>")    # Only matches integers
@app.route("/files/<path:filepath>")   # Matches paths with slashes
```

---

### Query Parameters (request.args)

```python
from flask import request

year = request.args.get("year", datetime.now().year, type=int)
```

- `request.args` is a dictionary of URL query parameters.
- URL: `/api/calculate/admin?year=2026` → `request.args.get("year")` returns `"2026"`.
- `type=int` automatically converts the string `"2026"` to the integer `2026`.
- The second argument (`datetime.now().year`) is the default if `year` is not provided.

---

### jsonify

```python
from flask import jsonify

return jsonify(result), 200

return jsonify({"status": "healthy", "service": "calculator", "mongodb": mongo_status}), 200
```

- `jsonify(data)` converts a Python dictionary into a JSON HTTP response.
- Sets the `Content-Type` header to `application/json` automatically.
- `200` is the HTTP status code (OK). You can return other codes like `404`, `500`, etc.

**Example response:**
```json
{
    "username": "admin",
    "year": 2026,
    "primary_count": 2,
    "secondary_count": 2,
    "total_shifts": 4
}
```

---

### List Comprehensions and Generator Expressions

```python
entries = list(oncall_col.find({"username": username}))

primary_count = sum(
    1 for e in entries if _in_year(e.get("oncall_primary_date", ""), year)
)

secondary_count = sum(
    1 for e in entries if _in_year(e.get("oncall_secondary_date", ""), year)
)
```

**`list(cursor)`:**
- `oncall_col.find(...)` returns a cursor (lazy iterator).
- `list(...)` forces evaluation and puts all results into a Python list.

**Generator expression (`sum(1 for e in entries if ...)`):**
- This counts how many entries match a condition.
- `for e in entries` — iterate over each entry.
- `if _in_year(...)` — only include entries where the date is in the target year.
- `1` — contribute 1 to the sum for each matching entry.
- `sum(...)` — adds up all the 1s.

**Equivalent verbose version:**
```python
primary_count = 0
for e in entries:
    date_str = e.get("oncall_primary_date", "")
    if _in_year(date_str, year):
        primary_count += 1
```

**`dict.get(key, default)`:**
```python
e.get("oncall_primary_date", "")
```
- Returns the value for `"oncall_primary_date"` if it exists in the dictionary.
- Returns `""` (empty string) if the key doesn't exist.
- Safer than `e["oncall_primary_date"]` which would raise a `KeyError`.

---

### try / except (Error Handling)

```python
try:
    client.admin.command("ping")
    mongo_status = "connected"
except Exception:
    mongo_status = "disconnected"
```

- `try:` — run code that might fail.
- `except Exception:` — catch any error. `Exception` is the base class for most errors.
- In the health check, if MongoDB is down, the ping fails and we report "disconnected" instead of crashing.

**In `_in_year()`:**
```python
try:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.year == year
except ValueError:
    logger.warning("Unparseable date: %s", date_str)
    return False
```

- `except ValueError` catches only `ValueError` (raised when the date string doesn't match the format).
- More specific exception types are preferred over bare `except:` because they only catch expected errors.

---

### if \_\_name\_\_ == "\_\_main\_\_"

```python
if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=5001, debug=debug)
```

- `__name__` equals `"__main__"` when the script is run directly (`python app.py`).
- When imported by Gunicorn (`gunicorn app:app`), `__name__` equals `"app"`, so this block is skipped.
- This allows the same file to work as both a standalone development server and a module imported by Gunicorn.

---

### app.run()

```python
app.run(host="0.0.0.0", port=5001, debug=debug)
```

| Parameter | Purpose |
|-----------|---------|
| `host="0.0.0.0"` | Listen on all network interfaces (needed inside Docker) |
| `port=5001` | Listen on port 5001 (the calculator's assigned port) |
| `debug=True/False` | Debug mode enables auto-reload and detailed error pages |

> **Production note:** `app.run()` is only for development. In production, Gunicorn runs the app (see below).

---

## Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5001
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "2", "--access-logfile", "-", "app:app"]
```

| Instruction | Purpose |
|-------------|---------|
| `FROM python:3.12-slim` | Base image — Python 3.12 on minimal Debian Linux (`slim` removes docs, man pages, etc.) |
| `WORKDIR /app` | All subsequent commands run in `/app` inside the container |
| `COPY requirements.txt .` | Copy dependencies file first — Docker caches this layer, so re-builds are faster if only code changes |
| `RUN pip install --no-cache-dir -r requirements.txt` | Install Python packages; `--no-cache-dir` saves disk space |
| `COPY . .` | Copy all remaining source code into the container |
| `EXPOSE 5001` | Documentation: tells users/tools this container uses port 5001 (does NOT actually open the port) |
| `CMD [...]` | Default command to run when the container starts |

**Layer caching optimization:** By copying `requirements.txt` before the rest of the code, Docker can reuse the cached `pip install` layer when only Python code changes (requirements haven't changed).

---

## Gunicorn (WSGI Server)

```
gunicorn --bind 0.0.0.0:5001 --workers 2 --access-logfile - app:app
```

| Part | Meaning |
|------|---------|
| `gunicorn` | Green Unicorn — a production WSGI HTTP server for Python |
| `--bind 0.0.0.0:5001` | Listen on all interfaces, port 5001 |
| `--workers 2` | Fork 2 worker processes to handle requests concurrently |
| `--access-logfile -` | Print HTTP access logs to stdout (captured by Docker/Kubernetes) |
| `app:app` | `module:variable` — load the `app` variable from the `app.py` module |

**Why Gunicorn instead of `app.run()`?**

| Feature | `app.run()` (Flask dev server) | Gunicorn |
|---------|-------------------------------|----------|
| Concurrent requests | Single-threaded | Multiple workers |
| Stability | Will crash on errors | Workers auto-restart |
| Performance | Slow | Production-grade |
| Use case | Development only | Production |

---

## requirements.txt

```
Flask==3.1.0
pymongo==4.10.1
gunicorn==23.0.0
```

| Package | Version | Purpose |
|---------|---------|---------|
| **Flask** | 3.1.0 | Web framework for routing and request handling |
| **pymongo** | 4.10.1 | MongoDB driver for Python |
| **gunicorn** | 23.0.0 | Production WSGI HTTP server |

**Note:** Fewer packages than the frontend because the calculator doesn't need `Werkzeug` (password hashing), `requests` (outbound HTTP), or template rendering.

Versions are pinned with `==` to ensure every build uses exactly the same package versions (reproducible builds).
