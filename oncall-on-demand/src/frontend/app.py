import os
import logging
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from werkzeug.security import generate_password_hash, check_password_hash
import requests as http_requests

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("frontend")

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://mongodb:27017")
CALCULATOR_URL = os.environ.get("CALCULATOR_URL", "http://calculator:5001")
DB_NAME = os.environ.get("DB_NAME", "oncall_db")

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client[DB_NAME]
users_col = db["users"]
oncall_col = db["oncall_entries"]


def seed_default_admin():
    """Ensure a default admin user always exists."""
    try:
        users_col.update_one(
            {"username": "admin"},
            {
                "$setOnInsert": {
                    "username": "admin",
                    "password": generate_password_hash("admin"),
                    "employee_id": "ADMIN-001",
                    "created_at": datetime.utcnow(),
                }
            },
            upsert=True,
        )
        logger.info("Default admin user ensured (admin/admin)")
    except DuplicateKeyError:
        logger.info("Default admin user already exists")


with app.app_context():
    seed_default_admin()


@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        logger.info("Login attempt for user: %s", username)

        user = users_col.find_one({"username": username})
        if user and check_password_hash(user["password"], password):
            session["username"] = username
            session["employee_id"] = user.get("employee_id", "")
            logger.info("Login successful for user: %s", username)
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))

        logger.warning("Failed login attempt for user: %s", username)
        flash("Invalid username or password.", "danger")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        employee_id = request.form.get("employee_id", "").strip()

        if users_col.find_one({"username": username}):
            flash("Username already exists.", "danger")
            return render_template("register.html")

        users_col.insert_one(
            {
                "username": username,
                "password": generate_password_hash(password),
                "employee_id": employee_id,
                "created_at": datetime.utcnow(),
            }
        )
        logger.info("New user registered: %s (id: %s)", username, employee_id)
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "username" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        employee_id = request.form.get("employee_id", "").strip()
        primary_date = request.form.get("oncall_primary_date", "")
        secondary_date = request.form.get("oncall_secondary_date", "")

        entry = {
            "username": username,
            "employee_id": employee_id,
            "oncall_primary_date": primary_date,
            "oncall_secondary_date": secondary_date,
            "created_at": datetime.utcnow(),
        }
        oncall_col.insert_one(entry)
        logger.info(
            "Oncall entry saved — user: %s, primary: %s, secondary: %s",
            username,
            primary_date,
            secondary_date,
        )
        flash("On-call entry saved successfully!", "success")

    entries = list(
        oncall_col.find({"username": session["username"]}, {"_id": 0}).sort(
            "created_at", -1
        )
    )

    return render_template(
        "dashboard.html",
        username=session["username"],
        employee_id=session.get("employee_id", ""),
        entries=entries,
    )


@app.route("/stats")
def stats():
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]
    year = request.args.get("year", datetime.now().year, type=int)

    try:
        logger.info("Requesting stats from calculator — user: %s, year: %d", username, year)
        resp = http_requests.get(
            f"{CALCULATOR_URL}/api/calculate/{username}",
            params={"year": year},
            timeout=5,
        )
        resp.raise_for_status()
        stats_data = resp.json()
        logger.info("Stats received for %s: %s", username, stats_data)
    except http_requests.exceptions.RequestException as exc:
        logger.error("Calculator service error for %s: %s", username, exc)
        stats_data = {"error": str(exc), "primary_count": 0, "secondary_count": 0, "total_shifts": 0}
        flash("Could not retrieve statistics from calculator service.", "warning")

    return render_template("stats.html", username=username, year=year, stats=stats_data)


@app.route("/logout")
def logout():
    username = session.get("username", "unknown")
    session.clear()
    logger.info("User logged out: %s", username)
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))


@app.route("/health")
def health():
    try:
        client.admin.command("ping")
        mongo_status = "connected"
    except Exception:
        mongo_status = "disconnected"
    return {"status": "healthy", "service": "frontend", "mongodb": mongo_status}, 200


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=5000, debug=debug)
