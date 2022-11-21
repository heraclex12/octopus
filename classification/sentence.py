from typing import Text, Optional

from transformers import AutoConfig, AutoTokenizer, AutoModelForSequenceClassification

from model import BaseModel


class SentenceClassifier(BaseModel):
    def __init__(
        self,
        task_name: Text,
        model_name: Text,
        num_labels: int,
        cache_dir: Optional[Text] = None,
        auth_token: Optional[Text] = None,
        use_tf: bool = False,
        use_fast_tokenizer: bool = True,
        ignore_mismatched_sizes: bool = False,
    ):
        super().__init__(
            task_name,
            model_name=model_name,
            auth_token=auth_token,
            cache_dir=cache_dir,
            use_tf=use_tf,
            use_fast_tokenizer=use_fast_tokenizer,
            ignore_mismatched_sizes=ignore_mismatched_sizes
        )
        self.config = AutoConfig.from_pretrained(
            self.model_name,
            num_labels=num_labels,
            finetuning_task=self.task_name,
            cache_dir=self.cache_dir,
            use_auth_token=self.auth_token,
        )
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            cache_dir=self.cache_dir,
            use_fast=self.use_fast_tokenizer,
            use_auth_token=self.auth_token
        )
        self.model = AutoModelForSequenceClassification.from_pretrained(
            self.model_name,
            from_tf=self.use_tf,
            config=self.config,
            cache_dir=self.cache_dir,
            use_auth_token=self.auth_token,
            ignore_mismatched_sizes=self.ignore_mismatched_sizes,
        )

