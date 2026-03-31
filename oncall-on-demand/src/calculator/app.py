import os
import logging
from datetime import datetime

from flask import Flask, jsonify, request
from pymongo import MongoClient

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("calculator")

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://mongodb:27017")
DB_NAME = os.environ.get("DB_NAME", "oncall_db")

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client[DB_NAME]
oncall_col = db["oncall_entries"]


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


@app.route("/api/calculate/<username>", methods=["GET"])
def calculate_oncall(username):
    year = request.args.get("year", datetime.now().year, type=int)
    logger.info("Calculating oncall stats — user: %s, year: %d", username, year)

    entries = list(oncall_col.find({"username": username}))
    logger.info("Found %d total entries for user %s", len(entries), username)

    primary_count = sum(
        1 for e in entries if _in_year(e.get("oncall_primary_date", ""), year)
    )
    secondary_count = sum(
        1 for e in entries if _in_year(e.get("oncall_secondary_date", ""), year)
    )

    result = {
        "username": username,
        "year": year,
        "primary_count": primary_count,
        "secondary_count": secondary_count,
        "total_shifts": primary_count + secondary_count,
    }

    logger.info(
        "Stats for %s (%d): primary=%d, secondary=%d, total=%d",
        username,
        year,
        primary_count,
        secondary_count,
        result["total_shifts"],
    )
    return jsonify(result), 200


@app.route("/api/health", methods=["GET"])
def health():
    try:
        client.admin.command("ping")
        mongo_status = "connected"
    except Exception:
        mongo_status = "disconnected"
    return jsonify({"status": "healthy", "service": "calculator", "mongodb": mongo_status}), 200


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=5001, debug=debug)
