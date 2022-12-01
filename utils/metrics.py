import importlib
from typing import Optional, Union, List, Text, Any

from sklearn.metrics import (
    f1_score,
    recall_score,
    precision_score,
    accuracy_score,
    roc_auc_score,
    mean_squared_error,
    classification_report
)
from seqeval.metrics import classification_report as entity_classification_report


SUPPORTED_METRICS = ["accuracy", "f1", "recall", "precision", "mse", "roc_auc", "seqeval"]


def recall(
        predictions,
        references,
        labels: Optional[List[int]] = None,
        pos_label: int = 1,
        average: Optional[Text] = None,
        sample_weight: Optional[List[int]] = None,
        zero_division: Union[Text, int] = "warn",
        **kwargs
):
    score = recall_score(
        references,
        predictions,
        labels=labels,
        pos_label=pos_label,
        average=average,
        sample_weight=sample_weight,
        zero_division=zero_division,
    )
    return {"recall": float(score) if score.size == 1 else score.tolist()}


def precision(
        predictions,
        references,
        labels: Optional[List[int]] = None,
        pos_label: int = 1,
        average: Optional[Text] = None,
        sample_weight: Optional[List[int]] = None,
        zero_division: Union[Text, int] = "warn",
        **kwargs
):
    score = precision_score(
        references,
        predictions,
        labels=labels,
        pos_label=pos_label,
        average=average,
        sample_weight=sample_weight,
        zero_division=zero_division,
    )
    return {"precision": float(score) if score.size == 1 else score.tolist()}


def f1(
        predictions,
        references,
        labels: Optional[List[int]] = None,
        pos_label: int = 1,
        average: Optional[Text] = None,
        sample_weight: Optional[List[int]] = None,
        **kwargs
):
    score = f1_score(
        references, predictions, labels=labels, pos_label=pos_label, average=average, sample_weight=sample_weight
    )
    return {"f1": float(score) if score.size == 1 else score.tolist()}


def accuracy(predictions, references, normalize: bool = True, sample_weight: Optional[List[int]] = None, **kwargs):
    return {
        "accuracy": float(
            accuracy_score(references, predictions, normalize=normalize, sample_weight=sample_weight)
        )
    }


def seqeval(
        predictions,
        references,
        suffix: bool = False,
        scheme: Optional[Text] = None,
        mode: Optional[Text] = None,
        sample_weight: Optional[List[int]] = None,
        zero_division: Union[Text, int] = "warn",
        labels: Optional[List[Any]] = None,
        target_names: Optional[List[Any]] = None,
        label_is_int: bool = False,
        **kwargs
):
    if not label_is_int:
        if scheme is not None:
            try:
                scheme_module = importlib.import_module("seqeval.scheme")
                scheme = getattr(scheme_module, scheme)
            except AttributeError:
                raise ValueError(f"Scheme should be one of [IOB1, IOB2, IOE1, IOE2, IOBES, BILOU], got {scheme}")
        report = entity_classification_report(
            y_true=references,
            y_pred=predictions,
            suffix=suffix,
            output_dict=True,
            scheme=scheme,
            mode=mode,
            sample_weight=sample_weight,
            zero_division=zero_division,
        )
    else:
        report = classification_report(
            y_true=references,
            y_pred=predictions,
            output_dict=True,
            labels=labels,
            target_names=target_names,
            sample_weight=sample_weight,
            zero_division=zero_division,
        )
    report.pop("macro avg")
    report.pop("weighted avg")
    if "micro avg" in report:
        overall_score = report.pop("micro avg")
        scores = {
            type_name: {
                "precision": score["precision"],
                "recall": score["recall"],
                "f1": score["f1-score"],
                "number": score["support"],
            }
            for type_name, score in report.items()
        }
        scores["overall_precision"] = overall_score["precision"]
        scores["overall_recall"] = overall_score["recall"]
        scores["overall_f1"] = overall_score["f1-score"]
        scores["overall_accuracy"] = accuracy_score(y_true=references, y_pred=predictions)
    else:
        overall_score = report.pop("accuracy")
        scores = {
            type_name: {
                "precision": score["precision"],
                "recall": score["recall"],
                "f1": score["f1-score"],
                "number": score["support"],
            }
            for type_name, score in report.items()
        }
        scores["overall_precision"] = overall_score
        scores["overall_recall"] = overall_score
        scores["overall_f1"] = overall_score
        scores["overall_accuracy"] = overall_score
    return scores


def roc_auc(
        predictions,
        references,
        average: Text = "macro",
        sample_weight: Optional[List[int]] = None,
        max_fpr: Optional[float] = None,
        multi_class: Text = "raise",
        labels: Optional[List[int]] = None,
        **kwargs
):
    return {
        "roc_auc": roc_auc_score(
            references,
            predictions,
            average=average,
            sample_weight=sample_weight,
            max_fpr=max_fpr,
            multi_class=multi_class,
            labels=labels,
        )
    }


def mse(
        predictions,
        references,
        sample_weight: Optional[List[int]] = None,
        multioutput: Text = "uniform_average",
        squared: bool = True,
        **kwargs
):
    return {"mse": mean_squared_error(
        references, predictions, sample_weight=sample_weight, multioutput=multioutput, squared=squared
        )
    }
