import sqlite3
import logging
import json
from pathlib import Path
from passlib.context import CryptContext
from typing import List # <-- FIX: Import List
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
        
        cursor.execute("BEGIN TRANSACTION;")
        try:
            # Users Table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
            if cursor.fetchone() is None:
                cursor.execute("""
                    CREATE TABLE users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        hashed_password TEXT NOT NULL,
                        role TEXT NOT NULL CHECK(role IN ('admin', 'user')),
                        name TEXT,
                        email TEXT,
                        team TEXT, -- This will store teams as a JSON list
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                hashed_pass = hash_password('admin')
                # --- FIX: Store default team as a JSON list ---
                default_team_json = json.dumps(['Default'])
                cursor.execute(
                    "INSERT INTO users (username, hashed_password, role, name, email, team) VALUES (?, ?, ?, ?, ?, ?)",
                    ('admin', hashed_pass, 'admin', 'Admin', '', default_team_json)
                )
                logger.info("Table 'users' created and default admin added.")
            else:
                cursor.execute("PRAGMA table_info(users)")
                columns = [column['name'] for column in cursor.fetchall()]
                if 'team' not in columns:
                    cursor.execute("ALTER TABLE users ADD COLUMN team TEXT;")
                    logger.info("Column 'team' added to 'users' table.")

            # ... (rest of init_db is unchanged) ...
            
            # Chat History Table
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
            
            # Document Teams Table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='document_teams';")
            if cursor.fetchone() is None:
                cursor.execute("""
                    CREATE TABLE document_teams (
                        doc_id TEXT NOT NULL,
                        team TEXT NOT NULL,
                        PRIMARY KEY (doc_id, team)
                    );
                """)
                logger.info("Table 'document_teams' created.")

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
        user_row = cursor.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        
        if user_row:
            # --- FIX: Deserialize 'team' from JSON string to list ---
            user_dict = dict(user_row)
            try:
                user_dict['teams'] = json.loads(user_row['team']) if user_row['team'] else []
            except json.JSONDecodeError:
                user_dict['teams'] = [user_row['team']] # Fallback for old non-JSON data
            # Also keep 'team' for compatibility if needed, but 'teams' is preferred
            user_dict['team'] = user_dict['teams'] 
            return user_dict
        return None

def create_user(username: str, password: str, role: str, teams: List[str]):
    """ --- FIX: Changed 'team: str' to 'teams: List[str]' --- """
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            hashed_pass = hash_password(password)
            # --- FIX: Serialize teams list into JSON string ---
            teams_json = json.dumps(teams)
            cursor.execute(
                "INSERT INTO users (username, hashed_password, role, name, email, team) VALUES (?, ?, ?, ?, ?, ?)",
                (username, hashed_pass, role, '', '', teams_json)
            )
            conn.commit()
            logger.info(f"User '{username}' created with role '{role}' and teams '{teams_json}'.")
        except sqlite3.IntegrityError:
            logger.warning(f"User '{username}' already exists.")

def update_user_details(username: str, name: str, email: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET name = ?, email = ? WHERE username = ?", (name, email, username)
        )
        conn.commit()

# --- FIX: Added new function to update role and teams for admin ---
def admin_update_user(username: str, new_role: str, new_teams: List[str]):
    """Updates a user's role and teams (Admin only)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        teams_json = json.dumps(new_teams)
        cursor.execute(
            "UPDATE users SET role = ?, team = ? WHERE username = ?",
            (new_role, teams_json, username)
        )
        conn.commit()
        logger.info(f"Admin updated user '{username}'. New role: '{new_role}', New teams: '{teams_json}'.")


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
    with get_db_connection() as conn:
        cursor = conn.cursor()
        users_rows = cursor.execute("SELECT id, username, role, created_at, team FROM users ORDER BY created_at DESC").fetchall()
        
        users_list = []
        for user_row in users_rows:
            # --- FIX: Deserialize 'team' for each user ---
            user_dict = {key: user_row[key] for key in user_row.keys()}
            try:
                # 'team' column now stores a JSON list, 'teams' is the deserialized list
                user_dict['teams'] = json.loads(user_row['team']) if user_row['team'] else []
            except json.JSONDecodeError:
                 # Fallback for old data that wasn't a JSON list
                user_dict['teams'] = [user_row['team']] if user_row['team'] else []
            users_list.append(user_dict)
            
        return users_list

def delete_user(username: str):
    if username == 'admin':
        raise ValueError("The default 'admin' user cannot be deleted.")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION;")
        try:
            user_row = cursor.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if not user_row:
                logger.warning(f"Attempted to delete non-existent user: {username}")
                cursor.execute("ROLLBACK;")
                return
            user_id = user_row['id']
            cursor.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            cursor.execute("COMMIT;")
            logger.info(f"Successfully deleted user '{username}' and their chat history.")
        except sqlite3.Error as e:
            cursor.execute("ROLLBACK;")
            logger.error(f"Database error during user deletion: {e}")
            raise

# --- Chat History Functions ---
def save_chat_message(user_id: int, session_id: str, role: str, message: str, is_new_chat: bool):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        session_name = None
        if is_new_chat:
            session_name = " ".join(message.split()[:5]) if role == 'user' and message.strip() else "Untitled Chat"
        cursor.execute(
            "INSERT INTO chat_history (user_id, session_id, role, message, session_name) VALUES (?, ?, ?, ?, ?)",
            (user_id, session_id, role, message, session_name)
        )
        conn.commit()

def get_all_chat_sessions(user_id: int):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        sessions = cursor.execute("""
            SELECT t1.session_id, t1.session_name FROM chat_history t1
            INNER JOIN (
                SELECT session_id, MIN(id) as min_id FROM chat_history
                WHERE user_id = ? GROUP BY session_id
            ) t2 ON t1.session_id = t2.session_id AND t1.id = t2.min_id
            WHERE t1.user_id = ? ORDER BY t1.timestamp DESC
        """, (user_id, user_id)).fetchall()
        return [{"session_id": row["session_id"], "name": row["session_name"]} for row in sessions]

def get_chat_history_by_session(user_id: int, session_id: str):
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

# --- Document Team Functions ---
def add_document_teams(doc_id: str, teams: list[str]):
    """Adds team associations for a given document ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # First, remove existing teams for the doc_id to handle updates
        cursor.execute("DELETE FROM document_teams WHERE doc_id = ?", (doc_id,))
        # Then, insert the new teams
        teams_data = [(doc_id, team) for team in teams]
        cursor.executemany("INSERT INTO document_teams (doc_id, team) VALUES (?, ?)", teams_data)
        conn.commit()

def get_document_teams(doc_id: str) -> list[str]:
    """Retrieves all teams associated with a given document ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        teams = cursor.execute("SELECT team FROM document_teams WHERE doc_id = ?", (doc_id,)).fetchall()
        return [row['team'] for row in teams]
