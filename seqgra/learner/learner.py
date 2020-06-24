"""Contains abstract classes for all learners.

Classes:
    - :class:`Learner`: abstract base class for all learners
    - :class:`MultiClassClassificationLearner`: abstract class for multi-class classification learners
    - :class:`MultiLabelClassificationLearner`: abstract class for multi-label classification learners
    - :class:`MultipleRegressionLearner`: abstract class for multiple regression learners
    - :class:`MultivariateRegressionLearner`: abstract class for multivariate regression learners
"""
from abc import ABC, abstractmethod
import logging
import os
import re
from typing import Any, List, Optional, Set

import pandas as pd

from seqgra import AnnotationSet, ExampleSet, MiscHelper
import seqgra.constants as c
from seqgra.model import ModelDefinition


class Learner(ABC):
    """Abstract base class for all learners.

    Attributes:
        definition (ModelDefinition): contains model meta info,
            architecture and hyperparameters
        data_dir (str): directory with data files, e.g., `training.txt`
        output_dir (str): model output directory,
            `{OUTPUTDIR}/models/{GRAMMAR ID}/{MODEL ID}/`
        validate_data (bool): whether input data should be validated (e.g.,
            check if valid DNA or protein sequence)
        gpu_id (int): ID of GPU used by TensorFlow and PyTorch
        model: PyTorch or TensorFlow model
        optimizer: PyTorch or TensorFlow optimizer
        criterion: PyTorch or TensorFlow criterion (loss)
        metrics (List[str]): metrics that are collected, usually `loss` and
            `accuracy`

    Arguments:
        model_definition (ModelDefinition): contains model meta info,
            architecture and hyperparameters
        data_dir (str): directory with data files,
            `{OUTPUTDIR}/input/{GRAMMAR ID}`
        output_dir (str): model output directory without model folder,
            `{OUTPUTDIR}/models/{GRAMMAR ID}`
        validate_data (bool): whether input data should be validated (e.g.,
            check if valid DNA or protein sequence)
        gpu_id (int): ID of GPU used by TensorFlow and PyTorch

    See Also:
        - :class:`MultiClassClassificationLearner`: for classification models with mutually exclusive classes
        - :class:`MultiLabelClassificationLearner`: for classification models with non-mutually exclusive classes
        - :class:`MultipleRegressionLearner`: for regression models with multiple independent variables and one dependent variable
    """

    @abstractmethod
    def __init__(self, model_definition: ModelDefinition, data_dir: str,
                 output_dir: str, validate_data: bool = True,
                 gpu_id: int = 0) -> None:
        self.logger = logging.getLogger(__name__)
        self.definition: ModelDefinition = model_definition
        self.data_dir: str = MiscHelper.prepare_path(data_dir)
        self.output_dir: str = MiscHelper.prepare_path(output_dir + "/" +
                                                       self.definition.model_id,
                                                       allow_exists=True)
        self.validate_data: bool = validate_data
        self.gpu_id: int = gpu_id
        self.model = None
        self.optimizer = None
        self.criterion = None
        self.metrics = ["loss", "accuracy"]

    def train_model(self,
                    training_file: Optional[str] = None,
                    validation_file: Optional[str] = None,
                    x_train: Optional[List[str]] = None,
                    y_train: Optional[List[str]] = None,
                    x_val: Optional[List[str]] = None,
                    y_val: Optional[List[str]] = None) -> None:
        """Train model.

        Specify either `training_file` and `validation_file` or
        `x_train`, `y_train`, `x_val`, and `y_val`.

        Arguments:
            training_file (Optional[str]): TODO
            validation_file (Optional[str]): TODO
            x_train (Optional[List[str]]): TODO
            y_train (Optional[List[str]]): TODO
            x_val (Optional[List[str]]): TODO
            y_val (Optional[List[str]]): TODO

        Raises:
            Exception: output directory non-empty
            Exception: specify either training_file and validation_file
                or x_train, y_train, x_val, y_val
        """
        if len(os.listdir(self.output_dir)) > 0:
            raise Exception("output directory non-empty")

        self.set_seed()

        if training_file is not None:
            x_train, y_train = self.parse_examples_data(training_file)

        if validation_file is not None:
            x_val, y_val = self.parse_examples_data(validation_file)

        if x_train is None or y_train is None or \
           x_val is None or y_val is None:
            raise Exception("specify either training_file and validation_file"
                            " or x_train, y_train, x_val, y_val")
        else:
            self._train_model(x_train, y_train, x_val, y_val)

    @abstractmethod
    def parse_examples_data(self, file_name: str) -> ExampleSet:
        """Abstract method to parse examples data file.

        Checks validity of sequences with sequence data type specific
        implementations provided for DNA and amino acid sequences.

        Arguments:
            file_name (str): file name

        Returns:
            ExampleSet:
                x (List[str]): sequences
                y (List[str]): labels
        """

    def parse_annotations_data(self, file_name: str) -> AnnotationSet:
        """Method to parse annotations data file.

        Checks validity of annotations.

        Arguments:
            file_name (str): file name

        Returns:
            AnnotationSet:
                annotations (List[str]): annotations
                y (List[str]): labels
        """
        df = pd.read_csv(file_name, sep="\t", dtype={"annotation": "string",
                                                     "y": "string"})
        df = df.fillna("")
        annotations: List[str] = df["annotation"].tolist()
        y: List[str] = df["y"].tolist()

        if self.validate_data:
            self.check_annotations(annotations)
            self.check_labels(y)
        return AnnotationSet(annotations, y)

    @abstractmethod
    def get_label_set(self, y: List[str]) -> Set[str]:
        pass

    def check_labels(self, y: List[str], throw_exception: bool = True) -> bool:
        is_valid: bool = True
        if isinstance(self.definition.labels, list):
            model_labels: Set[str] = set(self.definition.labels)
        else:
            model_labels: Set[str] = {self.definition.labels}

        for label in self.get_label_set(y):
            if not label in model_labels:
                message: str = "examples with invalid label: " + \
                    label + " (valid labels are " + \
                    ", ".join(self.definition.labels) + ")"
                if throw_exception:
                    raise Exception(message)

                self.logger.warning(message)
                is_valid = False

        return is_valid

    def check_annotations(self, annotations: List[str]) -> bool:
        is_valid: bool = True
        for annotation in annotations:
            if not re.match("^[\_GC]*$", annotation):
                self.logger.warning("example with invalid annotation "
                                    "(only 'G' for grammar position, 'C' for "
                                    "confounding position, and '_' for "
                                    "background "
                                    "position allowed): %s", annotation)
                is_valid = False

        return is_valid

    def get_examples_file(self, set_name: str = "test") -> str:
        """Get path to examples file.

        E.g., `get_examples_file("training")` returns
        `{OUTPUTDIR}/input/{GRAMMAR ID}/training.txt`, if it exists.

        Arguments:
            set_name (str, optional): set name can be one of the following:
                `training`, `validation`, or `test`; defaults to `test`

        Returns:
            str: file path to examples file

        Raises:
            Exception: in case requested examples file does not exist
        """
        f: str = self.data_dir + "/" + set_name + ".txt"
        f = f.replace("\\", "/").replace("//", "/").strip()
        if os.path.isfile(f):
            return f
        else:
            raise Exception("examples file does not exist for set " + set_name)

    def get_annotations_file(self, set_name: str = "test") -> str:
        """Get path to annotations file.

        E.g., `get_annotations_file("training")` returns
        `{OUTPUTDIR}/input/{GRAMMAR ID}/training-annotation.txt`, if it exists.

        Arguments:
            set_name (str, optional): set name can be one of the following:
                `training`, `validation`, or `test`; defaults to `test`

        Returns:
            str: file path to annotations file

        Raises:
            Exception: in case requested annotations file does not exist
        """
        f: str = self.data_dir + "/" + set_name + "-annotation.txt"
        f = f.replace("\\", "/").replace("//", "/").strip()
        if os.path.isfile(f):
            return f
        else:
            raise Exception("annotations file does not exist for set " +
                            set_name)

    @abstractmethod
    def create_model(self) -> None:
        """Abstract method to create library-specific model.

        Machine learning library specific implementations are provided for
        TensorFlow and PyTorch.
        """

    @abstractmethod
    def save_model(self, file_name: Optional[str] = None):
        """TODO

        TODO

        Arguments:
            file_name (str, optional): file name in output dir;
                default is library-dependent
        """

    @abstractmethod
    def load_model(self, file_name: Optional[str] = None):
        """TODO

        TODO

        Arguments:
            file_name (str, optional): file name in output dir;
                default is library-dependent
        """

    @abstractmethod
    def print_model_summary(self) -> None:
        """TODO

        TODO
        """

    @abstractmethod
    def predict(self, x: Any, encode: bool = True):
        """TODO

        TODO

        Arguments:
            x (array): TODO
            encode (bool, optional): whether `x` should be encoded;
                defaults to `True`
        """

    @abstractmethod
    def encode_x(self, x):
        """TODO

        TODO

        Arguments:
            x (array): TODO
        """

    @abstractmethod
    def decode_x(self, x):
        """TODO

        TODO

        Arguments:
            x (array): TODO
        """

    @abstractmethod
    def encode_y(self, y):
        """TODO

        TODO

        Arguments:
            y (array): TODO
        """

    @abstractmethod
    def decode_y(self, y):
        """TODO

        TODO

        Arguments:
            y (array): TODO
        """

    @abstractmethod
    def get_num_params(self):
        """TODO

        TODO
        """

    @abstractmethod
    def set_seed(self) -> None:
        """TODO

        TODO
        """

    @abstractmethod
    def _train_model(self,
                     x_train: List[str], y_train: List[str],
                     x_val: List[str], y_val: List[str]) -> None:
        pass


