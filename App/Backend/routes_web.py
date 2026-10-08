import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Request, Form, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
import mysql.connector

from dotenv import load_dotenv

# Ensure App/.env is loaded regardless of current working directory
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv()

# Reuse existing backend auth, expenses, and fetch logic
from auth import (
    get_db,
    verify_password,
    hash_password,
    verify_session,
    login as api_login,
    register as api_register,
    AuthRequest,
)
from expenses import (
    create_expense,
    approve_expense,
    reject_expense,
    reopen_expense,
    ExpenseCreate,
    SessionRequest,
    RejectAction,
)
from fetch import fetch_expenses, FetchExpensesRequest

router = APIRouter(include_in_schema=False)

templates_path = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_path)


# -----------------------------------------------------------------------------
# Custom Exceptions & Auth Dependencies
# -----------------------------------------------------------------------------
class AuthenticationRequired(Exception):
    """Raised when an unauthenticated user attempts to access a protected page."""
    pass


class ForbiddenError(Exception):
    """Raised when an authenticated user lacks permission for an action/route."""
    def __init__(self, message: str = "You are not authorized to perform this action."):
        self.message = message


def get_current_user(request: Request) -> dict:
    """Dependency: Extract session_id from cookie, verify in DB, return user dict."""
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise AuthenticationRequired()

    user = verify_session(session_id)
    if not user:
        raise AuthenticationRequired()

    return user


def get_optional_user(request: Request) -> Optional[dict]:
    """Helper: Return user dict if session cookie is valid, else None."""
    session_id = request.cookies.get("session_id")
    if not session_id:
        return None
    try:
        user = verify_session(session_id)
        return user if user else None
    except Exception:
        return None


def require_role(allowed_roles: list[str]):
    """Factory dependency to enforce role-based access on server routes."""
    def role_checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in allowed_roles:
            raise ForbiddenError(f"Access restricted. Required role: {', '.join(allowed_roles)}")
        return user
    return role_checker


# -----------------------------------------------------------------------------
# Auth Routes (/login, /register, /logout)
# -----------------------------------------------------------------------------
@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    registered: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
):
    current_user = get_optional_user(request)
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=303)

    message = None
    if registered == "1":
        message = "Account registered successfully! Please sign in with your credentials."

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "user": None,
            "active_page": "login",
            "message": message,
            "error": error,
        },
    )


@router.post("/login")
async def login_action(request: Request):
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            data = await request.json()
            auth_req = AuthRequest(**data)
            return api_login(auth_req)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=422, detail=str(e))

    # Form submission
    form = await request.form()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    db_user = cursor.fetchone()

    if not db_user or not verify_password(db_user["password_hash"], db_user["salt"], password):
        db.close()
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "user": None,
                "active_page": "login",
                "username": username,
                "error": "Invalid username or password.",
            },
            status_code=401,
        )

    # Issue secure session token
    session_id = secrets.token_hex(32)
    expires_at = datetime.now() + timedelta(hours=24)

    cursor.execute(
        "INSERT INTO sessions (session_id, user_id, expires_at) VALUES (%s, %s, %s)",
        (session_id, db_user["id"], expires_at),
    )
    db.commit()
    db.close()

    # Set HttpOnly, SameSite=Lax cookie and redirect
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=86400,
    )
    return response


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    current_user = get_optional_user(request)
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={"user": None, "active_page": "register"},
    )


@router.post("/register")
async def register_action(request: Request):
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            data = await request.json()
            auth_req = AuthRequest(**data)
            return api_register(auth_req)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=422, detail=str(e))

    form = await request.form()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))
    confirm_password = str(form.get("confirm_password", ""))

    if len(username) < 3:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={
                "user": None,
                "active_page": "register",
                "username": username,
                "error": "Username must be at least 3 characters long.",
            },
            status_code=400,
        )

    if password != confirm_password:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={
                "user": None,
                "active_page": "register",
                "username": username,
                "error": "Passwords do not match.",
            },
            status_code=400,
        )

    if len(password) < 4:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={
                "user": None,
                "active_page": "register",
                "username": username,
                "error": "Password must be at least 4 characters long.",
            },
            status_code=400,
        )

    db = get_db()
    cursor = db.cursor()
    hashed_pw, salt = hash_password(password)

    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash, salt, role) VALUES (%s, %s, %s, %s)",
            (username, hashed_pw, salt, "Employee"),
        )
        db.commit()
    except mysql.connector.IntegrityError:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={
                "user": None,
                "active_page": "register",
                "username": username,
                "error": "Username is already taken. Please choose another.",
            },
            status_code=400,
        )
    finally:
        cursor.close()
        db.close()

    return RedirectResponse(url="/login?registered=1", status_code=303)


@router.get("/logout")
def logout_action(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id:
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("DELETE FROM sessions WHERE session_id = %s", (session_id,))
            db.commit()
            db.close()
        except Exception:
            pass

    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="session_id")
    return response


