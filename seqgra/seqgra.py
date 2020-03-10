#!/usr/bin/env python

'''
MIT - CSAIL - Gifford Lab - seqgra

seqgra complete pipeline:
1. generate data based on data definition (once), see run_simulator.py
2. train model on data (once), see run_learner.py
3. evaluate model performance with SIS, see run_sis.py

@author: Konstantin Krismer
'''

import sys
import os
import argparse
import logging
from typing import Dict, List

import numpy as np
import pandas as pd

from seqgra.parser.dataparser import DataParser
from seqgra.parser.xmldataparser import XMLDataParser
from seqgra.parser.modelparser import ModelParser
from seqgra.parser.xmlmodelparser import XMLModelParser
from seqgra.simulator.simulator import Simulator
from seqgra.learner.learner import Learner
from seqgra.learner.keraslearner import KerasMultiClassClassificationLearner
from seqgra.learner.keraslearner import KerasMultiLabelClassificationLearner
from seqgra.learner.torchlearner import TorchMultiClassClassificationLearner
from seqgra.evaluator.evaluator import Evaluator
from seqgra.evaluator.sisevaluator import SISEvaluator


def parse_config_file(file_name: str) -> str:
    with open(file_name.strip()) as f:
        config: str = f.read()
    return config


def get_learner(model_parser: ModelParser, data_parser_type: str, 
                output_dir: str) -> Learner:
    if data_parser_type is not None and \
       model_parser.get_learner_type() != data_parser_type:
        raise Exception("learner and data type incompatible (" + 
                        "learner type: " + model_parser.get_learner_type() + 
                        ", data type: " + data_parser_type + ")")

    if model_parser.get_learner_implementation() == "KerasMultiClassClassificationLearner":
        return KerasMultiClassClassificationLearner(model_parser, output_dir)
    elif model_parser.get_learner_implementation() == "KerasMultiLabelClassificationLearner":
        return KerasMultiLabelClassificationLearner(model_parser, output_dir)
    elif model_parser.get_learner_implementation() == "TorchMultiClassClassificationLearner":
        return TorchMultiClassClassificationLearner(model_parser, output_dir)
    else:
        raise Exception("invalid learner ID")


def get_evaluator(evaluator_id: str, learner: Learner,
                  data_dir: str, output_dir: str) -> Evaluator:
    evaluator_id = evaluator_id.lower().strip()
    if evaluator_id == "sis":
        return SISEvaluator(learner, data_dir, output_dir)
    else:
        raise Exception("invalid evaluator ID")


def format_output_dir(output_dir: str) -> str:
    output_dir = output_dir.strip().replace("\\", "/")
    if not output_dir.endswith("/"):
        output_dir += "/"
    return output_dir


def get_valid_file(data_file: str) -> str:
    data_file = data_file.replace("\\", "/").replace("//", "/").strip()
    if os.path.isfile(data_file):
        return data_file
    else:
        raise Exception("file does not exist: " + data_file)


def save_metrics(training_set_metrics,
                 validation_set_metrics,
                 test_set_metrics,
                 names,
                 file_name):
    df = pd.DataFrame([["training", training_set_metrics["loss"],
                        training_set_metrics["accuracy"]],
                       ["validation", validation_set_metrics["loss"],
                        validation_set_metrics["accuracy"]],
                       ["test", test_set_metrics["loss"], 
                        test_set_metrics["accuracy"]]],
                      columns=["set", "loss", "accuracy"])
    df.to_csv(file_name, sep="\t", index=False)


