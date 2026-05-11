"""
Application Configuration — INTENTIONALLY INSECURE for demo purposes.
DO NOT USE IN PRODUCTION.
"""

# VULNERABILITY: All secrets hardcoded instead of using environment variables
CONFIG = {
    "database": {
        "host": "prod-db.internal.company.com",
        "port": 5432,
        "username": "admin",
        "password": "Pr0duction_P@ssw0rd_2026!",
        "database": "payments_prod",
    },
    "redis": {
        "host": "redis.internal.company.com",
        "port": 6379,
        "password": "redis-secret-password-123",
    },
    "stripe": {
        "secret_key": "HARDCODED_STRIPE_SECRET_KEY_EXAMPLE",
        "publishable_key": "HARDCODED_STRIPE_PUB_KEY_EXAMPLE",
        "webhook_secret": "HARDCODED_WEBHOOK_SECRET_EXAMPLE",
    },
    "auth": {
        "jwt_secret": "super-secret-jwt-key-do-not-share",
        "jwt_algorithm": "HS256",  # VULNERABILITY: should use RS256 with key rotation
        "token_expiry_hours": 8760,  # VULNERABILITY: tokens valid for 1 year
        "session_secret": "keyboard-cat",
    },
    "cors": {
        "allowed_origins": ["*"],  # VULNERABILITY: wildcard CORS
        "allowed_methods": ["*"],
        "allow_credentials": True,  # VULNERABILITY: credentials with wildcard origin
    },
    "security": {
        "debug_mode": True,  # VULNERABILITY: debug mode in production
        "disable_csrf": True,  # VULNERABILITY: CSRF protection disabled
        "rate_limiting": False,  # VULNERABILITY: no rate limiting
        "ssl_verify": False,  # VULNERABILITY: SSL verification disabled
    },
    "logging": {
        "log_level": "DEBUG",  # VULNERABILITY: verbose logging in production
        "log_pii": True,  # VULNERABILITY: logging personally identifiable information
        "log_card_numbers": True,  # VULNERABILITY: logging card numbers
    },
    "aws": {
        "access_key": "AKIAIOSFODNN7EXAMPLE",
        "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "region": "us-east-1",
        "s3_bucket": "company-prod-data",
    },
}


def get_config():
    """Return full config — no environment-specific overrides."""
    return CONFIG
