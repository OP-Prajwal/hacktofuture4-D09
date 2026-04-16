import os
from datetime import datetime, timedelta
import jwt
import bcrypt
from db.mongo import mongo
import re

# We pre-truncate all passwords in _truncate_password() before they reach bcrypt.
# Using native bcrypt because passlib is incompatible with bcrypt>=4.0

JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_fallback")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days


def normalize_email(email: str) -> str:
    return email.strip().lower()

def _truncate_password(password: str) -> bytes:
    """Truncate password to 72 bytes (bcrypt hard limit)."""
    return password.encode("utf-8")[:72]

def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(_truncate_password(plain_password), hashed_password.encode('utf-8'))

def get_password_hash(password):
    return bcrypt.hashpw(_truncate_password(password), bcrypt.gensalt()).decode('utf-8')

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None

# Slugs deprecated. Using plain workspace names.

def register_user(workspace_type: str, email: str, password: str, name: str, company: str, role: str):
    email = normalize_email(email)
    password = password.strip()
    users = mongo.get_collection("users")
    workspaces = mongo.get_collection("workspaces")
    
    if users.find_one({"email": email}):
        raise ValueError("User with this email already exists")
    
    workspace_name = company if workspace_type == 'enterprise' else f"{name}'s Workspace"
    workspace_id = workspace_name.strip()
    
    # Ensure workspace_id is unique
    base_slug = workspace_id
    counter = 1
    while workspaces.find_one({"workspace": workspace_id}): # Check new primary key 'workspace'
        workspace_id = f"{base_slug} {counter}"
        counter += 1
        
    workspace_doc = {
        "workspace": workspace_id,
        "name": workspace_name,
        "type": workspace_type,
        "created_at": datetime.utcnow()
    }
    workspaces.insert_one(workspace_doc)
    
    hashed_pass = get_password_hash(password)
    user_doc = {
        "email": email,
        "hashed_password": hashed_pass,
        "name": name,
        "role": role,
        "workspace": workspace_id,
        "created_at": datetime.utcnow()
    }
    users.insert_one(user_doc)
    
    # Generate token
    token = create_access_token({"sub": email, "workspace": workspace_id})
    
    return {
        "access_token": token,
        "user": {
            "name": name,
            "email": email,
            "role": role,
            "company": company,
            "type": workspace_type,
            "workspace": workspace_id
        }
    }

def login_user(email: str, password: str):
    email = normalize_email(email)
    password = password.strip()
    users = mongo.get_collection("users")
    user = users.find_one({"email": email})
    
    if not user or not verify_password(password, user["hashed_password"]):
        raise ValueError("Incorrect email or password")
        
    workspaces = mongo.get_collection("workspaces")
    # Legacy migration support: try "workspace", fallback to "workspace_id"
    workspace_id = user.get("workspace", user.get("workspace_id"))
    workspace = workspaces.find_one({"workspace": workspace_id}) or workspaces.find_one({"slug": workspace_id})
    token = create_access_token({"sub": email, "workspace": workspace_id})
    
    company_name = workspace["name"] if workspace["type"] == "enterprise" else ""
    return {
        "access_token": token,
        "user": {
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
            "company": company_name,
            "type": workspace["type"],
            "workspace": workspace_id
        }
    }
