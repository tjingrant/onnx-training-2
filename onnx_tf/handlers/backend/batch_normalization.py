import tensorflow as tf
import onnx_tf.backend

from onnx_tf.handlers.backend_handler import BackendHandler
from onnx_tf.handlers.handler import onnx_op
from onnx_tf.handlers.handler import tf_func


@onnx_op("BatchNormalization")
@tf_func(tf.nn.batch_normalization)
class BatchNormalization(BackendHandler):

  @classmethod
  def get_attrs_processor_param(cls):
    return {
        "default": {
            "epsilon": 1e-5
        },
        "rename": {
            "epsilon": "variance_epsilon"
        }
    }

  @classmethod
  def _common(cls, node, **kwargs):
    tensor_dict = kwargs["tensor_dict"]
    x = tensor_dict[node.inputs[0]]
    x_shape = x.get_shape().as_list()
    x_rank = len(x_shape)

    params_shape_broadcast = list([1, x_shape[1]] +
                                  [1 for _ in range(2, x_rank)])
    if params_shape_broadcast[1] is None:
      params_shape_broadcast[1] = tf.shape(x)[1]
      params_shape_broadcast = tf.stack(params_shape_broadcast)

    total_num_dim = len(x.get_shape())
    scale = tf.reshape(tensor_dict[node.inputs[1]], params_shape_broadcast)
    bias = tf.reshape(tensor_dict[node.inputs[2]], params_shape_broadcast)

    running_mean_1d = tensor_dict[node.inputs[3]]
    running_var_1d = tensor_dict[node.inputs[4]]

    # # from version 7, force to use test mode
    # if cls.SINCE_VERSION >= 7 or node.attrs.get("is_test", 0):
    #   inputs = [x, running_mean, running_variance, bias, scale]
    #   return [cls.make_tensor_from_onnx_node(node, inputs=inputs)]

    spatial = node.attrs.get("spatial", 1) == 1
    momentum = node.attrs.get("momentum", 0.9)
    axis = [0] if spatial else [0] + list(range(2, total_num_dim))

    is_training = tensor_dict[onnx_tf.backend.training_flag_name]
    batch_mean, batch_var = tf.nn.moments(x, [0, 2, 3])

    # Update running mean/variance only in training mode,
    # in inference mode, we perform identity assignment.
    running_mean_to_assign = tf.cond(
        is_training, lambda: running_mean_1d * momentum + batch_mean *
        (1 - momentum), lambda: running_mean_1d)
    running_var_to_assign = tf.cond(
        is_training, lambda: running_var_1d * momentum + batch_var *
        (1 - momentum), lambda: running_var_1d)
    assign_mean = tf.compat.v1.assign(running_mean_1d, running_mean_to_assign)
    assign_var = tf.compat.v1.assign(running_var_1d, running_var_to_assign)

    # If in training mode, use batch mean, else if in inference mode,
    # use running mean and variance recorded during training.
    running_mean_to_use = tf.cond(is_training, lambda: batch_mean,
                                  lambda: running_mean_1d)
    running_var_to_use = tf.cond(is_training, lambda: batch_var,
                                 lambda: running_var_1d)

    running_mean = tf.reshape(running_mean_to_use, params_shape_broadcast)
    running_variance = tf.reshape(running_var_to_use, params_shape_broadcast)

    # print("raw running mean", tensor_dict[node.inputs[3]])
    # print()
    # print(mean)
    # exit(0)
    # mean = tf.cond(tensor_dict[training_flag_name], )
    tf.compat.v1.add_to_collection(tf.compat.v1.GraphKeys.UPDATE_OPS,
                                   assign_mean)
    tf.compat.v1.add_to_collection(tf.compat.v1.GraphKeys.UPDATE_OPS,
                                   assign_var)
    # running_mean, running_variance = mean, variance
    # TODO: need to conform to the documentation here
    inputs = [x, running_mean, running_variance, bias, scale]
    return [cls.make_tensor_from_onnx_node(node, inputs=inputs)]

  @classmethod
  def version_1(cls, node, **kwargs):
    return cls._common(node, **kwargs)

  @classmethod
  def version_6(cls, node, **kwargs):
    return cls._common(node, **kwargs)

  @classmethod
  def version_7(cls, node, **kwargs):
    return cls._common(node, **kwargs)

  @classmethod
  def version_9(cls, node, **kwargs):
    return cls._common(node, **kwargs)
