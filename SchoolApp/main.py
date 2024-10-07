from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from .models import Base
from .database import engine
from .routers import auth, performance, users
from starlette.staticfiles import StaticFiles
from starlette import status

app = FastAPI()

Base.metadata.create_all(bind=engine)

app.mount("/static", StaticFiles(directory="SchoolApp/static"), name="static")

@app.get("/")
async def root():
    return RedirectResponse(url="/auth", status_code=status.HTTP_302_FOUND)

app.include_router(auth.router)
app.include_router(performance.router)
app.include_router(users.router)

