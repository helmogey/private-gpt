import sqlite3
import logging
from pathlib import Path
from passlib.context import CryptContext
from private_gpt.constants import PROJECT_ROOT_PATH

# --- Configuration ---
# Define a dedicated folder for the database
DB_FOLDER = PROJECT_ROOT_PATH / "userdb"
DB_FILE = DB_FOLDER / "private_gpt.db"

# Password hashing context
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
    # Ensure the userdb directory exists before any database operations
    try:
        DB_FOLDER.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(f"Fatal: Could not create database directory at {DB_FOLDER}: {e}")
        return

    if DB_FILE.exists():
        return # Database already exists

    logger.info("Database not found. Initializing new database...")
    conn = None # Initialize connection to None for robust error handling
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
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
        
        # Create chat_history table
        cursor.execute("""
            CREATE TABLE chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
        """)
        
        conn.commit()
        logger.info("Database tables 'users' and 'chat_history' created successfully.")
        
        # Create a default admin user
        create_user('admin', 'admin', 'admin')
        logger.info("Default admin user ('admin'/'admin') created.")
        
    except sqlite3.Error as e:
        logger.error(f"Database error during initialization: {e}")
    finally:
        if conn:
            conn.close()

# --- Password Utilities ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed one."""
    return pwd_context.verify(plain_password, hashed_password)

def hash_password(password: str) -> str:
    """Hashes a plain password."""
    return pwd_context.hash(password)

# --- User Management Functions ---
def get_user(username: str):
    """Retrieves a user by username from the database."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        user = cursor.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return user
    finally:
        conn.close()

def create_user(username: str, password: str, role: str = 'user'):
    """Creates a new user in the database."""
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
def save_chat_message(user_id: int, session_id: str, role: str, message: str):
    """Saves a chat message to the database."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_history (user_id, session_id, role, message) VALUES (?, ?, ?, ?)",
            (user_id, session_id, role, message)
        )
        conn.commit()
    finally:
        conn.close()

def get_chat_history(user_id: int):
    """Retrieves the most recent chat session history for a given user."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Find the most recent session_id for the user
        latest_session = cursor.execute(
            "SELECT session_id FROM chat_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1",
            (user_id,)
        ).fetchone()

        if not latest_session:
            return {"session_id": None, "messages": []}

        latest_session_id = latest_session['session_id']

        # Retrieve all messages for that session, ordered by when they were created
        messages = cursor.execute(
            "SELECT role, message FROM chat_history WHERE user_id = ? AND session_id = ? ORDER BY timestamp ASC",
            (user_id, latest_session_id)
        ).fetchall()
        
        # Format for the frontend
        history = [{"role": row["role"], "content": row["message"]} for row in messages]
        return {"session_id": latest_session_id, "messages": history}
    except Exception as e:
        logger.error(f"Error fetching chat history: {e}")
        return {"session_id": None, "messages": []}
    finally:
        conn.close()

