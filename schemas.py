# schemas.py
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# Token schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    phone: Optional[str] = None

# User schemas
class UserBase(BaseModel):
    name: str
    phone: str

class UserCreate(UserBase):
    password: Optional[str] = None

class UserLogin(BaseModel):
    phone: str
    password: Optional[str] = None

class UserResponse(UserBase):
    id: int
    created_at: datetime
    
    class Config:
        orm_mode = True

# Comment schemas
class CommentBase(BaseModel):
    message: str

class CommentCreate(CommentBase):
    pass

class CommentResponse(CommentBase):
    id: int
    product_id: int
    phone: str
    timestamp: datetime
    
    class Config:
        orm_mode = True

# ProductImage schemas
class ProductImageBase(BaseModel):
    image_url: str

class ProductImageCreate(ProductImageBase):
    pass

class ProductImageResponse(ProductImageBase):
    id: int
    
    class Config:
        orm_mode = True

# Product schemas
class ProductBase(BaseModel):
    title: str
    description: str
    category: str
    price: float

class ProductCreate(ProductBase):
    pass

class ProductUpdate(ProductBase):
    pass

class ProductResponse(ProductBase):
    id: int
    user_phone: str
    created_at: datetime
    updated_at: datetime
    images: List[ProductImageResponse] = []
    
    class Config:
        orm_mode = True