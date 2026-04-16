# auth.py
from database import DatabaseManager

def validate_credentials(user, password):
    # Intentional bug: if user is None, this will throw an AttributeError
    normalized_user = user.strip().lower() 
    
    # Imagine this hashes the password and checks DB
    db = DatabaseManager()
    db.connect()
    result = db.query(f"SELECT id FROM users WHERE user='{user}' AND pass='{password}'")
    return True

def login_user(user, password):
    if validate_credentials(user, password):
        return "JWT-TOKEN-123"
    return None
