import os

from pick import pick
from utils.helpers import pull_from_gcs, makerdir


TEMP_DIR = "/tmp/octopus/models"

DEFAULT_MODEL_SUGGESTION = [
    "moberta-mlm-medium",
    "moberta-mlm-base",
    "moberta-nsp-base",
    "vinai/phobert-base",
    "vinai/phobert-large",
    "microsoft/mdeberta-v3-base",
    "momo-nlp/vimrc-roberta-large-finetuned"
]

BERT_MODEL_FILES = [
    'config.json',
    'pytorch_model.bin',
    'special_tokens_map.json',
    'tokenizer.json',
    'tokenizer_config.json',
    'vocab.txt'
]

PRIVATE_REPO_AUTH = "<ask_nlp_team_to_get_access_token>"

MOBERTA_DOWNLOAD_LINKS = {
    "moberta-mlm-medium": {
        "bucket": "nlp/hieutt/models/moberta_mlm_medium",
        "files": BERT_MODEL_FILES
    },
    "moberta-mlm-base": {
        "bucket": "nlp/hieutt/models/moberta_mlm_base",
        "files": BERT_MODEL_FILES
    },
    "moberta-nsp-base": {
        "bucket": "nlp/hieutt/models/moberta_nsp_medium",
        "files": BERT_MODEL_FILES
    },
}


def select_model_suggestion():
    title = "Please choose one of our model suggestions that are used widely on finetuning Vietnamese datasets:"
    option, index = pick(DEFAULT_MODEL_SUGGESTION, title)
    if option.startswith("vinai/") or option.startswith("microsoft/"):
        return option, None
    if option.startswith("momo-nlp/"):
        return option, PRIVATE_REPO_AUTH
    else:
        saved_model_path = os.path.join(TEMP_DIR, option)
        if os.path.exists(saved_model_path):
            return saved_model_path, None
        makerdir(saved_model_path)
        for filename in MOBERTA_DOWNLOAD_LINKS[option]['files']:
            pull_from_gcs(os.path.join(MOBERTA_DOWNLOAD_LINKS[option]["bucket"], filename),
                          os.path.join(saved_model_path, filename))
        return saved_model_path, None
