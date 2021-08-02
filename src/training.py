import tensorflow as tf

from src.metrics import precision, recall, accuracy, f1score
from src.utils import get_balance_factor, get_device
from src.dataset import get_dataset


@tf.function
def forward_step(model, inputs):
    with tf.device(get_device()):
        output = model(inputs, training=False)
    return output


@tf.function
def forward_backward_step(model, inputs, label, optimizer, loss_fn, balance_factor):
    with tf.device(get_device()):
        with tf.GradientTape() as tape:
            logits = model(inputs, training=True)
            loss = loss_fn(logits, label, activation=None, balance_factor=balance_factor, training=True)
        gradients = tape.gradient(loss, model.trainable_weights)
        optimizer.apply_gradients(zip(gradients, model.trainable_weights))
        return logits, loss


@tf.function
def train_loop(model, training_set, train_steps, optimizer, loss_fn, balance_factor):
    print('TRACE TRAIN LOOP')
    loss_arr = tf.TensorArray(tf.float32, size=train_steps)
    f1_score_arr = tf.TensorArray(tf.float32, size=train_steps)
    acc_arr = tf.TensorArray(tf.float32, size=train_steps)
    for b, (image, template, label) in zip(range(train_steps), training_set.take(train_steps)):
        tf.print('\rstep {0}/{1}'.format(b + 1, train_steps), end='')
        logits, loss = forward_backward_step(model, [image, template], label, optimizer, loss_fn, balance_factor)
        b = tf.cast(b, dtype=tf.int32)
        loss_arr = loss_arr.write(b, loss)
        prec = precision(logits, label)
        rec = recall(logits, label)
        f1_score_arr = f1_score_arr.write(b, f1score(prec, rec))
        acc = accuracy(logits, label)
        acc_arr = acc_arr.write(b, acc)
    return loss_arr.stack(), f1_score_arr.stack(), acc_arr.stack()


@tf.function
def val_loop(model, validation_set, val_steps, loss_fn, balance_factor):
    print('TRACE VAL LOOP')
    loss_arr = tf.TensorArray(tf.float32, size=val_steps)
    f1_score_arr = tf.TensorArray(tf.float32, size=val_steps)
    acc_arr = tf.TensorArray(tf.float32, size=val_steps)
    for b, (image, template, label) in zip(range(val_steps), validation_set.take(val_steps)):
        tf.print('\rstep {0}/{1}'.format(b + 1, val_steps), end='')
        logits = forward_step(model, [image, template])
        loss = loss_fn(logits, label, activation=None, balance_factor=balance_factor, training=False)
        b = tf.cast(b, dtype=tf.int32)
        loss_arr = loss_arr.write(b, loss)
        prec = precision(logits, label)
        rec = recall(logits, label)
        f1_score_arr = f1_score_arr.write(b, f1score(prec, rec))
        acc = accuracy(logits, label)
        acc_arr = acc_arr.write(b, acc)
    return loss_arr.stack(), f1_score_arr.stack(), acc_arr.stack()


@tf.function
def update(new_metric, old_metric, improvement, metric_name):
    print('TRACE UPDATE')
    tf.print('Improve ', metric_name, ' value: ', old_metric, ' ----> ', new_metric)
    improvement = tf.add(improvement, 1)
    return [new_metric, improvement]


