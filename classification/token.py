import logging
import sys
from typing import Text, Optional, Union, Dict, List, Any

import numpy as np
from torch import nn, Tensor
from transformers import (
    AutoConfig,
    AutoTokenizer,
    AutoModelForTokenClassification,
    PretrainedConfig,
    DataCollatorForTokenClassification, EvalPrediction
)

from base import BaseModel
from utils import metrics
from utils.helpers import sigmoid, softmax

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%m/%d/%Y %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)

_DEFAULT_METRIC = metrics.seqeval


class TokenClassifier(BaseModel):
    def __init__(
        self,
        task_name: Text,
        model_name: Text,
        num_labels: Optional[int] = None,
        cache_dir: Optional[Text] = None,
        auth_token: Optional[Text] = None,
        use_tf: bool = False,
        use_fast_tokenizer: bool = True,
        ignore_mismatched_sizes: bool = True,
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
        if self.config.model_type in {"gpt2", "roberta"}:
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                cache_dir=self.cache_dir,
                use_fast=self.use_fast_tokenizer,
                use_auth_token=self.auth_token,
                add_prefix_space=True,
            )
        else:
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                cache_dir=self.cache_dir,
                use_fast=self.use_fast_tokenizer,
                use_auth_token=self.auth_token
            )
        self.model = AutoModelForTokenClassification.from_pretrained(
            self.model_name,
            from_tf=self.use_tf,
            config=self.config,
            cache_dir=self.cache_dir,
            use_auth_token=self.auth_token,
            ignore_mismatched_sizes=self.ignore_mismatched_sizes,
        )

    def _get_collator(self, padding: bool = True, fp16: bool = True):
        return DataCollatorForTokenClassification(self.tokenizer, pad_to_multiple_of=8 if fp16 else None)

    def _preprocess_function(
        self,
        examples,
        input_key: Text,
        label_key: Text,
        max_seq_length: int = 128,
        padding: Union[Text, bool] = True,
        label_all_tokens: bool = False,
    ):
        tokenized_inputs = self.tokenizer(
            examples[input_key],
            padding=padding,
            truncation=True,
            max_length=max_seq_length,
            # We use this argument because the texts in our dataset are lists of words (with a label for each word).
            is_split_into_words=True,
        )
        labels = []
        for i, label in enumerate(examples[label_key]):
            word_ids = tokenized_inputs.word_ids(batch_index=i)
            previous_word_idx = None
            label_ids = []
            for word_idx in word_ids:
                # Special tokens have a word id that is None. We set the label to -100, so they are automatically
                # ignored in the loss function.
                if word_idx is None:
                    label_ids.append(-100)
                # We set the label for the first token of each word.
                elif word_idx != previous_word_idx:
                    label_ids.append(self.model.config.label2id[label[word_idx]])
                # For the other tokens in a word, we set the label to either the current label or -100, depending on
                # the label_all_tokens flag.
                else:
                    if label_all_tokens:
                        label_ids.append(self.model.config.b2i_label[self.model.config.label2id[label[word_idx]]])
                    else:
                        label_ids.append(-100)
                previous_word_idx = word_idx

            labels.append(label_ids)
        tokenized_inputs["labels"] = labels
        return tokenized_inputs

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
                        f"Your model was initialized with different number of labels: ",
                        f"model num labels: {self.config.num_labels}, dataset num labels: {num_labels}\n"
                        f"Re-initializing the linear classifier to match with the number of labels of the dataset."
                    )
                else:
                    logger.warning(
                        f"Your model seems to have been trained with labels, but they don't match the dataset: ",
                        f"model labels: {list(sorted(label_name_to_id.keys()))}, dataset labels: {list(sorted(label_list))}."
                        f"\nIgnoring the model labels as a result.",
                    )
        else:
            label_to_id = {v: i for i, v in enumerate(label_list)}
        b_to_i_label = []
        for idx, label in enumerate(label_list):
            if type(label) == str and label.startswith("B-") and label.replace("B-", "I-") in label_list:
                b_to_i_label.append(label_list.index(label.replace("B-", "I-")))
            else:
                b_to_i_label.append(idx)
        self.model.config.b2i_label = b_to_i_label
        self.model.config.label2id = label_to_id
        self.model.config.id2label = {i: l for l, i in self.config.label2id.items()}

    def _preprocess_data(
        self,
        dataset,
        max_seq_length: int = 128,
        pad_to_max_length: bool = True,
        overwrite_cache: bool = False,
        do_train: bool = True,
        split: Text = "train",
        **kwargs,
    ):
        column_names = [col for col in dataset[split].column_names if col != 'id']
        input_key = "input" if 'input' in column_names else column_names[0]
        label_key = "label" if 'label' in column_names else column_names[1]
        padding = "max_length" if pad_to_max_length else False
        if max_seq_length > self.tokenizer.model_max_length:
            logger.warning(
                f"The max_seq_length passed ({max_seq_length}) is larger than the maximum length for the"
                f"model ({self.tokenizer.model_max_length}). Using max_seq_length={self.tokenizer.model_max_length}."
            )
        max_seq_length = min(max_seq_length, self.tokenizer.model_max_length)
        if do_train:
            unique_labels = set()
            for label in dataset[split][label_key]:
                unique_labels = unique_labels | set(label)
            label_list = list(unique_labels)
            label_list.sort()
            self._update_model_number_labels(label_list)

        processed_dataset = dataset.map(
            self._preprocess_function,
            batched=True,
            load_from_cache_file=not overwrite_cache,
            desc="Running tokenizer on dataset",
            fn_kwargs={
                'max_seq_length': max_seq_length,
                'input_key': input_key,
                'label_key': label_key,
                'padding': padding,
                'label_all_tokens': kwargs.get('label_all_tokens')
            }
        )
        return processed_dataset

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

    def compute_metrics(self, p: EvalPrediction, metric: Optional[Text] = None, **kwargs):
        predictions, labels = p
        predictions = np.argmax(predictions, axis=2)

        # Remove ignored index (special tokens)
        true_predictions = [
            [self.model.config.id2label[p] for (p, l) in zip(prediction, label) if l != -100]
            for prediction, label in zip(predictions, labels)
        ]
        true_labels = [
            [self.model.config.id2label[l] for (p, l) in zip(prediction, label) if l != -100]
            for prediction, label in zip(predictions, labels)
        ]

        results = _DEFAULT_METRIC(predictions=true_predictions, references=true_labels)
        if kwargs.get('return_entity_level_metrics'):
            # Unpack nested dictionaries
            final_results = {}
            for key, value in results.items():
                if isinstance(value, dict):
                    for n, v in value.items():
                        final_results[f"{key}_{n}"] = v
                else:
                    final_results[key] = value
            return final_results
        else:
            return {
                "precision": results["overall_precision"],
                "recall": results["overall_recall"],
                "f1": results["overall_f1"],
                "accuracy": results["overall_accuracy"],
            }
