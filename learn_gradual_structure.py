
import utils
import models
import datasets
import numpy as np
import tensorflow as tf
from tensorflow.keras import metrics
from tensorflow.keras.datasets import mnist
from tensorflow.keras.utils import to_categorical
import pickle
from sklearn.neighbors import KNeighborsClassifier
from tensorflow.keras.layers import Input, Dense, Flatten
from tensorflow.keras.models import Model


def compile_model(model, loss='ce'):
    loss = models.get_loss(loss, model.output_shape[1])
    model.compile(optimizer='adam',
                  loss=[loss],
                  metrics=[metrics.sparse_categorical_accuracy])


def oracle_performance(dataset_func, n_classes, input_shape, save_file, model_func=models.simple_softmax_conv_model,
    epochs=10, loss='ce'):
    (src_tr_x, src_tr_y, src_val_x, src_val_y, inter_x, inter_y, dir_inter_x, dir_inter_y,
        trg_val_x, trg_val_y, trg_test_x, trg_test_y) = dataset_func()
    def new_model():
        model = model_func(n_classes, input_shape=input_shape)
        compile_model(model, loss)
        return model
    def run(seed):
        utils.rand_seed(seed)
        trg_eval_x = trg_val_x
        trg_eval_y = trg_val_y
        # Train source model.
        source_model = new_model()
        xs = np.concatenate([src_tr_x, inter_x])
        ys = np.concatenate([src_tr_y, inter_y])
        source_model.fit(xs, ys, epochs=epochs, verbose=True)
        _, src_acc = source_model.evaluate(src_val_x, src_val_y)
        _, target_acc = source_model.evaluate(trg_eval_x, trg_eval_y)
        print(src_acc, target_acc)
        return src_acc, target_acc
    return run(0)


def nearest_neighbor_selective_classification(dataset_func, n_classes, input_shape, save_file, model_func=models.simple_softmax_conv_model,
    epochs=10, loss='ce', layer=-2, k=5):
    (src_tr_x, src_tr_y, src_val_x, src_val_y, inter_x, inter_y, dir_inter_x, dir_inter_y,
        trg_val_x, trg_val_y, trg_test_x, trg_test_y) = dataset_func()
    def new_model():
        model = model_func(n_classes, input_shape=input_shape)
        compile_model(model, loss)
        return model
    def run(seed):
        utils.rand_seed(seed)
        trg_eval_x = trg_val_x
        trg_eval_y = trg_val_y
        # Train source model.
        source_model = new_model()
        source_model.fit(src_tr_x, src_tr_y, epochs=epochs, verbose=True)
        features = source_model.layers[layer].output
        print(features.shape)
        rep_model = Model(inputs=source_model.inputs, outputs=features)
        source_reps = rep_model.predict
    run(0)

    # Train a model on source
    # Get representations for source examples and inter examples
    # For each inter example find distance to nearest neighbor (or ave to k nearest)
    # Confidence is negative distance
    # Select top 2000 confident, plot histogram
    # argsort and plot confidences


def rotated_mnist_60_conv_oracle_all_experiment():
    oracle_performance(
        dataset_func=datasets.rotated_mnist_60_data_func, n_classes=10, input_shape=(28, 28, 1),
        save_file='saved_files/rot_mnist_60_conv_oracle_all.dat',
        model_func=models.simple_softmax_conv_model, epochs=10, loss='ce')


def rotated_mnist_60_conv_nn_experiment():
    nearest_neighbor_selective_classification(
        dataset_func=datasets.rotated_mnist_60_data_func, n_classes=10, input_shape=(28, 28, 1),
        save_file='saved_files/rot_mnist_60_conv_oracle_all.dat',
        model_func=models.simple_softmax_conv_model, epochs=2, loss='ce', layer=-2, k=1)


if __name__ == "__main__":
    rotated_mnist_60_conv_nn_experiment()
