import os
import re
import sqlite3
from typing import Any

import mysql.connector
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from mysql.connector import Error

load_dotenv()

app = Flask(__name__)
CORS(app)
app.config["JSON_SORT_KEYS"] = False

def get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default

    try:
        return int(value)
    except (TypeError, ValueError):
        app_logger = app.logger if "app" in globals() else None
        if app_logger is not None:
            app_logger.warning("Invalid %s value '%s'. Using default %s.", name, value, default)
        return default


DB_HOST = (os.getenv("DB_HOST") or "localhost").strip()
if DB_HOST in ("", "0.0.0.0"):
    DB_HOST = "localhost"

DB_PORT = get_int_env("DB_PORT", 3306)
DB_USER = (os.getenv("DB_USER") or "root").strip()
DB_PASSWORD = os.getenv("DB_PASSWORD") or ""
DB_NAME = (os.getenv("DB_NAME") or "street_racer_db").strip()
DB_FILE = os.path.join(os.path.dirname(__file__), "data", "street_racer.db")
os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)

MYSQL_READY = False


def normalize_player_name(raw_name: Any) -> str:
    if raw_name is None:
        raise ValueError("Player name is required.")

    clean_name = str(raw_name).strip()
    clean_name = re.sub(r"\s+", " ", clean_name)

    if not clean_name:
        raise ValueError("Player name is required.")

    if len(clean_name) < 3 or len(clean_name) > 20:
        raise ValueError("Player name must be between 3 and 20 characters long.")

    if not re.fullmatch(r"[A-Za-z0-9 _-]+", clean_name):
        raise ValueError("Player name can only contain letters, numbers, spaces, underscores, and hyphens.")

    return clean_name


