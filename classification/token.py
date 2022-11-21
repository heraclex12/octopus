from typing import Text

from model import BaseModel


class TokenClassifier(BaseModel):
    def __init__(self, task_name: Text):
        super().__init__(task_name)
