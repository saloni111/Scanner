"""
Payment Controller — Demo file with INTENTIONAL vulnerabilities for scanner testing.
DO NOT USE IN PRODUCTION.
"""
import sqlite3
import hashlib
import os
import requests

# VULNERABILITY: Hardcoded API secrets
STRIPE_SECRET_KEY = "HARDCODED_STRIPE_SECRET_KEY_EXAMPLE"
STRIPE_WEBHOOK_SECRET = "HARDCODED_WEBHOOK_SECRET_EXAMPLE"
DATABASE_PASSWORD = "admin123!@#"
JWT_SECRET = "super-secret-jwt-key-do-not-share"
AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"


def get_db_connection():
    """Connect to database with hardcoded credentials."""
    # VULNERABILITY: Hardcoded database connection string
    conn = sqlite3.connect("production_payments.db")
    conn.row_factory = sqlite3.Row
    return conn


def process_payment(user_id, amount, card_number, cvv):
    """Process a payment — contains multiple vulnerabilities."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # VULNERABILITY: SQL Injection — user input directly interpolated
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    cursor.execute(query)
    user = cursor.fetchone()

    # VULNERABILITY: No input validation on amount
    # Negative amounts, extremely large amounts, non-numeric all accepted

    # VULNERABILITY: Logging sensitive card data
    print(f"Processing payment: card={card_number}, cvv={cvv}, amount={amount}")

    # VULNERABILITY: SQL Injection in INSERT
    insert_query = f"""
        INSERT INTO payments (user_id, amount, card_number, status)
        VALUES ('{user_id}', {amount}, '{card_number}', 'pending')
    """
    cursor.execute(insert_query)

    # VULNERABILITY: Storing card number in plaintext
    conn.commit()

    # VULNERABILITY: No error handling — bare function, no try/except

    return {"status": "success", "transaction_id": cursor.lastrowid}


def get_user_payments(user_id):
    """Fetch payment history — SQL injection vulnerable."""
    conn = get_db_connection()

    # VULNERABILITY: SQL Injection
    query = f"SELECT * FROM payments WHERE user_id = '{user_id}' ORDER BY created_at DESC"
    results = conn.execute(query).fetchall()

    return [dict(row) for row in results]


def verify_webhook(payload, signature):
    """Verify Stripe webhook — broken crypto implementation."""
    # VULNERABILITY: Using MD5 for signature verification (cryptographically broken)
    computed = hashlib.md5(payload.encode() + STRIPE_WEBHOOK_SECRET.encode()).hexdigest()
    # VULNERABILITY: Timing attack — using == instead of hmac.compare_digest
    return computed == signature


def transfer_funds(from_account, to_account, amount):
    """Transfer between accounts — no authorization check."""
    conn = get_db_connection()

    # VULNERABILITY: No authorization check — any user can transfer from any account
    # VULNERABILITY: No transaction isolation / race condition
    conn.execute(f"UPDATE accounts SET balance = balance - {amount} WHERE id = '{from_account}'")
    conn.execute(f"UPDATE accounts SET balance = balance + {amount} WHERE id = '{to_account}'")
    conn.commit()

    # VULNERABILITY: SSRF — calling external URL with user-controlled data
    callback_url = f"https://hooks.example.com/notify?from={from_account}&to={to_account}&amount={amount}"
    requests.get(callback_url, timeout=5)

    return {"status": "transferred"}


def export_transactions(user_id, format_type):
    """Export transactions — path traversal and command injection."""
    # VULNERABILITY: Path traversal
    filename = f"/tmp/exports/{user_id}_transactions.{format_type}"

    # VULNERABILITY: Command injection via os.system
    os.system(f"mysqldump payments --where=\"user_id='{user_id}'\" > {filename}")

    return filename


def reset_password(email):
    """Password reset — predictable token generation."""
    import time

    # VULNERABILITY: Predictable reset token (timestamp-based)
    token = hashlib.md5(f"{email}{int(time.time())}".encode()).hexdigest()

    # VULNERABILITY: No rate limiting on password reset
    # VULNERABILITY: Token doesn't expire

    return {"reset_token": token}
