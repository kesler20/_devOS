from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, status
import modelOS_spec.infrastructure.adapters as adapters
import typing
import json
from pydantic import BaseModel

APP_NAME = "modelOS_spec Model API"
APP_VERSION = "1.0"

no_sql_db = adapters.RedisTopicResourceAdapter()
ts_db = adapters.RedisTimeSeriesAdapter()

app = FastAPI(title=APP_NAME, version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===========================#
#                            #
#   TIME SERIES DATA QUERY   #
#                            #
# ===========================#


@app.get("/processData/{convertedKey}/{offset}/{resolution}")
async def process_data(
    convertedKey: str,
    offset: int,
    resolution: typing.Literal["seconds", "minutes", "hours", "days", "weeks"],
):
    data_points = ts_db.query(
        key=convertedKey,
        offset=offset,
        resolution=resolution,
    )
    return data_points


# ============================#
#                             #
#   RESOURCES CRUD ENDPOINTS  #
#                             #
# ============================#
# This is the part of the code that interfaces with the Frontend to manage resources


class ResourcePayload(BaseModel):
    resourceName: str
    resourceContent: str


class ResourceUpdatePayload(BaseModel):
    resourceContent: str


@app.post("/resources/{topic}", status_code=status.HTTP_201_CREATED)
async def create_resource(topic: str, payload: ResourcePayload):
    print("Creating resource...")
    try:
        parsed_content = json.loads(payload.resourceContent)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in resourceContent")
    result = no_sql_db.put_resource(topic, payload.resourceName, parsed_content)
    return result


@app.post("/resources/{topic}/{topicPath}", status_code=status.HTTP_201_CREATED)
async def create_resource_in_path(topic: str, topicPath: str, payload: ResourcePayload):
    print("Creating resource in subtopic...")
    try:
        parsed_content = json.loads(payload.resourceContent)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in resourceContent")
    resource_id = f"{topicPath}:{payload.resourceName}"
    result = no_sql_db.put_resource(topic, resource_id, parsed_content)
    return result


@app.get("/resources/{topic}/{resourceName}")
async def get_resource(topic: str, resourceName: str):
    print("Fetching resource...")
    resource = await no_sql_db.get_resource(topic, resourceName)
    if resource:
        return resource
    raise HTTPException(status_code=404, detail="Resource not found")


@app.get("/resources/{topic}")
async def list_resources(topic: str):
    print("Listing resources...")
    resources = await no_sql_db.get_resources(topic)
    return resources


@app.put("/resources/{topic}/{resourceName}")
async def update_resource(
    topic: str, resourceName: str, payload: ResourceUpdatePayload
):
    print("Updating resource...")
    try:
        parsed_content = json.loads(payload.resourceContent)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in resourceContent")
    new_name = parsed_content.get("name") if isinstance(parsed_content, dict) else None

    if isinstance(new_name, str) and new_name and new_name != resourceName:
        no_sql_db.delete_resource(topic, resourceName)
        target_name = new_name
    else:
        target_name = resourceName

    result = no_sql_db.put_resource(topic, target_name, parsed_content)
    return result


@app.delete("/resources/{topic}/{resourceName}")
async def delete_resource(topic: str, resourceName: str):
    print("Deleting resource...")
    result = no_sql_db.delete_resource(topic, resourceName)
    return result


# ============================#
#                             #
#   GENERAL CRUD ENDPOINTS    #
#                             #
# ============================#


@app.get("/", tags=["root"])
async def read_root():
    return RedirectResponse(url="/docs")
