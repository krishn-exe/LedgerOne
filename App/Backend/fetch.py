from fastapi import APIRouter, HTTPException
from auth import verify_session
from pydantic import BaseModel, Field
import mysql.connector
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

router = APIRouter()

def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password=os.getenv("MYSQL_PASSWORD", ""),
        database="ledger"
    )


class FetchExpensesRequest(BaseModel):
    session_id: str

    start_date: str = None
    end_date: str = None
    category: str = None
    status: str = None
    min_amount: float = None
    max_amount: float = None
    page: int = 1
    limit: int = Field(20, le=100)
    sort_by: str = "created_at"
    order: str = "desc"

@router.post("/expenses/search")
def fetch_expenses(req: FetchExpensesRequest):
    user = verify_session(req.session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")

    conditions = []
    parameters = []

    if user["role"] == "Employee":
        conditions.append("e.user_id = %s")
        parameters.append(user["id"])

    if req.start_date:
        conditions.append("e.created_at >= %s")
        parameters.append(req.start_date)
        
    if req.end_date:
        conditions.append("e.created_at <= %s")
        parameters.append(req.end_date)
        
    if req.category:
        conditions.append("e.category = %s")
        parameters.append(req.category)
        
    if req.status:
        conditions.append("e.status = %s")
        parameters.append(req.status)
        
    if req.min_amount is not None:
        conditions.append("e.amount >= %s")
        parameters.append(req.min_amount)
        
    if req.max_amount is not None:
        conditions.append("e.amount <= %s")
        parameters.append(req.max_amount)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    db = get_db()
    cursor = db.cursor(dictionary=True)

    count_query = f"SELECT COUNT(*) as total FROM expenses e JOIN users u ON e.user_id = u.id {where_clause}"
    cursor.execute(count_query, parameters)
    total_records = cursor.fetchone()["total"]

    valid_sort_columns = {
        "created_at": "e.created_at",
        "amount": "e.amount",
        "status": "e.status",
        "category": "e.category",
        "title": "e.title"
    }
    sort_col = valid_sort_columns.get(req.sort_by, "e.created_at")
    sort_dir = "ASC" if req.order.upper() == "ASC" else "DESC"


    offset = (req.page - 1) * req.limit
    
    data_parameters = parameters + [req.limit, offset]

    data_query = f"""
        SELECT 
            e.*, 
            u.username 
        FROM expenses e 
        JOIN users u ON e.user_id = u.id 
        {where_clause} 
        ORDER BY {sort_col} {sort_dir} 
        LIMIT %s OFFSET %s
    """
    
    cursor.execute(data_query, data_parameters)
    expenses_data = cursor.fetchall()
    db.close()

    return {
        "total": total_records,
        "page": req.page,
        "limit": req.limit,
        "data": expenses_data
    }