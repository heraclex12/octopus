import logging
import os
import sys
from typing import Text, Optional

from transformers import Trainer

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%m/%d/%Y %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)


class AutoModel:
    def __init__(
            self,
            task_name: Text,
            model_name: Text,
            cache_dir: Optional[Text] = None,
            auth_token: Optional[Text] = None,
            use_tf: bool = False,
            use_fast_tokenizer: bool = True,
            ignore_mismatched_sizes: bool = False,
    ):
        self.task_name = task_name
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.use_tf = use_tf
        self.auth_token = auth_token
        self.use_fast_tokenizer = use_fast_tokenizer
        self.ignore_mismatched_sizes = ignore_mismatched_sizes
        if task_name == 'sentence-classification':
            pass

    def train(self):
        pass

    def evaluate(self):
        pass

    def predict(self):
        pass
