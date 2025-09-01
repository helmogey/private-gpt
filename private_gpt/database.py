import sqlite3
import logging
from pathlib import Path
from passlib.context import CryptContext
from private_gpt.constants import PROJECT_ROOT_PATH

# --- Configuration ---
DB_FOLDER = PROJECT_ROOT_PATH / "userdb"
DB_FILE = DB_FOLDER / "private_gpt.db"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger(__name__)

# --- Database Initialization ---
def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database and creates tables if they don't exist."""
    DB_FOLDER.mkdir(parents=True, exist_ok=True)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Use a transaction to ensure all tables are created together
        cursor.execute("BEGIN TRANSACTION;")
        
        try:
            # Create users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin', 'user')),
                    name TEXT,
                    email TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Create chat_history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    message TEXT NOT NULL,
                    session_name TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                );
            """)
            
            # Check for and create the default admin user
            cursor.execute("SELECT id FROM users WHERE username = 'admin'")
            if cursor.fetchone() is None:
                hashed_pass = hash_password('admin')
                cursor.execute(
                    "INSERT INTO users (username, hashed_password, role, name, email) VALUES (?, ?, ?, ?, ?)",
                    ('admin', hashed_pass, 'admin', 'Admin User', '')
                )
                logger.info("Default 'admin' user created.")
            else:
                # Ensure existing admin has email field correctly set
                cursor.execute("UPDATE users SET email = '' WHERE username = 'admin' AND email IS NULL")

            conn.commit()
            logger.info("Database initialized successfully.")
            
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Database error during initialization: {e}")
            raise

# --- Password Utilities ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

# --- User Management Functions ---
def get_user(username: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        user = cursor.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return user

def create_user(username: str, password: str, role: str = 'user'):
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            hashed_pass = hash_password(password)
            cursor.execute(
                "INSERT INTO users (username, hashed_password, role, name, email) VALUES (?, ?, ?, ?, ?)",
                (username, hashed_pass, role, '', '')
            )
            conn.commit()
            logger.info(f"User '{username}' created with role '{role}'.")
        except sqlite3.IntegrityError:
            logger.warning(f"User '{username}' already exists.")

def update_user_details(user_id: int, name: str, email: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET name = ?, email = ? WHERE id = ?", (name, email, user_id))
        conn.commit()

def update_user_password(user_id: int, new_password: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        hashed_pass = hash_password(new_password)
        cursor.execute("UPDATE users SET hashed_password = ? WHERE id = ?", (hashed_pass, user_id))
        conn.commit()

def get_all_users():
    """Retrieves all users from the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        users = cursor.execute("SELECT id, username, role, created_at FROM users ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in users]

# --- Chat History Functions ---
def save_chat_message(user_id: int, session_id: str, role: str, message: str, is_new_chat: bool):
    """Saves a chat message, adding a session name if it's a new chat."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        session_name = None
        
        if is_new_chat:
            if role == 'user' and message.strip():
                session_name = " ".join(message.split()[:5])
            else:
                session_name = "Untitled Chat"
        
        cursor.execute(
            "INSERT INTO chat_history (user_id, session_id, role, message, session_name) VALUES (?, ?, ?, ?, ?)",
            (user_id, session_id, role, message, session_name)
        )
        conn.commit()

def get_all_chat_sessions(user_id: int):
    """
    Retrieves all distinct chat sessions for a given user, correctly named and ordered.
    This version is more robust against timestamp race conditions.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # This query robustly finds the first message (by MIN(id)) for each session to get its name,
        # and sorts the sessions by the most recent message in each.
        sessions = cursor.execute("""
            SELECT
                t1.session_id,
                t1.session_name
            FROM chat_history t1
            INNER JOIN (
                SELECT
                    session_id,
                    MIN(id) as min_id,
                    MAX(timestamp) as max_ts
                FROM chat_history
                WHERE user_id = ?
                GROUP BY session_id
            ) t2 ON t1.id = t2.min_id
            WHERE t1.user_id = ?
            ORDER BY t2.max_ts DESC
        """, (user_id, user_id)).fetchall()
        
        return [{"session_id": row["session_id"], "name": row["session_name"]} for row in sessions]

def get_chat_history_by_session(user_id: int, session_id: str):
    """Retrieves the chat history for a specific session."""
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            messages = cursor.execute(
                "SELECT role, message FROM chat_history WHERE user_id = ? AND session_id = ? ORDER BY timestamp ASC",
                (user_id, session_id)
            ).fetchall()
            
            history = [{"role": row["role"], "content": row["message"]} for row in messages]
            return {"session_id": session_id, "messages": history}
        except Exception as e:
            logger.error(f"Error fetching chat history for session {session_id}: {e}")
            return {"session_id": session_id, "messages": []}