def run_seqgra(data_config_file: str,
         data_folder: str,
         model_config_file: str,
         evaluator_id: str,
         output_dir: str) -> None:
    output_dir = format_output_dir(output_dir.strip())

    if data_config_file is None:
        data_parser_type = None
        simulator_id = data_folder.strip()
        logging.info("loading experimental data")
    else:
        # generate synthetic data
        data_config_file = data_config_file.strip()
        data_config = parse_config_file(data_config_file)
        data_parser: DataParser = XMLDataParser(data_config)
        data_parser_type = data_parser.get_type()
        simulator = Simulator(data_parser, output_dir + "input")
        simulator_id = simulator.id
        synthetic_data_available: bool = \
            len(os.listdir(simulator.output_dir)) > 0
        if synthetic_data_available:
            logging.info("loading previously generated synthetic data")
        else:
            logging.info("generating synthetic data")
            simulator.simulate_data()

    # get learner
    model_config = parse_config_file(model_config_file.strip())
    model_parser: ModelParser = XMLModelParser(model_config)
    learner: Learner = get_learner(model_parser, data_parser_type, 
                                   output_dir + "models/" + simulator_id)

    # load data
    training_set_file: str = get_valid_file(
        output_dir + "input/" + simulator_id + "/training.txt")
    validation_set_file: str = get_valid_file(
        output_dir + "input/" + simulator_id + "/validation.txt")
    test_set_file: str = get_valid_file(
        output_dir + "input/" + simulator_id + "/test.txt")

    x_train, y_train = learner.parse_data(training_set_file)
    x_val, y_val = learner.parse_data(validation_set_file)
    x_test, y_test = learner.parse_data(test_set_file)

    # train model on data
    trained_model_available: bool = len(os.listdir(learner.output_dir)) > 0
    if trained_model_available:
        logging.info("loading previously trained model")
        learner.load_model()
    else:
        logging.info("training model")

        learner.create_model()
        learner.print_model_summary()
        learner.train_model(x_train=x_train, y_train=y_train,
                            x_val=x_val, y_val=y_val)
        learner.save_model()

    # evaluate model using conventional performance metrics
    logging.info("evaluating model")
    training_set_metrics = learner.evaluate_model(x=x_train, y=y_train)
    validation_set_metrics = learner.evaluate_model(x=x_val, y=y_val)
    test_set_metrics = learner.evaluate_model(x=x_test, y=y_test)
    logging.info("training, validation, test set metrics computed")

    evaluation_dir = output_dir + "evaluation/" + simulator_id + "/" + \
        learner.id
    os.makedirs(evaluation_dir, exist_ok=True)
    save_metrics(training_set_metrics,
                 validation_set_metrics,
                 test_set_metrics,
                 learner.metrics,
                 evaluation_dir + "/metrics.txt")
    logging.info("training, validation, test set metrics saved")

    # save all predictions
    y_hat_train = learner.predict(x_train)
    y_hat_val = learner.predict(x_val)
    y_hat_test = learner.predict(x_test)
    logging.info("training, validation, test set predictions calculated")

    pd.DataFrame(y_hat_train, columns=learner.labels).to_csv(
        evaluation_dir + "/y-hat-train.txt", sep="\t", index=False)
    pd.DataFrame(y_hat_val, columns=learner.labels).to_csv(
        evaluation_dir + "/y-hat-val.txt", sep="\t", index=False)
    pd.DataFrame(y_hat_test, columns=learner.labels).to_csv(
        evaluation_dir + "/y-hat-test.txt", sep="\t", index=False)
    logging.info("training, validation, test set predictions saved")

    # plot ROC and PR curves
    encoded_y_train = learner.encode_y(y_train)
    encoded_y_val = learner.encode_y(y_val)
    encoded_y_test = learner.encode_y(y_test)

    learner.create_roc_curve(encoded_y_train, y_hat_train,
                             evaluation_dir + "/roc-curve-train.pdf")
    learner.create_roc_curve(encoded_y_val, y_hat_val,
                             evaluation_dir + "/roc-curve-val.pdf")
    learner.create_roc_curve(encoded_y_test, y_hat_test,
                             evaluation_dir + "/roc-curve-test.pdf")
    logging.info("ROC curves generated")

    learner.create_precision_recall_curve(
        encoded_y_train, y_hat_train, evaluation_dir + "/pr-curve-train.pdf")
    learner.create_precision_recall_curve(
        encoded_y_val, y_hat_val, evaluation_dir + "/pr-curve-val.pdf")
    learner.create_precision_recall_curve(
        encoded_y_test, y_hat_test, evaluation_dir + "/pr-curve-test.pdf")
    logging.info("PR curves generated")

    # evaluate model with SIS
    if evaluator_id is None:
        logging.info("skipping evaluation step: no evaluator specified")
    else:
        logging.info("evaluating model using interpretability methods")
        evaluator: Evaluator = get_evaluator(
            evaluator_id, learner,
            output_dir + "input/" + simulator_id, evaluation_dir)
        evaluator.evaluate_model("test")
    

def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(
        prog="seqgra",
        description="Generate synthetic data based on grammar, train model on "
        "synthetic data, evaluate model")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-d",
        "--dataconfigfile",
        type=str,
        help="path to the segra XML data configuration file. Use this option "
        "to generate synthetic data based on a seqgra grammar (specify "
        "either -d or -f, not both)"
    )
    group.add_argument(
        "-f",
        "--datafolder",
        type=str,
        help="experimental data folder name inside outputdir/input. Use this "
        "option to train the model on experimental or externally synthesized "
        "data (specify either -f or -d, not both)"
    )
    parser.add_argument(
        "-m",
        "--modelconfigfile",
        type=str,
        required=True,
        help="path to the seqgra XML model configuration file"
    )
    parser.add_argument(
        "-e",
        "--evaluator",
        type=str,
        default=None,
        choices=["sis"],
        help="evaluator ID of interpretability method"
    )
    parser.add_argument(
        "-o",
        "--outputdir",
        type=str,
        required=True,
        help="output directory, subdirectories are created for generated "
        "data, trained model, and model evaluation"
    )
    args = parser.parse_args()

    if args.modelconfigfile and args.outputdir:
        if args.dataconfigfile or args.datafolder:
            run_seqgra(args.dataconfigfile,
                args.datafolder,
                args.modelconfigfile,
                args.evaluator,
                args.outputdir)
        else:
            parser.print_help()
            sys.exit(2)
    else:
        parser.print_help()
        sys.exit(2)

if __name__ == "__main__":
    main()