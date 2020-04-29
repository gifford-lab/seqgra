"""
MIT - CSAIL - Gifford Lab - seqgra

- class for all saliency evaluators
- models must be in pytorch

@author: Jennifer Hammelman
"""
from typing import Any, List

import numpy as np
import pandas as pd
import torch

import seqgra.constants as c
from seqgra.learner import Learner
from seqgra.evaluator import FeatureImportanceEvaluator
from seqgra.evaluator.explainer.backprop import VanillaGradExplainer
from seqgra.evaluator.explainer.backprop import GradxInputExplainer
from seqgra.evaluator.explainer.backprop import SaliencyExplainer
from seqgra.evaluator.explainer.backprop import IntegrateGradExplainer
from seqgra.evaluator.explainer.backprop import NonlinearIntegrateGradExplainer
from seqgra.evaluator.explainer.deeplift import DeepLIFTRescaleExplainer
from seqgra.evaluator.explainer.gradcam import GradCAMExplainer
from seqgra.evaluator.explainer.ebp import ExcitationBackpropExplainer
from seqgra.evaluator.explainer.ebp import ContrastiveExcitationBackpropExplainer


class GradientBasedEvaluator(FeatureImportanceEvaluator):
    def __init__(self, evaluator_id: str, evaluator_name: str,
                 learner: Learner, output_dir: str) -> None:
        super().__init__(evaluator_id, evaluator_name, learner, output_dir,
                         supported_libraries=[c.LibraryType.TORCH])
        self.explainer = None
        self.relevance_threshold = 0.1

    def _evaluate_model(self, x: List[str], y: List[str],
                        annotations: List[str]) -> Any:
        use_cuda = torch.cuda.is_available()

        # encode
        encoded_x = self.learner.encode_x(x)
        encoded_y = self.learner.encode_y(y)

        # convert bool to float32 and long, as expected by explainers
        encoded_x = encoded_x.astype(np.float32)
        encoded_y = encoded_y.astype(np.int64)

        # add H dimension?
        # e.g., for 100 nt window, 1 example, TensorFlow format (N, H, W, C):
        # (1, 100, 4) -> (1, 1, 100, 4)
        encoded_x = np.expand_dims(encoded_x, axis=0)

        # TensorFlow format to Torch format (N, C, H, W):
        # e.g., for 100 nt window, 1 example, added height dimension:
        # (1, 1, 100, 4) -> (1, 4, 1, 100)
        encoded_x = np.transpose(encoded_x, (1, 3, 0, 2))

        self._check_tensor_dimensions(encoded_x)
        # convert np array to torch tensor
        encoded_x = torch.from_numpy(encoded_x)
        encoded_y = torch.from_numpy(encoded_y)

        if use_cuda:
            # store input tensor, label tensor and model on GPU
            encoded_x = encoded_x.cuda()
            encoded_y = encoded_y.cuda()
            self.explainer.model.cuda()

        encoded_x = torch.autograd.Variable(encoded_x, requires_grad=True)

        # enable inference mode
        self.explainer.model.eval()

        result = self.calculate_saliency(encoded_x, encoded_y)

        self._check_tensor_dimensions(result)
        return (result, y, annotations)

    def _save_results(self, results, set_name: str = "test") -> None:
        np.save(self.output_dir + set_name + ".npy", results[0])

    def calculate_saliency(self, data, label):
        result = self.explainer.explain(data, label)
        return self._explainer_transform(data, result)

    def _explainer_transform(self, data, result):
        return result.cpu().numpy()

    def __get_agreement_group(self, annotation_position: str,
                              importance_vector) -> str:
        if annotation_position == c.PositionType.GRAMMAR:
            if np.max(importance_vector) < self.relevance_threshold:
                return "FN"
            else:
                return "TP"
        else:
            if np.max(importance_vector) < self.relevance_threshold:
                return "TN"
            else:
                return "FP"

    def _check_tensor_dimensions(self, tensor) -> None:
        if self.learner.definition.library == c.LibraryType.TENSORFLOW:
            expected_shape: str = "(N, W, C) or (N, 1, W, C)"
            channel_dim: int = 2
            channel_dim_with_height: int = 3
            height_dim: int = 1
        elif self.learner.definition.library == c.LibraryType.TORCH:
            expected_shape: str = "(N, C, W) or (N, C, 1, W)"
            channel_dim: int = 1
            channel_dim_with_height: int = 1
            height_dim: int = 2

        if len(tensor.shape) == 3:
            if self.learner.definition.sequence_space == c.SequenceSpaceType.DNA:
                if tensor.shape[channel_dim] != 4:
                    raise Exception("tensor shape invalid for DNA "
                                    "sequence space: expected 4 channels, got " +
                                    str(tensor.shape[channel_dim]))
            elif self.learner.definition.sequence_space == c.SequenceSpaceType.PROTEIN:
                if tensor.shape[channel_dim] != 20:
                    raise Exception("tensor shape invalid for protein "
                                    "sequence space: expected 20 "
                                    "channels, got " +
                                    str(tensor.shape[channel_dim]))
        elif len(tensor.shape) == 4:
            if self.learner.definition.sequence_space == c.SequenceSpaceType.DNA:
                if tensor.shape[channel_dim_with_height] != 4:
                    raise Exception("tensor shape invalid for DNA "
                                    "sequence space: expected 4 channels, got " +
                                    str(tensor.shape[channel_dim_with_height]))
            elif self.learner.definition.sequence_space == c.SequenceSpaceType.PROTEIN:
                if tensor.shape[channel_dim_with_height] != 20:
                    raise Exception("tensor shape invalid for protein "
                                    "sequence space: expected 20 "
                                    "channels, got " +
                                    str(tensor.shape[channel_dim_with_height]))
            if tensor.shape[height_dim] != 1:
                raise Exception("tensor shape invalid: expected "
                                "height dimension size of none or 1, got " +
                                str(tensor.shape[height_dim]))
        else:
            raise Exception("tensor shape invalid: expected " +
                            expected_shape + ", got " +
                            str(tensor.shape))

    def _convert_to_data_frame(self, results) -> pd.DataFrame:
        """Takes gradient-based evaluator-specific results and turns them into
        a pandas data frame.

        The data frame has the following columns:
            - example_column (int): example index
            - position (int): position within example (one-based)
            - group (str): group label, one of the following:
                - "TP": grammar position, important for model prediction
                - "FN": grammar position, not important for model prediction,
                - "FP": background position, important for model prediction,
                - "TN": background position, not important for model prediction
            - label (str): label of example, e.g., "cell type 1"
        """
        importance_matrix = results[0]
        y: List[str] = results[1]
        annotations: List[str] = results[2]

        # remove empty height dimension
        if len(importance_matrix.shape) == 4:
            if self.learner.definition.library == c.LibraryType.TENSORFLOW:
                height_dim: int = 1
            elif self.learner.definition.library == c.LibraryType.TORCH:
                height_dim: int = 2
            importance_matrix = np.squeeze(importance_matrix, axis=height_dim)

        example_column: List[int] = list()
        position_column: List[int] = list()
        group_column: List[str] = list()
        label_column: List[str] = list()

        for example_id, annotation in enumerate(annotations):
            example_column += [example_id] * len(annotation)
            position_column += list(range(1, len(annotation) + 1))
            group_column += [self.__get_agreement_group(
                char, importance_matrix[example_id, :, i])
                for i, char in enumerate(annotation)]
            label_column += [y[example_id]] * len(annotation)

        df = pd.DataFrame({"example": example_column,
                           "position": position_column,
                           "group": group_column,
                           "label": label_column})

        return df