@tf.function
def train(model, train_data_path, epochs, batch_size, loss_fn, optimizer, early_stopping=15):
    # print("TRACE TRAIN")
    training_set, validation_set, train_steps, val_steps = get_dataset(train_data_path, batch_size, show=False)

    balance_factor = get_balance_factor()

    best_loss = tf.constant(1000000, dtype=tf.float32)
    last_improvement = tf.constant(0, dtype=tf.float32)
    early_stopping = tf.constant(early_stopping, tf.float32)

    train_loss_history = tf.TensorArray(tf.float32, size=epochs)
    train_f1_score_history = tf.TensorArray(tf.float32, size=epochs)
    train_accuracy_history = tf.TensorArray(tf.float32, size=epochs)

    val_loss_history = tf.TensorArray(tf.float32, size=epochs)
    val_f1_score_history = tf.TensorArray(tf.float32, size=epochs)
    val_accuracy_history = tf.TensorArray(tf.float32, size=epochs)

    pretty_line = '\n! --------------------------------------------------------- !\n'

    for epoch in range(epochs):

        tf.print(f'{pretty_line}Epoch: {epoch + 1}/{epochs}')
        tf.print('\nTRAIN')
        train_loss = tf.TensorArray(tf.float32, size=train_steps)
        train_f1_score = tf.TensorArray(tf.float32, size=train_steps)
        train_accuracy = tf.TensorArray(tf.float32, size=train_steps)

        for b, (image, template, label) in zip(range(train_steps), training_set.take(train_steps)):
            tf.print('\rstep {0}/{1}'.format(b + 1, train_steps), end='')
            logits, loss = forward_backward_step(model, [image, template], label, optimizer, loss_fn, balance_factor)
            b = tf.cast(b, dtype=tf.int32)
            train_loss = train_loss.write(b, loss)
            prec = precision(logits, label)
            rec = recall(logits, label)
            train_f1_score = train_f1_score.write(b, f1score(prec, rec))
            acc = accuracy(logits, label)
            train_accuracy = train_accuracy.write(b, acc)

        train_loss = tf.reduce_mean(train_loss.stack())
        train_f1_score = tf.reduce_mean(train_f1_score.stack())
        train_accuracy = tf.reduce_mean(train_accuracy.stack())
        tf.print('\nLoss: ', train_loss, ' F1 Score: ', train_f1_score, ' Accuracy: ', train_accuracy)

        train_loss_history = train_loss_history.write(epoch, train_loss)
        train_f1_score_history = train_f1_score_history.write(epoch, train_f1_score)
        train_accuracy_history = train_accuracy_history.write(epoch, train_accuracy)

        tf.print("\nVALIDATE")
        val_loss = tf.TensorArray(tf.float32, size=val_steps)
        val_f1_score = tf.TensorArray(tf.float32, size=val_steps)
        val_accuracy = tf.TensorArray(tf.float32, size=val_steps)

        for b, (image, template, label) in zip(range(val_steps), validation_set.take(val_steps)):
            tf.print('\rStep {0}/{1}'.format(b + 1, val_steps), end='')
            logits = forward_step(model, [image, template])
            loss = loss_fn(logits, label, activation=None, balance_factor=balance_factor, training=False)
            b = tf.cast(b, dtype=tf.int32)
            val_loss = val_loss.write(b, loss)
            prec = precision(logits, label)
            rec = recall(logits, label)
            val_f1_score = val_f1_score.write(b, f1score(prec, rec))
            acc = accuracy(logits, label)
            val_accuracy = val_accuracy.write(b, acc)

        val_loss = tf.reduce_mean(val_loss.stack())
        val_f1_score = tf.reduce_mean(val_f1_score.stack())
        val_accuracy = tf.reduce_mean(val_accuracy.stack())
        tf.print('\nLoss: ', val_loss, ' F1 Score: ', val_f1_score, ' Accuracy: ', val_accuracy)

        val_loss_history = val_loss_history.write(epoch, val_loss)
        val_f1_score_history = val_f1_score_history.write(epoch, val_f1_score)
        val_accuracy_history = val_accuracy_history.write(epoch, val_accuracy)

        best_loss, last_improvement = tf.cond(tf.less(val_loss, best_loss),
                                              lambda: update(val_loss, best_loss, last_improvement, 'Validation Loss'),
                                              lambda: [best_loss, last_improvement])
        epoch = tf.cond(tf.greater_equal(last_improvement, early_stopping), lambda: epochs, lambda: epoch)

    return train_loss_history.stack(), train_f1_score_history.stack(), train_accuracy_history.stack(), \
           val_loss_history.stack(), val_f1_score_history.stack(), val_accuracy_history.stack()
