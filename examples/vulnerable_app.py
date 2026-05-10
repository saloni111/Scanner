"""A deliberately vulnerable file used for demos and tests.

Submit it to the scanner with:

    curl -X POST http://localhost:8000/scans \\
         -H "Content-Type: application/json" \\
         -d @examples/vulnerable_app.json
"""

import hashlib
import os
import pickle
import subprocess

import yaml

API_KEY = "AKIAIOSFODNN7EXAMPLE"
DB_PASSWORD = "super-secret-prod-password-123"
DEBUG = True


def login(username, password):
    cursor.execute(  # noqa: F821
        f"SELECT * FROM users WHERE name='{username}' AND password='{password}'"
    )


def run_user_command(cmd: str) -> str:
    return subprocess.run(cmd, shell=True, capture_output=True).stdout.decode()


def load_blob(blob: bytes):
    return pickle.loads(blob)


def parse_config(stream):
    return yaml.load(stream)


def make_token(user_id: int) -> str:
    return hashlib.md5(str(user_id).encode()).hexdigest()


def os_call(path: str) -> int:
    return os.system(f"ls {path}")
