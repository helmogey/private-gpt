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
    """Initializes the database using atomic, idempotent operations."""
    DB_FOLDER.mkdir(parents=True, exist_ok=True)
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Create users table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'user')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                name TEXT,
                email TEXT
            );
        """)

        # Add columns for backward compatibility if they don't exist
        cursor.execute("PRAGMA table_info(users)")
        columns = [column['name'] for column in cursor.fetchall()]
        if 'name' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN name TEXT;")
            logger.info("Column 'name' added to 'users' table.")
        if 'email' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN email TEXT;")
            logger.info("Column 'email' added to 'users' table.")

        # Create chat_history table if it doesn't exist
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

        # Check if default admin exists, and if not, create it
        cursor.execute("SELECT id FROM users WHERE username = 'admin'")
        if cursor.fetchone() is None:
            hashed_pass = hash_password('admin')
            cursor.execute(
                "INSERT INTO users (username, hashed_password, role, name, email) VALUES (?, ?, ?, ?, ?)",
                ('admin', hashed_pass, 'admin', '', '')
            )
            logger.info("Default admin user created.")

        # Commit all changes at once
        conn.commit()
        
    except sqlite3.Error as e:
        logger.error(f"Database error during initialization: {e}")
        # Re-raise the exception to prevent the app from starting with a broken DB
        raise e
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

def create_user(username: str, password: str, role: str = 'user', name: str = None, email: str = None):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        hashed_pass = hash_password(password)
        cursor.execute(
            "INSERT INTO users (username, hashed_password, role, name, email) VALUES (?, ?, ?, ?, ?)",
            (username, hashed_pass, role, name, email)
        )
        conn.commit()
        logger.info(f"User '{username}' created with role '{role}'.")
    except sqlite3.IntegrityError:
        logger.warning(f"User '{username}' already exists.")
    finally:
        conn.close()



def update_user_details(user_id: int, name: str, email: str):
    """Updates a user's name and email."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET name = ?, email = ? WHERE id = ?",
            (name, email, user_id)
        )
        conn.commit()
        logger.info(f"Updated details for user_id: {user_id}")
    finally:
        conn.close()

def update_user_password(user_id: int, new_password: str):
    """Updates a user's password."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        hashed_pass = hash_password(new_password)
        cursor.execute(
            "UPDATE users SET hashed_password = ? WHERE id = ?",
            (hashed_pass, user_id)
        )
        conn.commit()
        logger.info(f"Updated password for user_id: {user_id}")
    finally:
        conn.close()




def get_all_users():
    """Retrieves all users from the database."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # --- EDIT START: Select new name and email columns ---
        users = cursor.execute("SELECT id, username, role, name, email, created_at FROM users ORDER BY created_at DESC").fetchall()
        # --- EDIT END ---
        return [dict(row) for row in users]
    finally:
        conn.close()



# --- Chat History Functions ---
def save_chat_message(user_id: int, session_id: str, role: str, message: str, is_new_chat: bool):
    """Saves a chat message, adding a session name if it's a new chat."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        session_name = None
        
        # Only assign a name if it's a new chat.
        if is_new_chat:
            # Generate a name from the user's message.
            # If the message is empty or not from a user, default to "Untitled Chat".
            if role == 'user' and message.strip():
                session_name = " ".join(message.split()[:5])
            else:
                session_name = "Untitled Chat"
        
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
