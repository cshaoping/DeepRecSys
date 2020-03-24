'''
@Description: 
@version: 
@License: MIT
@Author: Wang Yao
@Date: 2020-03-22 17:48:05
@LastEditors: Wang Yao
@LastEditTime: 2020-03-24 17:47:36
'''
from __future__ import print_function

import os
import numpy as np
import tensorflow as tf
import tensorflow.keras.backend as K
from tensorflow.keras.layers import Layer



class Embedding(Layer):

    def __init__(self, input_dim, output_dim, 
                    initializer='glorot_uniform',
                    **kwargs):
        self._input_dim = input_dim
        self._output_dim = output_dim
        self._initializer = initializer
        super(Embedding, self).__init__(**kwargs)


    def build(self, input_shape):
        self.embeddings = self.add_weight(
            shape=(self._input_dim, self._output_dim),
            initializer=self._initializer,
            name="embeddings")
        super(Embedding, self).build(input_shape)


    def call(self, inputs):
        if K.dtype(inputs) != 'int32':
            inputs = K.cast(inputs, 'int32')
        out = K.gather(self.embeddings, inputs)
        return out

    def compute_output_shape(self, input_shape):

        return input_shape + (self._output_dim,)


class PositionEncoding(Layer):

    def __init__(self, model_dim, **kwargs):
        self._model_dim = model_dim
        super(PositionEncoding, self).__init__(**kwargs)

    def call(self, inputs):
        batch_size, seq_length = K.shape(inputs)[0], K.shape(inputs)[1]
        postion_encodings = np.zeros((batch_size, seq_length, self._model_dim))
        for pos in range(seq_length):
            for i in range(self._model_dim):
                postion_encodings[:, pos, i] = pos / np.power(10000, (i-i%2) / self._model_dim)
        postion_encodings[:, :, 0::2] = np.sin(postion_encodings[:, :, 0::2]) # 2i
        postion_encodings[:, :, 1::2] = np.cos(postion_encodings[:, :, 1::2]) # 2i+1    
        postion_encodings = K.cast(postion_encodings, 'float32')

        return postion_encodings

    def compute_output_shape(self, input_shape):
        return input_shape


