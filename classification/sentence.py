import logging
import os
import sys
from typing import Text, Optional, Union, Dict, List, Any

import numpy as np
from torch import nn, Tensor
from transformers import (
    AutoConfig,
    AutoTokenizer,
    AutoModelForSequenceClassification,
    default_data_collator,
    DataCollatorWithPadding, PretrainedConfig, EvalPrediction
)
from utils.helpers import sigmoid, softmax
from model import BaseModel

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%m/%d/%Y %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)


class SentenceClassifier(BaseModel):
    def __init__(
        self,
        task_name: Text,
        model_name: Text,
        num_labels: Optional[int] = None,
        cache_dir: Optional[Text] = None,
        auth_token: Optional[Text] = None,
        use_tf: bool = False,
        use_fast_tokenizer: bool = True,
        ignore_mismatched_sizes: bool = False,
    ):
        super().__init__(
            model_name=model_name,
            cache_dir=cache_dir,
            auth_token=auth_token,
            use_tf=use_tf,
            use_fast_tokenizer=use_fast_tokenizer,
            ignore_mismatched_sizes=ignore_mismatched_sizes
        )
        self.task_name = task_name
        if num_labels is not None:
            self.config = AutoConfig.from_pretrained(
                self.model_name,
                num_labels=num_labels,
                finetuning_task=self.task_name,
                cache_dir=self.cache_dir,
                use_auth_token=self.auth_token,
            )
        else:
            self.config = AutoConfig.from_pretrained(
                self.model_name,
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

    def _get_collator(self, padding: bool = True, fp16: bool = True):
        if padding:
            data_collator = default_data_collator
        elif fp16:
            data_collator = DataCollatorWithPadding(self.tokenizer, pad_to_multiple_of=8)
        else:
            data_collator = None
        return data_collator

    def _preprocess_function(
        self,
        examples,
        input_key_1: Text,
        input_key_2: Optional[Text] = None,
        max_seq_length: int = 128,
        padding: Union[Text, bool] = True,
        label_to_id: Optional[Dict[Text, int]] = None
    ):
        # Tokenize the texts
        args = (
            (examples[input_key_1],) if input_key_2 is None else (examples[input_key_1], examples[input_key_2])
        )
        result = self.tokenizer(*args, padding=padding, max_length=max_seq_length, truncation=True)

        # Map labels to IDs
        if label_to_id is not None and "label" in examples:
            result["label"] = [(label_to_id[l] if l != -1 else -1) for l in examples["label"]]
        return result

    def _init_linear_weights(self):
        self.model.classifier.weight.data.normal_(mean=0.0, std=self.config.initializer_range)
        if self.model.classifier.bias is not None:
            self.model.classifier.bias.data.zero_()

    def _update_model_number_labels(self, label_list: List[Any]) -> None:
        num_labels = len(label_list)
        if self.model.config.label2id != PretrainedConfig(num_labels=num_labels).label2id:
            label_name_to_id = {k.lower(): v for k, v in self.model.config.label2id.items()}
            if list(sorted(label_name_to_id.keys())) == list(sorted(label_list)):
                label_to_id = {i: int(label_name_to_id[label_list[i]]) for i in range(num_labels)}
            else:
                label_to_id = {v: i for i, v in enumerate(label_list)}
                if num_labels != self.config.num_labels:
                    self.model.num_labels = self.config.num_labels = num_labels
                    self.model.classifier = nn.Linear(self.config.hidden_size, self.config.num_labels)
                    self._init_linear_weights()
                    logger.warning(
                        "Your model was initialized with different number of labels: ",
                        f"model num labels: {self.config.num_labels}, dataset num labels: {num_labels}"
                        "Re-initializing the linear classifier to match with the number of labels of the dataset."
                    )
                else:
                    logger.warning(
                        "Your model seems to have been trained with labels, but they don't match the dataset: ",
                        f"model labels: {list(sorted(label_name_to_id.keys()))}, dataset labels: {list(sorted(label_list))}."
                        "\nIgnoring the model labels as a result.",
                    )
        else:
            label_to_id = {v: i for i, v in enumerate(label_list)}
        self.model.config.label2id = label_to_id
        self.model.config.id2label = {id: label for label, id in self.config.label2id.items()}

    def _preprocess_data(
        self,
        dataset,
        max_seq_length: int = 128,
        pad_to_max_length: bool = True,
        overwrite_cache: bool = False,
        do_train: bool = True,
        split: Text = "train"
    ):
        non_label_column_names = [name for name in dataset[split].column_names if name != "label"]
        if "input1" in non_label_column_names and "input2" in non_label_column_names:
            input_key_1, input_key_2 = "input1", "input2"
        elif 'input' in non_label_column_names:
            input_key_1, input_key_2 = "input", None
        else:
            if len(non_label_column_names) >= 2:
                input_key_1, input_key_2 = non_label_column_names[:2]
            else:
                input_key_1, input_key_2 = non_label_column_names[0], None

        padding = "max_length" if pad_to_max_length else False
        if max_seq_length > self.tokenizer.model_max_length:
            logger.warning(
                f"The max_seq_length passed ({max_seq_length}) is larger than the maximum length for the"
                f"model ({self.tokenizer.model_max_length}). Using max_seq_length={self.tokenizer.model_max_length}."
            )
        max_seq_length = min(max_seq_length, self.tokenizer.model_max_length)
        if do_train:
            label_list = dataset[split].unique("label")
            label_list.sort()
            self._update_model_number_labels(label_list)

        processed_dataset = dataset.map(
            self._preprocess_function,
            batched=True,
            load_from_cache_file=not overwrite_cache,
            desc="Running tokenizer on dataset",
            fn_kwargs={
                'max_seq_length': max_seq_length,
                'input_key_1': input_key_1,
                'input_key_2': input_key_2,
                'padding': padding
            }
        )
        return processed_dataset

    @staticmethod
    def compute_metrics(p: EvalPrediction):
        preds = p.predictions[0] if isinstance(p.predictions, tuple) else p.predictions
        preds = np.argmax(preds, axis=1)
        return {"accuracy": (preds == p.label_ids).astype(np.float32).mean().item()}

    def preprocess_input(self, inputs, **kwargs: Dict) -> Dict[str, Tensor]:
        if isinstance(inputs, dict):
            return self.tokenizer(**inputs, return_tensors='pt', **kwargs)
        elif isinstance(inputs, list) and len(inputs) == 1 and isinstance(inputs[0], list) and len(inputs[0]) == 2:
            return self.tokenizer(
                text=inputs[0][0], text_pair=inputs[0][1], return_tensors='pt', **kwargs
            )
        elif isinstance(inputs, list) and len(inputs) == 2:
            return self.tokenizer(
                text=inputs[0], text_pair=inputs[1], return_tensors='pt', **kwargs
            )
        return self.tokenizer(inputs, return_tensors='pt', **kwargs)

    def postprocess_output(self, model_outputs, activation: Text = "softmax", top_k: int = 1) -> Any:
        outputs = model_outputs["logits"][0]
        outputs = outputs.detach().numpy()

        if activation == 'sigmoid':
            scores = sigmoid(outputs)
        elif activation == 'softmax':
            scores = softmax(outputs)
        elif activation is None:
            scores = outputs
        else:
            raise ValueError(f"Unrecognized `activation` argument: {activation}")

        if top_k == 1:
            return {"label": self.model.config.id2label[scores.argmax().item()], "score": scores.max().item()}
        else:
            dict_scores = [
                {"label": self.model.config.id2label[i], "score": score.item()} for i, score in enumerate(scores)
            ]
            dict_scores.sort(key=lambda x: x["score"], reverse=True)
            dict_scores = dict_scores[:top_k]
        return dict_scores