class MultiClassClassificationLearner(Learner):
    """Abstract class for multi-class classification learners.

    Multi-class classification learners are learners for models with
    mututally exclusive class labels.

    Attributes:
        definition (ModelDefinition): contains model meta info,
            architecture and hyperparameters
        data_dir (str): directory with data files, e.g., `training.txt`
        output_dir (str): model output directory,
            `{OUTPUTDIR}/models/{GRAMMAR ID}/{MODEL ID}/`
        validate_data (bool): whether input data should be validated (e.g.,
            check if valid DNA or protein sequence)
        gpu_id (int): ID of GPU used by TensorFlow and PyTorch
        model: PyTorch or TensorFlow model
        optimizer: PyTorch or TensorFlow optimizer
        criterion: PyTorch or TensorFlow criterion (loss)
        metrics (List[str]): metrics that are collected, usually `loss` and
            `accuracy`

    Arguments:
        model_definition (ModelDefinition): contains model meta info,
            architecture and hyperparameters
        data_dir (str): directory with data files,
            `{OUTPUTDIR}/input/{GRAMMAR ID}`
        output_dir (str): model output directory without model folder,
            `{OUTPUTDIR}/models/{GRAMMAR ID}`
        validate_data (bool): whether input data should be validated (e.g.,
            check if valid DNA or protein sequence)
        gpu_id (int): ID of GPU used by TensorFlow and PyTorch
    """

    @abstractmethod
    def __init__(self, model_definition: ModelDefinition, data_dir: str,
                 output_dir: str, validate_data: bool = True,
                 gpu_id: int = 0) -> None:
        super().__init__(model_definition, data_dir, output_dir,
                         validate_data, gpu_id)

        if self.definition.task != c.TaskType.MULTI_CLASS_CLASSIFICATION:
            raise Exception("task of model definition must be multi-class "
                            "classification, but is '" +
                            self.definition.task + "' instead")

    def evaluate_model(self, file_name: Optional[str] = None,
                       x: Optional[List[str]] = None,
                       y: Optional[List[str]] = None):
        """TODO

        TODO

        Arguments:
            file_name (str): TODO
            x (Optional[List[str]]): TODO
            y (Optional[List[str]]): TODO

        Returns:
            array: TODO

        Raises:
            Exception: if neither `file_name` nor (`x` and `y`) are specified
        """
        if file_name is not None:
            x, y = self.parse_examples_data(file_name)

        if x is None or y is None:
            raise Exception(
                "specify either file_name or x and y")
        else:
            return self._evaluate_model(x, y)

    @abstractmethod
    def _evaluate_model(self, x: List[str], y: List[str]):
        pass

    def get_label_set(self, y: List[str]) -> Set[str]:
        if isinstance(y, list):
            return set(y)
        else:
            return {y}


