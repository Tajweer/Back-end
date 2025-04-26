# main.py
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import jwt
import os
import shutil
import bcrypt
from dotenv import load_dotenv

from database import SessionLocal, engine
import models
import schemas

# Load environment variables
load_dotenv()

# Create database tables
models.Base.metadata.create_all(bind=engine)

# Create FastAPI instance
app = FastAPI(title="Tajweer Marketplace API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, replace with your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-tajweer-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# OAuth2 setup
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Create uploads directory if it doesn't exist
UPLOAD_DIRECTORY = "uploads"
if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)

# Mount static files directory for serving images
app.mount("/images", StaticFiles(directory=UPLOAD_DIRECTORY), name="images")

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Authentication functions
def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def authenticate_user(db: Session, phone: str, password: str = ""):
    # In your app, authentication is just by phone number
    # but we'll make it more secure with an optional password
    user = db.query(models.User).filter(models.User.phone == phone).first()
    if not user:
        return False
    if password and not verify_password(password, user.password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        phone: str = payload.get("sub")
        if phone is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    
    user = db.query(models.User).filter(models.User.phone == phone).first()
    if user is None:
        raise credentials_exception
    return user

# Token endpoint
@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.phone}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# User endpoints
@app.post("/users/", response_model=schemas.UserResponse)
async def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.phone == user.phone).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Phone number already registered")
    
    password = user.password if user.password else "default-password"  # You might want to handle this differently
    hashed_password = get_password_hash(password)
    
    db_user = models.User(
        name=user.name,
        phone=user.phone,
        password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.get("/users/me/", response_model=schemas.UserResponse)
async def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user

@app.post("/users/login/", response_model=schemas.Token)
async def login_user(user_login: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.phone == user_login.phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.phone}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Product endpoints
@app.post("/products/", response_model=schemas.ProductResponse)
async def create_product(
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    price: float = Form(...),
    images: List[UploadFile] = File([]),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Create product
    product = models.Product(
        title=title,
        description=description,
        category=category,
        price=price,
        user_phone=current_user.phone
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    
    # Save images
    image_urls = []
    for image in images:
        product_images_dir = os.path.join(UPLOAD_DIRECTORY, f"product_{product.id}")
        if not os.path.exists(product_images_dir):
            os.makedirs(product_images_dir)
        
        file_location = os.path.join(product_images_dir, image.filename)
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(image.file, file_object)
        
        image_url = f"/images/product_{product.id}/{image.filename}"
        image_urls.append(image_url)
        
        # Add image to database
        db_image = models.ProductImage(
            product_id=product.id,
            image_url=image_url
        )
        db.add(db_image)
    
    db.commit()
    
    # Refresh product to get the images
    db.refresh(product)
    return product

@app.get("/products/", response_model=List[schemas.ProductResponse])
async def get_products(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.Product)
    
    if category:
        query = query.filter(models.Product.category == category)
    
    if search:
        query = query.filter(
            (models.Product.title.ilike(f"%{search}%")) | 
            (models.Product.description.ilike(f"%{search}%"))
        )
    
    products = query.offset(skip).limit(limit).all()
    return products

@app.get("/products/my/", response_model=List[schemas.ProductResponse])
async def get_my_products(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    products = db.query(models.Product).filter(
        models.Product.user_phone == current_user.phone
    ).all()
    return products

@app.get("/products/{product_id}", response_model=schemas.ProductResponse)
async def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@app.put("/products/{product_id}", response_model=schemas.ProductResponse)
async def update_product(
    product_id: int,
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    price: float = Form(...),
    images: List[UploadFile] = File([]),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if product.user_phone != current_user.phone:
        raise HTTPException(status_code=403, detail="Not authorized to update this product")
    
    # Update product
    product.title = title
    product.description = description
    product.category = category
    product.price = price
    product.updated_at = datetime.utcnow()
    
    # Handle new images if uploaded
    if images:
        # Delete old images if requested
        product_images_dir = os.path.join(UPLOAD_DIRECTORY, f"product_{product.id}")
        
        # Delete existing image records
        db.query(models.ProductImage).filter(models.ProductImage.product_id == product.id).delete()
        
        # Create directory if needed
        if not os.path.exists(product_images_dir):
            os.makedirs(product_images_dir)
        
        # Save new images
        for image in images:
            file_location = os.path.join(product_images_dir, image.filename)
            with open(file_location, "wb+") as file_object:
                shutil.copyfileobj(image.file, file_object)
            
            image_url = f"/images/product_{product.id}/{image.filename}"
            
            # Add image to database
            db_image = models.ProductImage(
                product_id=product.id,
                image_url=image_url
            )
            db.add(db_image)
    
    db.commit()
    db.refresh(product)
    return product

@app.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if product.user_phone != current_user.phone:
        raise HTTPException(status_code=403, detail="Not authorized to delete this product")
    
    # Delete product images
    db.query(models.ProductImage).filter(models.ProductImage.product_id == product.id).delete()
    
    # Delete comments
    db.query(models.Comment).filter(models.Comment.product_id == product.id).delete()
    
    # Delete the product
    db.delete(product)
    db.commit()
    
    # Clean up image directory
    product_images_dir = os.path.join(UPLOAD_DIRECTORY, f"product_{product_id}")
    if os.path.exists(product_images_dir):
        shutil.rmtree(product_images_dir)
    
    return {"status": "success"}

# Comment endpoints
@app.post("/products/{product_id}/comments/", response_model=schemas.CommentResponse)
async def create_comment(
    product_id: int,
    comment: schemas.CommentCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    db_comment = models.Comment(
        product_id=product_id,
        phone=current_user.phone,
        message=comment.message,
        timestamp=datetime.utcnow()
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment

@app.get("/products/{product_id}/comments/", response_model=List[schemas.CommentResponse])
async def get_product_comments(
    product_id: int,
    db: Session = Depends(get_db)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    comments = db.query(models.Comment).filter(
        models.Comment.product_id == product_id
    ).all()
    
    return comments

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)