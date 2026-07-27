import mysql.connector
import os
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

def get_db():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database="ledger"
    )

db = get_db()
cursor = db.cursor()

cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
cursor.execute("TRUNCATE TABLE expenses")
cursor.execute("TRUNCATE TABLE users")
cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

roles = (
    ['Employee'] * 6 + 
    ['Manager'] * 3 + 
    ['Finance'] * 1
)

user_ids = []

for i, role in enumerate(roles):
    username = f"{role.lower()}_{i+1}"
    dummy_hash = "dummy_hash_12345"
    dummy_salt = "dummy_salt_abcde"
    
    cursor.execute("""
        INSERT INTO users (username, password_hash, salt, role)
        VALUES (%s, %s, %s, %s)
    """, (username, dummy_hash, dummy_salt, role))
    
    user_ids.append(cursor.lastrowid)


expense_templates = [
    ("Client Lunch", "Meals"),
    ("Flight to Mumbai", "Travel"),
    ("AWS Hosting", "Software"),
    ("New Keyboard", "Equipment"),
    ("Taxi to Office", "Travel"),
    ("Team Dinner", "Meals"),
    ("Adobe License", "Software"),
    ("Office Supplies", "Other")
]

statuses = ['submitted', 'approved', 'rejected']
rejection_reasons = [
    "Amount exceeds policy limits.",
    "Missing clear description.",
    "Category is incorrect.",
    "Not a business expense."
]

total_expenses = 0
current_time = datetime.now()

for user_id in user_ids:
    num_expenses = random.randint(3, 4)
    
    for _ in range(num_expenses):
        title, category = random.choice(expense_templates)
        amount = round(random.uniform(500.00, 15000.00), 2)
        status = random.choice(statuses)
        
        reason = random.choice(rejection_reasons) if status == 'rejected' else None
        
        days_ago = random.randint(0, 30)
        hours_ago = random.randint(0, 23)
        random_date = current_time - timedelta(days=days_ago, hours=hours_ago)

        cursor.execute("""
            INSERT INTO expenses 
            (title, amount, category, status, user_id, rejection_reason, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            title, 
            amount, 
            category, 
            status, 
            user_id, 
            reason, 
            random_date, 
            random_date
        ))
        total_expenses += 1

db.commit()
cursor.close()
db.close()

print("Database populated successfully!")