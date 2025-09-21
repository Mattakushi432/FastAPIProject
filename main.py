import string

from random import choice
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Dict

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from fastapi import FastAPI, Form, Request, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse


class Settings(BaseSettings):
    MONGO_USERNAME: str = ""
    MONGO_PASSWORD: str = ""
    MONGO_HOST: str = "localhost"
    MONGO_PORT: int = 27017
    MONGO_DB_NAME: str = "test"
    MONGO_AUTH_SOURCE: str = "admin"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def build_mongo_uri(s: Settings) -> str:
    if s.MONGO_USERNAME and s.MONGO_PASSWORD:
        return f"mongodb://{s.MONGO_USERNAME}:{s.MONGO_PASSWORD}@{s.MONGO_HOST}:{s.MONGO_PORT}/?authSource={s.MONGO_AUTH_SOURCE}"
    return f"mongodb://{s.MONGO_HOST}:{s.MONGO_PORT}"


settings = Settings()
MONGO_URI = build_mongo_uri(settings)

BASE_DIR = Path(__file__).resolve().parent
SHORT_URLS_LENGTH = 6
ALPHABET = string.ascii_uppercase + string.digits

db_state: Dict[str, AsyncIOMotorClient | AsyncIOMotorDatabase] = {}


def generate_short_code(length: int = SHORT_URLS_LENGTH, alphabet: str = ALPHABET) -> str:
    return ''.join(choice(alphabet) for _ in range(length))


class URLMapping(BaseModel):
    long_url: str
    short_code: str = Field(default_factory=generate_short_code)
    visits: int = 0


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db_state["client"] = AsyncIOMotorClient(MONGO_URI)
    db_state["database"] = db_state["client"][settings.MONGO_DB_NAME]
    yield
    db_state["client"].close()
    print("MongoDB connection closed")


app = FastAPI(title="URL Shorten with MongoDB", lifespan=lifespan)

static_dir = BASE_DIR / "static"
if static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory="templates")


async def generate_unique_short_code() -> str:
    db = db_state["database"]
    while True:
        short_code = ''.join(choice(ALPHABET) for _ in range(SHORT_URLS_LENGTH))
        if await db.urls.find_one({"short_code": short_code}) is None:
            return short_code


@app.get("/", response_class=HTMLResponse, name="root")
async def root(request: Request, short_url: Optional[str] = None) -> HTMLResponse:
    return templates.TemplateResponse("mainpage.html", {"request": request, "short_url": short_url})


@app.post("/", name="shorten")
async def create_url(request: Request, longurl: str = Form(...)) -> RedirectResponse:
    db = db_state["database"]
    existing_mapping = await db.urls.find_one({"long_url": longurl})
    if existing_mapping:
        short_url_code = existing_mapping["short_code"]
    else:
        short_url_code = await generate_unique_short_code()
        new_mapping = URLMapping(long_url=longurl, short_code=short_url_code)
        await db.urls.insert_one(new_mapping.model_dump())
    redirect_url = request.url_for("root").include_query_params(short_url=short_url_code)
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)


@app.get("/{short_code}", name="redirect_to_url")
async def short_url_handler(short_code: str) -> RedirectResponse:
    db = db_state["database"]
    document = await db.urls.find_one_and_update(
        {"short_code": short_code},
        {"$inc": {"visits": 1}}
    )
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Short URL not found"
        )
    return RedirectResponse(url=document["long_url"], status_code=status.HTTP_301_MOVED_PERMANENTLY)
