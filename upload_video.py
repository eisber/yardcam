import os, uuid
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from filelock import Timeout, FileLock
import re
import requests
import xml.etree.ElementTree as ET
import tqdm
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

lock = FileLock("/tmp/cam-video.lock", timeout=600)
with lock:
    print(f"{datetime.now()} Get recordings...")
    r = requests.get(
            f"http://{HOSTNAME}/axis-cgi/record/list.cgi?maxnumberofresults={MAX_RESULT}&startatresultnumber=0&recordingid=all&sortorder=descending",
            auth=HTTPDigestAuth(USERNAME, PASSWORD))

    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)

    xml_doc = ET.fromstring(r.text)
    t = tqdm.tqdm(list(xml_doc.iter('recording')))
    for recording in t:
        id = recording.get("recordingid")

        # Parse filename
        m = re.search("(\d{4})(\d\d)(\d\d)_(\d\d)(\d\d)(\d\d)", id)
        s = "/".join([m.group(i) for i in range(1, 5)])
        filename = f"data/{s}-{m.group(5)}-{m.group(6)}-00.mkv"

        # Get Blob endpoint
        blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=filename)

        # Don't upload twice
        if not blob_client.exists():
            t.set_description(f"Transferring {filename}...")

            # Stream copy the video
            with requests.get(
                    f"http://{HOSTNAME}/axis-cgi/record/download.cgi?recordingid={id}",
                    stream=True,
                    auth=HTTPDigestAuth(USERNAME, PASSWORD)) as video_req:

                video_req.raise_for_status()

                # upload chunks of 4MB
                blob_id = 0
                for chunk in video_req.iter_content(chunk_size=4*1024*1024):

                    blob_client.stage_block(str(blob_id).zfill(6), chunk)

                    blob_id += 1

                blob_client.commit_block_list(
                        [str(i).zfill(6) for i in range(blob_id)])
