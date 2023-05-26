import uuid
from typing import List

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from pydantic import BaseModel

import os

from app.app import find_skills, get_jobs, clean_jobs, text_process, visualize

# setup loggers
static_directory = "static" if os.getenv('JK_STATIC_DIR') is None else os.getenv('JK_STATIC_DIR')


def create_static_dir_if_not_exists():
    if not os.path.exists(static_directory):
        os.makedirs(static_directory)
    print(f"Static directory: {os.path.abspath(static_directory)}")


create_static_dir_if_not_exists()

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.mount("/static", StaticFiles(directory=static_directory), name="static")

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


class CreateSearchTaskRequest(BaseModel):
    searchToken: str


class Skill(BaseModel):
    name: str
    occurences: int


class CreateSearchTaskResponse(BaseModel):
    uuid: str
    imageUrl: str
    skills: List[Skill]


@app.get("/")
@limiter.limit("5/second")
async def root(request: Request):
    return {"message": "Hello Bigger Applications!"}


def transform_skills(skills):
    skill_list = []
    skill_dict = skills.to_dict('records')
    for skill in skill_dict:
        skill_list.append(Skill(name=skill['word'], occurences=skill['occurences']))
    return skill_list


@app.post("/search/tasks")
@limiter.limit("5/second")
async def create_search_task(body: CreateSearchTaskRequest, request: Request):
    id = str(uuid.uuid4())

    job_title = body.searchToken
    # Set your Google Cloud Storage project ID
    project_id = "job-selector"

    # Set the name of the bucket where you want to upload the image
    bucket_name = "job_images_bucket"

    # Set the name you want to give the image in Google Cloud Storage
    gcs_file_name = os.path.join(static_directory, f"{id}.png")

    # Get the skills
    job_data = get_jobs([0, 10, 20, 30], job_title)  # Get the jobs
    job_descriptions = clean_jobs(job_data)  # Clean the job description
    clean_texts = text_process(job_descriptions)  # Clean the job description text
    skills = find_skills(clean_texts)  # Aggregates the words
    visualize(skills, project_id, bucket_name, gcs_file_name)  # Visualizes the text and creates a URL

    skill_list: List[Skill] = transform_skills(skills)

    return CreateSearchTaskResponse(uuid=id, imageUrl=f"http://localhost:8000/static/{id}.png", skills=skill_list)


@app.get("/search/tasks/{task_id}")
@limiter.limit("5/second")
async def get_search_task(task_id: str, request: Request):
    return {"task-id": task_id}
