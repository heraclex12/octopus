# Classification

### About

We provide an approach to finetune pretrained language models (i.g., BERT, RoBERTa, etc.) on
Text Classification datasets.

You can use our framework for:

🛸 Task name: `sentence-classification`
  - Binary/Multi-class/Multi-label Sentence Classification (i.g., Sentiment Analysis)
  - Sentence Pairs Classification (i.g., Natural Language Inference)

🛸 Task name: `token-classification`
  - Token/Sequence Classification (i.g., Named entity recognition)

### Sample Data Format

#### For Sentence
Default column names: `input,label` or `input1,input2,label` (sentence pair)


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

Instead of using our default column names, you can use arbitrary column names for one or two first columns but have to make sure that
your label column name is `label`.

#### For Token
Default column names: `input,label`


CSV format (TBD)

JSON format
```json lines
{"id": 1, "input": ["tok1", "tok2", "tok3"], ",label": "<label_1>"}
{"id": 2, "input": ["tok1", "tok2"], "label": "<label_2>"}
...
```
