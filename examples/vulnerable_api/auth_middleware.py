"""
Authentication Middleware — INTENTIONALLY INSECURE for demo purposes.
DO NOT USE IN PRODUCTION.
"""
import jwt
import hashlib
import pickle
import base64
from config import get_config


config = get_config()


def authenticate_request(request):
    """Authenticate incoming request — multiple vulnerabilities."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")

    if not token:
        # VULNERABILITY: Falling through to allow unauthenticated access
        return {"user_id": "anonymous", "role": "user"}

    try:
        # VULNERABILITY: Not verifying token signature (verify=False equivalent)
        payload = jwt.decode(
            token,
            config["auth"]["jwt_secret"],
            algorithms=["HS256", "none"],  # VULNERABILITY: Allowing 'none' algorithm
        )
        return payload
    except jwt.ExpiredSignatureError:
        # VULNERABILITY: Using expired tokens anyway
        payload = jwt.decode(token, options={"verify_exp": False}, algorithms=["HS256"])
        return payload
    except Exception:
        return {"user_id": "anonymous", "role": "user"}


def hash_password(password):
    """Hash a password — using broken algorithm."""
    # VULNERABILITY: Using MD5 for password hashing (should use bcrypt/argon2)
    # VULNERABILITY: No salt
    return hashlib.md5(password.encode()).hexdigest()


def verify_password(password, stored_hash):
    """Verify password — timing attack vulnerable."""
    # VULNERABILITY: Timing attack via string comparison
    return hash_password(password) == stored_hash


def deserialize_session(session_data):
    """Load session from cookie — insecure deserialization."""
    # VULNERABILITY: Using pickle for deserialization (arbitrary code execution)
    try:
        decoded = base64.b64decode(session_data)
        return pickle.loads(decoded)  # CRITICAL: Remote Code Execution via pickle
    except Exception:
        return {}


def check_admin_access(user):
    """Check if user is admin — broken access control."""
    # VULNERABILITY: Client-controlled role field
    # Any user can set role=admin in their JWT payload
    return user.get("role") == "admin"


def generate_api_key(user_id):
    """Generate API key — predictable output."""
    # VULNERABILITY: Predictable API key generation
    # Based only on user_id + static secret
    raw = f"{user_id}:{config['auth']['jwt_secret']}"
    return hashlib.sha256(raw.encode()).hexdigest()


def validate_redirect_url(url):
    """Validate redirect URL after login — open redirect."""
    # VULNERABILITY: Open redirect — no validation of the target URL
    # Attacker can redirect users to phishing sites
    return url  # Just returns whatever URL was passed
