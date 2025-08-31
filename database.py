# In private_gpt/database.py

import sqlite3
import logging
import os
from private_gpt.constants import PROJECT_ROOT_PATH

logger = logging.getLogger(__name__)

# Define the path for the database in the project root
DB_PATH = os.path.join(PROJECT_ROOT_PATH, "chat_history.db")

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    return conn

def init_db():
    """Initializes the database and creates the chat_history table if it doesn't exist."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    role TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            logger.info("Database initialized successfully.")
    except sqlite3.Error as e:
        logger.error(f"Database error during initialization: {e}")


def add_message_to_history(username: str, role: str, message: str):
    """Adds a chat message to the history for a specific user."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chat_history (username, role, message) VALUES (?, ?, ?)",
                (username, role, message)
            )
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Failed to add message to history for user '{username}': {e}")


def get_chat_history(username: str) -> list[dict]:
    """Retrieves the chat history for a specific user."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role, message FROM chat_history WHERE username = ? ORDER BY timestamp ASC",
                (username,)
            )
            history = [dict(row) for row in cursor.fetchall()]
            return history
    except sqlite3.Error as e:
        logger.error(f"Failed to retrieve chat history for user '{username}': {e}")
        return []


