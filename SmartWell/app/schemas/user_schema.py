from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from uuid import UUID

class AccountCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)

class UserCreate(AccountCreate):
    role: str = Field(default="user")


class PasswordReset(BaseModel):
    password: str = Field(..., min_length=8, max_length=72)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    role: str = "user"
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=72)
    new_password: str = Field(..., min_length=8, max_length=72)

class AccountDelete(BaseModel):
    confirm: bool = Field(default=False)