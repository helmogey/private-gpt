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
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Check if users table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
        if cursor.fetchone() is None:
            # Create users table
            cursor.execute("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin', 'user')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            create_user('admin', 'admin', 'admin') # Create default admin
            logger.info("Table 'users' created and default admin added.")

        # Check if chat_history table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_history';")
        if cursor.fetchone() is None:
            cursor.execute("""
                CREATE TABLE chat_history (
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
            logger.info("Table 'chat_history' created.")

        # Add session_name column if it doesn't exist (for backward compatibility)
        cursor.execute("PRAGMA table_info(chat_history)")
        columns = [column['name'] for column in cursor.fetchall()]
        if 'session_name' not in columns:
            cursor.execute("ALTER TABLE chat_history ADD COLUMN session_name TEXT;")
            logger.info("Column 'session_name' added to 'chat_history' table.")

        conn.commit()
        
    except sqlite3.Error as e:
        logger.error(f"Database error during initialization: {e}")
    finally:
        if conn:
            conn.close()

# --- Password Utilities ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

# --- User Management Functions ---
def get_user(username: str):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        user = cursor.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return user
    finally:
        conn.close()

def create_user(username: str, password: str, role: str = 'user'):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        hashed_pass = hash_password(password)
        cursor.execute(
            "INSERT INTO users (username, hashed_password, role) VALUES (?, ?, ?)",
            (username, hashed_pass, role)
        )
        conn.commit()
        logger.info(f"User '{username}' created with role '{role}'.")
    except sqlite3.IntegrityError:
        logger.warning(f"User '{username}' already exists.")
    finally:
        conn.close()

# --- Chat History Functions ---
def save_chat_message(user_id: int, session_id: str, role: str, message: str, is_new_chat: bool):
    """Saves a chat message, adding a session name if it's a new chat."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        session_name = " ".join(message.split()[:5]) if is_new_chat else None
        
        cursor.execute(
            "INSERT INTO chat_history (user_id, session_id, role, message, session_name) VALUES (?, ?, ?, ?, ?)",
            (user_id, session_id, role, message, session_name)
        )
        conn.commit()
    finally:
        conn.close()

def get_all_chat_sessions(user_id: int):
    """
    Retrieves all distinct chat sessions for a given user, correctly named.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # FIX: This query correctly finds the first message in each session and uses its
        # session_name to identify the chat, avoiding the user_id bug.
        sessions = cursor.execute("""
            SELECT
                t1.session_id,
                t1.session_name
            FROM chat_history t1
            INNER JOIN (
                SELECT session_id, MIN(timestamp) as min_ts
                FROM chat_history
                WHERE user_id = ?
                GROUP BY session_id
            ) t2 ON t1.session_id = t2.session_id AND t1.timestamp = t2.min_ts
            WHERE t1.user_id = ?
            ORDER BY t1.timestamp DESC
        """, (user_id, user_id)).fetchall()
        
        return [{"session_id": row["session_id"], "name": row["session_name"]} for row in sessions]
    finally:
        conn.close()

def get_chat_history_by_session(user_id: int, session_id: str):
    """Retrieves the chat history for a specific session."""
    conn = get_db_connection()
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
    finally:
        conn.close()

