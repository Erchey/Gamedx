import os
import sys
sys.path.append("..")

from starlette.responses import RedirectResponse
from fastapi import Depends, HTTPException, status, APIRouter, Request, Response, Form
from pydantic import BaseModel
from typing import Optional
from SchoolApp import models
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from ..database import SessionLocal, engine
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from ..models import Performance, Students, Subjects, Teachers

from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv


load_dotenv(dotenv_path='keys.env')
SECRET_KEY = os.getenv('SECRET_KEY')
ALGORITHM = 'HS256'

templates = Jinja2Templates(directory="SchoolApp/templates")

models.Base.metadata.create_all(bind=engine)

oauth2_bearer = OAuth2PasswordBearer(tokenUrl="token")

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    responses={401: {"user": "Not authorized"}}
)


class LoginForm:
    def __init__(self, request: Request):
        self.request: Request = request
        self.username: Optional[str] = None
        self.password: Optional[str] = None

    async def create_oauth_form(self):
        form = await self.request.form()
        self.username = form.get("email")
        self.password = form.get("password")


def get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


def get_password_hash(password):
    return bcrypt_context.hash(password)


def verify_password(plain_password, hashed_password):
    print(f"plain_password: {plain_password} hashed_password: {hashed_password}")
    return bcrypt_context.verify(plain_password, hashed_password)


def authenticate_user(username: str, password: str, db):
    user = db.query(models.Students).filter(models.Students.username == username).first()

    if not user:
        print("User not found")
        return None

    print(f"Stored hashed password: {user.hashed_password}")  # Debug statement to print the stored hashed password

    if not verify_password(password, user.hashed_password):
        print(f"Password verification failed: {password}")
        return None

    print("Password verification succeeded")
    return user


# Function to authenticate teachers
def authenticate_teacher(username: str, password: str, db):
    teacher = db.query(models.Teachers).filter(models.Teachers.username == username).first()

    if not teacher:
        print("Teacher not found")
        return None  # Return None instead of False

    print(f"Stored hashed password (Teacher): {teacher.hashed_password}")
    if not verify_password(password, teacher.hashed_password):
        print(f"Password verification failed for teacher: {username}")
        return None  # Return None instead of False

    print("Password verification succeeded for teacher")
    return teacher  # Return the teacher object


def create_access_token(username: str, user_id: int, firstname: str, studyhours: Optional[int], expires_delta: Optional[timedelta] = None):
    # Handle null studyhours
    studyhours = studyhours if studyhours is not None else 0
    
    encode = {"sub": username, "id": user_id, "firstname": firstname, "studyhours": studyhours}
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    encode.update({"exp": expire})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)



async def get_current_user(request: Request):
    try:
        token = request.cookies.get("access_token")
        if token is None:
            return None
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("id")
        firstname: str = payload.get("firstname")
        studyhours: int = payload.get("studyhours")
        
        if username is None or user_id is None:
            return None
        
        return {"username": username, "id": user_id, "firstname": firstname, "studyhours": studyhours}
    except JWTError:
        return None


