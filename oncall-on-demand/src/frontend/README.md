# Frontend Service — Code Reference Guide

The frontend is a **Python Flask** web application that serves HTML pages using **Jinja2 templates** styled with **Bootstrap 5**. This document explains every code construct used in this service.

---

## Table of Contents

- [Python / Flask (app.py)](#python--flask-apppy)
  - [Imports](#imports)
  - [Flask Application Object](#flask-application-object)
  - [Logging](#logging)
  - [Environment Variables with os.environ](#environment-variables-with-osenviron)
  - [MongoDB Connection (PyMongo)](#mongodb-connection-pymongo)
  - [Functions (def)](#functions-def)
  - [Route Decorators (@app.route)](#route-decorators-approute)
  - [Request Object](#request-object)
  - [Session](#session)
  - [Flash Messages](#flash-messages)
  - [Redirects and URL Building](#redirects-and-url-building)
  - [render_template](#render_template)
  - [Password Hashing (Werkzeug)](#password-hashing-werkzeug)
  - [HTTP Requests to Other Services](#http-requests-to-other-services)
  - [try / except (Error Handling)](#try--except-error-handling)
  - [app.app_context()](#appapp_context)
  - [if \_\_name\_\_ == "\_\_main\_\_"](#if-__name__--__main__)
  - [app.run()](#apprun)
- [HTML / Jinja2 Templates](#html--jinja2-templates)
  - [Document Structure (DOCTYPE, html, head, body)](#document-structure-doctype-html-head-body)
  - [meta](#meta)
  - [title](#title)
  - [link (stylesheets)](#link-stylesheets)
  - [script](#script)
  - [nav (navigation bar)](#nav-navigation-bar)
  - [div](#div)
  - [ul and li (lists)](#ul-and-li-lists)
  - [a (links)](#a-links)
  - [button](#button)
  - [span](#span)
  - [i (icons)](#i-icons)
  - [main](#main)
  - [footer and small](#footer-and-small)
  - [form](#form)
  - [label](#label)
  - [input](#input)
  - [table, thead, tbody, tr, th, td](#table-thead-tbody-tr-th-td)
  - [h1–h6 (headings)](#h1h6-headings)
  - [p (paragraph)](#p-paragraph)
  - [hr (horizontal rule)](#hr-horizontal-rule)
  - [Bootstrap CSS Classes](#bootstrap-css-classes)
- [Jinja2 Template Syntax](#jinja2-template-syntax)
  - [Template Inheritance (extends, block, endblock)](#template-inheritance-extends-block-endblock)
  - [Variables ({{ }})](#variables--)
  - [Control Flow (if, endif, for, endfor)](#control-flow-if-endif-for-endfor)
  - [with / endwith](#with--endwith)
  - [url_for()](#url_for)
  - [Filters and Methods](#filters-and-methods)
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

from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from werkzeug.security import generate_password_hash, check_password_hash
import requests as http_requests
```

| Statement | What it does |
|-----------|-------------|
| `import os` | Access operating system functions like environment variables (`os.environ`) |
| `import logging` | Python's built-in logging framework for writing structured log messages |
| `from datetime import datetime` | Import the `datetime` class for working with dates and times |
| `from flask import Flask, ...` | Import specific objects from the Flask web framework |
| `from pymongo import MongoClient` | Import the MongoDB client driver for Python |
| `from pymongo.errors import DuplicateKeyError` | Import a specific exception type for handling duplicate key errors |
| `from werkzeug.security import ...` | Import password hashing utilities (Werkzeug is Flask's underlying toolkit) |
| `import requests as http_requests` | Import the HTTP client library, aliased to avoid name collision with Flask's `request` |

**`import` vs `from ... import`:**
```python
import os              # Imports the whole module; use as os.environ, os.path, etc.
from flask import Flask  # Imports only Flask from the flask module; use directly as Flask()
import requests as http_requests  # Imports and renames to avoid name conflicts
```

---

### Flask Application Object

```python
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod")
```

- `Flask(__name__)` creates the application instance. `__name__` tells Flask where the app lives (used to find templates, static files, etc.).
- `app.secret_key` is required for session management and flash messages. Flask uses it to cryptographically sign session cookies.
- `os.environ.get("SECRET_KEY", "default")` reads an environment variable with a fallback default.

---

### Logging

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("frontend")
```

- `logging.basicConfig()` configures the root logger with a minimum level and output format.
- `logging.getLogger("frontend")` creates a named logger for this service.
- Log levels (from lowest to highest): `DEBUG` → `INFO` → `WARNING` → `ERROR` → `CRITICAL`

**Usage:**
```python
logger.info("Login successful for user: %s", username)    # Informational
logger.warning("Failed login attempt for user: %s", username)  # Warning
logger.error("Calculator service error: %s", exc)          # Error
```

The `%s` is a placeholder replaced by the argument. This is preferred over f-strings in logging because the string formatting is skipped if the log level is filtered out.

---

### Environment Variables with os.environ

```python
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://mongodb:27017")
CALCULATOR_URL = os.environ.get("CALCULATOR_URL", "http://calculator:5001")
DB_NAME = os.environ.get("DB_NAME", "oncall_db")
```

- `os.environ` is a dictionary of all environment variables.
- `.get("KEY", "default")` returns the value if the variable exists, or the default if it doesn't.
- This makes the app configurable without changing code — just set environment variables in Docker, Kubernetes, or the shell.

---

### MongoDB Connection (PyMongo)

```python
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client[DB_NAME]
users_col = db["users"]
oncall_col = db["oncall_entries"]
```

| Object | What it is |
|--------|-----------|
| `MongoClient(...)` | Creates a connection pool to the MongoDB server |
| `client[DB_NAME]` | Selects a database (like `use oncall_db` in mongosh) |
| `db["users"]` | Selects a collection (like a table in SQL) |
| `serverSelectionTimeoutMS=5000` | Wait at most 5 seconds to find a server |

**Common collection operations used in this app:**
```python
users_col.find_one({"username": "admin"})     # Find one document matching a filter
users_col.insert_one({...})                    # Insert a new document
users_col.update_one(filter, update, upsert=True)  # Update or insert if not found
oncall_col.find({"username": "admin"})         # Find all matching documents (returns cursor)
oncall_col.find(...).sort("created_at", -1)    # Sort results (-1 = descending)
list(cursor)                                    # Convert cursor to a Python list
```

---

### Functions (def)

```python
def seed_default_admin():
    """Ensure a default admin user always exists."""
    try:
        users_col.update_one(
            {"username": "admin"},
            {"$setOnInsert": {"username": "admin", "password": generate_password_hash("admin"), ...}},
            upsert=True,
        )
        logger.info("Default admin user ensured (admin/admin)")
    except DuplicateKeyError:
        logger.info("Default admin user already exists")
```

- `def function_name():` defines a function.
- The triple-quoted string `"""..."""` right after `def` is a **docstring** — documentation for the function.
- `upsert=True` means: update if found, insert if not found.
- `$setOnInsert` is a MongoDB operator — only sets fields when inserting (not when updating an existing document).

---

### Route Decorators (@app.route)

```python
@app.route("/login", methods=["GET", "POST"])
def login():
    ...
```

- `@app.route(path, methods=[...])` is a **decorator** that registers a function as a URL handler.
- When a browser visits `/login`, Flask calls the `login()` function.
- `methods=["GET", "POST"]` allows both reading the page (GET) and submitting a form (POST).
- If `methods` is omitted, only GET is allowed by default.

**Routes in this app:**

| Decorator | URL | Methods | Purpose |
|-----------|-----|---------|---------|
| `@app.route("/")` | `/` | GET | Redirect to dashboard or login |
| `@app.route("/login", methods=["GET", "POST"])` | `/login` | GET, POST | Show login form / process login |
| `@app.route("/register", methods=["GET", "POST"])` | `/register` | GET, POST | Show registration form / process registration |
| `@app.route("/dashboard", methods=["GET", "POST"])` | `/dashboard` | GET, POST | Show dashboard / add on-call entry |
| `@app.route("/stats")` | `/stats` | GET | Show on-call statistics |
| `@app.route("/logout")` | `/logout` | GET | Log user out |
| `@app.route("/health")` | `/health` | GET | Health check endpoint |

---

### Request Object

```python
from flask import request

# Reading form data (from POST)
username = request.form.get("username", "").strip()

# Reading query parameters (from URL like /stats?year=2026)
year = request.args.get("year", datetime.now().year, type=int)

# Checking HTTP method
if request.method == "POST":
    ...
```

| Property | What it does | Example |
|----------|-------------|---------|
| `request.method` | The HTTP method (`"GET"`, `"POST"`, etc.) | `if request.method == "POST"` |
| `request.form` | Dictionary of POST form data | `request.form.get("username")` |
| `request.args` | Dictionary of URL query parameters | `request.args.get("year", 2026, type=int)` |
| `.get(key, default)` | Safe access — returns default if key is missing | Never raises KeyError |
| `.strip()` | Removes whitespace from start/end of string | `"  hello  ".strip()` → `"hello"` |

---

### Session

```python
from flask import session

session["username"] = username       # Store data in the session
session.get("employee_id", "")       # Read data safely
"username" in session                # Check if a key exists
session.clear()                      # Remove all session data (logout)
```

- Sessions store user-specific data (like login state) across HTTP requests.
- Flask stores sessions as encrypted cookies in the browser (signed with `app.secret_key`).
- Data persists until the user closes the browser or `session.clear()` is called.

---

### Flash Messages

```python
from flask import flash

flash("Login successful!", "success")
flash("Invalid username or password.", "danger")
flash("Logged out successfully.", "info")
```

- `flash(message, category)` stores a one-time message to display on the next page load.
- Categories match Bootstrap alert classes: `success` (green), `danger` (red), `warning` (yellow), `info` (blue).
- Messages are consumed in templates via `get_flashed_messages()` (see Jinja2 section below).

---

### Redirects and URL Building

```python
from flask import redirect, url_for

return redirect(url_for("dashboard"))   # Redirect to the dashboard route
return redirect(url_for("login"))       # Redirect to the login route
```

- `url_for("function_name")` generates the URL for a route function. It's better than hardcoding URLs because it stays correct even if you change the route path.
- `redirect(url)` sends an HTTP 302 response, telling the browser to go to a different URL.

---

### render_template

```python
from flask import render_template

return render_template("login.html")

return render_template(
    "dashboard.html",
    username=session["username"],
    employee_id=session.get("employee_id", ""),
    entries=entries,
)
```

- Loads an HTML template from the `templates/` folder, processes Jinja2 syntax, and returns the result.
- Keyword arguments (`username=...`) become variables available inside the template.

---

### Password Hashing (Werkzeug)

```python
from werkzeug.security import generate_password_hash, check_password_hash

hashed = generate_password_hash("admin")        # "scrypt:32768:8:1$salt$hash..."
is_valid = check_password_hash(hashed, "admin")  # True
is_valid = check_password_hash(hashed, "wrong")  # False
```

- **Never store plain-text passwords.** `generate_password_hash()` creates a one-way hash.
- `check_password_hash()` verifies a plain password against a stored hash.
- The hash includes a random salt, so hashing the same password twice gives different results.

---

### HTTP Requests to Other Services

```python
import requests as http_requests

resp = http_requests.get(
    f"{CALCULATOR_URL}/api/calculate/{username}",
    params={"year": year},
    timeout=5,
)
resp.raise_for_status()  # Raise an exception if status code is 4xx/5xx
stats_data = resp.json()  # Parse JSON response into a Python dict
```

- `requests.get(url, params=..., timeout=...)` sends an HTTP GET request.
- `params={"year": 2026}` adds `?year=2026` to the URL automatically.
- `timeout=5` prevents the request from hanging indefinitely.
- `resp.json()` parses the JSON response body into a Python dictionary.

---

### try / except (Error Handling)

```python
try:
    resp = http_requests.get(...)
    resp.raise_for_status()
    stats_data = resp.json()
except http_requests.exceptions.RequestException as exc:
    logger.error("Calculator service error: %s", exc)
    stats_data = {"error": str(exc), ...}
```

- `try:` block runs the code that might fail.
- `except ExceptionType as exc:` catches a specific error type and stores it in `exc`.
- Without try/except, an error would crash the request and return a 500 error to the user.

---

### app.app_context()

```python
with app.app_context():
    seed_default_admin()
```

- Some Flask operations (like accessing config or extensions) require an "application context."
- `with app.app_context():` creates a temporary context so `seed_default_admin()` can run at startup (outside of a request).

---

### if \_\_name\_\_ == "\_\_main\_\_"

```python
if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=5000, debug=debug)
```

- `__name__` is a special Python variable. It equals `"__main__"` only when the file is run directly (`python app.py`).
- If the file is imported by another module (like Gunicorn), this block is skipped.
- This allows the same file to work both as a standalone script and as an importable module.

---

### app.run()

```python
app.run(host="0.0.0.0", port=5000, debug=debug)
```

| Parameter | What it does |
|-----------|-------------|
| `host="0.0.0.0"` | Listen on all network interfaces (required inside Docker containers) |
| `port=5000` | Listen on port 5000 |
| `debug=True` | Auto-reload on code changes and show detailed error pages (development only) |

> In production, `app.run()` is NOT used. Instead, Gunicorn runs the app (see Gunicorn section below).

---

## HTML / Jinja2 Templates

### Document Structure (DOCTYPE, html, head, body)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <!-- Metadata, stylesheets, title -->
</head>
<body>
    <!-- Visible page content -->
</body>
</html>
```

| Tag | Purpose |
|-----|---------|
| `<!DOCTYPE html>` | Tells the browser this is an HTML5 document |
| `<html lang="en">` | Root element; `lang="en"` declares English language (helps screen readers and search engines) |
| `<head>` | Contains metadata that is NOT displayed on the page (title, stylesheets, meta tags) |
| `<body>` | Contains everything the user sees on the page |

---

### meta

```html
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
```

| Attribute | Purpose |
|-----------|---------|
| `charset="UTF-8"` | Declares character encoding (supports all languages and symbols) |
| `name="viewport"` | Controls how the page scales on mobile devices |
| `width=device-width` | Page width matches the device screen width |
| `initial-scale=1.0` | No zoom on initial load |

---

### title

```html
<title>{% block title %}OnCall On-Demand{% endblock %}</title>
```

- Sets the browser tab title.
- Uses Jinja2 `{% block title %}` so child templates can override it.

---

### link (stylesheets)

```html
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"
      rel="stylesheet"
      integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YcnS..."
      crossorigin="anonymous">

<link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
```

| Attribute | Purpose |
|-----------|---------|
| `rel="stylesheet"` | Tells the browser this is a CSS file |
| `href="..."` | URL of the stylesheet |
| `integrity="sha384-..."` | Security hash — browser verifies the file hasn't been tampered with |
| `crossorigin="anonymous"` | Required when using `integrity` with CDN resources |

---

### script

```html
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"
        integrity="sha384-YvpcrYf0tY3lHB60NNkmXc5s9..."
        crossorigin="anonymous"></script>
```

- Loads JavaScript. Placed at the end of `<body>` so it doesn't block page rendering.
- Bootstrap's JS enables interactive components (dropdown menus, dismissible alerts, navbar toggler).

---

### nav (navigation bar)

```html
<nav class="navbar navbar-expand-lg navbar-dark bg-primary">
    <div class="container-fluid px-4">
        <a class="navbar-brand fw-bold" href="...">OnCall On-Demand</a>
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse"
                data-bs-target="#navbarNav">
            <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse" id="navbarNav">
            ...
        </div>
    </div>
</nav>
```

| Element / Class | Purpose |
|-----------------|---------|
| `<nav>` | Semantic HTML element for navigation sections |
| `navbar` | Bootstrap class that styles a navigation bar |
| `navbar-expand-lg` | Collapses to a hamburger menu below the `lg` breakpoint (992px) |
| `navbar-dark bg-primary` | White text on a blue background |
| `navbar-brand` | The logo / app name, styled larger |
| `navbar-toggler` | Hamburger button that appears on small screens |
| `data-bs-toggle="collapse"` | Bootstrap data attribute — tells JS to toggle the target element |
| `data-bs-target="#navbarNav"` | ID of the element to show/hide |
| `collapse navbar-collapse` | Content that collapses on mobile |

---

### div

```html
<div class="container-fluid px-4">...</div>
<div class="row g-4">...</div>
<div class="col-lg-6">...</div>
<div class="card shadow-sm">...</div>
<div class="alert alert-success">...</div>
<div class="d-flex align-items-center ms-auto">...</div>
```

- `<div>` is a generic container with no inherent meaning. It's the most-used HTML element for layout.
- All styling comes from CSS classes (especially Bootstrap classes).
- `<div>` does NOT display anything by itself — it's a box to group other elements.
- `d-flex` + `align-items-center` + `ms-auto` creates a flex container pushed to the right — used for the navbar's logout area.

---

### ul and li (lists)

```html
<ul class="navbar-nav me-auto mb-2 mb-lg-0">
    <li class="nav-item">
        <a class="nav-link" href="...">Dashboard</a>
    </li>
    <li class="nav-item">
        <a class="nav-link" href="...">Statistics</a>
    </li>
</ul>
```

| Tag | Purpose |
|-----|---------|
| `<ul>` | **U**nordered **l**ist (no numbers, just bullets — though Bootstrap removes the bullets for nav) |
| `<li>` | A single **l**ist **i**tem inside a `<ul>` or `<ol>` |
| `navbar-nav` | Bootstrap class that styles the list as navigation links |
| `nav-item` | Styles each list item as a nav element |
| `nav-link` | Styles the link inside each nav item |

---

### a (links)

```html
<a class="navbar-brand" href="{{ url_for('index') }}">OnCall On-Demand</a>
<a class="btn btn-outline-primary w-100" href="{{ url_for('stats') }}">View Statistics</a>
<a class="btn btn-light btn-sm px-3 py-1 fw-semibold" href="{{ url_for('logout') }}">Logout</a>
<a href="{{ url_for('login') }}">Sign in</a>
```

- `<a>` creates a hyperlink. `href` is the destination URL.
- Can be styled as a button using Bootstrap's `btn` classes.
- `btn-light` creates a white button (used for the Logout button in the dark navbar).
- `{{ url_for('function_name') }}` dynamically generates the correct URL.

---

### button

```html
<button type="submit" class="btn btn-primary btn-lg">
    <i class="bi bi-save me-1"></i>Save Entry
</button>

<button type="button" class="btn-close" data-bs-dismiss="alert"></button>

<button class="navbar-toggler" type="button" data-bs-toggle="collapse"
        data-bs-target="#navbarNav">
    <span class="navbar-toggler-icon"></span>
</button>
```

| Attribute | Purpose |
|-----------|---------|
| `type="submit"` | Submits the parent `<form>` when clicked |
| `type="button"` | Does nothing by default — requires JavaScript or Bootstrap data attributes |
| `class="btn btn-primary"` | Bootstrap styled button (blue) |
| `class="btn btn-lg"` | Larger button size |
| `data-bs-dismiss="alert"` | Bootstrap: closes the parent alert when clicked |

---

### span

```html
<span class="text-light opacity-75 me-3">
    <i class="bi bi-person-circle me-1"></i>{{ session['username'] }}
</span>

<span class="badge bg-danger">{{ entry.oncall_primary_date }}</span>
```

- `<span>` is an inline container (unlike `<div>` which is block-level).
- Used to style a piece of text within a line without breaking the flow.
- Common with Bootstrap badges, labels, and inline styling.

---

### i (icons)

```html
<i class="bi bi-telephone-inbound-fill me-2"></i>
<i class="bi bi-calendar-check me-1"></i>
<i class="bi bi-save me-1"></i>
```

- `<i>` is traditionally the "italic" tag, but Bootstrap Icons repurposes it for icon display.
- `bi bi-icon-name` loads the icon from the Bootstrap Icons font.
- `me-1`, `me-2` adds right margin (margin-end) for spacing between the icon and text.

---

### main

```html
<main class="container-lg mt-4 px-4">
    {% block content %}{% endblock %}
</main>
```

- `<main>` is a semantic HTML element representing the dominant content of the page.
- There should be only one `<main>` per page.
- `container-lg` is a Bootstrap class that centers and constrains content width.

---

### footer and small

```html
<footer class="text-center text-muted py-4 mt-5 border-top">
    <small>&copy; 2026 OnCall On-Demand</small>
</footer>
```

| Tag | Purpose |
|-----|---------|
| `<footer>` | Semantic element for page footer content |
| `<small>` | Renders text in a smaller font size |
| `&copy;` | HTML entity for the copyright symbol © |

---

### form

```html
<form method="POST" action="{{ url_for('dashboard') }}">
    <table class="table table-borderless mb-0">
        <tbody>
            <tr>
                <td class="text-end" style="width:40%">
                    <label>User Name</label>
                </td>
                <td>
                    <input type="text" class="form-control" name="username" required>
                </td>
            </tr>
            <!-- more rows ... -->
        </tbody>
    </table>
</form>

<form method="GET" action="{{ url_for('stats') }}">
    <!-- query parameters -->
</form>
```

| Attribute | Purpose |
|-----------|---------|
| `method="POST"` | Sends form data in the request body (for creating/updating data) |
| `method="GET"` | Sends data as URL query parameters (for reading/searching) |
| `action="..."` | The URL to submit the form to |

Forms in this app use a `table-borderless` table for layout, placing labels on the left (right-aligned) and inputs on the right with equal row spacing.

---

### label

```html
<label for="username" class="form-label mb-0">User Name</label>
<input type="text" id="username" name="username">
```

- `<label>` associates text with a form input.
- `for="username"` must match the `id` of the input it labels.
- Clicking the label focuses the input (accessibility feature).
- `form-label` is Bootstrap styling; `mb-0` removes bottom margin when used in a table layout.

---

### input

```html
<input type="text" class="form-control" id="username" name="username"
       value="{{ username }}" required>

<input type="password" class="form-control" id="password" name="password"
       placeholder="Enter your password" required>

<input type="date" class="form-control form-control-lg" id="oncall_primary_date"
       name="oncall_primary_date" required>

<input type="number" class="form-control form-control-sm" id="year"
       name="year" value="{{ year }}" min="2020" max="2099">
```

| Attribute | Purpose |
|-----------|---------|
| `type="text"` | Plain text input |
| `type="password"` | Text is hidden (dots/asterisks) |
| `type="date"` | Shows a date picker |
| `type="number"` | Only allows numbers; shows increment/decrement arrows |
| `name="..."` | The key used when submitting the form (maps to `request.form["name"]`) |
| `id="..."` | Unique identifier on the page (used by `<label for="...">`) |
| `value="..."` | Pre-fills the input with a value |
| `placeholder="..."` | Grey hint text shown when the input is empty |
| `required` | Browser won't submit the form unless this field is filled |
| `min`, `max` | Minimum/maximum values for number inputs |
| `minlength` | Minimum character count for text inputs |

---

### table, thead, tbody, tr, th, td

Tables are used in two ways in this app: **data display** (on-call entries list) and **form layout** (label-left, input-right).

**Data table (entries list):**
```html
<table class="table table-striped table-hover mb-0 align-middle">
    <thead class="table-light">
        <tr>
            <th class="px-4 py-3">Employee ID</th>
            <th class="px-4 py-3">Primary Date</th>
            <th class="px-4 py-3">Secondary Date</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td class="px-4 py-3">ADMIN-001</td>
            <td class="px-4 py-3"><span class="badge bg-danger">2026-04-07</span></td>
            <td class="px-4 py-3"><span class="badge bg-warning text-dark">2026-04-14</span></td>
        </tr>
    </tbody>
</table>
```

**Form layout table (label left, input right):**
```html
<table class="table table-borderless mb-0">
    <tbody>
        <tr>
            <td class="ps-0 pe-3 py-3 text-end" style="width:35%">
                <label for="username" class="form-label mb-0">Username</label>
            </td>
            <td class="ps-3 pe-0 py-3">
                <input type="text" class="form-control" id="username" name="username" required>
            </td>
        </tr>
    </tbody>
</table>
```

| Tag / Class | Purpose |
|-------------|---------|
| `<table>` | Creates a data table or a layout grid |
| `<thead>` | Table header section (column titles) — used in data tables only |
| `<tbody>` | Table body section (data rows) |
| `<tr>` | A single table **r**ow |
| `<th>` | A header cell (bold, centered by default) |
| `<td>` | A data cell |
| `table-striped` | Alternating row colors for readability |
| `table-hover` | Highlights row on mouse hover |
| `table-borderless` | Removes all borders — used for form layouts so it looks clean |
| `table-light` | Light background for the header |
| `text-end` | Right-aligns text (used to push labels to the right in form layout) |
| `px-4 py-3` | Padding (horizontal 4 units, vertical 3 units) |
| `ps-0 pe-3` | Padding-start 0, padding-end 3 (controls spacing between label and input columns) |

---

### h1–h6 (headings)

```html
<h3 class="card-title text-center mb-4">Sign In</h3>
<h4 class="text-center mb-4">{{ username }} — Year {{ year }}</h4>
<h5 class="mb-0">Add On-Call Entry</h5>
<h6 class="card-subtitle text-muted mb-2">Primary Shifts</h6>
```

- `<h1>` through `<h6>` are heading elements (h1 is largest, h6 is smallest).
- Used for titles, section headers, and card headers.
- `mb-0`, `mb-2`, `mb-4` control bottom margin spacing.

---

### p (paragraph)

```html
<p class="display-4 text-danger fw-bold">{{ stats.primary_count }}</p>
<p class="text-center mb-0">Don't have an account? <a href="...">Register here</a></p>
<p class="mt-2">No on-call entries yet.</p>
```

- `<p>` creates a paragraph block with automatic spacing above and below.
- `display-4` makes text very large (Bootstrap display heading).
- `text-danger` makes text red; `fw-bold` makes it bold.

---

### hr (horizontal rule)

```html
<hr>
```

- Draws a horizontal line across the page. Used as a visual separator between sections.

---

### Bootstrap CSS Classes

Bootstrap classes used throughout the templates:

| Category | Classes | Purpose |
|----------|---------|---------|
| **Layout** | `container`, `container-fluid`, `container-lg` | Centers content with max-width constraints |
| **Grid** | `row`, `col-md-6`, `col-lg-6`, `col-md-4` | Responsive grid system (12 columns) |
| **Spacing** | `mt-4`, `mb-3`, `px-4`, `py-3`, `me-1`, `ms-auto`, `g-3`, `g-4` | Margin (m) and padding (p) for top/bottom/left/right/x/y |
| **Text** | `text-center`, `text-muted`, `text-white`, `text-light`, `text-dark` | Text alignment and color |
| **Font** | `fw-bold`, `fw-semibold`, `opacity-75` | Font weight and opacity |
| **Flexbox** | `d-flex`, `justify-content-between`, `align-items-center`, `gap-2` | Flexible layouts |
| **Cards** | `card`, `card-header`, `card-body`, `card-title`, `card-subtitle`, `shadow-sm` | Card component with header, body, and shadow |
| **Alerts** | `alert`, `alert-success`, `alert-danger`, `alert-warning`, `alert-dismissible` | Notification banners |
| **Buttons** | `btn`, `btn-primary`, `btn-light`, `btn-outline-primary`, `btn-lg`, `btn-sm`, `w-100` | Styled buttons |
| **Badges** | `badge`, `bg-danger`, `bg-warning` | Small colored labels |
| **Forms** | `form-control`, `form-control-lg`, `form-control-sm`, `form-label` | Styled form elements |
| **Tables** | `table`, `table-striped`, `table-hover`, `table-borderless`, `table-responsive`, `table-light`, `align-middle` | Styled data tables and form layouts |
| **Borders** | `border-top`, `border-danger`, `border-warning`, `border-primary` | Border styling |
| **Display** | `h-100`, `w-100` | 100% height / width |

**Spacing notation:** `{property}{side}-{size}` where:
- Property: `m` (margin), `p` (padding)
- Side: `t` (top), `b` (bottom), `s` (start/left), `e` (end/right), `x` (left+right), `y` (top+bottom)
- Size: `0` through `5`, or `auto`

Example: `mt-4` = margin-top size 4, `px-3` = padding left+right size 3

---

## Jinja2 Template Syntax

### Template Inheritance (extends, block, endblock)

**base.html (parent):**
```html
<title>{% block title %}OnCall On-Demand{% endblock %}</title>
<body>
    {% block content %}{% endblock %}
</body>
```

**login.html (child):**
```html
{% extends "base.html" %}
{% block title %}Login — OnCall On-Demand{% endblock %}

{% block content %}
<div>Login form here...</div>
{% endblock %}
```

- `{% extends "base.html" %}` makes the child template inherit everything from the parent.
- `{% block name %}...{% endblock %}` defines a replaceable section.
- The child overrides only the blocks it needs — everything else comes from the parent.

---

### Variables ({{ }})

```html
{{ session['username'] }}
{{ username }}
{{ year }}
{{ entry.employee_id }}
{{ entry.oncall_primary_date }}
{{ stats.primary_count }}
{{ message }}
```

- `{{ expression }}` outputs the value of a Python expression into the HTML.
- Variables come from `render_template(...)` arguments or Flask globals like `session`.

---

### Control Flow (if, endif, for, endfor)

**Conditional rendering:**
```html
{% if session.get('username') %}
    <span>Welcome, {{ session['username'] }}</span>
{% endif %}

{% if entries %}
    <table>...</table>
{% else %}
    <p>No entries yet.</p>
{% endif %}

{% if stats.get('error') %}
    <div class="alert alert-warning">{{ stats.error }}</div>
{% endif %}
```

**Loops:**
```html
{% for entry in entries %}
<tr>
    <td>{{ entry.employee_id }}</td>
    <td>{{ entry.oncall_primary_date }}</td>
</tr>
{% endfor %}

{% for category, message in messages %}
<div class="alert alert-{{ category }}">{{ message }}</div>
{% endfor %}
```

- `{% if condition %}...{% endif %}` — conditionally render HTML.
- `{% for item in list %}...{% endfor %}` — loop over a list.
- `{% else %}` — optional fallback for both `if` and `for`.
- Note: `alert-{{ category }}` dynamically builds a CSS class name.

---

### with / endwith

```html
{% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
        {% for category, message in messages %}
            <div class="alert alert-{{ category }}">{{ message }}</div>
        {% endfor %}
    {% endif %}
{% endwith %}
```

- `{% with %}` creates a local scope — the variable `messages` only exists within this block.
- `get_flashed_messages(with_categories=true)` retrieves flash messages set via `flash()` in Python, returning `(category, message)` tuples.

---

### url_for()

```html
{{ url_for('index') }}            →  /
{{ url_for('login') }}            →  /login
{{ url_for('dashboard') }}        →  /dashboard
{{ url_for('stats') }}            →  /stats
{{ url_for('logout') }}           →  /logout
{{ url_for('static', filename='style.css') }}  →  /static/style.css
```

- Generates URLs dynamically based on Flask route function names.
- Avoids hardcoded paths — if you change a route, all links update automatically.

---

### Filters and Methods

```html
{{ now().year if now is defined else 2026 }}
```

- `now()` is a function call (if provided by the app).
- `is defined` tests if a variable exists.
- `if ... else ...` is Jinja2's inline conditional (ternary) expression.

---

## Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--access-logfile", "-", "app:app"]
```

| Instruction | Purpose |
|-------------|---------|
| `FROM python:3.12-slim` | Base image — Python 3.12 on a minimal Debian Linux |
| `WORKDIR /app` | Set the working directory inside the container |
| `COPY requirements.txt .` | Copy dependencies list first (for Docker layer caching) |
| `RUN pip install ...` | Install Python packages; `--no-cache-dir` reduces image size |
| `COPY . .` | Copy all application code into the container |
| `EXPOSE 5000` | Documents that the container listens on port 5000 (informational only) |
| `CMD [...]` | The command to run when the container starts |

---

## Gunicorn (WSGI Server)

```
gunicorn --bind 0.0.0.0:5000 --workers 2 --access-logfile - app:app
```

| Flag | Purpose |
|------|---------|
| `--bind 0.0.0.0:5000` | Listen on all interfaces, port 5000 |
| `--workers 2` | Run 2 worker processes to handle requests in parallel |
| `--access-logfile -` | Print access logs to stdout (captured by Docker/Kubernetes) |
| `app:app` | Load the `app` object from the `app.py` module |

Flask's built-in server (`app.run()`) is single-threaded and meant for development only. Gunicorn is a production-grade WSGI server that handles concurrent requests, worker management, and graceful restarts.

---

## requirements.txt

```
Flask==3.1.0
pymongo==4.10.1
Werkzeug==3.1.3
requests==2.32.3
gunicorn==23.0.0
```

| Package | Purpose |
|---------|---------|
| **Flask** | Web framework for routing, templates, sessions |
| **pymongo** | MongoDB driver for Python |
| **Werkzeug** | WSGI toolkit (Flask dependency); also provides password hashing |
| **requests** | HTTP client for calling the calculator service |
| **gunicorn** | Production WSGI server |

Versions are pinned with `==` for reproducible builds — every install gets exactly the same versions.
