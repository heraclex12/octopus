import logging
import os
import sys
import random
from typing import Text, Optional

import numpy as np
from datasets import load_dataset
from torch.utils.data import DataLoader, Dataset
from transformers import (
    Trainer,
    EvalPrediction,
    AutoConfig,
    AutoModel,
    AutoTokenizer,
    default_data_collator,
    DataCollator
)
from transformers.trainer_utils import get_last_checkpoint

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%m/%d/%Y %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)


class BaseModel:
    def __init__(
            self,
            model_name: Text,
            cache_dir: Optional[Text] = None,
            auth_token: Optional[Text] = None,
            use_tf: bool = False,
            use_fast_tokenizer: bool = True,
            ignore_mismatched_sizes: bool = False,
    ):
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.use_tf = use_tf
        self.auth_token = auth_token
        self.use_fast_tokenizer = use_fast_tokenizer
        self.ignore_mismatched_sizes = ignore_mismatched_sizes
        self.config = AutoConfig()
        self.model = AutoModel.from_config(self.config)
        self.tokenizer = AutoTokenizer()

    def _train(
            self,
            train_dataset: Dataset,
            eval_dataset: Dataset,
            data_collator: DataCollator,
            output_dir: Text,
            resume_from_checkpoint: Optional[Text] = None,
            max_train_samples: Optional[int] = None,
            overwrite_output_dir: bool = False
    ):
        for index in random.sample(range(len(train_dataset)), 3):
            logger.info(f"Sample {index} of the training set: {train_dataset[index]}.")

        # Detecting last checkpoint.
        last_checkpoint = None
        if os.path.isdir(output_dir) and not overwrite_output_dir:
            last_checkpoint = get_last_checkpoint(output_dir)
            if last_checkpoint is None and len(os.listdir(output_dir)) > 0:
                raise ValueError(
                    f"Output directory ({output_dir}) already exists and is not empty. "
                    "Use --overwrite_output_dir to overcome."
                )
            elif last_checkpoint is not None and resume_from_checkpoint is None:
                logger.info(
                    f"Checkpoint detected, resuming training at {last_checkpoint}. To avoid this behavior, change "
                    "the `--output_dir` or add `--overwrite_output_dir` to train from scratch."
                )

        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            compute_metrics=self.compute_metrics,
            tokenizer=self.tokenizer,
            data_collator=data_collator,
        )
        checkpoint = None
        if resume_from_checkpoint is not None:
            checkpoint = resume_from_checkpoint
        elif last_checkpoint is not None:
            checkpoint = last_checkpoint
        train_result = trainer.train(resume_from_checkpoint=checkpoint)
        metrics = train_result.metrics
        max_train_samples = (max_train_samples if max_train_samples is not None else len(train_dataset))
        metrics["train_samples"] = min(max_train_samples, len(train_dataset))

        trainer.save_model()  # Saves the tokenizer too for easy upload

        trainer.log_metrics("train", metrics)
        trainer.save_metrics("train", metrics)
        trainer.save_state()

    def _load_dataset(
        self,
        dataset_name: Optional[Text] = None,
        dataset_config_name: Optional[Text] = None,
        train_file: Optional[Text] = None,
        validation_file: Optional[Text] = None,
        max_train_samples: Optional[int] = None,
        max_eval_samples: Optional[int] = None
    ):
        if dataset_name is not None:
            # Downloading and loading a dataset from the hub.
            raw_datasets = load_dataset(
                dataset_name,
                dataset_config_name,
                cache_dir=self.cache_dir,
                use_auth_token=self.auth_token,
            )
        else:
            # Loading a dataset from your local files.
            # CSV/JSON training and evaluation files are needed.
            data_files = {"train": train_file, "validation": validation_file}
            extension = train_file.split(".")[-1]
            for key in data_files.keys():
                logger.info(f"load a local file for {key}: {data_files[key]}")
            raw_datasets = load_dataset(
                extension,
                data_files=data_files,
                cache_dir=self.cache_dir,
                use_auth_token=self.auth_token,
            )
        train_dataset = raw_datasets['train']
        if max_train_samples:
            max_train_samples = min(len(train_dataset), max_train_samples)
            train_dataset = train_dataset.select(range(max_train_samples))
        if "validation" in raw_datasets:
            eval_dataset = raw_datasets['validation']
            if max_eval_samples:
                max_eval_samples = min(len(eval_dataset), max_eval_samples)
                eval_dataset = eval_dataset.select(range(max_eval_samples))
        else:
            eval_dataset = None
        return train_dataset, eval_dataset

    @staticmethod
    def _get_collator():
        return default_data_collator

    def train(
            self,
            output_dir: Text,
            dataset_name: Optional[Text] = None,
            dataset_config_name: Optional[Text] = None,
            train_file: Optional[Text] = None,
            validation_file: Optional[Text] = None,
            resume_from_checkpoint: Optional[Text] = None,
            max_train_samples: Optional[int] = None,
            max_eval_samples: Optional[int] = None,
            overwrite_output_dir: bool = False
    ):
        if dataset_name is None and train_file is None:
            raise ValueError("Need either a training/validation file or a dataset name.")
        else:
            train_extension = train_file.split(".")[-1]
            assert train_extension in ["csv", "json"], "`train_file` should be a csv or a json file."
            if validation_file is not None:
                validation_extension = validation_file.split(".")[-1]
                assert (
                        validation_extension == train_extension
                ), "`validation_file` should have the same extension (csv or json) as `train_file`."

        train_dataset, eval_dataset = self._load_dataset(dataset_name=dataset_name,
                                                         dataset_config_name=dataset_config_name,
                                                         train_file=train_file,
                                                         validation_file=validation_file,
                                                         max_train_samples=max_train_samples,
                                                         max_eval_samples=max_eval_samples)
        self._train(
            train_dataset,
            eval_dataset,
            data_collator=self._get_collator(),
            output_dir=output_dir,
            resume_from_checkpoint=resume_from_checkpoint,
            max_train_samples=max_train_samples,
            overwrite_output_dir=overwrite_output_dir
        )

    def evaluate(self):
        pass

    def predict(self):
        pass

    @staticmethod
    def compute_metrics(p: EvalPrediction):
        preds = p.predictions[0] if isinstance(p.predictions, tuple) else p.predictions
        preds = np.argmax(preds, axis=1)
        return {"accuracy": (preds == p.label_ids).astype(np.float32).mean().item()}
