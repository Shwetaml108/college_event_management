import tempfile
import unittest
from pathlib import Path

from app import EventError, create_event, delete_event, initialize_database, list_events, set_rsvp, update_event


def sample_event(**overrides):
    event = {
        "title": "Open Mic",
        "description": "An evening of performances",
        "category": "Arts",
        "location": "Main Hall",
        "start_at": "2030-05-10T18:30",
        "organizer": "Arts Club",
        "capacity": 2,
    }
    return {**event, **overrides}


class EventApiDataTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        initialize_database(self.db_path, seed=False)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_and_update_event(self):
        event = create_event(sample_event(), self.db_path)
        self.assertEqual(len(list_events(db_path=self.db_path)), 1)
        updated = update_event(event["id"], sample_event(title="Open Mic Night"), self.db_path)
        self.assertEqual(updated["title"], "Open Mic Night")
        self.assertEqual(list_events(db_path=self.db_path)[0]["title"], "Open Mic Night")

    def test_rsvp_is_unique_and_capacity_is_enforced(self):
        event = create_event(sample_event(capacity=1), self.db_path)
        first = set_rsvp(event["id"], "student-one", True, self.db_path)
        repeated = set_rsvp(event["id"], "student-one", True, self.db_path)
        self.assertEqual(first["rsvp_count"], 1)
        self.assertEqual(repeated["rsvp_count"], 1)
        self.assertEqual(list_events("student-one", self.db_path)[0]["attending"], 1)
        with self.assertRaisesRegex(EventError, "full"):
            set_rsvp(event["id"], "student-two", True, self.db_path)
        set_rsvp(event["id"], "student-one", False, self.db_path)
        self.assertEqual(list_events("student-one", self.db_path)[0]["rsvp_count"], 0)

    def test_delete_removes_event(self):
        event = create_event(sample_event(), self.db_path)
        delete_event(event["id"], self.db_path)
        self.assertEqual(list_events(db_path=self.db_path), [])
        with self.assertRaisesRegex(EventError, "not found"):
            delete_event(event["id"], self.db_path)

    def test_invalid_capacity_and_overbooking_edit_are_rejected(self):
        with self.assertRaisesRegex(EventError, "Capacity"):
            create_event(sample_event(capacity=0), self.db_path)
        event = create_event(sample_event(capacity=2), self.db_path)
        set_rsvp(event["id"], "student-one", True, self.db_path)
        set_rsvp(event["id"], "student-two", True, self.db_path)
        with self.assertRaisesRegex(EventError, "lower than"):
            update_event(event["id"], sample_event(capacity=1), self.db_path)


if __name__ == "__main__":
    unittest.main()
