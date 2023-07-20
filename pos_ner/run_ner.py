# coding=utf-8
# Copyright 2018 The Google AI Language Team Authors and The HuggingFace Inc. team.
# Copyright (c) 2018, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
""" Fine-tuning the library models for named entity recognition on CoNLL-2003 (Bert or Roberta). """


import logging
import os
import sys
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import numpy as np
from seqeval.metrics import f1_score, precision_score, recall_score
from torch import nn

from transformers import (
    AutoConfig,
    AutoModelForTokenClassification,
    AutoTokenizer,
    EvalPrediction,
    HfArgumentParser,
    TrainingArguments,
    set_seed,
)
from utils_ner import NerDataset, Split, get_labels
from trainer import Trainer
from tokenizer import normalize_string, tokenize as splitter


logger = logging.getLogger(__name__)

# Config
SEED = 1
BATCH_SIZE = 32
NUM_EPOCHS = 30
SAVE_STEPS = 750
MAX_SEQ_LENGTH = 128
BERT_MODEL = "indolem/indobert-base-uncased"


@dataclass
class ModelArguments:
    """
    Arguments pertaining to which model/config/tokenizer we are going to fine-tune from.
    """

    model_name_or_path: str = field(
        default=BERT_MODEL,
    )
    config_name: Optional[str] = field(
        default=None, metadata={"help": "Pretrained config name or path if not the same as model_name"}
    )
    tokenizer_name: Optional[str] = field(
        default=None, metadata={"help": "Pretrained tokenizer name or path if not the same as model_name"}
    )
    use_fast: bool = field(default=False, metadata={"help": "Set this flag to use fast tokenization."})
    # If you want to tweak more attributes on your tokenizer, you should do it in a distinct script,
    # or just modify its tokenizer_config.json.
    cache_dir: Optional[str] = field(
        default=None, metadata={"help": "Where do you want to store the pretrained models downloaded from s3"}
    )


@dataclass
class DataTrainingArguments:
    """
    Arguments pertaining to what data we are going to input our model for training and eval.
    """

    data_dir: str = field(
        default=None,
    )
    labels: Optional[str] = field(
        default=None,
    )
    max_seq_length: int = field(
        default=MAX_SEQ_LENGTH,
    )
    overwrite_cache: bool = field(
        default=False, metadata={"help": "Overwrite the cached training and evaluation sets"}
    )

sys.argv.append('--output_dir')
sys.argv.append('.')
# See all possible arguments in src/transformers/training_args.py
# or by passing the --help flag to this script.
# We now keep distinct sets of args, for a cleaner separation of concerns.

parser = HfArgumentParser((ModelArguments, DataTrainingArguments, TrainingArguments))
if len(sys.argv) == 2 and sys.argv[1].endswith(".json"):
    # If we pass only one argument to the script and it's the path to a json file,
    # let's parse it to get our arguments.
    model_args, data_args, training_args = parser.parse_json_file(json_file=os.path.abspath(sys.argv[1]))
else:
    model_args, data_args, training_args = parser.parse_args_into_dataclasses()

if (
    os.path.exists(training_args.output_dir)
    and os.listdir(training_args.output_dir)
    and training_args.do_train
    and not training_args.overwrite_output_dir
):
    raise ValueError(
        f"Output directory ({training_args.output_dir}) already exists and is not empty. Use --overwrite_output_dir to overcome."
    )

data_args.data_dir = './data_ner'

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s -   %(message)s",
    datefmt="%m/%d/%Y %H:%M:%S",
    level=logging.INFO if training_args.local_rank in [-1, 0] else logging.WARN,
)
logger.warning(
    "Process rank: %s, device: %s, n_gpu: %s, distributed training: %s, 16-bits training: %s",
    training_args.local_rank,
    training_args.device,
    training_args.n_gpu,
    bool(training_args.local_rank != -1),
    training_args.fp16,
)
logger.info("Training/evaluation parameters %s", training_args)

# Set seed
set_seed(SEED)

# Prepare CONLL-2003 task
labels = get_labels('labels_ner.txt')
label_map: Dict[int, str] = {i: label for i, label in enumerate(labels)}
num_labels = len(labels)

# Load pretrained model and tokenizer
#
# Distributed training:
# The .from_pretrained methods guarantee that only one local process can concurrently
# download model & vocab.

config = AutoConfig.from_pretrained(
    model_args.config_name if model_args.config_name else model_args.model_name_or_path,
    num_labels=num_labels,
    id2label=label_map,
    label2id={label: i for i, label in enumerate(labels)},
    cache_dir=model_args.cache_dir,
)
if 'malay' not in model_args.model_name_or_path:
    tokenizer = AutoTokenizer.from_pretrained(
        model_args.tokenizer_name if model_args.tokenizer_name else model_args.model_name_or_path,
        cache_dir=model_args.cache_dir,
        use_fast=model_args.use_fast,
    )
