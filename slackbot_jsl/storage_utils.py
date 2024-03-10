import os
from google.cloud import storage as gcs
from google.cloud.storage.blob import Blob
env_dict = {key:os.environ.get(key, "") for key in ["GCP_PROJ_ID","GCP_CS_BUKT_SLACK"]}

def __get_client() -> gcs.Client:
    # キーが1個でも足りなければ失敗
    if (missing_key:= next((key for key, value in env_dict.items() if value == ""), None)) and missing_key != None:
        raise EnvironmentError(f"ENV:{missing_key} not found.")
    return gcs.Client(env_dict["GCP_PROJ_ID"])

def __get_bucket() -> gcs.Bucket:
    client = __get_client()
    return client.bucket(env_dict["GCP_CS_BUKT_SLACK"])

def get_file_list() -> dict[str, Blob]:
    blobs:list[Blob] = __get_bucket().list_blobs()
    return {blob.name: blob for blob in blobs if blob.size != 0}

def get_filename_list() -> list[str]:
    return list(get_file_list().keys())

def get_file(blob_name:str) -> bytes:
    blob_dict = get_file_list()
    if blob_name not in blob_dict:
        raise KeyError(f"key:{blob_name} not found.")
    return blob_dict[blob_name].download_as_bytes()

# アプリを起動します
if __name__ == "__main__":
    result = get_file_list()
    print(result)