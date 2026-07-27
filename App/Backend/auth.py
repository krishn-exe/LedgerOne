from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import mysql.connector
import hashlib
import os
import secrets
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

router = APIRouter()

class AuthRequest(BaseModel):
    username: str
    password: str
    role: str = "Employee"

def get_db():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database="ledger"
    )

def hash_password(password: str, salt: bytes = None):
    if salt is None:
        salt = os.urandom(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return pwd_hash.hex(), salt.hex()

def verify_password(stored_password: str, stored_salt: str, provided_password: str):
    provided_hash, _ = hash_password(provided_password, bytes.fromhex(stored_salt))
    return stored_password == provided_hash

@router.post("/register")
def register(user: AuthRequest):
    db = get_db()
    cursor = db.cursor()
    hashed_pw, salt = hash_password(user.password)
    
    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash, salt, role) VALUES (%s, %s, %s, %s)",
            (user.username, hashed_pw, salt, user.role)
        )
        db.commit()
    except mysql.connector.IntegrityError:
        db.close()
        raise HTTPException(status_code=400, detail="Username already exists")
        
    db.close()
    return {"message": "User registered successfully"}

@router.post("/login")
def login(user: AuthRequest): 
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM users WHERE username = %s", (user.username,))
    db_user = cursor.fetchone()
    
    if not db_user or not verify_password(db_user['password_hash'], db_user['salt'], user.password):
        db.close()
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    session_id = secrets.token_hex(32)
    expires_at = datetime.now() + timedelta(hours=24)
    
    cursor.execute(
        "INSERT INTO sessions (session_id, user_id, expires_at) VALUES (%s, %s, %s)",
        (session_id, db_user['id'], expires_at)
    )
    db.commit()
    db.close()
    
    return {
        "message": "Login successful",
        "session_id": session_id,
        "role": db_user['role']
    }

def verify_session(session_id: str):

    if not session_id:
        return False

    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT u.id, u.username, u.role, s.expires_at 
        FROM sessions s 
        JOIN users u ON s.user_id = u.id 
        WHERE s.session_id = %s
    """, (session_id,))
    
    user = cursor.fetchone()
    
    if not user or user['expires_at'] < datetime.now():
        if user:
            cursor.execute("DELETE FROM sessions WHERE session_id = %s", (session_id,))
            db.commit()
        db.close()
        return False
        
    db.close()
    return user