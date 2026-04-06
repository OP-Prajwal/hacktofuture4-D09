# main.py
from auth import login_user
from database import DatabaseManager

def start_server():
    db = DatabaseManager()
    db.connect()
    
    user_token = login_user("admin", "password123")
    if user_token:
        print("Server running!")
        db.query("SELECT * FROM users")

if __name__ == "__main__":
    start_server()
