from fastapi import APIRouter, HTTPException
from auth import verify_session
from pydantic import BaseModel, Field
import mysql.connector
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

class Expense(BaseModel):
    id: int
    title: str
    amount: float
    currency: str = "INR"
    category: str
    status: str = "submitted"
    user_id: int
    username: str
    image_url: str = None
    notes: str = None
    rejection_reason: str = None
    created_at: datetime
    updated_at: datetime

class ExpenseCreate(BaseModel):
    session_id: str
    title: str = Field(..., max_length=255)
    amount: float = Field(..., gt=0)
    currency: str = "INR"
    category: str  
    image_url: str = None
    notes: str = None

class SessionRequest(BaseModel):
    session_id: str

class RejectAction(BaseModel):
    session_id: str
    rejection_reason: str = Field(..., min_length=5)

def get_db():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database="ledger"
    )

@router.post("/expenses")
def create_expense(expense: ExpenseCreate):
    user = verify_session(expense.session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")

    if user["role"] == "Finance":
        raise HTTPException(status_code=403, detail="Not Permitted to perform this action")

    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    cursor.execute("""
        INSERT INTO expenses 
        (title, amount, currency, category, status, user_id, image_url, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        expense.title,
        expense.amount,
        expense.currency.upper(),
        expense.category,
        "submitted",
        user["id"],
        expense.image_url,
        expense.notes
    ))
    
    expense_id = cursor.lastrowid
    db.commit()
    db.close()
    
    return {"message": "Expense submitted successfully", "expense_id": expense_id}

@router.post("/expenses/{expense_id}/approve")
def approve_expense(expense_id: int, action: SessionRequest):
    user = verify_session(action.session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")

    if user['role'] != 'Manager':
        raise HTTPException(status_code=403, detail="Not Permitted to perform this action")

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM expenses WHERE id = %s", (expense_id,))
    expense = cursor.fetchone()

    if not expense:
        db.close()
        raise HTTPException(status_code=404, detail="Expense not found")

    if expense['user_id'] == user['id']:
        db.close()
        raise HTTPException(status_code=403, detail="Not Permitted to perform this action")
    if expense['status'] != 'submitted':
        db.close()
        raise HTTPException(status_code=422, detail="Expense already processed")

    cursor.execute("UPDATE expenses SET status = 'approved' WHERE id = %s", (expense_id,))
    db.commit()
    db.close()

    return {"message": f"Expense {expense_id} approved"}

@router.post("/expenses/{expense_id}/reject")
def reject_expense(expense_id: int, action: RejectAction):
    user = verify_session(action.session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")

    if user['role'] != 'Manager':
        raise HTTPException(status_code=403, detail="Not Permitted to perform this action")

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM expenses WHERE id = %s", (expense_id,))
    expense = cursor.fetchone()

    if not expense:
        db.close()
        raise HTTPException(status_code=404, detail="Expense not found")

    if expense['user_id'] == user['id']:
        db.close()
        raise HTTPException(status_code=403, detail="Not Permitted to perform this action")
    if expense['status'] != 'submitted':
        db.close()
        raise HTTPException(status_code=422, detail="Expense already processed")

    cursor.execute(
        "UPDATE expenses SET status = 'rejected', rejection_reason = %s WHERE id = %s", 
        (action.rejection_reason, expense_id)
    )
    db.commit()
    db.close()

    return {"message": f"Expense {expense_id} rejected"}

@router.post("/expenses/{expense_id}/reopen")
def reopen_expense(expense_id: int, action: SessionRequest):
    user = verify_session(action.session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM expenses WHERE id = %s", (expense_id,))
    expense = cursor.fetchone()

    if not expense:
        db.close()
        raise HTTPException(status_code=404, detail="Expense not found")

    if expense['user_id'] != user['id']:
        db.close()
        raise HTTPException(status_code=403, detail="Not Permitted to perform this action")
    if expense['status'] != 'rejected':
        db.close()
        raise HTTPException(status_code=422, detail="Expense already processed")

    cursor.execute(
        "UPDATE expenses SET status = 'submitted', rejection_reason = NULL WHERE id = %s", 
        (expense_id,)
    )
    db.commit()
    db.close()

    return {"message": f"Expense {expense_id} reopened and resubmitted"}