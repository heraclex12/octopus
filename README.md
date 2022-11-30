# Octopus

Standardized framework to train and evaluate NLP models fast and easily.
No need to have advanced knowledge of implementing or training NLP models.

### Prerequisites

In order to run this framework, you have to install some dependencies as follows:
```commandline
$ pip install -r requirements.txt
```

Some dependencies include:
- transformers==4.24.0
- datasets==2.7.0
- torch==1.12.1

If you want to use a GPU/CUDA, you must install PyTorch with the matching CUDA Version.
Follow [PyTorch - Get Started](https://pytorch.org/get-started/locally/) for further details how to install PyTorch.

## Instructions

There are two ways to use this framework:
1. via command line (CLI)
2. via import python module

### Getting started with python module
This example shows you how to train/evaluate/inference a Text Classification model.
```python
from classification.sentence import SentenceClassifier

model = SentenceClassifier('sentence-classification',
                           <model_name>)
model.train(output_dir="./",
            train_file=<path_to_train_file>,
            validation_file=<path_to_validation_file>,
            num_train_epochs=3,
            max_seq_length=128,
            learning_rate=3e-5,
            weight_decay=0.0,
            warmup_steps=0,
            gradient_accumulation_steps=1,
            per_device_train_batch_size=16,
            do_eval=True,
            fp16=True,
            evaluation_strategy="epoch")

# Evaluate a file
print("Result:", model.evaluate(eval_filename))

# Predict an input sentence
print(model.predict("Good night 😊"))

# Output
# {"positive": 0.8466}
```

### Getting started with CLI

🔮 The guide below shows you how to train a Text classifier via CLI.
```commandline
python3 run_cli.py train --task_name=sentence-classification \
                          --model_name=<model_name> \
                          --train_file=<path_to_train_file> \
                          --validation_file=<path_to_validation_file> \
                          --output_dir=./ \
                          --lr=3e-5 \
                          --epochs=3 \
                          --max_length=128 \
                          --warmup_steps=0 \
                          --weight_decay=0.0 \
                          --batch_size=16 \
                          --gradient_accumulation_steps=1 \
                          --fp16
```

For training, if you don't know what pretrained model to use, just remove the `model_name` argument then we will show you a list of model suggestions.

🔥 To evaluate the model,
```commandline
python3 run_cli.py evaluate --task_name=sentence-classification \
                             --model_name=<model_name> \
                             --eval_file=<path_to_train_file> \
                             --max_length=128 \
                             --batch_size=32 \
                             --fp16
```

### Sample Data Format

For sentence classification, we define `input,label` or `input1,input2,label` (sentence pair) as default column names.
Instead of using our default column names, you can use arbitrary column names for one or two sentence columns but have to make sure that
your label column name is `label`.

CSV format
```
input,label
sentence1,label1
sentence2,label2
...
```

JSON format
```json lines
{"id": 1, "input": "<sentence_1>", "label": "<label_1>"}
{"id": 2, "input": "<sentence_2>", "label": "<label_2>"}
...
```

## Application Examples

Currently, we support applications below:
- [Text Classification](./classification/README.md)
- [Token Classification](./classification/README.md)

Please refer to specific application example for more details.

## Contact

If you want to get help or have any questions, don't hesitate to drop our NLP team a message or contact **hieu.tran5** directly.