class ScaledDotProductAttention(Layer):

    def __init__(self, masking=True, dropout_rate=0., **kwargs):
        self._masking = masking
        self._dropout_rate = dropout_rate
        super(ScaledDotProductAttention, self).__init__(**kwargs)

    def mask(self, inputs, masks):
        masking_num=-2**32+1
        masks = K.cast(masks, 'float32')
        masks = K.tile(masks, [K.shape(inputs)[0] // K.shape(masks)[0], 1])
        masks = K.expand_dims(masks, 1)
        return inputs + masks * masking_num

    def call(self, inputs):
        if self._masking:
            assert len(inputs) == 4, "inputs should be set [queries, keys, values, masks]."
            queries, keys, values, masks = inputs
        else:
            assert len(inputs) == 3, "inputs should be set [queries, keys, values]."
            queries, keys, values = inputs

        if K.dtype(queries) != 'float32':  queries = K.cast(queries, 'float32')
        if K.dtype(keys) != 'float32':  keys = K.cast(keys, 'float32')
        if K.dtype(values) != 'float32':  values = K.cast(values, 'float32')

        matmul = K.batch_dot(queries, tf.transpose(keys, [0, 2, 1])) # MatMul
        scaled_matmul = matmul / int(K.shape(queries)[-1]) ** 0.5  # Scale
        if self._masking:
            scaled_matmul = self.mask(scaled_matmul, masks) # Mask(opt.)
        softmax_out = K.softmax(scaled_matmul) # SoftMax
        # Dropout
        out = K.dropout(softmax_out, self._dropout_rate)
        
        outputs = K.batch_dot(out, values)

        return outputs

    def compute_output_shape(self, input_shape):
        return input_shape


class MultiHeadAttention(Layer):

    def __init__(self, n_heads, head_dim, masking=True, trainable=True, **kwargs):
        self._n_heads = n_heads
        self._head_dim = head_dim
        self._masking = masking
        self._trainable = trainable
        super(MultiHeadAttention, self).__init__(**kwargs)

    def build(self, input_shape):
        self._weights_queries = self.add_weight(
            shape=(input_shape[0][-1], self._n_heads * self._head_dim),
            initializer='glorot_uniform',
            trainable=self._trainable,
            name='weights_queries')
        self._weights_keys = self.add_weight(
            shape=(input_shape[1][-1], self._n_heads * self._head_dim),
            initializer='glorot_uniform',
            trainable=self._trainable,
            name='weights_keys')
        self._weights_values = self.add_weight(
            shape=(input_shape[2][-1], self._n_heads * self._head_dim),
            initializer='glorot_uniform',
            trainable=self._trainable,
            name='weights_values')
        super(MultiHeadAttention, self).build(input_shape)


    def call(self, inputs):
        if self._masking:
            assert len(inputs) == 4, "inputs should be set [queries, keys, values, masks]."
            queries, keys, values, masks = inputs
        else:
            assert len(inputs) == 3, "inputs should be set [queries, keys, values]."
            queries, keys, values = inputs
        
        queries_linear = K.dot(queries, self._weights_queries) 
        keys_linear = K.dot(keys, self._weights_keys)
        values_linear = K.dot(values, self._weights_values)

        queries_multi_heads = tf.concat(tf.split(queries_linear, self._n_heads, axis=2), axis=0)
        keys_multi_heads = tf.concat(tf.split(keys_linear, self._n_heads, axis=2), axis=0)
        values_multi_heads = tf.concat(tf.split(values_linear, self._n_heads, axis=2), axis=0)
        
        if self._masking:
            att_inputs = [queries_multi_heads, keys_multi_heads, values_multi_heads, masks]
        else:
            att_inputs = [queries_multi_heads, keys_multi_heads, values_multi_heads]
        
        attention = ScaledDotProductAttention(masking=self._masking)
        att_out = attention(att_inputs)

        outputs = tf.concat(tf.split(att_out, self._n_heads, axis=0), axis=2)
        
        return outputs

    def compute_output_shape(self, input_shape):
        return input_shape


class PositionWiseFeedForward(Layer):
    
    def __init__(self, model_dim, inner_dim, trainable=True, **kwargs):
        self._model_dim = model_dim
        self._inner_dim = inner_dim
        self._trainable = trainable
        super(PositionWiseFeedForward, self).__init__(**kwargs)

    def build(self, input_shape):
        self.weights_inner = self.add_weight(
            shape=(input_shape[-1], self._inner_dim),
            initializer='glorot_uniform',
            trainable=self._trainable,
            name="weights_inner")
        self.weights_out = self.add_weight(
            shape=(self._inner_dim, self._model_dim),
            initializer='glorot_uniform',
            trainable=self._trainable,
            name="weights_out")
        self.bais_inner = self.add_weight(
            shape=(self._inner_dim,),
            initializer='uniform',
            trainable=self._trainable,
            name="bais_inner")
        self.bais_out = self.add_weight(
            shape=(self._model_dim,),
            initializer='uniform',
            trainable=self._trainable,
            name="bais_out")
        super(PositionWiseFeedForward, self).build(input_shape)

    def call(self, inputs):
        if K.dtype(inputs) != 'float32':
            inputs = K.cast(inputs, 'float32')
        inner_out = K.relu(K.dot(inputs, self.weights_inner) + self.bais_inner)
        outputs = K.dot(inner_out, self.weights_out) + self.bais_out
        return outputs

    def compute_output_shape(self, input_shape):
        return self._model_dim


class LayerNormalization(Layer):

    def __init__(self, epsilon=1e-8, **kwargs):
        self._epsilon = epsilon
        super(LayerNormalization, self).__init__(**kwargs)

    def build(self, input_shape):
        self.beta = self.add_weight(
            shape=(input_shape[-1],),
            initializer='zero',
            name='beta')
        self.gamma = self.add_weight(
            shape=(input_shape[-1],),
            initializer='one',
            name='gamma')
        super(LayerNormalization, self).build(input_shape)

    def call(self, inputs):
        mean, variance = tf.nn.moments(inputs, [-1], keepdims=True)
        normalized = (inputs - mean) / ((variance + self._epsilon) ** 0.5)
        outputs = self.gamma * normalized + self.beta
        return outputs

    def compute_output_shape(self, input_shape):
        return input_shape




if __name__ == "__main__":
    # emb = Embedding(500, 10)
    # emb_out = emb(np.array([[1,2,3], [2,3,4]]))
    # # print(emb_out)
    # pe = PositionEncoding(10)
    # pe_out = pe(emb_out)
    # print(pe_out)
    # atte = MultiHeadAttention(2, 5, masking=True)
    # key_masks = tf.constant([[0., 0., 1.],[0., 1., 1.]])
    # atte_out = atte([pe_out, pe_out, pe_out, key_masks])
    
    # ff = PositionWiseFeedForward(10, 2048)
    # ff_out = ff(atte_out)
    # # print(out)

    # ln = LayerNormalization()
    # ln_out = ln(ff_out)
    # print(ln_out)
    masks = tf.math.equal([[1,2,3,0,0,0], [1,2,2,0,0,0]], 0) # (N, T1)
    # masks = K.equal([1,2,3,0,0,0], 0)
    masks = K.cast(masks, 'float32')
    print(masks)

