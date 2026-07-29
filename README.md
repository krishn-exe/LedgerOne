# LedgerOne 

LedgerOne is an expense management software designed for organizations to track, monitor, and control corporate spending. It automates expense tracking, simplifies approval workflows.
*currently supports backend API requests only*

## Tech stack

- **Language:** Python 3.14
- **Frameworks:** FastAPI
- **Libraries:** Uvicorn, Pydantic, mysql-connector, hashlib, os, datetime, dotenv, secrets, random
- **Database** MySQL


## Features

- **Registration, Login, User Authentication**
- **Create Expenses, Fetch Expenses**
- **Approval Workflow**
- **Role based Authentication**

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
*Mac*
```bash
python -m venv .venv
source .venv/bin/activate
```

#### 3. Install the external libraries

```bash
pip install fastapi uvicorn pydantic mysql-connector-python python-dotenv
```

#### 4. Setup enviroment variables

Create a .env inside of the "App" folder, and enter the following data
```
MYSQL_PASSWORD= YOUR PASSWORD
MYSQL_HOST= YOUR HOST NAME
MYSQL_USER= YOU USER NAME
```
#### 5. Initialise the database

inside of app/database
```bash
python setup.py
```

#### 6. Populate the database (*optional*)

inside of app/database
```bash
python populate.py
```

#### 6. Run the Server

Inside of app/backend
```bash
uvicorn main:app
```

## Testing

The API utilises the built in **Swagger UI** from FASTAPI for testing and interactive documenting

To access this, on a browser navigate to ```http://localhost:8000/docs```