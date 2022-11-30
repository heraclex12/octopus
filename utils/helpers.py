import os
import numpy as np
from google.cloud import storage


def sigmoid(_outputs):
    return 1.0 / (1.0 + np.exp(-_outputs))


def softmax(_outputs):
    maxes = np.max(_outputs, axis=-1, keepdims=True)
    shifted_exp = np.exp(_outputs - maxes)
    return shifted_exp / shifted_exp.sum(axis=-1, keepdims=True)


def makerdir(path: str, exist_ok=True):
  if not os.path.exists(path):
    os.makedirs(path, mode=0o776, exist_ok=exist_ok)


def pull_from_gcs(source: str, destination: str):
    client = storage.Client(project="momovn-dev-us")
    bucket = client.bucket("momovn-models-dev")
    blob = bucket.blob(source)
    blob.download_to_filename(destination)
