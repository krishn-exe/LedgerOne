# LedgerOne 

LedgerOne is an expense management platform designed for organizations to track, monitor, and control corporate spending. It automates expense tracking and simplifies approval workflows with both a REST API and a lightweight, reactive web frontend.

## Tech stack

- **Language:** Python 3.14
- **Backend Framework:** FastAPI, Uvicorn, Starlette
- **Frontend & Templating:** Jinja2, HTMX (script tag CDN), Pico CSS v2 (CDN)
- **Database:** MySQL (`mysql-connector-python`)
- **Libraries:** Pydantic, python-dotenv, python-multipart, hashlib, secrets

## Features

- **Interactive Web Interface:** Served directly by FastAPI with zero Node/build steps.
- **Reactive UI with HTMX:** Partial DOM updates for filtering, submission, approving, and rejecting without full-page reloads.
- **Semantic, Clean Styling:** Responsive UI powered by Pico CSS.
- **Secure Cookie-Based Authentication:** `HttpOnly`, `SameSite=Lax` cookies for browser sessions, with automated redirects to `/login` when unauthorized.
- **Role-Based Access Control (RBAC):** Server-side enforced permissions tailored for `Employee`, `Manager`, and `Finance` roles.
- **Interactive Dashboard:** Role-tailored expense summary cards (Total Spent, Pending, Approved, Rejected) and recent activity logs.
- **Expenses Filter & Pagination:** Real-time filtering by status (`submitted`, `approved`, `rejected`) and category (`Meals`, `Travel`, `Software`, `Equipment`, `Other`).
- **Approval Workflow:** Dedicated approvals queue for managers with inline Approve and Reject (with required reason) actions.
- **Rejected Expense Resubmission:** Employees can reopen and edit/resubmit their rejected expenses in place.
- **Full REST API Compatibility:** Existing JSON endpoints remain completely intact and documented in Swagger UI (`/docs`).

## Setup

#### 1. Clone the repository

```bash
git clone https://github.com/krishn-exe/LedgerOne.git
cd LedgerOne
```

#### 2. Setup python virtual environment (*optional*)

*Windows*
```bash
python -m venv .venv
.venv\Scripts\activate
```

*Mac / Linux*
```bash
python -m venv .venv
source .venv/bin/activate
```

#### 3. Install dependencies

```bash
pip install fastapi uvicorn pydantic mysql-connector-python python-dotenv jinja2 python-multipart
```

#### 4. Setup environment variables

Create a `.env` file inside the `App/` folder (or project root) with your database credentials:
```env
MYSQL_PASSWORD=YOUR_PASSWORD
MYSQL_HOST=localhost
MYSQL_USER=root
```

#### 5. Initialize the database

Inside `App/Database` (or from project root):
```bash
python App/Database/setup.py
```

#### 6. Populate demo seed data (*optional*)

```bash
python App/Database/populate.py
```
*Demo accounts seeded with password `password123`:*
- **Employee:** `employee_1` (Submit & view personal expenses)
- **Manager:** `manager_7` (Review, approve, or reject team expenses)
- **Finance:** `finance_10` (Audit all expenses and organization reports)

#### 7. Run the Server

```bash
cd App/Backend
uvicorn main:app --reload
```

## Web UI Pages & URLs

Once the server is running (`http://localhost:8000`):

| URL | Description | Access |
|---|---|---|
| [`/login`](http://localhost:8000/login) | Sign in with username & password | Public |
| [`/register`](http://localhost:8000/register) | Create a new employee account | Public |
| [`/dashboard`](http://localhost:8000/dashboard) | Role-tailored summary stats & recent expenses | Authenticated |
| [`/expenses`](http://localhost:8000/expenses) | Filterable expenses list with HTMX partial table updates | Authenticated |
| [`/expenses/new`](http://localhost:8000/expenses/new) | Create a new expense claim with inline validation | Employee, Manager |
| [`/approvals`](http://localhost:8000/approvals) | Queue to approve or reject pending claims in-place | Manager only |
| [`/logout`](http://localhost:8000/logout) | Clears session cookie and redirects to `/login` | Authenticated |

## API Documentation

The REST API utilizes FastAPI's built-in **Swagger UI**:
Navigate to [`http://localhost:8000/docs`](http://localhost:8000/docs) in your browser.