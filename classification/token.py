import logging
import sys
from typing import Text, Optional, Union, Dict, List, Any, Tuple

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
                    label_ids.append(int(self.model.config.label2id[label[word_idx]]))
                # For the other tokens in a word, we set the label to either the current label or -100, depending on
                # the label_all_tokens flag.
                else:
                    if label_all_tokens:
                        label_ids.append(int(self.model.config.b2i_label[self.model.config.label2id[label[word_idx]]]))
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
                        f"Your model was initialized with different number of labels: "
                        f"model num labels: {self.config.num_labels}, dataset num labels: {num_labels}\n"
                        f"Re-initializing the linear classifier to match with the number of labels of the dataset."
                    )
                else:
                    logger.warning(
                        f"Your model seems to have been trained with labels, but they don't match the dataset: "
                        f"model labels: {list(sorted(label_name_to_id.keys()))}, dataset labels: {list(sorted(label_list))}."
                        f"\nIgnoring the model labels as a result."
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
        column_names = dataset[split].column_names
        non_id_column_names = [col for col in column_names if col != 'id']
        input_key = "input" if 'input' in non_id_column_names else non_id_column_names[0]
        label_key = "label" if 'label' in non_id_column_names else non_id_column_names[1]
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
            remove_columns=column_names,
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
        truncation = True if self.tokenizer.model_max_length and self.tokenizer.model_max_length > 0 else False
        model_inputs = self.tokenizer(
            inputs,
            return_tensors="pt",
            truncation=truncation,
            return_offsets_mapping=self.tokenizer.is_fast,
        )
        return model_inputs

    def forward(self, model_inputs: Dict[str, Tensor]):
        offset_mapping = model_inputs.pop("offset_mapping", None)
        model_outputs = self.model(**model_inputs)
        return {
            "input_ids": model_inputs["input_ids"],
            "offset_mapping": offset_mapping,
            **model_outputs,
        }

    def postprocess_output(self, model_outputs, activation: Text = "softmax", top_k: int = 1) -> Any:
        logits = model_outputs["logits"][0].detach().numpy()
        input_ids = model_outputs["input_ids"][0]
        offset_mapping = model_outputs["offset_mapping"][0] if model_outputs["offset_mapping"] is not None else None

        maxes = np.max(logits, axis=-1, keepdims=True)
        shifted_exp = np.exp(logits - maxes)
        scores = shifted_exp / shifted_exp.sum(axis=-1, keepdims=True)

        pre_entities = self.gather_pre_entities(input_ids, scores, offset_mapping)
        grouped_entities = self.aggregate(pre_entities)
        return grouped_entities

    def gather_pre_entities(
        self,
        input_ids: np.ndarray,
        scores: np.ndarray,
        offset_mapping: Optional[List[Tuple[int, int]]],
    ) -> List[dict]:
        pre_entities = []
        for idx, token_scores in enumerate(scores):
            if input_ids[idx] in self.tokenizer.all_special_ids:
                continue
            word = self.tokenizer.convert_ids_to_tokens(int(input_ids[idx]))
            if offset_mapping is not None:
                start_ind, end_ind = offset_mapping[idx]
                if not isinstance(start_ind, int):
                    start_ind = start_ind.item()
                    end_ind = end_ind.item()
            else:
                start_ind = None
                end_ind = None

            pre_entity = {
                "word": word,
                "scores": token_scores,
                "start": start_ind,
                "end": end_ind,
                "index": idx,
            }
            pre_entities.append(pre_entity)
        return pre_entities

    def aggregate(self, pre_entities: List[dict]) -> List[dict]:
        entity_groups = []
        entity_group_disagg = []
        subword_prefix = self.tokenizer._tokenizer.model.continuing_subword_prefix
        for pre_entity in pre_entities:
            entity_idx = pre_entity["scores"].argmax()
            score = pre_entity["scores"][entity_idx]
            entity = {
                "entity": self.model.config.id2label[entity_idx],
                "score": score,
                "index": pre_entity["index"],
                "word": pre_entity["word"],
                "start": pre_entity["start"],
                "end": pre_entity["end"],
            }
            if not entity_group_disagg:
                entity_group_disagg.append(entity)
                continue

            bi, tag = self.get_tag(entity["entity"])
            last_bi, last_tag = self.get_tag(entity_group_disagg[-1]["entity"])
            is_subword = entity["word"].strip(subword_prefix) != entity["word"]
            if tag == last_tag and bi != "B" or is_subword:
                entity_group_disagg.append(entity)
            else:
                entity_groups.append(self.group_sub_entities(entity_group_disagg))
                entity_group_disagg = [entity]
        if entity_group_disagg:
            entity_groups.append(self.group_sub_entities(entity_group_disagg))

        return entity_groups

    @staticmethod
    def get_tag(entity_name: str) -> Tuple[str, str]:
        if entity_name.startswith("B-") or entity_name.startswith("I-"):
            bi, tag = entity_name.split('-')
        else:
            bi = "B"
            tag = entity_name
        return bi, tag

    def group_sub_entities(self, entities: List[dict]) -> dict:
        entity = entities[0]["entity"].split("-")[-1]
        scores = np.nanmean([entity["score"] for entity in entities])
        tokens = [entity["word"] for entity in entities]

        entity_group = {
            "entity_group": entity,
            "score": np.mean(scores),
            "word": self.tokenizer.convert_tokens_to_string(tokens),
            "start": entities[0]["start"],
            "end": entities[-1]["end"],
        }
        return entity_group

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
        if type(true_labels[0][0]) == int:
            label_is_int = True
            true_predictions = [p for prediction in true_predictions for p in prediction]
            true_labels = [l for label in true_labels for l in label]
        else:
            label_is_int = False
        results = _DEFAULT_METRIC(predictions=true_predictions, references=true_labels, label_is_int=label_is_int, **kwargs)
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
