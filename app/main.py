import json
import os
import uuid
from typing import List
import contextlib

import pandas
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

import sqlite3

from app.app import (
    find_skills,
    get_jobs,
    clean_jobs,
    text_process,
    visualize
)

# Configuration
STATIC_DIRECTORY = os.getenv('JK_STATIC_DIR', 'static')
DOMAIN = os.getenv('JK_DOMAIN', 'http://localhost:8000')

connection = sqlite3.connect("job-keywords.db")


def create_static_dir_if_not_exists():
    if not os.path.exists(STATIC_DIRECTORY):
        os.makedirs(STATIC_DIRECTORY)
    print(f"Static directory: {os.path.abspath(STATIC_DIRECTORY)}")


create_static_dir_if_not_exists()


@contextlib.contextmanager
def get_db_cursor():
    cursor = connection.cursor()
    try:
        yield cursor
    finally:
        cursor.close()


def create_db_tables():
    with get_db_cursor() as cursor:
        cursor.execute(
            """
                create table if not exists requests (
                    requestId TEXT not null primary key, 
                    search_text TEXT not null, 
                    skills TEXT not null,
                    created_at TEXT not null,
                    ip_address TEXT
                )
            """
        )
        cursor.execute(
            """
                create table if not exists cached_requests (
                    search_text TEXT not null primary key, 
                    skills TEXT not null,
                    image_url TEXT not null,
                    created_at not null
                )
            """
        )
        connection.commit()


create_db_tables()


def get_cached_request(search_text):
    with get_db_cursor() as cursor:
        cursor.execute(
            """
                select skills, image_url, created_at from cached_requests where search_text = ?
            """,
            (search_text,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return {
            "skills": row[0],
            "imageUrl": row[1],
            "createdAt": row[2]
        }


def cache_request(search_text, skills, image_url):
    with get_db_cursor() as cursor:
        cursor.execute(
            """
                insert into cached_requests (search_text, skills, image_url, created_at) 
                values (?, ?, ?, datetime('now'))
            """,
            (search_text, skills, image_url)
        )
        connection.commit()


def save_request(request_id, search_text, skills):
    with get_db_cursor() as cursor:
        cursor.execute(
            """
                insert into requests (requestId, search_text, skills, created_at) values (?, ?, ?, datetime('now'))
            """,
            (request_id, search_text, skills)
        )
        connection.commit()


def clone_file(src, dst):
    with open(src, 'rb') as file_src:
        with open(dst, 'wb') as file_dst:
            file_dst.write(file_src.read())


# Middleware Setup
limiter = Limiter(key_func=get_remote_address)
app = FastAPI()

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.mount("/static", StaticFiles(directory=STATIC_DIRECTORY), name="static")

origins = [
    "https://job-keywords.khremin.com",
    "http://localhost:63342"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Models
class CreateSearchTaskRequest(BaseModel):
    searchToken: str


class Skill(BaseModel):
    name: str
    occurrences: int


class CreateSearchTaskResponse(BaseModel):
    uuid: str
    imageUrl: str
    skills: List[Skill]


@app.get("/")
@limiter.limit("5/second")
async def root(request: Request):
    return {"message": "Hello!"}


def transform_skills(skills):
    return [Skill(name=skill['word'], occurrences=skill['occurrences']) for skill in skills.to_dict('records')]


@app.post("/search/tasks")
@limiter.limit("5/second")
async def create_search_task(body: CreateSearchTaskRequest, request: Request):
    task_id = str(uuid.uuid4())

    job_title = str.strip(body.searchToken)

    # Set the name you want to give the image in Google Cloud Storage
    gcs_file_name = os.path.join(STATIC_DIRECTORY, f"{task_id}.png")

    # check if we have a cached request
    cached_request = get_cached_request(job_title)
    if cached_request is not None:
        save_request(task_id, job_title, cached_request["skills"])

        clone_file(cached_request["imageUrl"], gcs_file_name)

        return CreateSearchTaskResponse(uuid=task_id, imageUrl=f"{DOMAIN}/static/{task_id}.png",
                                        skills=transform_skills(pandas.DataFrame(json.loads(cached_request["skills"]))))

    # Set your Google Cloud Storage project ID
    project_id = "job-selector"

    # Set the name of the bucket where you want to upload the image
    bucket_name = "job_images_bucket"

    # Get the skills
    job_data = get_jobs([0, 10, 20, 30], job_title)  # Get the jobs
    job_descriptions = clean_jobs(job_data)  # Clean the job description
    clean_texts = text_process(job_descriptions)  # Clean the job description text
    skills = find_skills(clean_texts)  # Aggregates the words
    visualize(skills, project_id, bucket_name, gcs_file_name)  # Visualizes the text and creates a URL

    skill_list: List[Skill] = transform_skills(skills)

    cached_file_name = os.path.join(STATIC_DIRECTORY, f"cached_{task_id}.png")

    # cache the request
    cache_request(job_title, skills.to_json(), cached_file_name)
    clone_file(gcs_file_name, cached_file_name)

    save_request(task_id, job_title, skills.to_json())

    return CreateSearchTaskResponse(uuid=task_id, imageUrl=f"{DOMAIN}/static/{task_id}.png",
                                    skills=skill_list)


@app.get("/search/tasks/{task_id}")
@limiter.limit("5/second")
async def get_search_task(task_id: str, request: Request):
    return {"task-id": task_id}
