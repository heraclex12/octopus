import os
import numpy as np


def sigmoid(_outputs):
    return 1.0 / (1.0 + np.exp(-_outputs))


def softmax(_outputs):
    maxes = np.max(_outputs, axis=-1, keepdims=True)
    shifted_exp = np.exp(_outputs - maxes)
    return shifted_exp / shifted_exp.sum(axis=-1, keepdims=True)


def makerdir(path: str, exist_ok=True):
  if not os.path.exists(path):
    os.makedirs(path, mode=0o776, exist_ok=exist_ok)
