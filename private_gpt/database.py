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
        
        # Use a transaction for atomic operations
        cursor.execute("BEGIN TRANSACTION;")
        try:
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
                        name TEXT,
                        email TEXT,
                        team TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                # Create default admin user
                hashed_pass = hash_password('admin')
                cursor.execute(
                    "INSERT INTO users (username, hashed_password, role, name, email, team) VALUES (?, ?, ?, ?, ?, ?)",
                    ('admin', hashed_pass, 'admin', 'Admin', '', 'Default')
                )
                logger.info("Table 'users' created and default admin added.")
            else:
                # Add columns if they don't exist for backward compatibility
                cursor.execute("PRAGMA table_info(users)")
                columns = [column['name'] for column in cursor.fetchall()]
                if 'name' not in columns:
                    cursor.execute("ALTER TABLE users ADD COLUMN name TEXT;")
                    logger.info("Column 'name' added to 'users' table.")
                if 'email' not in columns:
                    cursor.execute("ALTER TABLE users ADD COLUMN email TEXT;")
                    logger.info("Column 'email' added to 'users' table.")
                if 'team' not in columns:
                    cursor.execute("ALTER TABLE users ADD COLUMN team TEXT;")
                    logger.info("Column 'team' added to 'users' table.")

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
            else:
                # Add session_name column if it doesn't exist
                cursor.execute("PRAGMA table_info(chat_history)")
                columns = [column['name'] for column in cursor.fetchall()]
                if 'session_name' not in columns:
                    cursor.execute("ALTER TABLE chat_history ADD COLUMN session_name TEXT;")
                    logger.info("Column 'session_name' added to 'chat_history' table.")
            


            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='document_tags';")
            if cursor.fetchone() is None:
                cursor.execute("""
                    CREATE TABLE document_tags (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_name TEXT NOT NULL,
                        team TEXT NOT NULL,
                        UNIQUE(file_name, team)
                    );
                """)
                logger.info("Table 'document_tags' created.")


            cursor.execute("COMMIT;")
        except sqlite3.Error as e:
            cursor.execute("ROLLBACK;")
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

def create_user(username: str, password: str, role: str, team: str):
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            hashed_pass = hash_password(password)
            cursor.execute(
                "INSERT INTO users (username, hashed_password, role, name, email, team) VALUES (?, ?, ?, ?, ?, ?)",
                (username, hashed_pass, role, '', '', team)
            )
            conn.commit()
            logger.info(f"User '{username}' created with role '{role}' and team '{team}'.")
        except sqlite3.IntegrityError:
            logger.warning(f"User '{username}' already exists.")

def update_user_details(username: str, name: str, email: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET name = ?, email = ? WHERE username = ?", (name, email, username)
        )
        conn.commit()

def update_user_password(username: str, new_password: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        new_hashed_password = hash_password(new_password)
        cursor.execute(
            "UPDATE users SET hashed_password = ? WHERE username = ?",
            (new_hashed_password, username),
        )
        conn.commit()

def get_all_users():
    """Retrieves all users from the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        users_rows = cursor.execute("SELECT id, username, role, created_at, team FROM users ORDER BY created_at DESC").fetchall()
        # Explicitly convert each row to a dictionary to ensure all fields are included
        users_list = [{key: user_row[key] for key in user_row.keys()} for user_row in users_rows]
        return users_list

def delete_user(username: str):
    """Deletes a user and all their associated chat history."""
    if username == 'admin':
        raise ValueError("The default 'admin' user cannot be deleted.")
        
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Use a transaction for atomic operations
        cursor.execute("BEGIN TRANSACTION;")
        try:
            # Find the user_id first
            user_row = cursor.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if not user_row:
                logger.warning(f"Attempted to delete non-existent user: {username}")
                cursor.execute("ROLLBACK;")
                return

            user_id = user_row['id']
            
            # Delete associated chat history
            cursor.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
            
            # Delete the user
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            
            cursor.execute("COMMIT;")
            logger.info(f"Successfully deleted user '{username}' and their chat history.")
        except sqlite3.Error as e:
            cursor.execute("ROLLBACK;")
            logger.error(f"Database error during user deletion: {e}")
            raise

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
    Retrieves all distinct chat sessions for a given user, correctly named.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        sessions = cursor.execute("""
            SELECT
                t1.session_id,
                t1.session_name
            FROM chat_history t1
            INNER JOIN (
                SELECT session_id, MIN(id) as min_id
                FROM chat_history
                WHERE user_id = ?
                GROUP BY session_id
            ) t2 ON t1.session_id = t2.session_id AND t1.id = t2.min_id
            WHERE t1.user_id = ?
            ORDER BY t1.timestamp DESC
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





def add_document_tags(file_name: str, teams: list[str]):
    """Adds team tags to a document, replacing any existing ones."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION;")
        try:
            # Delete old tags for this file first
            cursor.execute("DELETE FROM document_tags WHERE file_name = ?", (file_name,))
            # Insert new tags
            if teams:
                tags_to_insert = [(file_name, team) for team in teams]
                cursor.executemany("INSERT INTO document_tags (file_name, team) VALUES (?, ?)", tags_to_insert)
            cursor.execute("COMMIT;")
            logger.info(f"Updated tags for file '{file_name}' to: {teams}")
        except sqlite3.Error as e:
            cursor.execute("ROLLBACK;")
            logger.error(f"Database error adding document tags for {file_name}: {e}")
            raise

def get_files_for_teams(teams: list[str]) -> list[str]:
    """Retrieves all unique file names associated with a list of teams."""
    if not teams:
        return []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        placeholders = ','.join('?' for _ in teams)
        query = f"SELECT DISTINCT file_name FROM document_tags WHERE team IN ({placeholders})"
        files = cursor.execute(query, teams).fetchall()
        return [row['file_name'] for row in files]

def delete_document_tags(file_name: str):
    """Deletes all tags associated with a specific file."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM document_tags WHERE file_name = ?", (file_name,))
        conn.commit()
        logger.info(f"Deleted tags for file '{file_name}'.")



