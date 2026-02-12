"""
MongoDB database configuration and setup for Mergington High School API
"""

import os
from copy import deepcopy
from pymongo import MongoClient
from argon2 import PasswordHasher, exceptions as argon2_exceptions


class _UpdateResult:
    def __init__(self, modified_count):
        self.modified_count = modified_count


class _InMemoryCollection:
    def __init__(self):
        self._docs = {}

    def count_documents(self, query):
        # Avoid materializing all matching documents into a list; just count via iteration
        return sum(1 for _ in self.find(query))

    def insert_one(self, doc):
        document = deepcopy(doc)
        self._docs[document["_id"]] = document
        return {"inserted_id": document["_id"]}

    def find_one(self, query):
        if "_id" in query:
            doc = self._docs.get(query["_id"])
            return deepcopy(doc) if doc else None

        for doc in self.find(query):
            return doc

        return None

    def _matches(self, doc, query):
        if not query:
            return True

        for key, value in query.items():
            if key == "_id":
                if doc.get("_id") != value:
                    return False
                continue

            if key == "schedule_details.days":
                days = doc.get("schedule_details", {}).get("days", [])
                required = value.get("$in", [])
                if not any(day in days for day in required):
                    return False
                continue

            if key == "schedule_details.start_time":
                start_time = doc.get("schedule_details", {}).get("start_time")
                threshold = value.get("$gte")
                if threshold and (not start_time or start_time < threshold):
                    return False
                continue

            if key == "schedule_details.end_time":
                end_time = doc.get("schedule_details", {}).get("end_time")
                threshold = value.get("$lte")
                if threshold and (not end_time or end_time > threshold):
                    return False
                continue

            if doc.get(key) != value:
                return False

        return True

    def find(self, query=None):
        for doc in self._docs.values():
            if self._matches(doc, query or {}):
                yield deepcopy(doc)

    def update_one(self, query, update):
        document_id = query.get("_id")
        if document_id not in self._docs:
            return _UpdateResult(modified_count=0)

        doc = self._docs[document_id]
        modified = 0

        if "$push" in update:
            for key, value in update["$push"].items():
                array = doc.setdefault(key, [])
                array.append(value)
                modified = 1

        if "$pull" in update:
            for key, value in update["$pull"].items():
                array = doc.get(key, [])
                new_array = [item for item in array if item != value]
                if new_array != array:
                    doc[key] = new_array
                    modified = 1

        return _UpdateResult(modified_count=modified)

    def aggregate(self, pipeline):
        days = set()
        for doc in self._docs.values():
            schedule_days = doc.get("schedule_details", {}).get("days", [])
            for day in schedule_days:
                days.add(day)

        for day in sorted(days):
            yield {"_id": day}


def _create_collections():
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=1000)
        client.admin.command("ping")
        db = client["mergington_high"]
        return db["activities"], db["teachers"]
    except Exception:
        return _InMemoryCollection(), _InMemoryCollection()


activities_collection, teachers_collection = _create_collections()

# Methods


def hash_password(password):
    """Hash password using Argon2"""
    ph = PasswordHasher()
    return ph.hash(password)


def verify_password(hashed_password: str, plain_password: str) -> bool:
    """Verify a plain password against an Argon2 hashed password.

    Returns True when the password matches, False otherwise.
    """
    ph = PasswordHasher()
    try:
        ph.verify(hashed_password, plain_password)
        return True
    except argon2_exceptions.VerifyMismatchError:
        return False
    except Exception:
        # For any other exception (e.g., invalid hash), treat as non-match
        return False


def init_database():
    """Initialize database if empty"""

    # Initialize activities if empty
    if activities_collection.count_documents({}) == 0:
        for name, details in initial_activities.items():
            activities_collection.insert_one({"_id": name, **details})

    # Initialize teacher accounts if empty
    if teachers_collection.count_documents({}) == 0:
        for teacher in initial_teachers:
            teachers_collection.insert_one(
                {"_id": teacher["username"], **teacher})


