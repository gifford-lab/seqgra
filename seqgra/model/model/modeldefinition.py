from __future__ import annotations

from typing import List, Dict, Optional

from seqgra.model.model import Architecture


class ModelDefinition:
    def __init__(self, model_id: str = "", name: str = "",
                 description: str = "",
                 task: str = "multi-class classification",
                 sequence_space: str = "DNA",
                 library: str = "PyTorch",
                 implementation: Optional[str] = None,
                 labels: Optional[List[str]] = None,
                 seed: int = 0,
                 architecture: Optional[Architecture] = None,
                 loss_hyperparameters: Optional[Dict[str, str]] = None,
                 optimizer_hyperparameters: Optional[Dict[str, str]] = None,
                 training_process_hyperparameters: Optional[Dict[str, str]] = None) -> None:
        self.model_id: str = model_id
        self.name: str = name
        self.description: str = description
        self.task: str = task
        self.sequence_space: str = sequence_space
        self.library: str = library
        self.implementation: Optional[str] = implementation
        self.labels: Optional[List[str]] = labels
        self.seed: int = seed
        self.architecture: Optional[Architecture] = architecture
        self.loss_hyperparameters: Optional[Dict[str,
                                                 str]] = loss_hyperparameters
        self.optimizer_hyperparameters: Optional[Dict[str,
                                                      str]] = optimizer_hyperparameters
        self.training_process_hyperparameters: Optional[Dict[str,
                                                             str]] = training_process_hyperparameters

    def __str__(self):
        str_rep: List[str] = ["seqgra model definition:\n",
                              "\tGeneral:\n",
                              "\t\tID: ", self.model_id, " [mid]\n",
                              "\t\tName: ", self.name, "\n",
                              "\t\tDescription:\n"]
        if self.description:
            str_rep += ["\t\t\t", self.description, "\n"]
        str_rep += ["\t\tTask: ", self.task, "\n",
                    "\t\tSequence space: ", self.sequence_space, "\n",
                    "\t\tLibrary: ", self.library, "\n",
                    "\t\tImplementation: ", self.implementation, "\n",
                    "\t\tLabels:\n"]
        if self.labels is not None and len(self.labels) > 0:
            str_rep += ["\t\t\t" + label + "\n" for label in self.labels]
        str_rep += ["\t\tSeed: ", str(self.seed), "\n"]
        str_rep += ["\t" + s + "\n"
                    for s in str(self.architecture).splitlines()]
        str_rep += ["\tLoss hyperparameters:\n", "\t\t",
                    str(self.loss_hyperparameters), "\n"]
        str_rep += ["\tOptimizer hyperparameters:\n", "\t\t",
                    str(self.optimizer_hyperparameters), "\n"]
        str_rep += ["\tTraining process hyperparameters:\n", "\t\t",
                    str(self.training_process_hyperparameters), "\n"]

        return "".join(str_rep)
