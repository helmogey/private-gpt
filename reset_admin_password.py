#!/usr/bin/env python3
"""Script to reset admin password in the database."""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from private_gpt.database import get_db_connection, hash_password, get_user

def reset_admin_password():
    """Reset admin password to 'admin'."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        new_hash = hash_password('admin')
        cursor.execute(
            "UPDATE users SET hashed_password = ? WHERE username = ?",
            (new_hash, 'admin')
        )
        conn.commit()
        print("Admin password reset successfully!")
        print("Username: admin")
        print("Password: admin")

if __name__ == "__main__":
    reset_admin_password()

