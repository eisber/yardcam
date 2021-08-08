import os, uuid
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from filelock import Timeout, FileLock
import requests
from datetime import datetime 
from requests.auth import HTTPDigestAuth
import dotenv

# load .env
dotenv.load()

AZURE_STORAGE_CONNECTION_STRING = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.environ.get("CONTAINER_NAME")
HOSTNAME = os.environ.get("HOSTNAME")
USERNAME = os.environ.get("USERNAME")
PASSWORD = os.environ.get("PASSWORD")

MAX_RESULT = os.environ.get("MAX_RESULT")

# make sure we don't overlap when called multiple times in crontab
lock = FileLock("/tmp/cam-image.lock", timeout=600)
with lock:
    # fetch image
    print(f"{datetime.now()} Get image...")
    r = requests.get(
            f"http://{HOSTNAME}/axis-cgi/jpg/image.cgi?resolution=1280x720",
            auth=HTTPDigestAuth(USERNAME, PASSWORD))


    # Create filename
    now = datetime.now()
    filename = now.strftime("data-image/%Y/%m/%d/%H-%M-%S-00.jpg")
    print(filename)

    # Upload image
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=filename)
    blob_client.upload_blob(r.content)
