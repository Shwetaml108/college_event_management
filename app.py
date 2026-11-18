#!/usr/bin/env python3
import json
import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "static"
DB_PATH = Path(os.environ.get("EVENTS_DB", ROOT / "data" / "events.db"))
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
CATEGORIES = {"Academic", "Arts", "Career", "Community", "Sports", "Tech"}


class EventError(ValueError):
    pass


def connect(db_path=DB_PATH):
    connection = sqlite3.connect(db_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(db_path=DB_PATH, seed=True):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with closing(connect(db_path)) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                location TEXT NOT NULL,
                start_at TEXT NOT NULL,
                organizer TEXT NOT NULL,
                capacity INTEGER NOT NULL CHECK (capacity > 0),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS rsvps (
                event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                attendee_id TEXT NOT NULL,
                PRIMARY KEY (event_id, attendee_id)
            );
            """
        )
        if seed and db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0:
            now = datetime.now().replace(second=0, microsecond=0)
            samples = [
                ("Welcome Week: Club Fair", "Meet the people behind 40+ student clubs and find your next campus community.", "Community", "Student Union Lawn", 2, "Student Life Office", 180),
                ("Build Night: Creative Coding", "A relaxed, beginner-friendly evening of playful experiments with code, visuals, and sound.", "Tech", "Innovation Lab 204", 4, "Campus Coders", 48),
                ("Spring Student Showcase", "An evening of live performances, original work, and creative collaboration from across campus.", "Arts", "Black Box Theater", 7, "Arts Council", 120),
                ("Internship Prep: Resume Studio", "Get practical feedback on your resume and learn how to make your experience stand out.", "Career", "Career Center", 10, "Career Services", 32),
            ]
            db.executemany(
                """INSERT INTO events
                   (id, title, description, category, location, start_at, organizer, capacity, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        str(uuid.uuid4()),
                        title,
                        description,
                        category,
                        location,
                        (now + timedelta(days=days)).isoformat(timespec="minutes"),
                        organizer,
                        capacity,
                        now.isoformat(timespec="minutes"),
                    )
                    for title, description, category, location, days, organizer, capacity in samples
                ],
            )
        db.commit()


def validate_event(data):
    if not isinstance(data, dict):
        raise EventError("Expected an event object.")
    fields = ("title", "description", "category", "location", "start_at", "organizer")
    event = {}
    limits = {"title": 100, "description": 1000, "location": 120, "organizer": 100}
    for field in fields:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise EventError(f"{field.replace('_', ' ').capitalize()} is required.")
        value = value.strip()
        if field in limits and len(value) > limits[field]:
            raise EventError(f"{field.replace('_', ' ').capitalize()} must be {limits[field]} characters or fewer.")
        event[field] = value
    if event["category"] not in CATEGORIES:
        raise EventError("Choose a valid event category.")
    try:
        parsed_date = datetime.fromisoformat(event["start_at"])
    except ValueError as exc:
        raise EventError("Enter a valid event date and time.") from exc
    event["start_at"] = parsed_date.isoformat(timespec="minutes")
    capacity = data.get("capacity")
    if isinstance(capacity, bool) or not isinstance(capacity, int) or not 1 <= capacity <= 100000:
        raise EventError("Capacity must be a whole number between 1 and 100000.")
    event["capacity"] = capacity
    return event


def list_events(attendee_id=None, db_path=DB_PATH):
    with closing(connect(db_path)) as db:
        rows = db.execute(
            """
            SELECT e.*, COUNT(r.attendee_id) AS rsvp_count,
                   MAX(CASE WHEN r.attendee_id = ? THEN 1 ELSE 0 END) AS attending
            FROM events e
            LEFT JOIN rsvps r ON r.event_id = e.id
            GROUP BY e.id
            ORDER BY e.start_at ASC
            """,
            (attendee_id or "",),
        ).fetchall()
        return [dict(row) for row in rows]


def create_event(data, db_path=DB_PATH):
    event = validate_event(data)
    event["id"] = str(uuid.uuid4())
    event["created_at"] = datetime.now().isoformat(timespec="minutes")
    with closing(connect(db_path)) as db:
        with db:
            db.execute(
                """INSERT INTO events
                   (id, title, description, category, location, start_at, organizer, capacity, created_at)
                   VALUES (:id, :title, :description, :category, :location, :start_at, :organizer, :capacity, :created_at)""",
                event,
            )
    return event


