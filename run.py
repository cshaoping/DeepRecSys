"""
@Description: 训练模型
@version: 1.0.0
@License: MIT
@Author: Wang Yao
@Date: 2020-12-01 16:26:40
@LastEditors: Wang Yao
@LastEditTime: 2020-12-02 19:00:27
"""
import argparse
from pathlib import Path
import yaml
from deep_recommend.recommend.ctr.dataset.dataset import TfDatasetCSV
from deep_recommend.recommend.ctr.embedding_mlp import EmbeddingMLP
from deep_recommend.trainner import ModelTrainer
from deep_recommend.recommend.ctr.deepfm.fm import FmPart
from deep_recommend.recommend.ctr.dcn.cross_net import CrossNet
from deep_recommend.recommend.ctr.xdeepfm.xdeepfm import CIN


parser = argparse.ArgumentParser()
parser.add_argument("mode", type=str, choices=["ctr"])
parser.add_argument("model", type=str, choices=["deepfm", "dcn", "xdeepfm"])
parser.add_argument("dataset", type=str, choices=["criteo"])
parser.add_argument("train_data_dir", type=str)
parser.add_argument("valid_data_dir", type=str)
parser.add_argument("test_data_dir", type=str)
parser.add_argument("save_path", type=str)
parser.add_argument("--version", type=str, default="1")
parser.add_argument("--batch_size", type=int, default=512)
parser.add_argument("--epochs", type=int, default=10)


ctr_models_yaml = "deep_recommend/recommend/ctr/ctr_models.yml"


def run_ctr_model(args):
    """ 训练模型 """
    configs = yaml.load(open(ctr_models_yaml), Loader=yaml.FullLoader)
    model_yaml = configs.get("models").get(args.model).get("yaml")
    model_config = yaml.load(open(model_yaml), Loader=yaml.FullLoader)
    dataset_yaml = configs.get("datasets").get(args.dataset).get("yaml")
    dataset_config = yaml.load(open(dataset_yaml), Loader=yaml.FullLoader)

    dataseter = TfDatasetCSV(
        dataset_config.get("dataset").get("header").split(","),
        dataset_config.get("dataset").get("select_indexs").split(","),
        dataset_config.get("dataset").get("select_defs").split(","),
        dataset_config.get("dataset").get("label_index"),
        dataset_config.get("dataset").get("batch_size"),
        dataset_config.get("dataset").get("skip_head_lines"),
        field_delim=dataset_config.get("dataset").get("field_delim"),
        na_value=dataset_config.get("dataset").get("na_value")
    )
    train_dataset, train_steps = dataseter(
        [str(fn) for fn in Path(args.train_data_dir).glob("*.txt")])
    valid_dataset, valid_steps = dataseter(
        [str(fn) for fn in Path(args.valid_data_dir).glob("*.txt")])
    test_dataset, test_steps = dataseter(
        [str(fn) for fn in Path(args.test_data_dir).glob("*.txt")])

    embedding_mlp = EmbeddingMLP(
        dataset_config.get("features").get("dense_features"),
        dataset_config.get("features").get("sparse_features"),
        model_config.get("ff").get("hidden_sizes").split(","),
        model_config.get("ff").get("hidden_activation"),
        model_config.get("ff").get("hidden_dropout_rates").split(","),
        model_config.get("logits").get("size"),
        model_config.get("logits").get("activation"),
        model_config.get("model").get("name"),
        model_config.get("model").get("loss"),
        model_config.get("model").get("optimizer")
    )
    if args.model == "deepfm":
        explicit_part = FmPart(model_config.get("fm").get("factors"))
    elif args.model == "dcn":
        explicit_part = CrossNet(model_config.get("dcn").get("cross_layers_num"))
    elif args.model == "xdeepfm":
        explicit_part = CIN(
            model_config.get("cin").get("feature_maps").split(","),
            model_config.get("cin").get("feature_embedding_dim"))
    else:
        return f"Unsupport model {args.model}"

    model = embedding_mlp(explicit_part)

    trainer = ModelTrainer(
        model,
        train_steps,
        valid_steps,
        test_steps,
        args.save_path,
        args.version,
        epochs=args.epochs)
    trainer(train_dataset, valid_dataset, test_dataset)


if __name__ == "__main__":
    args = parser.parse_args()
    print("Model: {}".format(args.model))
    print("Dataset: {}".format(args.dataset))
    print("Train: batch_size={}, epochs={}".format(args.batch_size, args.epochs))
    print("Train Data Dir: {}".format(args.train_data_dir))
    print("Valid Data Dir: {}".format(args.valid_data_dir))
    print("Test Data Dir: {}".format(args.test_data_dir))
    print("Save Path: {}".format(args.save_path))
    run_ctr_model(args)