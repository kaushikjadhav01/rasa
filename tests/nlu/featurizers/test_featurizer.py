import numpy as np
import pytest
import scipy.sparse

from rasa.nlu.classifiers.diet_classifier import DIETClassifier
from rasa.nlu.featurizers.sparse_featurizer.count_vectors_featurizer import (
    CountVectorsFeaturizer,
)
from rasa.nlu.featurizers.sparse_featurizer.lexical_syntactic_featurizer import (
    LexicalSyntacticFeaturizer,
)
from rasa.nlu.tokenizers.whitespace_tokenizer import WhitespaceTokenizer
from rasa.nlu.training_data import Message, TrainingData
from rasa.nlu.featurizers.featurizer import DenseFeaturizer, Features
from rasa.nlu.constants import TEXT, FEATURIZER_CLASS_ALIAS
from rasa.utils.tensorflow.constants import FEATURIZERS


def test_combine_with_existing_dense_features():
    existing_features = Features(np.array([[1, 0, 2, 3], [2, 0, 0, 1]]), TEXT, "test")
    new_features = np.array([[1, 0], [0, 1]])
    expected_features = np.array([[1, 0, 2, 3, 1, 0], [2, 0, 0, 1, 0, 1]])

    actual_features = existing_features.combine_with_features(new_features)

    assert np.all(expected_features == actual_features)


def test_combine_with_existing_dense_features_shape_mismatch():
    existing_features = Features(np.array([[1, 0, 2, 3], [2, 0, 0, 1]]), TEXT, "test")
    new_features = np.array([[0, 1]])

    with pytest.raises(ValueError):
        existing_features.combine_with_features(new_features)


def test_combine_with_existing_sparse_features():
    existing_features = Features(
        scipy.sparse.csr_matrix([[1, 0, 2, 3], [2, 0, 0, 1]]), TEXT, "test"
    )
    new_features = scipy.sparse.csr_matrix([[1, 0], [0, 1]])
    expected_features = [[1, 0, 2, 3, 1, 0], [2, 0, 0, 1, 0, 1]]

    actual_features = existing_features.combine_with_features(new_features)
    actual_features = actual_features.toarray()

    assert np.all(expected_features == actual_features)


def test_combine_with_existing_sparse_features_shape_mismatch():
    existing_features = Features(
        scipy.sparse.csr_matrix([[1, 0, 2, 3], [2, 0, 0, 1]]), TEXT, "test"
    )
    new_features = scipy.sparse.csr_matrix([[0, 1]])

    with pytest.raises(ValueError):
        existing_features.combine_with_features(new_features)


@pytest.mark.parametrize(
    "pooling, features, expected",
    [
        (
            "mean",
            np.array([[0.5, 3, 0.4, 0.1], [0, 0, 0, 0], [0.5, 3, 0.4, 0.1]]),
            np.array([[0.5, 3, 0.4, 0.1]]),
        ),
        (
            "max",
            np.array([[1.0, 3.0, 0.0, 2.0], [4.0, 3.0, 1.0, 0.0]]),
            np.array([[4.0, 3.0, 1.0, 2.0]]),
        ),
        (
            "max",
            np.array([[0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0]]),
            np.array([[0.0, 0.0, 0.0, 0.0]]),
        ),
    ],
)
def test_calculate_cls_vector(pooling, features, expected):
    actual = DenseFeaturizer._calculate_cls_vector(features, pooling)

    assert np.all(actual == expected)


def test_flexible_nlu_pipeline():
    message = Message("This is a test message.", data={"intent": "test"})
    training_data = TrainingData([message, message, message, message, message])

    tokenizer = WhitespaceTokenizer()
    tokenizer.train(training_data)

    featurizer = CountVectorsFeaturizer(
        component_config={FEATURIZER_CLASS_ALIAS: "cvf_word"}
    )
    featurizer.train(training_data)

    featurizer = CountVectorsFeaturizer(
        component_config={
            FEATURIZER_CLASS_ALIAS: "cvf_char",
            "min_ngram": 1,
            "max_ngram": 3,
            "analyzer": "char_wb",
        }
    )
    featurizer.train(training_data)

    featurizer = LexicalSyntacticFeaturizer({})
    featurizer.train(training_data)

    assert len(message.features) == 4
    assert message.features[0].origin == "cvf_word"
    # cvf word is also extracted for the intent
    assert message.features[1].origin == "cvf_word"
    assert message.features[2].origin == "cvf_char"
    assert message.features[3].origin == "LexicalSyntacticFeaturizer"

    feature_dim = (
        message.features[0].features.shape[1] + message.features[3].features.shape[1]
    )

    classifier = DIETClassifier(
        component_config={FEATURIZERS: ["cvf_word", "LexicalSyntacticFeaturizer"]}
    )
    model_data = classifier.preprocess_train_data(training_data)

    assert len(model_data.get("text_features")) == 1
    assert len(model_data.get("label_features")) == 1
    assert model_data.get("text_features")[0][0].shape == (6, feature_dim)
    assert model_data.get("label_features")[0][0].shape == (1, 1)
