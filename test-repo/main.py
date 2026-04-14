# main.py
from auth import login_user
from database import DatabaseManager
from logger import log_event

def start_server():
    db = DatabaseManager()
    db.connect()
    
    user_token = login_user("admin", "password123")
    if user_token:
        log_event("AUTH", "Server running and admin verified!")
        db.query("SELECT * FROM users")

if __name__ == "__main__":
    start_server()