# -----------------------------------------------------------------------------
# Dashboard Page (/dashboard)
# -----------------------------------------------------------------------------
@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request, user: dict = Depends(get_current_user)):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Calculate statistics tailored to role
    if user["role"] == "Employee":
        cursor.execute("""
            SELECT 
                status, 
                COUNT(*) as count, 
                COALESCE(SUM(amount), 0) as total 
            FROM expenses 
            WHERE user_id = %s 
            GROUP BY status
        """, (user["id"],))
        stats_rows = cursor.fetchall()

        cursor.execute("""
            SELECT e.*, u.username 
            FROM expenses e 
            JOIN users u ON e.user_id = u.id 
            WHERE e.user_id = %s 
            ORDER BY e.created_at DESC 
            LIMIT 5
        """, (user["id"],))
        recent_expenses = cursor.fetchall()
    else:
        # Manager and Finance roles see organization-wide metrics
        cursor.execute("""
            SELECT 
                status, 
                COUNT(*) as count, 
                COALESCE(SUM(amount), 0) as total 
            FROM expenses 
            GROUP BY status
        """)
        stats_rows = cursor.fetchall()

        cursor.execute("""
            SELECT e.*, u.username 
            FROM expenses e 
            JOIN users u ON e.user_id = u.id 
            ORDER BY e.created_at DESC 
            LIMIT 5
        """)
        recent_expenses = cursor.fetchall()

    db.close()

    pending_count = 0
    approved_count = 0
    rejected_count = 0
    total_amount = 0.0

    for row in stats_rows:
        total_amount += float(row["total"])
        if row["status"] == "submitted":
            pending_count = row["count"]
        elif row["status"] == "approved":
            approved_count = row["count"]
        elif row["status"] == "rejected":
            rejected_count = row["count"]

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "user": user,
            "active_page": "dashboard",
            "pending_count": pending_count,
            "approved_count": approved_count,
            "rejected_count": rejected_count,
            "total_amount": total_amount,
            "recent_expenses": recent_expenses,
        },
    )