class MultiLabelClassificationLearner(Learner):
    """Abstract class for multi-label classification learners.

    Multi-label classification learners are learners for models with class
    labels that are not mututally exclusive.

    Attributes:
        definition (ModelDefinition): contains model meta info,
            architecture and hyperparameters
        data_dir (str): directory with data files, e.g., `training.txt`
        output_dir (str): model output directory,
            `{OUTPUTDIR}/models/{GRAMMAR ID}/{MODEL ID}/`
        validate_data (bool): whether input data should be validated (e.g.,
            check if valid DNA or protein sequence)
        gpu_id (int): ID of GPU used by TensorFlow and PyTorch
        model: PyTorch or TensorFlow model
        optimizer: PyTorch or TensorFlow optimizer
        criterion: PyTorch or TensorFlow criterion (loss)
        metrics (List[str]): metrics that are collected, usually `loss` and
            `accuracy`

    Arguments:
        model_definition (ModelDefinition): contains model meta info,
            architecture and hyperparameters
        data_dir (str): directory with data files,
            `{OUTPUTDIR}/input/{GRAMMAR ID}`
        output_dir (str): model output directory without model folder,
            `{OUTPUTDIR}/models/{GRAMMAR ID}`
        validate_data (bool): whether input data should be validated (e.g.,
            check if valid DNA or protein sequence)
        gpu_id (int): ID of GPU used by TensorFlow and PyTorch
    """

    @abstractmethod
    def __init__(self, model_definition: ModelDefinition, data_dir: str,
                 output_dir: str, validate_data: bool = True,
                 gpu_id: int = 0) -> None:
        super().__init__(model_definition, data_dir, output_dir,
                         validate_data, gpu_id)

        if self.definition.task != c.TaskType.MULTI_LABEL_CLASSIFICATION:
            raise Exception("task of model definition must be multi-label "
                            "classification, but is '" +
                            self.definition.task, "' instead")

    def evaluate_model(self, file_name: Optional[str] = None,
                       x: Optional[List[str]] = None,
                       y: Optional[List[List[str]]] = None):
        """TODO

        TODO

        Arguments:
            file_name (Optional[str]): TODO
            x (Optional[List[str]]): TODO
            y (Optional[List[List[str]]]): TODO

        Returns:
            array: TODO

        Raises:
            Exception: if neither `file_name` nor (`x` and `y`) are specified
        """
        if file_name is not None:
            x, y = self.parse_examples_data(file_name)

        if x is None or y is None:
            raise Exception(
                "specify either file_name or x and y")
        else:
            return self._evaluate_model(x, y)

    @abstractmethod
    def _evaluate_model(self, x: List[str], y: List[List[str]]):
        pass

    def get_label_set(self, y: List[str]) -> Set[str]:
        if isinstance(y, list):
            multilabels = set(y)
        else:
            multilabels = {y}

        temp: List[str] = list()
        for multilabel in multilabels:
            if len(multilabel) > 0:
                temp += multilabel.split("|")
        return set(temp)