class GradientEvaluator(GradientBasedEvaluator):
    def __init__(self, learner: Learner, output_dir: str) -> None:
        super().__init__(c.EvaluatorID.GRADIENT, "Vanilla gradient saliency",
                         learner, output_dir)
        self.explainer = VanillaGradExplainer(learner.model)


class GradientxInputEvaluator(GradientBasedEvaluator):
    def __init__(self, learner: Learner, output_dir: str) -> None:
        super().__init__(c.EvaluatorID.GRADIENT_X_INPUT, "Gradient x input",
                         learner, output_dir)
        self.explainer = GradxInputExplainer(learner.model)


class SaliencyEvaluator(GradientBasedEvaluator):
    def __init__(self, learner: Learner, output_dir: str) -> None:
        super().__init__(c.EvaluatorID.SALIENCY, "Saliency", learner,
                         output_dir)
        self.explainer = SaliencyExplainer(learner.model)


class IntegratedGradientEvaluator(GradientBasedEvaluator):
    def __init__(self, learner: Learner, output_dir: str) -> None:
        super().__init__(c.EvaluatorID.INTEGRATED_GRADIENTS,
                         "Integrated Gradients", learner, output_dir)
        self.explainer = IntegrateGradExplainer(learner.model)


class NonlinearIntegratedGradientEvaluator(GradientBasedEvaluator):
    def __init__(self, learner: Learner, output_dir: str) -> None:
        # TODO NonlinearIntegratedGradExplainer
        # requires other data and how to handle reference (default is None)
        super().__init__(c.EvaluatorID.NONLINEAR_INTEGRATED_GRADIENTS,
                         "Nonlinear Integrated Gradients", learner,
                         output_dir)
        # self.explainer = NonlinearIntegrateGradExplainer(learner.model)


class GradCamGradientEvaluator(GradientBasedEvaluator):
    def __init__(self, learner: Learner, output_dir: str) -> None:
        super().__init__(c.EvaluatorID.GRAD_CAM, "Grad-CAM", learner,
                         output_dir)
        self.explainer = GradCAMExplainer(learner.model)

    def _explainer_transform(self, data, result):
        return torch.nn.functional.interpolate(result.view(1, 1, -1),
                                               size=data.shape[2],
                                               mode="linear").cpu().numpy()


class DeepLiftEvaluator(GradientBasedEvaluator):
    # TODO where to set reference?
    def __init__(self, learner: Learner, output_dir: str) -> None:
        super().__init__(c.EvaluatorID.DEEP_LIFT, "DeepLIFT", learner,
                         output_dir)
        self.explainer = DeepLIFTRescaleExplainer(learner.model, "shuffled")


class ExcitationBackpropEvaluator(GradientBasedEvaluator):
    def __init__(self, learner: Learner, output_dir: str) -> None:
        super().__init__(c.EvaluatorID.EXCITATION_BACKPROP,
                         "Excitation Backprop", learner, output_dir)
        self.explainer = ExcitationBackpropExplainer(learner.model)


class ContrastiveExcitationBackpropEvaluator(GradientBasedEvaluator):
    def __init__(self, learner: Learner, output_dir: str) -> None:
        super().__init__(c.EvaluatorID.CONTRASTIVE_EXCITATION_BACKPROP,
                         "Contrastive Excitation Backprop", learner,
                         output_dir)
        self.explainer = ContrastiveExcitationBackpropExplainer(
            learner.model)
