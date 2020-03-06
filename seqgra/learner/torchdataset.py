"""MIT - CSAIL - Gifford Lab - seqgra

PyTorch DataSet class

@author: Konstantin Krismer
"""
import logging
import re
from typing import List
import warnings

import torch
import pandas as pd
import numpy as np
from sklearn.preprocessing import MultiLabelBinarizer

from seqgra.dna.dnahelper import DNAHelper


class DNAMultiClassDataSet(torch.utils.data.Dataset):
    def __init__(self, x: List[str], y: List[str] = None,
                 labels: List[str] = None, encode_data: bool = True):
        
        self.x: List[str] = x
        self.y: List[str] = y
        DNAHelper.check_sequence(self.x)

        self.labels = labels

        if encode_data:
            self.x = self.__encode_x(self.x)
            if self.y is not None:
                self.y = self.__encode_y(self.y)

    def __len__(self):
        return len(self.x)

    def __getitem__(self, idx):
        if torch.is_tensor(idx):
            idx = idx.tolist()

        if self.y is None:
            return self.x[idx]
        else:
            return self.x[idx], self.y[idx]

    def __encode_x(self, x: List[str]):
        return np.stack([DNAHelper.convert_dense_to_one_hot_encoding(seq)
                         for seq in x]).astype(np.float32)
        
    def __encode_y(self, y: List[str]):
        if self.labels is None:
            raise Exception("labels not specified")
        labels = np.array(self.labels)
        y = np.vstack([ex == labels for ex in y]).astype(np.int64)
        return np.argmax(y, axis=1)


class DNAMultiLabelDataSet(torch.utils.data.Dataset):
    def __init__(self, x: List[str], y: List[str] = None,
                 labels: List[str] = None, encode_data: bool = True):
        
        self.x: List[str] = x
        self.y: List[str] = y
        DNAHelper.check_sequence(self.x)

        self.labels = labels

        if encode_data:
            self.x = self.__encode_x(self.x)
            if self.y is not None:
                self.y = self.__encode_y(self.y)

    def __len__(self):
        return len(self.x)

    def __getitem__(self, idx):
        if torch.is_tensor(idx):
            idx = idx.tolist()

        if self.y is None:
            return self.x[idx]
        else:
            return self.x[idx], self.y[idx]

    def __encode_x(self, x: List[str]):
        return np.stack([DNAHelper.convert_dense_to_one_hot_encoding(seq) 
                         for seq in x]).astype(np.float32)
        
    def __encode_y(self, y: List[str]):
        if self.labels is None:
            raise Exception("labels not specified")

        y = [ex.split("|") for ex in y]
        mlb = MultiLabelBinarizer(classes = self.labels)
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            y = mlb.fit_transform(y).astype(bool)
        return y
