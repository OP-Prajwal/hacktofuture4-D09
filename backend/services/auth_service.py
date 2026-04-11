import os
from datetime import datetime, timedelta
import jwt
from passlib.context import CryptContext
from db.mongo import mongo
import re

# Password hashing config
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__truncate_error=False)

JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_fallback")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

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

def generate_slug(name: str):
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug

def register_user(workspace_type: str, email: str, password: str, name: str, company: str, role: str):
    users = mongo.get_collection("users")
    workspaces = mongo.get_collection("workspaces")
    
    if users.find_one({"email": email}):
        raise ValueError("User with this email already exists")
    
    workspace_name = company if workspace_type == 'enterprise' else f"{name}'s Workspace"
    workspace_slug = generate_slug(workspace_name)
    
    # Ensure workspace_slug is unique
    base_slug = workspace_slug
    counter = 1
    while workspaces.find_one({"slug": workspace_slug}):
        workspace_slug = f"{base_slug}-{counter}"
        counter += 1
        
    workspace_doc = {
        "slug": workspace_slug,
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
        "workspace_slug": workspace_slug,
        "created_at": datetime.utcnow()
    }
    users.insert_one(user_doc)
    
    # Generate token
    token = create_access_token({"sub": email, "workspace": workspace_slug})
    
    return {
        "access_token": token,
        "user": {
            "name": name,
            "email": email,
            "role": role,
            "company": company,
            "type": workspace_type,
            "workspace": workspace_slug
        }
    }

def login_user(email: str, password: str):
    users = mongo.get_collection("users")
    user = users.find_one({"email": email})
    
    if not user or not verify_password(password, user["hashed_password"]):
        raise ValueError("Incorrect email or password")
        
    workspaces = mongo.get_collection("workspaces")
    workspace = workspaces.find_one({"slug": user["workspace_slug"]})
    
    token = create_access_token({"sub": email, "workspace": user["workspace_slug"]})
    
    company_name = workspace["name"] if workspace["type"] == "enterprise" else ""
    return {
        "access_token": token,
        "user": {
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
            "company": company_name,
            "type": workspace["type"],
            "workspace": user["workspace_slug"]
        }
    }
