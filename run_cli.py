import logging
import os
from typing import Text, Optional, Union
import click
import json
import datasets
import transformers

from classification.sentence import SentenceClassifier
from classification.token import TokenClassifier
from utils.helpers import makerdir
from utils.model_selection import select_model_suggestion

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
logger = logging.getLogger(__name__)


@click.group()
def commands():
  pass


@commands.command()
@click.option('--task_name', help='Name of the training task. Currently we only support `sentence-classification')
@click.option('--model_name', help='Path to pretrained model or model identifier from huggingface.co/models.')
@click.option('--output_dir', help='Where to store the final model.')
@click.option('--dataset_name', help='The name of the dataset to use (via the datasets library).')
@click.option('--dataset_config_name', help='The configuration name of the dataset to use (via the datasets library).')
@click.option('--train_file', help='A csv or a json file containing the training data.')
@click.option('--validation_file', help='A csv or a json file containing the validation data.')
@click.option('--max_length', type=int, default=128, help='The maximum total input sequence length after tokenization.')
@click.option('--overwrite_cache', is_flag=True, default=False, help='Overwrite the cached training and evaluation sets.')
@click.option('--resume_from_checkpoint', help='If the training should continue from a checkpoint folder.')
@click.option('--n_train', help='For debugging purposes or quicker training, '
                                'truncate the number of training examples to this value.')
@click.option('--n_eval', help='For debugging purposes or quicker training, '
                               'truncate the number of evaluation examples to this value.')
@click.option('--padding', is_flag=True, default=True, help='Whether to pad all samples to `max_length`.')
@click.option('--fp16', is_flag=True, default=True, help='Whether to use mixed-precision fp16.')
@click.option('--batch_size', type=int, default=32, help='Batch size for the training.')
@click.option('--epochs', type=int, default=3, help='Total number of training epochs to perform.')
@click.option('--lr', type=float, default=3e-5, help='Initial learning rate (after the potential warmup period) to use.')
@click.option('--warmup_steps', type=int, default=0, help='Number of steps for the warmup in the lr scheduler.')
@click.option('--gradient_accumulation_steps', type=int, default=1, help='Number of updates steps to accumulate '
                                                                         'before performing a backward/update pass.')
@click.option('--weight_decay', type=float, default=0.0, help='Weight decay to use.')
@click.option('--hub_token', help='The token to use to pull the model from HuggingFace Hub.')
@click.option('--use_fast', is_flag=True, default=True, help='Whether to use fast Tokenizer.')
@click.option('--overwrite_output_dir', is_flag=True, default=False, help='Whether to overwrite the existing output dir.')
def train(
        task_name: Text,
        model_name: Text,
        output_dir: Optional[Text] = None,
        dataset_name: Optional[Text] = None,
        dataset_config_name: Optional[Text] = None,
        train_file: Optional[Text] = None,
        validation_file: Optional[Text] = None,
        max_length: Optional[int] = 128,
        overwrite_cache: bool = False,
        resume_from_checkpoint: Optional[Text] = None,
        n_train: Optional[int] = None,
        n_eval: Optional[int] = None,
        padding: bool = True,
        fp16: bool = True,
        batch_size: int = 32,
        epochs: int = 3,
        lr: float = 3e-5,
        warmup_steps: int = 0,
        gradient_accumulation_steps: int = 1,
        weight_decay: float = 0.0,
        hub_token: Optional[Text] = None,
        use_fast: bool = True,
        overwrite_output_dir: bool = False,
) -> None:
    logger.setLevel(logging.DEBUG)
    datasets.utils.logging.set_verbosity(logging.DEBUG)
    transformers.utils.logging.set_verbosity(logging.DEBUG)
    if model_name is None:
        model_name, hub_token = select_model_suggestion()
    if task_name == 'sentence-classification':
        model = SentenceClassifier(task_name, model_name, auth_token=hub_token, use_fast_tokenizer=use_fast)
    elif task_name == 'token-classification':
        model = TokenClassifier(task_name, model_name, auth_token=hub_token, use_fast_tokenizer=use_fast)
    else:
        raise ValueError("Currently we only support `sentence-classification` and `token-classification`")
    if output_dir is None:
        output_dir = os.path.join(CURRENT_DIR, 'outputs/')
        makerdir(output_dir)

    model.train(output_dir=output_dir,
                dataset_name=dataset_name,
                dataset_config_name=dataset_config_name,
                train_file=train_file,
                validation_file=validation_file,
                max_seq_length=max_length,
                overwrite_cache=overwrite_cache,
                resume_from_checkpoint=resume_from_checkpoint,
                max_train_samples=n_train,
                max_eval_samples=n_eval,
                pad_to_max_length=padding,
                fp16=fp16,
                num_train_epochs=epochs,
                per_device_train_batch_size=batch_size,
                do_eval=True,
                evaluation_strategy="epoch",
                learning_rate=lr,
                warmup_steps=warmup_steps,
                gradient_accumulation_steps=gradient_accumulation_steps,
                weight_decay=weight_decay,
                overwrite_output_dir=overwrite_output_dir)


@commands.command()
@click.option('--task_name', help='Name of the training task. Currently we only support `sentence-classification')
@click.option('--model_name', help='Path to pretrained model or model identifier from huggingface.co/models.')
@click.option('--eval_file', help='A csv or a json file containing the evaluation data.')
@click.option('--output_dir', help='Where to store the evaluation results.')
@click.option('--max_length', type=int, default=128, help='The maximum total input sequence length after tokenization.')
@click.option('--padding', default='max_length', help='Whether to pad all samples to `max_length`.')
@click.option('--fp16', is_flag=True, default=True, help='Whether to use mixed-precision fp16.')
@click.option('--batch_size', type=int, default=32, help='Batch size for the training.')
@click.option('--metric', type=str, default="accuracy", help='Metric type to compute score.')
@click.option('--metric_average', type=str, default=None, help='Determines the type of averaging performed on '
                                                               'the metrics (used for recall/precision/f1)')
@click.option('--hub_token', help='The token to use to pull the model from HuggingFace Hub.')
@click.option('--use_fast', is_flag=True, default=True, help='Whether to use fast Tokenizer.')
def evaluate(
        task_name: Text,
        model_name: Text,
        output_dir: Optional[Text] = None,
        eval_file: Optional[Text] = None,
        max_length: Optional[int] = 128,
        padding: Union[bool, Text] = True,
        fp16: bool = True,
        batch_size: int = 32,
        metric: Text = "accuracy",
        metric_average: Optional[Text] = None,
        hub_token: Optional[Text] = None,
        use_fast: bool = True,
        **kwargs
):
    logger.setLevel(logging.INFO)
    if task_name == 'sentence-classification':
        model = SentenceClassifier(task_name, model_name, auth_token=hub_token, use_fast_tokenizer=use_fast)
    else:
        raise ValueError("Currently we only support `sentence-classification`")
    if output_dir is None:
        output_dir = os.path.join(CURRENT_DIR, 'outputs/')
        makerdir(output_dir)

    results = model.evaluate(eval_file,
                             batch_size=batch_size,
                             max_length=max_length,
                             padding=padding,
                             fp16=fp16,
                             metric=metric,
                             average=metric_average,
                             **kwargs)
    with open(os.path.join(output_dir, "evaluation_results.json"), 'w') as f:
        results['task_name'] = task_name
        results['model_name'] = model_name
        json.dump(results, f)


if __name__ == "__main__":
  commands()