else:
    from transformers import AlbertTokenizer
    tokenizer = AlbertTokenizer.from_pretrained(model_args.model_name_or_path, 
                unk_token = '[UNK]', pad_token='[PAD]', do_lower_case=False)
model = AutoModelForTokenClassification.from_pretrained(
    model_args.model_name_or_path,
    from_tf=bool(".ckpt" in model_args.model_name_or_path),
    config=config,
    cache_dir=model_args.cache_dir,
)

def align_predictions(predictions: np.ndarray, label_ids: np.ndarray) -> Tuple[List[int], List[int]]:
    preds = np.argmax(predictions, axis=2)

    batch_size, seq_len = preds.shape

    out_label_list = [[] for _ in range(batch_size)]
    preds_list = [[] for _ in range(batch_size)]

    for i in range(batch_size):
        for j in range(seq_len):
            if label_ids[i, j] != nn.CrossEntropyLoss().ignore_index:
                out_label_list[i].append(label_map[label_ids[i][j]])
                preds_list[i].append(label_map[preds[i][j]])

    return preds_list, out_label_list

def compute_metrics(p: EvalPrediction) -> Dict:
    preds_list, out_label_list = align_predictions(p.predictions, p.label_ids)
    return {
        "precision": precision_score(out_label_list, preds_list),
        "recall": recall_score(out_label_list, preds_list),
        "f1": f1_score(out_label_list, preds_list),
    }

# Initialize our Trainer
trainer = Trainer(
    model=model,
    args=training_args,
    compute_metrics=compute_metrics,
)

# Training
if training_args.do_train:
    trainer.train(
        model_path=model_args.model_name_or_path if os.path.isdir(model_args.model_name_or_path) else None
    )
    trainer.save_model()
    # For convenience, we also re-save the tokenizer to the same directory,
    # so that you can share your model easily on huggingface.co/models =)
    if trainer.is_world_master():
        tokenizer.save_pretrained(training_args.output_dir)

# Evaluation
results = {}
if training_args.do_eval and training_args.local_rank in [-1, 0]:
    logger.info("*** Evaluate ***")

    result = trainer.evaluate()

    output_eval_file = os.path.join(training_args.output_dir, "eval_results.txt")
    with open(output_eval_file, "w") as writer:
        logger.info("***** Eval results *****")
        for key, value in result.items():
            logger.info("  %s = %s", key, value)
            writer.write("%s = %s\n" % (key, value))

        results.update(result)

# Predict
# text = "Kepala Dinas Pariwisata dan Ekonomi Kreatif Andhika Permata menyinggung soal pertemuan aktivis lesbian, gay, biseksual, dan transgender (LGBT) yang semula direncanakan akan digelar di Jakarta. Dia menegaskan Disparekraf DKI menolak keberadaan mereka sebab tidak sesuai dengan budaya Indonesia. \nHal itu disampaikan Andhika saat rapat bersama Komisi B DPRD DKI Jakarta soal perkembangan ekonomi Jakarta, Rabu (12/7/2023). Andhika mengungkapkan Disparekraf DKI senang jika ada wisatawan asing ke Jakarta tapi tidak dengan komunitas LGBT."
# words = text.split()

# dataset = []

# for word in words:
#     if bool(re.search(r'\W+', word)):
#         dataset.append(word[0:-1])
#         dataset.append(word[-1])
#     else:
#         dataset.append(word)
    
def get_ner(text):
    dataset, offsets = splitter(normalize_string(text))
    filename = datetime.now().strftime("%Y%m%d%H%M%S%f")

    saved_splitted_text = os.path.join(data_args.data_dir, filename + ".txt")
    with open(saved_splitted_text, "w") as writer:
        for value in dataset:
            writer.write("%s\n" % (value))

    test_dataset = NerDataset(
        data_dir=data_args.data_dir,
        tokenizer=tokenizer,
        labels=labels,
        model_type=config.model_type,
        mode=filename,
        max_seq_length=MAX_SEQ_LENGTH,
        local_rank=training_args.local_rank,
    )

    predictions, label_ids, metrics = trainer.predict(test_dataset)
    preds_list, _ = align_predictions(predictions, label_ids)
    print(preds_list)

    result_text = ""
    entities = []

    # Save predictions
    with open(os.path.join(data_args.data_dir, filename + ".txt"), "r") as f:
        example_id = 0
        index = 0
        for line in f:
            if line.startswith("-DOCSTART-") or line == "" or line == "\n":
                result_text = result_text + line
                if not preds_list[example_id]:
                    example_id += 1
                    index += 1
            elif preds_list[example_id]:
                word = line.split()[0]
                type = preds_list[example_id].pop(0)
                output_line = word + " " + type + "\n"
                entities.append({
                    'name': word,
                    'type': type,
                    'begin_offset': offsets[index][1]
                })
                result_text = result_text + output_line
                index += 1
            else:
                logger.warning("Maximum sequence length exceeded: No prediction for '%s'.", line.split()[0])

    print(result_text)

    os.remove(os.path.join(data_args.data_dir, filename + ".txt"))
    return entities