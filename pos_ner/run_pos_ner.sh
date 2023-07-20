#!/bin/bash

#conda create --name indolem
#conda activate indolem
#conda install -c pytorch pytorch
# pip install seqeval
# pip install transformers==2.9.0


# pos
for f in 1 2 3 4 5
do

export FOLD=0$f
export OUTPUT_DIR=indopos$FOLD
export BATCH_SIZE=32
export NUM_EPOCHS=30
export SAVE_STEPS=750
export SEED=1
export DATA_DIR_POS=./data_pos


cat $DATA_DIR_POS/train.$FOLD.tsv | tr '\t' ' '  | tr '  ' ' ' > train.txt
cat $DATA_DIR_POS/dev.$FOLD.tsv  | tr '\t' ' '  | tr '  ' ' ' > dev.txt
cat $DATA_DIR_POS/test.$FOLD.tsv  | tr '\t' ' '  | tr '  ' ' ' > test.txt
cat train.txt dev.txt test.txt | cut -d " " -f 2 | grep -v "^$"| sort | uniq > labels_pos.txt

done

# ner
for f in 1 2 3 4 5
do

export FOLD=0$f
export OUTPUT_DIR=indoner$FOLD
export BATCH_SIZE=32
export NUM_EPOCHS=30
export SAVE_STEPS=750
export SEED=1
export DATA_DIR_NER=./data_ner/nerui


cat $DATA_DIR_NER/train.$FOLD.tsv | tr '\t' ' '  | tr '  ' ' ' > train.txt
cat $DATA_DIR_NER/dev.$FOLD.tsv  | tr '\t' ' '  | tr '  ' ' ' > dev.txt
cat $DATA_DIR_NER/test.$FOLD.tsv  | tr '\t' ' '  | tr '  ' ' ' > test.txt
cat train.txt dev.txt test.txt | cut -d " " -f 2 | grep -v "^$"| sort | uniq > labels_ner.txt

done

CUDA_VISIBLE_DEVICES=0 flask --app app.py run