@router.post("/token")
async def login_for_access_token(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    
    token_expires = timedelta(minutes=60)
    token = create_access_token(user.username, user.id, user.first_name, user.study_hours, expires_delta=token_expires)

    # Set the token as a cookie in the response
    response.set_cookie(key="access_token", value=token, httponly=True)

    return {"access_token": token, "token_type": "bearer"}



@router.get("/", response_class=HTMLResponse)
async def authentication_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/", response_class=HTMLResponse)
async def login(request: Request, db: Session = Depends(get_db)):
    form = LoginForm(request)
    await form.create_oauth_form()
    
    form_data = OAuth2PasswordRequestForm(
        grant_type=None, 
        username=form.username, 
        password=form.password, 
        scope='', 
        client_id=None, 
        client_secret=None
    )
    user = authenticate_user(form_data.username, form_data.password, db)

    if user is None:
        msg = "Incorrect Username or Password"
        return templates.TemplateResponse("teacher-login.html", {"request": request, "msg": msg})

    

    # Authenticate and login user
    response = RedirectResponse(url=f"/dashboard/student/{user.id}", status_code=status.HTTP_302_FOUND)

    try:
        validate_user_cookie = await login_for_access_token(response=response, form_data=form_data, db=db)

        if not validate_user_cookie:
            msg = "Incorrect Username or Password"
            return templates.TemplateResponse("login.html", {"request": request, "msg": msg})
        return response
    except HTTPException as e:
        msg = e.detail
    except Exception:
        msg = "Unknown Error"
    return templates.TemplateResponse("login.html", {"request": request, "msg": msg, "user": None})


@router.get("/teachers", response_class=HTMLResponse)
async def authentication_page(request: Request):
    return templates.TemplateResponse("teacher-login.html", {"request": request})


@router.post("/teachers", response_class=HTMLResponse)
async def login(request: Request, db: Session = Depends(get_db)):
    # Initialize and validate the form
    form = LoginForm(request)
    await form.create_oauth_form()

    # Convert the login form to OAuth2PasswordRequestForm data
    form_data = OAuth2PasswordRequestForm(
        grant_type=None,
        username=form.username,
        password=form.password,
        scope='',
        client_id=None,
        client_secret=None
    )

    # Authenticate the teacher
    teacher_auth = authenticate_teacher(form_data.username, form_data.password, db)

    # Check if authentication is successful
    if teacher_auth is None:
        msg = "Incorrect Username or Password"
        return templates.TemplateResponse("teacher-login.html", {"request": request, "msg": msg})

    # Create response for redirection after successful login
    teacher_id = teacher_auth.id  # Now this will work since teacher_auth is guaranteed to be a valid teacher object here
    response = RedirectResponse(url=f"/dashboard/teacher/{teacher_id}", status_code=status.HTTP_302_FOUND)

    try:
        # Validate user cookie and create access token
        token_expires = timedelta(minutes=60)
        token = create_access_token(teacher_auth.username, teacher_auth.id, teacher_auth.first_name, teacher_auth.id, expires_delta=token_expires)

        # Set the token as a cookie in the response
        response.set_cookie(key="access_token", value=token, httponly=True)

        return response
    except HTTPException as e:
        msg = e.detail
    except Exception as ex:
        msg = str(ex)  # Capture the exception message for logging
        print(f"Exception occurred: {msg}")

    # Return to login page with error message in case of failure
    return templates.TemplateResponse("teacher-login.html", {"request": request, "msg": msg})


@router.get("/register", response_class=HTMLResponse)
async def register(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register", response_class=HTMLResponse)
async def register_user(request: Request, email: str = Form(...), username: str = Form(...),
                        firstname: str = Form(...), lastname: str = Form(...),
                        password: str = Form(...), password2: str = Form(...), gender: str = Form(...),
                        age: int = Form(...), g_name: str = Form(...), g_mail: str = Form(...),
                        g_phone: str = Form(...), state: str = Form(...),
                        db: Session = Depends(get_db)):

    validation1 = db.query(models.Students).filter(models.Students.username == username).first()

    validation2 = db.query(models.Students).filter(models.Students.email == email).first()

    if password != password2 or validation1 is not None or validation2 is not None:
        msg = "Invalid registration request"
        return templates.TemplateResponse("register.html", {"request": request, "msg": msg})

    user_model = models.Students()
    user_model.username = username
    user_model.email = email
    user_model.first_name = firstname
    user_model.last_name = lastname
    user_model.gender = gender
    user_model.age = age
    user_model.guardian_name = g_name
    user_model.guardian_mail = g_mail
    user_model.guardian_phone = g_phone
    user_model.state_of_origin = state
    

    hash_password = get_password_hash(password)
    user_model.hashed_password = hash_password
    user_model.is_active = True

    db.add(user_model)
    db.commit()

    msg = "Student Profile successfully created"
    return templates.TemplateResponse("login.html", {"request": request, "msg": msg})

@router.get("/register-teacher", response_class=HTMLResponse)
async def register(request: Request):
    return templates.TemplateResponse("register-teacher.html", {"request": request})


@router.post("/register-teacher", response_class=HTMLResponse)
async def register_user(request: Request, email: str = Form(...), username: str = Form(...),
                        firstname: str = Form(...), lastname: str = Form(...),
                        password: str = Form(...), password2: str = Form(...), gender: str = Form(...),
                        age: int = Form(...), address: str = Form(...), subject: str = Form(...),
                        db: Session = Depends(get_db)):

    # Check if username or email exists in Teachers
    validation1 = db.query(models.Teachers).filter(models.Teachers.username == username).first()
    validation2 = db.query(models.Teachers).filter(models.Teachers.email == email).first()

    if password != password2 or validation1 is not None or validation2 is not None:
        msg = "Invalid registration request."
        return templates.TemplateResponse("register-teacher.html", {"request": request, "msg": msg})

    # Check if the subject exists in the Subjects table
    subject_record = db.query(models.Subjects).filter(models.Subjects.subject_name == subject).first()

    # If subject doesn't exist, insert it
    if subject_record is None:
        new_subject = models.Subjects(subject_name=subject)
        db.add(new_subject)
        db.commit()
        db.refresh(new_subject)

    # Create new teacher
    user_model = models.Teachers()
    user_model.username = username
    user_model.email = email
    user_model.first_name = firstname
    user_model.last_name = lastname
    user_model.gender = gender
    user_model.age = age
    user_model.address = address
    user_model.subjects = subject  # Save subject directly as a string

    # Hash the password
    hash_password = get_password_hash(password)
    user_model.hashed_password = hash_password

    try:
        # Add new teacher to the database
        db.add(user_model)
        db.commit()
        msg = "User successfully created"
    except Exception as e:
        # Rollback in case of error
        db.rollback()
        msg = f"Error occurred: {str(e)}"
    
    return templates.TemplateResponse("login.html", {"request": request, "msg": msg})


@router.get("/logout")
async def logout(request: Request):
    msg = "Logout Successful"
    response = templates.TemplateResponse("login.html", {"request": request, "msg": msg})
    response.delete_cookie(key="access_token")
    return response

