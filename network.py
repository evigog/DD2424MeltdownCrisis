from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf
from testing_env import network_params
from Parameters import training_params


tf.logging.set_verbosity(tf.logging.INFO)


#basic CNN network with one channel
def cnn_basic(features, labels, mode, params):

  """Model function for CNN."""  #input image size (46,300) - one channel
  feature_shape = features['x'].get_shape()
  feature_width = feature_shape[1].value
  # Input Layer
  max_sentence_size =int(feature_width/ 300)	  #max sentence size
  print('max sentence size: ', max_sentence_size)
  vocab_size = 300  #wordvec dimensions

  #input_variable = tf.get_variable("input_variable", initializer=features['x'], validate_shape=False, trainable=False)
  input_layer = tf.reshape(features['x'], [-1, max_sentence_size, vocab_size, 1])


  #define each group of filters
  layer_output = []
  for filter_height in network_params.FILTER_SIZES:

      conv = tf.layers.conv2d(
          inputs=input_layer,
          filters=network_params.NUM_FILTERS,
          kernel_size = (filter_height, vocab_size), #width of filter equals to the wordvec dimension
          padding="same",
          activation=tf.nn.relu)

      # max over time pooling
      pooling = tf.nn.max_pool(conv, ksize=[1, max_sentence_size - filter_height + 1, 1, 1],
                               strides=[1, 1, 1, 1],
                               padding='VALID',
                               name="pool")

      layer_output.append(pooling)

  # concatenate the filter output
  concat_output = tf.concat(layer_output, 1)
  sum_filter_sizes = sum(network_params.FILTER_SIZES)
  reshape_output = tf.reshape(concat_output, [-1, sum_filter_sizes * vocab_size * network_params.NUM_FILTERS])

  # Dense Layer for the dropout,
  dense = tf.layers.dense(inputs=reshape_output, units=network_params.DENSE_UNITS, activation=tf.nn.relu,
                          activity_regularizer=tf.contrib.layers.l2_regularizer(3.0))
  dropout = tf.layers.dropout(
      inputs=dense, rate=training_params.DROPOUT, training=mode == tf.estimator.ModeKeys.TRAIN)  # dropout rate

  # Logits Layer
  logits = tf.layers.dense(inputs=dropout, units=2, activation=tf.nn.softmax)  # two classes (positive and negative)

  # prediction MODE
  predictions = {
        # Generate predictions (for PREDICT and EVAL mode)
        "classes": tf.argmax(input=logits, axis=1),
        # Add `softmax_tensor` to the graph. It is used for PREDICT and by the
        # `logging_hook`.
        "probabilities": tf.nn.softmax(logits, name="softmax_tensor")
  }

  if mode == tf.estimator.ModeKeys.PREDICT:
      return tf.estimator.EstimatorSpec(mode=mode, predictions=predictions)


  # adaptive learning rate - exponential decay
  global_step = tf.Variable(0, trainable=False)
  adaptive_learning_rate = tf.train.exponential_decay(training_params.LEARNING_RATE_INIT, global_step,
                                                        100, training_params.LEARNING_DECAY, staircase=True)

  # Configure the Training Op (for TRAIN mode)
  if mode == tf.estimator.ModeKeys.TRAIN:

      loss = tf.losses.sparse_softmax_cross_entropy(labels=labels, logits=logits)
      tf.summary.histogram("trainingLoss", loss)
      #print("Loss:"+str(loss))

      #create list of tf.Variables from input param
      trainable_list = []
      for dict in params:
          with tf.variable_scope(dict['scope'], reuse=tf.AUTO_REUSE):
            var = tf.get_variable(dict['name'], dict['shape'], dict['dtype'])
          trainable_list.append(var)


      optimizer = tf.train.AdadeltaOptimizer(learning_rate=adaptive_learning_rate, rho=network_params.RHO)
      train_op = optimizer.minimize(
            loss=loss,
            var_list=trainable_list,
            global_step=tf.train.get_global_step())

      return tf.estimator.EstimatorSpec(mode=mode, loss=loss, train_op=train_op)

      # Configure the Training Op (for EVAL mode)
  else: # mode == tf.estimator.ModeKeys.EVAL:

      loss = tf.losses.sparse_softmax_cross_entropy(labels=labels, logits=logits)
      tf.summary.histogram("trainingLoss", loss)
      eval_metric_ops = {
        "accuracy": tf.metrics.accuracy(
            labels=labels, predictions=predictions["classes"])}

      return tf.estimator.EstimatorSpec(mode=mode, loss=loss, eval_metric_ops=eval_metric_ops)


