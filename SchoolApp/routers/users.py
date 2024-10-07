import sys

from fastapi.templating import Jinja2Templates
sys.path.append("..")


from typing import Annotated
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from fastapi import Depends, APIRouter, HTTPException, Request, Form
from starlette import status
from ..models import Students
from passlib.context import CryptContext
from ..database import SessionLocal, engine
from .auth import get_current_user, verify_password, get_password_hash
from SchoolApp import models


router = APIRouter(
    prefix='/users',
    tags=['users'],
    responses={404: {"description": "Not Found"}}
    )

models.Base.metadata.create_all(bind=engine)

templates = Jinja2Templates(directory="SchoolApp/templates")

def get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


class Userverification(BaseModel):
    username: str
    password: str
    new_password: str

@router.get("/edit-password", response_class=HTMLResponse)
async def edit_user_view(request: Request):
    user = await get_current_user(request)
    if user is None:
        return RedirectResponse(url="/auth", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse("edit-user-password.html", {"request": request, "user": user})

@router.post("/edit-password", response_class=HTMLResponse)
async def user_password_change(request: Request, username: str = Form(...),
                               password: str = Form(...), password2: str = Form(...),
                               db: Session = Depends(get_db)):
    
    user = await get_current_user(request)
    if user is None:
        return RedirectResponse(url="/auth", status_code=status.HTTP_302_FOUND)
    
    
    user_data = db.query(Students).filter(Students.username == username).first()

    msg = "Invalid username or password"

    if user_data is not None:
        if username == user_data.username and verify_password(password, user_data.hashed_password):
            user_data.hashed_password = get_password_hash(password2)
            db.add(user_data)
            db.commit()
            msg = "Password Updated"

    return templates.TemplateResponse("edit-user-password.html", {"request": request, "user": user, "msg": msg})
 
    

# bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

# class UserRequest(BaseModel):
#     current_password: str = Field(min_length=3, max_length=100)
#     new_password: str = Field(min_length=3, max_length=100)


# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


# db_dependency = Annotated[Session, Depends(get_db)]
# user_dependency = Annotated[dict, Depends(get_current_user)]

# @router.get("/{user_id}", response_class=HTMLResponse)
# async def edit_todo(request: Request, user_id: int, db: Session = Depends(get_db)):
#     user = db.query(Users).filter(Users.id == user_id).first()

# @router.get('/', status_code=status.HTTP_200_OK)
# async def get_user(user: user_dependency, db: db_dependency):
#     if user is None:
#         raise HTTPException(status_code=401, detail='Authentication Failed')
#     return db.query(Users).filter(Users.id == user.get('id')).first()


# @router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
# async def change_password(user:user_dependency, db: db_dependency, user_request: UserRequest):
#     if user is None:
#         raise HTTPException(status_code=401, detail='Authorization Failed')
    
#     user_model = db.query(Users).filter(Users.id == user.get('id')).first()
#     if not bcrypt_context.verify(user_request.current_password, user_model.hashed_password):
#         raise HTTPException(status_code=401, detail='Error on password change')
#     user_model.hashed_password = bcrypt_context.hash(user_request.new_password)
#     db.add(user_model)
#     db.commit()

# @router.put('/phone/{phone_number}', status_code=status.HTTP_204_NO_CONTENT)
# async def change_phone_number(user:user_dependency, db:db_dependency, phone_number: str):
#     if user is None:
#         raise HTTPException(status_code=401, detail='Authorization Failed')
    
#     user_model = db.query(Users).filter(Users.id == user.get('id')).first()
#     user_model.phone_number = phone_number
#     db.add(user_model)
#     db.commit()
    