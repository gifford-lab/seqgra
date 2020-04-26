"""MIT - CSAIL - Gifford Lab - seqgra

PyTorch DataSet class

@author: Konstantin Krismer
"""
from typing import List, Optional
import warnings

import torch
import numpy as np
from sklearn.preprocessing import MultiLabelBinarizer

from seqgra.learner import DNAHelper
from seqgra.learner import ProteinHelper


class DNAMultiClassDataSet(torch.utils.data.Dataset):
    def __init__(self, x, y=None,
                 labels: Optional[List[str]] = None,
                 encode_data: bool = True,
                 add_empty_height_dim: bool = True):
        self.x = x
        self.y = y

        self.labels: Optional[List[str]] = labels

        if encode_data:
            DNAHelper.check_sequence(self.x)
            self.x = self.__encode_x(self.x)
            
            if add_empty_height_dim:
                # transpose for PyTorch from N x H x W x C to N x C x H x W
                self.x = np.expand_dims(self.x, axis=0)
                self.x = np.transpose(self.x, (1, 3, 0, 2))
            else:
                # transpose for PyTorch from N x W x C to N x C x W
                self.x = np.transpose(self.x, (0, 2, 1))
                
            if self.y is not None:
                self.y = self.__encode_y(self.y)

        self.x = np.array(self.x).astype(np.float32)

        if self.y is not None:
            if not isinstance(self.y, np.ndarray):
                self.y = np.array(self.y)

            if self.y.dtype == np.bool:
                self.y = np.argmax(self.y.astype(np.int64), axis=1)

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
                         for seq in x])

    def __encode_y(self, y: List[str]):
        if self.labels is None:
            raise Exception("labels not specified")
        labels = np.array(self.labels)
        return np.vstack([ex == labels for ex in y])


class DNAMultiLabelDataSet(torch.utils.data.Dataset):
    def __init__(self, x: List[str], y: Optional[List[str]] = None,
                 labels: Optional[List[str]] = None, 
                 encode_data: bool = True,
                 add_empty_height_dim: bool = True):
        self.x: List[str] = x
        self.y: Optional[List[str]] = y
        DNAHelper.check_sequence(self.x)

        self.labels: Optional[List[str]] = labels

        if encode_data:
            self.x = self.__encode_x(self.x)
            
            if add_empty_height_dim:
                # transpose for PyTorch from N x H x W x C to N x C x H x W
                self.x = np.expand_dims(self.x, axis=0)
                self.x = np.transpose(self.x, (1, 3, 0, 2))
            else:
                # transpose for PyTorch from N x W x C to N x C x W
                self.x = np.transpose(self.x, (0, 2, 1))
                
            if self.y is not None:
                self.y = self.__encode_y(self.y)

        self.x = np.array(self.x).astype(np.float32)

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
                         for seq in x])

    def __encode_y(self, y: List[str]):
        if self.labels is None:
            raise Exception("labels not specified")

        y = [ex.split("|") for ex in y]
        mlb = MultiLabelBinarizer(classes=self.labels)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            y = mlb.fit_transform(y).astype(bool)
        return y


class ProteinMultiClassDataSet(torch.utils.data.Dataset):
    def __init__(self, x, y=None,
                 labels: Optional[List[str]] = None, 
                 encode_data: bool = True,
                 add_empty_height_dim: bool = True):
        self.x = x
        self.y = y

        self.labels: Optional[List[str]] = labels

        if encode_data:
            ProteinHelper.check_sequence(self.x)
            self.x = self.__encode_x(self.x)
            
            if add_empty_height_dim:
                # transpose for PyTorch from N x H x W x C to N x C x H x W
                self.x = np.expand_dims(self.x, axis=0)
                self.x = np.transpose(self.x, (1, 3, 0, 2))
            else:
                # transpose for PyTorch from N x W x C to N x C x W
                self.x = np.transpose(self.x, (0, 2, 1))
                
            if self.y is not None:
                self.y = self.__encode_y(self.y)

        self.x = np.array(self.x).astype(np.float32)

        if self.y is not None:
            if not isinstance(self.y, np.ndarray):
                self.y = np.array(self.y)

            if self.y.dtype == np.bool:
                self.y = np.argmax(self.y.astype(np.int64), axis=1)

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
        return np.stack([ProteinHelper.convert_dense_to_one_hot_encoding(seq)
                         for seq in x])

    def __encode_y(self, y: List[str]):
        if self.labels is None:
            raise Exception("labels not specified")
        labels = np.array(self.labels)
        return np.vstack([ex == labels for ex in y])


class ProteinMultiLabelDataSet(torch.utils.data.Dataset):
    def __init__(self, x: List[str], y: Optional[List[str]] = None,
                 labels: Optional[List[str]] = None, 
                 encode_data: bool = True,
                 add_empty_height_dim: bool = True):
        self.x: List[str] = x
        self.y: Optional[List[str]] = y
        ProteinHelper.check_sequence(self.x)

        self.labels: Optional[List[str]] = labels

        if encode_data:
            self.x = self.__encode_x(self.x)

            if add_empty_height_dim:
                # transpose for PyTorch from N x H x W x C to N x C x H x W
                self.x = np.expand_dims(self.x, axis=0)
                self.x = np.transpose(self.x, (1, 3, 0, 2))
            else:
                # transpose for PyTorch from N x W x C to N x C x W
                self.x = np.transpose(self.x, (0, 2, 1))

            if self.y is not None:
                self.y = self.__encode_y(self.y)

        self.x = np.array(self.x).astype(np.float32)

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
        return np.stack([ProteinHelper.convert_dense_to_one_hot_encoding(seq)
                         for seq in x])

    def __encode_y(self, y: List[str]):
        if self.labels is None:
            raise Exception("labels not specified")

        y = [ex.split("|") for ex in y]
        mlb = MultiLabelBinarizer(classes=self.labels)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            y = mlb.fit_transform(y).astype(bool)
        return y
