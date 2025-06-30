from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db, User
from models import TokenData

# Security configuration
SECRET_KEY = "your-secret-key-here-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT token scheme
security = HTTPBearer()

# Hardcoded users
HARDCODED_USERS = {
    "recruiter": {
        "email": "recruiter",
        "password": "recruiter123",
        "role": "recruiter"
    },
    "arrequestor": {
        "email": "arrequestor",
        "password": "arrequestor123",
        "role": "ar_requestor"
    }
}

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def authenticate_user(db, username: str, password: str):
    user = HARDCODED_USERS.get(username)
    if not user or user["password"] != password:
        return False
    class UserObj:
        def __init__(self, username, role):
            self.username = username
            self.role = role
    return UserObj(user["email"], user["role"])

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not isinstance(username, str) or not username:
            return None
        token_data = TokenData(email=username)
        return token_data
    except JWTError:
        return None

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db=None):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token_data = verify_token(credentials.credentials)
    if token_data is None or not isinstance(token_data.email, str):
        raise credentials_exception
    user = HARDCODED_USERS.get(token_data.email)
    if user is None:
        raise credentials_exception
    class UserObj:
        def __init__(self, username, role):
            self.username = username
            self.role = role
    return UserObj(user["email"], user["role"])

def get_current_user_role(current_user: User = Depends(get_current_user)):
    return current_user.role

def require_role(*required_roles):
    roles = tuple(str(r) for r in required_roles)
    def role_checker(current_user = Depends(get_current_user)):
        if (current_user.role not in roles) and (current_user.role != "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return current_user
    return role_checker 