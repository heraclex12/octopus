import logging
import os
from typing import Text, Optional, Union
import click
import json
from classification.sentence import SentenceClassifier
from utils.helpers import makerdir

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
@click.option('--max_length', help='The maximum total input sequence length after tokenization.')
@click.option('--overwrite_cache', help='Overwrite the cached training and evaluation sets.')
@click.option('--resume_from_checkpoint', help='If the training should continue from a checkpoint folder.')
@click.option('--n_train', help='For debugging purposes or quicker training, '
                                'truncate the number of training examples to this value.')
@click.option('--n_eval', help='For debugging purposes or quicker training, '
                               'truncate the number of evaluation examples to this value.')
@click.option('--padding', is_flag=True, default=True, help='Whether to pad all samples to `max_length`.')
@click.option('--fp16', is_flag=True, default=True, help='Whether to use mixed-precision fp16.')
@click.option('--batch_size', help='Batch size for the training.')
@click.option('--epochs', help='Total number of training epochs to perform.')
@click.option('--lr', help='Initial learning rate (after the potential warmup period) to use.')
@click.option('--warmup_steps', help='Number of steps for the warmup in the lr scheduler.')
@click.option('--gradient_accumulation_steps', help='Number of updates steps to accumulate before performing '
                                                    'a backward/update pass.')
@click.option('--weight_decay', help='Weight decay to use.')
@click.option('--hub_token', help='The token to use to pull the model from HuggingFace Hub.')
@click.option('--use_fast', is_flag=True, default=True, help='Whether to use fast Tokenizer.')
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
        use_fast: bool = True
) -> None:
    logger.setLevel(logging.DEBUG)
    if task_name == 'sentence-classification':
        model = SentenceClassifier(task_name, model_name, auth_token=hub_token, use_fast_tokenizer=use_fast)
    else:
        raise ValueError("Currently we only support `sentence-classification`")
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
                weight_decay=weight_decay)


@commands.command()
@click.option('--task_name', help='Name of the training task. Currently we only support `sentence-classification')
@click.option('--model_name', help='Path to pretrained model or model identifier from huggingface.co/models.')
@click.option('--eval_file', help='A csv or a json file containing the evaluation data.')
@click.option('--output_dir', help='Where to store the evaluation results.')
@click.option('--max_length', type=int, default=128, help='The maximum total input sequence length after tokenization.')
@click.option('--padding', default='max_length', help='Whether to pad all samples to `max_length`.')
@click.option('--fp16', is_flag=True, default=True, help='Whether to use mixed-precision fp16.')
@click.option('--batch_size', type=int, default=32, help='Batch size for the training.')
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
        hub_token: Optional[Text] = None,
        use_fast: bool = True
):
    logger.setLevel(logging.INFO)
    if task_name == 'sentence-classification':
        model = SentenceClassifier(task_name, model_name, auth_token=hub_token, use_fast_tokenizer=use_fast)
    else:
        raise ValueError("Currently we only support `sentence-classification`")
    if output_dir is None:
        output_dir = os.path.join(CURRENT_DIR, 'outputs/')
        makerdir(output_dir)

    results = model.evaluate(eval_file, batch_size=batch_size, max_length=max_length, padding=padding, fp16=fp16)
    with open(os.path.join(output_dir, "evaluation_results.json"), 'w') as f:
        results['task_name'] = task_name
        results['model_name'] = model_name
        json.dump(results, f)


if __name__ == "__main__":
  commands()