class MultipleRegressionLearner(Learner):
    """Abstract class for multiple regression learners.

    Multiple regression learners are learners for models with
    multiple independent real-valued variables (:math:`x \\in R^n`) and
    one dependent real-valued variable (:math:`x \\in R`).

    Attributes:
        definition (ModelDefinition): contains model meta info,
            architecture and hyperparameters
        data_dir (str): directory with data files, e.g., `training.txt`
        output_dir (str): model output directory,
            `{OUTPUTDIR}/models/{GRAMMAR ID}/{MODEL ID}/`
        validate_data (bool): whether input data should be validated (e.g.,
            check if valid DNA or protein sequence)
        gpu_id (int): ID of GPU used by TensorFlow and PyTorch
        model: PyTorch or TensorFlow model
        optimizer: PyTorch or TensorFlow optimizer
        criterion: PyTorch or TensorFlow criterion (loss)
        metrics (List[str]): metrics that are collected, usually `loss` and
            `accuracy`

    Arguments:
        model_definition (ModelDefinition): contains model meta info,
            architecture and hyperparameters
        data_dir (str): directory with data files,
            `{OUTPUTDIR}/input/{GRAMMAR ID}`
        output_dir (str): model output directory without model folder,
            `{OUTPUTDIR}/models/{GRAMMAR ID}`
        validate_data (bool): whether input data should be validated (e.g.,
            check if valid DNA or protein sequence)
        gpu_id (int): ID of GPU used by TensorFlow and PyTorch
    """

    @abstractmethod
    def __init__(self, model_definition: ModelDefinition, data_dir: str,
                 output_dir: str, validate_data: bool = True,
                 gpu_id: int = 0) -> None:
        super().__init__(model_definition, data_dir, output_dir,
                         validate_data, gpu_id)

        if self.definition.task != c.TaskType.MULTIPLE_REGRESSION:
            raise Exception("task of model definition must be multiple "
                            "regression, but is '" +
                            self.definition.task, "' instead")

    def evaluate_model(self, file_name: Optional[str] = None,
                       x: Optional[List[str]] = None,
                       y: Optional[List[float]] = None):
        """TODO

        TODO

        Arguments:
            file_name (Optional[str]): TODO
            x (Optional[List[str]]): TODO
            y (Optional[List[float]]): TODO

        Returns:
            array: TODO

        Raises:
            Exception: if neither `file_name` nor (`x` and `y`) are specified
        """
        if file_name is not None:
            x, y = self.parse_examples_data(file_name)

        if x is None or y is None:
            raise Exception("specify either file_name or x and y")
        else:
            return self._evaluate_model(x, y)

    @abstractmethod
    def _evaluate_model(self, x: List[str], y: List[float]):
        pass

    def get_label_set(self, y: List[str]) -> Set[str]:
        return set()

    def check_labels(self, y: List[str], throw_exception: bool = True) -> bool:
        try:
            for value in y:
                float(value)
            return True
        except ValueError:
            message: str = "all labels must be numeric in regression"
            if throw_exception:
                raise Exception(message)

            self.logger.warning(message)
            return False


