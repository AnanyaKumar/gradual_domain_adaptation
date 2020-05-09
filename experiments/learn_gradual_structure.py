
import gradual_st.utils as utils
import gradual_st.models as models
import gradual_st.datasets as datasets
import numpy as np
import tensorflow as tf
from tensorflow.keras import metrics
from tensorflow.keras.datasets import mnist
from tensorflow.keras.utils import to_categorical
import pickle
from sklearn.neighbors import KNeighborsClassifier
from tensorflow.keras.layers import Input, Dense, Flatten
from tensorflow.keras.models import Model
import matplotlib.pyplot as plt


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


def nearest_neighbor_selective_classification(dataset_func, n_classes, input_shape, save_file,
    model_func=models.simple_softmax_conv_model, epochs=10, loss='ce', layer=-2, k=1,
    num_points_to_add=2000, accumulate=True, use_timestamps=False):
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
        rep_model = Model(inputs=source_model.inputs, outputs=features)
        source_reps = rep_model.predict(src_tr_x)
        nn = KNeighborsClassifier(n_neighbors=k)
        nn.fit(source_reps, src_tr_y)
        # Validation accuracy.
        val_reps = rep_model.predict(src_val_x)
        val_acc = np.mean(nn.predict(val_reps) == src_val_y)
        print('Source val acc: ', val_acc)
        # Target accuracy.
        trg_reps = rep_model.predict(trg_eval_x)
        trg_acc = np.mean(nn.predict(trg_reps) == trg_eval_y)
        print('Target acc: ', trg_acc)
        # Number of points to add with self-training.
        num_unsup = inter_x.shape[0]
        iters = int(num_unsup / num_points_to_add)
        if iters * num_points_to_add < num_unsup:
            iters += 1
        assert(iters * num_points_to_add >= num_unsup)
        assert((iters-1) * num_points_to_add < num_unsup)
        # Gradual self-training.
        reps, ys = source_reps, src_tr_y
        for i in range(iters):
            if use_timestamps:
                next_xs = inter_x[num_points_to_add*i:num_points_to_add*(i+1)]
                # Only use the labels for printing accuracy statistics.
                next_ys = inter_y[num_points_to_add*i:num_points_to_add*(i+1)]
            else:
                pass
            next_reps = rep_model.predict(next_xs)
            assert(len(next_reps.shape) == 2)
            next_pseudo_ys = nn.predict(next_reps)
            print(next_pseudo_ys.shape)
            # assert(len(next_pseudo_ys.shape) == 1)
            if accumulate:
                reps = np.concatenate([reps, next_reps])
                ys = np.concatenate([ys, next_pseudo_ys])
            else:
                reps, ys = next_reps, next_pseudo_ys
            nn.fit(reps, ys)
            cur_acc = np.mean(nn.predict(next_reps) == next_ys)
            print("Iteration %d: %.2f" % (i+1, cur_acc*100))
        # Target accuracy.
        trg_reps = rep_model.predict(trg_eval_x)
        trg_acc = np.mean(nn.predict(trg_reps) == trg_eval_y)
        print('Final Target acc: ', trg_acc) 
        inter_reps = rep_model.predict(inter_x)
        inter_acc = np.mean(nn.predict(inter_reps) == inter_y)
        print('Intermediate acc')
        # # For each intermediate point, get k nearest neighbor distance, average them.
        # inter_reps = rep_model.predict(inter_x)
        # neigh_dist, _ = nn.kneighbors(X=inter_reps, n_neighbors=k, return_distance=True)
        # ave_dist = np.mean(neigh_dist, axis=1)
        # print(ave_dist.shape)
        # indices = np.argsort(ave_dist)
        # keep_points = indices[:num_points_to_add]
        # utils.plot_histogram(keep_points / 42000.0)
        # # Get accuracy on the selected points.
        # print("Accuracy on easy examples")
        # easy_x = inter_x[keep_points]
        # easy_y = inter_y[keep_points]
        # easy_reps = rep_model.predict(easy_x)
        # easy_acc = np.mean(nn.predict(easy_reps) == easy_y)
        # print('Easy acc: ', easy_acc)
    run(0)


def rotated_mnist_60_conv_nn_experiment():
    nearest_neighbor_selective_classification(
        dataset_func=datasets.rotated_mnist_60_data_func, n_classes=10, input_shape=(28, 28, 1),
        save_file='saved_files/rot_mnist_60_conv_oracle_all.dat',
        model_func=models.simple_softmax_conv_model, epochs=10, loss='ce', layer=-2, k=1,
        use_timestamps=True, accumulate=False)


def rotated_mnist_60_conv_oracle_all_experiment():
    oracle_performance(
        dataset_func=datasets.rotated_mnist_60_data_func, n_classes=10, input_shape=(28, 28, 1),
        save_file='saved_files/rot_mnist_60_conv_oracle_all.dat',
        model_func=models.simple_softmax_conv_model, epochs=10, loss='ce')


def portraits_source_target_experiment(
    dataset_func=datasets.portraits_data_func, n_classes=2, input_shape=(32, 32, 1),
    model_func=models.simple_softmax_conv_model, interval=2000, epochs=20, loss='ce'):
    # Train a discriminator to classify between source and target.
    # Is this better able to identify the timestamps?
    (src_tr_x, src_tr_y, src_val_x, src_val_y, inter_x, inter_y, dir_inter_x, dir_inter_y,
        trg_val_x, trg_val_y, trg_test_x, trg_test_y) = dataset_func()
    def new_model():
        model = model_func(2, input_shape=input_shape)
        compile_model(model, loss)
        return model
    # Try using confidence instead.
    source_model = new_model()
    source_model.fit(src_tr_x, src_tr_y, epochs=epochs, verbose=True)
    inter_preds = source_model.predict(inter_x)[:,0]
    ranks = utils.get_confidence_ranks_by_time(inter_preds)
    rolled_ranks = utils.rolling_average(ranks, 100)
    plt.clf()
    plt.plot(np.arange(len(rolled_ranks)), rolled_ranks)
    plt.show()
    # Make discrimination dataset.
    xs = np.concatenate([src_tr_x, trg_val_x])
    ys = np.concatenate([np.zeros(len(src_tr_x)), np.ones(len(src_tr_x))])
    source_target_model = new_model()
    source_target_model.fit(xs, ys, epochs=epochs, verbose=True)
    source_preds = source_target_model.predict(src_val_x)[:,0]
    print(np.mean(source_preds))
    target_preds = source_target_model.predict(trg_test_x)[:,0]
    print(np.mean(target_preds))
    inter_preds = source_target_model.predict(inter_x)[:,0]
    rolled_preds = utils.rolling_average(inter_preds, 100)
    plt.clf()
    plt.plot(np.arange(len(rolled_preds)), rolled_preds)
    plt.show()


# def rotated_mnist_60_conv_nn_experiment():
#     nearest_neighbor_selective_classification(
#         dataset_func=datasets.rotated_mnist_60_data_func, n_classes=10, input_shape=(28, 28, 1),
#         save_file='saved_files/rot_mnist_60_conv_oracle_all.dat',
#         model_func=models.simple_softmax_conv_model, epochs=10, loss='ce', layer=-2, k=1)


if __name__ == "__main__":
    portraits_source_target_experiment()
    # rotated_mnist_60_conv_nn_experiment()
    # Another test to see how oracle does on representations.