# Initial database if empty
initial_activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Mondays and Fridays, 3:15 PM - 4:45 PM",
        "schedule_details": {
            "days": ["Monday", "Friday"],
            "start_time": "15:15",
            "end_time": "16:45"
        },
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 7:00 AM - 8:00 AM",
        "schedule_details": {
            "days": ["Tuesday", "Thursday"],
            "start_time": "07:00",
            "end_time": "08:00"
        },
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Morning Fitness": {
        "description": "Early morning physical training and exercises",
        "schedule": "Mondays, Wednesdays, Fridays, 6:30 AM - 7:45 AM",
        "schedule_details": {
            "days": ["Monday", "Wednesday", "Friday"],
            "start_time": "06:30",
            "end_time": "07:45"
        },
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 5:30 PM",
        "schedule_details": {
            "days": ["Tuesday", "Thursday"],
            "start_time": "15:30",
            "end_time": "17:30"
        },
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and compete in basketball tournaments",
        "schedule": "Wednesdays and Fridays, 3:15 PM - 5:00 PM",
        "schedule_details": {
            "days": ["Wednesday", "Friday"],
            "start_time": "15:15",
            "end_time": "17:00"
        },
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore various art techniques and create masterpieces",
        "schedule": "Thursdays, 3:15 PM - 5:00 PM",
        "schedule_details": {
            "days": ["Thursday"],
            "start_time": "15:15",
            "end_time": "17:00"
        },
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 3:30 PM - 5:30 PM",
        "schedule_details": {
            "days": ["Monday", "Wednesday"],
            "start_time": "15:30",
            "end_time": "17:30"
        },
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and prepare for math competitions",
        "schedule": "Tuesdays, 7:15 AM - 8:00 AM",
        "schedule_details": {
            "days": ["Tuesday"],
            "start_time": "07:15",
            "end_time": "08:00"
        },
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 3:30 PM - 5:30 PM",
        "schedule_details": {
            "days": ["Friday"],
            "start_time": "15:30",
            "end_time": "17:30"
        },
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "amelia@mergington.edu"]
    },
    "Weekend Robotics Workshop": {
        "description": "Build and program robots in our state-of-the-art workshop",
        "schedule": "Saturdays, 10:00 AM - 2:00 PM",
        "schedule_details": {
            "days": ["Saturday"],
            "start_time": "10:00",
            "end_time": "14:00"
        },
        "max_participants": 15,
        "participants": ["ethan@mergington.edu", "oliver@mergington.edu"]
    },
    "Science Olympiad": {
        "description": "Weekend science competition preparation for regional and state events",
        "schedule": "Saturdays, 1:00 PM - 4:00 PM",
        "schedule_details": {
            "days": ["Saturday"],
            "start_time": "13:00",
            "end_time": "16:00"
        },
        "max_participants": 18,
        "participants": ["isabella@mergington.edu", "lucas@mergington.edu"]
    },
    "Sunday Chess Tournament": {
        "description": "Weekly tournament for serious chess players with rankings",
        "schedule": "Sundays, 2:00 PM - 5:00 PM",
        "schedule_details": {
            "days": ["Sunday"],
            "start_time": "14:00",
            "end_time": "17:00"
        },
        "max_participants": 16,
        "participants": ["william@mergington.edu", "jacob@mergington.edu"]
    }
}

initial_teachers = [
    {
        "username": "mrodriguez",
        "display_name": "Ms. Rodriguez",
        "password": hash_password("art123"),
        "role": "teacher"
    },
    {
        "username": "mchen",
        "display_name": "Mr. Chen",
        "password": hash_password("chess456"),
        "role": "teacher"
    },
    {
        "username": "principal",
        "display_name": "Principal Martinez",
        "password": hash_password("admin789"),
        "role": "admin"
    }
]