class MultivariateRegressionLearner(Learner):
    """Abstract class for multivariate regression learners.

    Multivariate regression learners are used for models with
    multiple independent real-valued variables (:math:`x \\in R^n`) and
    multiple dependent real-valued variables (:math:`y \\in R^n`).

    Attributes:
        definition (ModelDefinition): contains model meta info,
            architecture and hyperparameters
        data_dir (str): directory with data files, e.g., `training.txt`
        output_dir (str): model output directory,
            `{OUTPUTDIR}/models/{GRAMMAR ID}/{MODEL ID}/`
        validate_data (bool): whether input data should be validated (e.g.,
            check if valid DNA or protein sequence)
        gpu_id (int): ID of GPU used by TensorFlow and PyTorch
        model: PyTorch or TensorFlow model
        optimizer: PyTorch or TensorFlow optimizer
        criterion: PyTorch or TensorFlow criterion (loss)
        metrics (List[str]): metrics that are collected, usually `loss` and
            `accuracy`

    Arguments:
        model_definition (ModelDefinition): contains model meta info,
            architecture and hyperparameters
        data_dir (str): directory with data files,
            `{OUTPUTDIR}/input/{GRAMMAR ID}`
        output_dir (str): model output directory without model folder,
            `{OUTPUTDIR}/models/{GRAMMAR ID}`
        validate_data (bool): whether input data should be validated (e.g.,
            check if valid DNA or protein sequence)
        gpu_id (int): ID of GPU used by TensorFlow and PyTorch
    """

    @abstractmethod
    def __init__(self, model_definition: ModelDefinition, data_dir: str,
                 output_dir: str, validate_data: bool = True,
                 gpu_id: int = 0) -> None:
        super().__init__(model_definition, data_dir, output_dir,
                         validate_data, gpu_id)

        if self.definition.task != c.TaskType.MULTIVARIATE_REGRESSION:
            raise Exception("task of model definition must be multivariate "
                            "regression, but is '" +
                            self.definition.task, "' instead")

    def evaluate_model(self, file_name: Optional[str] = None,
                       x: Optional[List[str]] = None,
                       y: Optional[List[List[float]]] = None):
        """TODO

        TODO

        Arguments:
            file_name (Optional[str]): TODO
            x (Optional[List[str]]): TODO
            y (Optional[List[List[float]]]): TODO

        Returns:
            array: TODO

        Raises:
            Exception: if neither `file_name` nor (`x` and `y`) are specified
        """
        if file_name is not None:
            x, y = self.parse_examples_data(file_name)

        if x is None or y is None:
            raise Exception(
                "specify either file_name or x and y")
        else:
            return self._evaluate_model(x, y)

    @abstractmethod
    def _evaluate_model(self, x: List[str], y: List[float]):
        pass

    def get_label_set(self, y: List[str]) -> Set[str]:
        return set()

    def check_labels(self, y: List[str], throw_exception: bool = True) -> bool:
        raise NotImplementedError()