def update_event(event_id, data, db_path=DB_PATH):
    event = validate_event(data)
    with closing(connect(db_path)) as db:
        with db:
            cursor = db.execute(
                """UPDATE events SET title = :title, description = :description,
                   category = :category, location = :location, start_at = :start_at,
                   organizer = :organizer, capacity = :capacity WHERE id = :id""",
                {**event, "id": event_id},
            )
            if cursor.rowcount == 0:
                raise EventError("Event not found.")
            if event["capacity"] < db.execute(
                "SELECT COUNT(*) FROM rsvps WHERE event_id = ?", (event_id,)
            ).fetchone()[0]:
                raise EventError("Capacity cannot be lower than the current RSVP count.")
    return event


def delete_event(event_id, db_path=DB_PATH):
    with closing(connect(db_path)) as db:
        with db:
            cursor = db.execute("DELETE FROM events WHERE id = ?", (event_id,))
            if cursor.rowcount == 0:
                raise EventError("Event not found.")


def set_rsvp(event_id, attendee_id, attending, db_path=DB_PATH):
    if not isinstance(attendee_id, str) or not 1 <= len(attendee_id) <= 80:
        raise EventError("A valid attendee ID is required.")
    if not isinstance(attending, bool):
        raise EventError("Attending must be true or false.")
    with closing(connect(db_path)) as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            event = db.execute("SELECT capacity FROM events WHERE id = ?", (event_id,)).fetchone()
            if event is None:
                raise EventError("Event not found.")
            if attending:
                count = db.execute(
                    "SELECT COUNT(*) FROM rsvps WHERE event_id = ?", (event_id,)
                ).fetchone()[0]
                already_attending = db.execute(
                    "SELECT 1 FROM rsvps WHERE event_id = ? AND attendee_id = ?",
                    (event_id, attendee_id),
                ).fetchone()
                if not already_attending and count >= event["capacity"]:
                    raise EventError("This event is full.")
                db.execute(
                    "INSERT OR IGNORE INTO rsvps (event_id, attendee_id) VALUES (?, ?)",
                    (event_id, attendee_id),
                )
            else:
                db.execute(
                    "DELETE FROM rsvps WHERE event_id = ? AND attendee_id = ?",
                    (event_id, attendee_id),
                )
            count = db.execute(
                "SELECT COUNT(*) FROM rsvps WHERE event_id = ?", (event_id,)
            ).fetchone()[0]
            db.commit()
        except Exception:
            db.rollback()
            raise
    return {"attending": attending, "rsvp_count": count}


class EventHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def send_json(self, status, payload):
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 16384:
                raise EventError("Request body is too large.")
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise EventError("Request body must be valid JSON.") from exc
        if not isinstance(payload, dict):
            raise EventError("Request body must be a JSON object.")
        return payload

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/events":
            attendee_id = parse_qs(parsed.query).get("attendee_id", [""])[0]
            self.send_json(200, {"events": list_events(attendee_id)})
        elif parsed.path == "/api/health":
            self.send_json(200, {"status": "ok"})
        elif parsed.path.startswith("/api/"):
            self.send_json(404, {"error": "Not found."})
        else:
            if parsed.path == "/":
                self.path = "/index.html"
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            data = self.read_json()
            if parsed.path == "/api/events":
                self.send_json(201, {"event": create_event(data)})
                return
            parts = parsed.path.strip("/").split("/")
            if len(parts) == 4 and parts[:2] == ["api", "events"] and parts[3] == "rsvp":
                result = set_rsvp(parts[2], data.get("attendee_id"), data.get("attending"))
                self.send_json(200, result)
                return
            self.send_json(404, {"error": "Not found."})
        except EventError as exc:
            self.send_json(400, {"error": str(exc)})

    def do_PUT(self):
        parts = urlparse(self.path).path.strip("/").split("/")
        if len(parts) != 3 or parts[:2] != ["api", "events"]:
            self.send_json(404, {"error": "Not found."})
            return
        try:
            self.send_json(200, {"event": update_event(parts[2], self.read_json())})
        except EventError as exc:
            status = 404 if str(exc) == "Event not found." else 400
            self.send_json(status, {"error": str(exc)})

    def do_DELETE(self):
        parts = urlparse(self.path).path.strip("/").split("/")
        if len(parts) != 3 or parts[:2] != ["api", "events"]:
            self.send_json(404, {"error": "Not found."})
            return
        try:
            delete_event(parts[2])
            self.send_json(200, {"deleted": True})
        except EventError as exc:
            status = 404 if str(exc) == "Event not found." else 400
            self.send_json(status, {"error": str(exc)})

    def log_message(self, format_string, *args):
        print(f"{self.address_string()} - {format_string % args}")


if __name__ == "__main__":
    initialize_database()
    server = ThreadingHTTPServer((HOST, PORT), EventHandler)
    print(f"Campus Events is serving on http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()