def get_sqlite_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def create_sqlite_tables() -> None:
    conn = get_sqlite_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                score INTEGER NOT NULL,
                distance INTEGER NOT NULL,
                coins INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def ensure_mysql_database() -> bool:
    global MYSQL_READY

    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            autocommit=True,
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.database = DB_NAME
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS players (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(50) NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS scores (
                id INT AUTO_INCREMENT PRIMARY KEY,
                player_id INT NOT NULL,
                score INT NOT NULL,
                distance INT NOT NULL,
                coins INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_score ON scores(score DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_player_name ON players(name)")
        conn.commit()
        MYSQL_READY = True
        return True
    except Error as exc:
        MYSQL_READY = False
        app.logger.warning("MySQL is unavailable. Falling back to SQLite for local testing. %s", exc)
        return False
    finally:
        if "conn" in locals() and conn is not None:
            conn.close()


def initialize_database() -> None:
    if ensure_mysql_database():
        return
    create_sqlite_tables()


initialize_database()


def get_db_connection():
    if MYSQL_READY:
        return mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            autocommit=True,
        )

    return get_sqlite_connection()


def get_player_by_name(conn, name: str):
    if MYSQL_READY:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, name FROM players WHERE name = %s LIMIT 1", (name,))
        return cursor.fetchone()

    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM players WHERE name = ? LIMIT 1", (name,))
    row = cursor.fetchone()
    if row is None:
        return None
    return {"id": row[0], "name": row[1]}


def get_player_profile(conn, name: str):
    name = normalize_player_name(name)

    if MYSQL_READY:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT p.id, p.name,
                   COALESCE(MAX(s.score), 0) AS best_score,
                   COALESCE(COUNT(s.id), 0) AS games_played,
                   COALESCE(SUM(s.coins), 0) AS total_coins,
                   COALESCE(MAX(s.distance), 0) AS best_distance
            FROM players p
            LEFT JOIN scores s ON s.player_id = p.id
            WHERE p.name = %s
            GROUP BY p.id, p.name
            LIMIT 1
            """,
            (name,),
        )
        return cursor.fetchone()

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT p.id, p.name,
               COALESCE(MAX(s.score), 0) AS best_score,
               COALESCE(COUNT(s.id), 0) AS games_played,
               COALESCE(SUM(s.coins), 0) AS total_coins,
               COALESCE(MAX(s.distance), 0) AS best_distance
        FROM players p
        LEFT JOIN scores s ON s.player_id = p.id
        WHERE p.name = ?
        GROUP BY p.id, p.name
        LIMIT 1
        """,
        (name,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "name": row[1],
        "best_score": row[2],
        "games_played": row[3],
        "total_coins": row[4],
        "best_distance": row[5],
    }


def normalize_score_row(row):
    if isinstance(row, dict):
        return {
            "name": row.get("name"),
            "score": row.get("score"),
            "distance": row.get("distance"),
            "coins": row.get("coins"),
            "created_at": row.get("created_at"),
        }

    return {
        "name": row[0],
        "score": row[1],
        "distance": row[2],
        "coins": row[3],
        "created_at": row[4],
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/register", methods=["POST"])
def register_player():
    data = request.get_json(silent=True) or {}

    try:
        player_name = normalize_player_name(data.get("name"))
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400

    conn = get_db_connection()
    try:
        existing = get_player_by_name(conn, player_name)
        if existing:
            return jsonify(
                {
                    "success": True,
                    "player": {"id": existing["id"], "name": existing["name"]},
                    "message": "Player already exists. Logged in.",
                }
            ), 200

        if MYSQL_READY:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO players (name, created_at) VALUES (%s, NOW())", (player_name,))
            player_id = cursor.lastrowid
            conn.commit()
        else:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO players (name, created_at) VALUES (?, datetime('now'))", (player_name,))
            player_id = cursor.lastrowid
            conn.commit()

        return jsonify(
            {
                "success": True,
                "player": {"id": player_id, "name": player_name},
                "message": "Player registered successfully.",
            }
        ), 201

    except mysql.connector.Error as exc:
        app.logger.error("Database error in register_player: %s", exc)
        return jsonify({"success": False, "message": "Database error while registering player."}), 500
    except sqlite3.Error as exc:
        app.logger.error("SQLite error in register_player: %s", exc)
        return jsonify({"success": False, "message": "Database error while registering player."}), 500
    finally:
        conn.close()


@app.route("/api/login", methods=["POST"])
def login_player():
    data = request.get_json(silent=True) or {}

    try:
        player_name = normalize_player_name(data.get("name"))
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400

    conn = get_db_connection()
    try:
        player = get_player_by_name(conn, player_name)
        if not player:
            return jsonify({"success": False, "message": "Player not found. Please register first."}), 404

        profile = get_player_profile(conn, player_name)
        return jsonify({"success": True, "player": player, "profile": profile}), 200

    except mysql.connector.Error as exc:
        app.logger.error("Database error in login_player: %s", exc)
        return jsonify({"success": False, "message": "Database error while logging in."}), 500
    except sqlite3.Error as exc:
        app.logger.error("SQLite error in login_player: %s", exc)
        return jsonify({"success": False, "message": "Database error while logging in."}), 500
    finally:
        conn.close()


@app.route("/api/scores", methods=["POST"])
def save_score():
    data = request.get_json(silent=True) or {}
    player_name = data.get("player_name")
    score = data.get("score")
    distance = data.get("distance")
    coins = data.get("coins")

    try:
        player_name = normalize_player_name(player_name)
        score = int(score)
        distance = int(distance)
        coins = int(coins)
    except (TypeError, ValueError) as exc:
        return jsonify({"success": False, "message": f"Invalid score payload: {exc}"}), 400

    if score < 0 or distance < 0 or coins < 0:
        return jsonify({"success": False, "message": "Score values cannot be negative."}), 400

    conn = get_db_connection()
    try:
        player = get_player_by_name(conn, player_name)
        if not player:
            # Automatically create the player if the name was not previously stored.
            if MYSQL_READY:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO players (name, created_at) VALUES (%s, NOW())", (player_name,))
                player_id = cursor.lastrowid
                conn.commit()
            else:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO players (name, created_at) VALUES (?, datetime('now'))", (player_name,))
                player_id = cursor.lastrowid
                conn.commit()
            player = {"id": player_id, "name": player_name}

        if MYSQL_READY:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO scores (player_id, score, distance, coins, created_at) VALUES (%s, %s, %s, %s, NOW())",
                (player["id"], score, distance, coins),
            )
            conn.commit()
        else:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO scores (player_id, score, distance, coins, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
                (player["id"], score, distance, coins),
            )
            conn.commit()

        best_score = get_player_profile(conn, player_name)
        return jsonify(
            {
                "success": True,
                "message": "Score saved successfully.",
                "player": player,
                "best_score": best_score["best_score"] if best_score else 0,
            }
        ), 201

    except mysql.connector.Error as exc:
        app.logger.error("Database error in save_score: %s", exc)
        return jsonify({"success": False, "message": "Database error while saving score."}), 500
    except sqlite3.Error as exc:
        app.logger.error("SQLite error in save_score: %s", exc)
        return jsonify({"success": False, "message": "Database error while saving score."}), 500
    finally:
        conn.close()


@app.route("/api/scores", methods=["GET"])
def get_scores():
    conn = get_db_connection()
    try:
        if MYSQL_READY:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT p.name, s.score, s.distance, s.coins, s.created_at
                FROM scores s
                INNER JOIN players p ON p.id = s.player_id
                ORDER BY s.score DESC, s.distance DESC, s.coins DESC, s.created_at DESC
                LIMIT 50
                """
            )
            rows = cursor.fetchall()
        else:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT p.name, s.score, s.distance, s.coins, s.created_at
                FROM scores s
                INNER JOIN players p ON p.id = s.player_id
                ORDER BY s.score DESC, s.distance DESC, s.coins DESC, s.created_at DESC
                LIMIT 50
                """
            )
            rows = [
                {"name": row[0], "score": row[1], "distance": row[2], "coins": row[3], "created_at": row[4]}
                for row in cursor.fetchall()
            ]

        scores = []
        for index, row in enumerate(rows, start=1):
            entry = normalize_score_row(row)
            scores.append({
                "rank": index,
                "player_name": entry["name"],
                "score": entry["score"],
                "distance": entry["distance"],
                "coins": entry["coins"],
                "date": (
                    entry["created_at"].strftime("%Y-%m-%d %H:%M:%S")
                    if hasattr(entry["created_at"], "strftime")
                    else entry["created_at"]
                ),
            })

        return jsonify({"success": True, "scores": scores}), 200

    except mysql.connector.Error as exc:
        app.logger.error("Database error in get_scores: %s", exc)
        return jsonify({"success": False, "message": "Database error while fetching scores."}), 500
    except sqlite3.Error as exc:
        app.logger.error("SQLite error in get_scores: %s", exc)
        return jsonify({"success": False, "message": "Database error while fetching scores."}), 500
    finally:
        conn.close()


@app.route("/api/scores/top", methods=["GET"])
def get_top_scores():
    conn = get_db_connection()
    try:
        if MYSQL_READY:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT p.name, s.score, s.distance, s.coins, s.created_at
                FROM scores s
                INNER JOIN players p ON p.id = s.player_id
                ORDER BY s.score DESC, s.distance DESC, s.coins DESC, s.created_at DESC
                LIMIT 10
                """
            )
            rows = cursor.fetchall()
        else:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT p.name, s.score, s.distance, s.coins, s.created_at
                FROM scores s
                INNER JOIN players p ON p.id = s.player_id
                ORDER BY s.score DESC, s.distance DESC, s.coins DESC, s.created_at DESC
                LIMIT 10
                """
            )
            rows = [
                {"name": row[0], "score": row[1], "distance": row[2], "coins": row[3], "created_at": row[4]}
                for row in cursor.fetchall()
            ]

        leaderboard = []
        for index, row in enumerate(rows, start=1):
            entry = normalize_score_row(row)
            leaderboard.append({
                "rank": index,
                "player_name": entry["name"],
                "score": entry["score"],
                "distance": entry["distance"],
                "coins": entry["coins"],
                "date": (
                    entry["created_at"].strftime("%Y-%m-%d %H:%M:%S")
                    if hasattr(entry["created_at"], "strftime")
                    else entry["created_at"]
                ),
            })

        return jsonify({"success": True, "leaderboard": leaderboard}), 200

    except mysql.connector.Error as exc:
        app.logger.error("Database error in get_top_scores: %s", exc)
        return jsonify({"success": False, "message": "Database error while fetching leaderboard."}), 500
    except sqlite3.Error as exc:
        app.logger.error("SQLite error in get_top_scores: %s", exc)
        return jsonify({"success": False, "message": "Database error while fetching leaderboard."}), 500
    finally:
        conn.close()


@app.route("/api/player", methods=["GET"])
def get_player_by_query():
    player_name = request.args.get("name", "").strip()
    if not player_name:
        return jsonify({"success": False, "message": "Player name query parameter is required."}), 400
    return get_player_detail(player_name)


@app.route("/api/player/<string:player_name>", methods=["GET"])
def get_player_detail(player_name: str):
    try:
        player_name = normalize_player_name(player_name)
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400

    conn = get_db_connection()
    try:
        profile = get_player_profile(conn, player_name)
        if not profile:
            return jsonify({"success": False, "message": "Player not found."}), 404
        return jsonify({"success": True, "player": profile}), 200
    except mysql.connector.Error as exc:
        app.logger.error("Database error in get_player_detail: %s", exc)
        return jsonify({"success": False, "message": "Database error while fetching player profile."}), 500
    except sqlite3.Error as exc:
        app.logger.error("SQLite error in get_player_detail: %s", exc)
        return jsonify({"success": False, "message": "Database error while fetching player profile."}), 500
    finally:
        conn.close()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
