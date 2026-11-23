import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip("torch")

from momo_fraud.models.gnn import fit_graph_model
from momo_fraud.models.text_transformer import (
    predict_text_probabilities,
    train_text_transformer,
)


def test_graph_model_scores_edges_with_unseen_nodes():
    train_transactions = pd.DataFrame(
        {
            "payer_number": ["A", "A", "B", "C", "D", "E", "F", "G"],
            "payee_number": ["B", "C", "C", "D", "E", "F", "G", "A"],
            "amount": [10, 20, 30, 40, 50, 60, 70, 80],
        }
    )
    train_features = pd.DataFrame(
        {
            "amount": np.arange(1, 9, dtype=float),
            "velocity": np.arange(8, dtype=float),
        }
    )
    labels = np.array([0, 1, 0, 1, 0, 1, 0, 1])
    model = fit_graph_model(
        train_transactions,
        train_features,
        labels,
        feature_columns=["amount", "velocity"],
        epochs=2,
        hidden=8,
    )
    test_transactions = pd.DataFrame(
        {"payer_number": ["A", "new"], "payee_number": ["new", "B"], "amount": [12, 14]}
    )
    probabilities = model.predict_proba(
        test_transactions,
        pd.DataFrame({"amount": [12.0, 14.0], "velocity": [1.0, 2.0]}),
    )
    assert probabilities.shape == (2,)
    assert np.isfinite(probabilities).all()
    assert np.all((probabilities >= 0) & (probabilities <= 1))


def test_transformer_training_requires_independent_binary_labels():
    with pytest.raises(ValueError, match="both binary classes"):
        train_text_transformer(
            ["text one", "text two"],
            [0, 0],
            ["validation one", "validation two"],
            [0, 1],
            output_dir="models/test-transformer",
        )


def test_transformer_trains_from_a_local_checkpoint_without_network(tmp_path):
    from transformers import BertConfig, BertForSequenceClassification, BertTokenizer

    vocabulary = tmp_path / "vocab.txt"
    vocabulary.write_text(
        "[PAD]\n[UNK]\n[CLS]\n[SEP]\n[MASK]\nsafe\nfraud\ntransfer\nusual\n",
        encoding="utf-8",
    )
    checkpoint = tmp_path / "tiny-checkpoint"
    checkpoint.mkdir()
    BertTokenizer(vocab_file=str(vocabulary)).save_pretrained(checkpoint)
    model = BertForSequenceClassification(
        BertConfig(
            vocab_size=9,
            hidden_size=16,
            num_hidden_layers=1,
            num_attention_heads=2,
            intermediate_size=32,
            num_labels=2,
        )
    )
    model.save_pretrained(checkpoint)

    output = tmp_path / "trained-text-model"
    report = train_text_transformer(
        ["safe transfer", "fraud transfer", "usual safe", "fraud"],
        [0, 1, 0, 1],
        ["safe", "fraud transfer"],
        [0, 1],
        output_dir=output,
        model_name=str(checkpoint),
        max_length=12,
        batch_size=2,
        epochs=1,
        patience=1,
    )
    probabilities = predict_text_probabilities(["safe transfer"], output)
    assert len(report["history"]) == 1
    assert probabilities.shape == (1,)
    assert np.isfinite(probabilities).all()