# -----------------------------------------------------------------------------
# Expenses List (/expenses) & HTMX Table Filter
# -----------------------------------------------------------------------------
@router.get("/expenses", response_class=HTMLResponse)
def expenses_page(
    request: Request,
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    session_id = request.cookies.get("session_id")
    filter_status = status if status in ["submitted", "approved", "rejected"] else None
    filter_category = category if category and category != "" else None

    # Re-use existing backend search logic
    req = FetchExpensesRequest.model_construct(
        session_id=session_id,
        status=filter_status,
        category=filter_category,
        page=page,
        limit=limit,
        start_date=None,
        end_date=None,
        min_amount=None,
        max_amount=None,
        sort_by="created_at",
        order="desc",
    )
    result = fetch_expenses(req)

    total_records = result["total"]
    total_pages = max(1, (total_records + limit - 1) // limit)
    expenses = result["data"]

    context = {
        "user": user,
        "active_page": "expenses",
        "expenses": expenses,
        "total": total_records,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "current_status": filter_status or "",
        "current_category": filter_category or "",
    }

    # If requested by HTMX, return only the partial table container
    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse(request=request, name="partials/_expense_rows.html", context=context)

    return templates.TemplateResponse(request=request, name="expenses.html", context=context)


# -----------------------------------------------------------------------------
# New Expense Submission (/expenses/new)
# -----------------------------------------------------------------------------
@router.get("/expenses/new", response_class=HTMLResponse)
def new_expense_page(request: Request, user: dict = Depends(get_current_user)):
    # Server-side role check: Finance role cannot submit expenses
    if user["role"] == "Finance":
        raise ForbiddenError("Finance accounts are not permitted to submit expenses.")

    return templates.TemplateResponse(
        request=request,
        name="expense_new.html",
        context={
            "user": user,
            "active_page": "new_expense",
            "form_data": {},
            "error": None,
        },
    )


@router.post("/expenses/new", response_class=HTMLResponse)
def new_expense_action(
    request: Request,
    title: str = Form(...),
    amount: float = Form(...),
    currency: str = Form("INR"),
    category: str = Form(...),
    notes: Optional[str] = Form(None),
    image_url: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
):
    if user["role"] == "Finance":
        raise ForbiddenError("Finance accounts are not permitted to submit expenses.")

    title_clean = title.strip()
    notes_clean = notes.strip() if notes else None
    image_clean = image_url.strip() if image_url else None

    form_data = {
        "title": title_clean,
        "amount": amount,
        "currency": currency,
        "category": category,
        "notes": notes_clean,
        "image_url": image_clean,
    }

    # Server-side validation
    if not title_clean:
        return templates.TemplateResponse(
            request=request,
            name="expense_new.html",
            context={
                "user": user,
                "active_page": "new_expense",
                "form_data": form_data,
                "error": "Expense title is required.",
            },
            status_code=400,
        )

    if amount <= 0:
        return templates.TemplateResponse(
            request=request,
            name="expense_new.html",
            context={
                "user": user,
                "active_page": "new_expense",
                "form_data": form_data,
                "error": "Amount must be greater than 0.",
            },
            status_code=400,
        )

    valid_categories = ["Meals", "Travel", "Software", "Equipment", "Other"]
    if category not in valid_categories:
        return templates.TemplateResponse(
            request=request,
            name="expense_new.html",
            context={
                "user": user,
                "active_page": "new_expense",
                "form_data": form_data,
                "error": f"Invalid category. Must be one of: {', '.join(valid_categories)}",
            },
            status_code=400,
        )

    # Reuse existing backend creation logic
    session_id = request.cookies.get("session_id")
    expense_req = ExpenseCreate.model_construct(
        session_id=session_id,
        title=title_clean,
        amount=amount,
        currency=currency,
        category=category,
        notes=notes_clean,
        image_url=image_clean,
    )

    try:
        create_expense(expense_req)
    except HTTPException as e:
        return templates.TemplateResponse(
            request=request,
            name="expense_new.html",
            context={
                "user": user,
                "active_page": "new_expense",
                "form_data": form_data,
                "error": e.detail,
            },
            status_code=e.status_code,
        )

    return RedirectResponse(url="/expenses", status_code=303)


# -----------------------------------------------------------------------------
# Reopen Rejected Expense (/expenses/{id}/reopen)
# -----------------------------------------------------------------------------
@router.post("/expenses/{expense_id}/reopen", response_class=HTMLResponse)
def reopen_expense_action(
    expense_id: int,
    request: Request,
    user: dict = Depends(get_current_user),
):
    session_id = request.cookies.get("session_id")
    try:
        reopen_expense(expense_id, SessionRequest(session_id=session_id))
    except HTTPException as e:
        return Response(f"<span style='color: #b91c1c;'>Error: {e.detail}</span>", status_code=e.status_code)

    # Fetch updated expense to render row
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT e.*, u.username 
        FROM expenses e 
        JOIN users u ON e.user_id = u.id 
        WHERE e.id = %s
    """, (expense_id,))
    updated_exp = cursor.fetchone()
    db.close()

    if not updated_exp:
        return Response("Expense not found", status_code=404)

    # Re-render single expense row
    return templates.TemplateResponse(
        request=request,
        name="partials/_expense_rows.html",
        context={
            "user": user,
            "expenses": [updated_exp],
            "total": 1,
            "page": 1,
            "limit": 1,
            "total_pages": 1,
        },
    )


# -----------------------------------------------------------------------------
# Approvals Workflow (/approvals, /approvals/{id}/approve, /approvals/{id}/reject)
# -----------------------------------------------------------------------------
@router.get("/approvals", response_class=HTMLResponse)
def approvals_page(
    request: Request,
    user: dict = Depends(require_role(["Manager"])),
):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Managers can only approve submitted expenses from other users (not their own)
    cursor.execute("""
        SELECT e.*, u.username 
        FROM expenses e 
        JOIN users u ON e.user_id = u.id 
        WHERE e.status = 'submitted' AND e.user_id != %s 
        ORDER BY e.created_at ASC
    """, (user["id"],))
    pending_expenses = cursor.fetchall()
    db.close()

    return templates.TemplateResponse(
        request=request,
        name="approvals.html",
        context={
            "user": user,
            "active_page": "approvals",
            "expenses": pending_expenses,
            "error": None,
        },
    )


@router.post("/approvals/{expense_id}/approve", response_class=HTMLResponse)
def approve_expense_action(
    expense_id: int,
    request: Request,
    user: dict = Depends(require_role(["Manager"])),
):
    session_id = request.cookies.get("session_id")
    try:
        approve_expense(expense_id, SessionRequest(session_id=session_id))
    except HTTPException as e:
        return Response(f"<span style='color: #b91c1c;'>Error: {e.detail}</span>", status_code=e.status_code)

    # Fetch updated expense to re-render row in-place
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT e.*, u.username 
        FROM expenses e 
        JOIN users u ON e.user_id = u.id 
        WHERE e.id = %s
    """, (expense_id,))
    updated_exp = cursor.fetchone()
    db.close()

    return templates.TemplateResponse(
        request=request,
        name="partials/_approval_row.html",
        context={"user": user, "exp": updated_exp},
    )


@router.post("/approvals/{expense_id}/reject", response_class=HTMLResponse)
def reject_expense_action(
    expense_id: int,
    request: Request,
    rejection_reason: str = Form(...),
    user: dict = Depends(require_role(["Manager"])),
):
    session_id = request.cookies.get("session_id")
    reason_clean = rejection_reason.strip()

    if len(reason_clean) < 5:
        return Response("<span style='color: #b91c1c;'>Rejection reason must be at least 5 characters.</span>", status_code=400)

    try:
        reject_expense(
            expense_id,
            RejectAction(session_id=session_id, rejection_reason=reason_clean),
        )
    except HTTPException as e:
        return Response(f"<span style='color: #b91c1c;'>Error: {e.detail}</span>", status_code=e.status_code)

    # Fetch updated expense to re-render row in-place
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT e.*, u.username 
        FROM expenses e 
        JOIN users u ON e.user_id = u.id 
        WHERE e.id = %s
    """, (expense_id,))
    updated_exp = cursor.fetchone()
    db.close()

    return templates.TemplateResponse(
        request=request,
        name="partials/_approval_row.html",
        context={"user": user, "exp": updated_exp},
    )
