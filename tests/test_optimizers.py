# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT license.

"""Unit Tests for optimizers such as TransposeOptimizer."""

from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import numpy as np
from onnx import helper, TensorProto
from tf2onnx import utils
from tf2onnx.graph import GraphUtil
from backend_test_base import Tf2OnnxBackendTestBase
from common import unittest_main


# pylint: disable=missing-docstring,invalid-name,unused-argument,using-constant-test

class OptimizerTests(Tf2OnnxBackendTestBase):
    """Run original model proto and modified model proto with onnxruntime, compare the results."""

    def run_and_compare(self, output_names_with_port, onnx_feed_dict, origin_proto, op_type,
                        remaining_op_num, debug=False, rtol=1e-07):
        utils.make_sure(op_type is not None, "op_type should be specified")
        utils.make_sure(remaining_op_num is not None, "remaining_op_num should be specified")

        origin_model_path = self.save_onnx_model(origin_proto, onnx_feed_dict, postfix="_origin")

        new_proto = GraphUtil.optimize_graph_with_model_proto(origin_proto)

        self.assertTrue(new_proto, msg="model proto after optimizer should not be None")

        new_model_path = self.save_onnx_model(new_proto, onnx_feed_dict, postfix="_opt")
        current = GraphUtil.get_node_count_from_onnx_graph(new_proto.graph)

        self.assertTrue(current[op_type] == remaining_op_num,
                        msg="Expect " + str(remaining_op_num) + " " + op_type + " ops left, but actually " +
                        str(current[op_type]) + " left")

        if self.config.is_onnxruntime_backend:
            expected = self.run_onnxruntime(origin_model_path, onnx_feed_dict, output_names_with_port)
            actual = self.run_onnxruntime(new_model_path, onnx_feed_dict, output_names_with_port)
        else:
            raise ValueError("only onnxruntime is supported to test transpose optimizer")

        for expected_val, actual_val in zip(expected, actual):
            self.assertAllClose(expected_val, actual_val, rtol=rtol, atol=1e-5)
            self.assertEqual(expected_val.dtype, actual_val.dtype)
            self.assertEqual(expected_val.shape, actual_val.shape)

    # Tranpose Optimizer Tests Start

    def run_transpose_compare(self, output_names_with_port, onnx_feed_dict, origin_proto,
                              remaining_transpose_num=None, debug=False, rtol=1e-07):
        self.run_and_compare(output_names_with_port, onnx_feed_dict, origin_proto, op_type="Transpose",
                             remaining_op_num=remaining_transpose_num, debug=debug, rtol=rtol)

    def test_transpose_relu(self):
        node1 = helper.make_node("Transpose", ["X"], ["Y"], perm=[0, 2, 3, 1], name="trans_1")
        node2 = helper.make_node("Relu", ["Y"], ["Z"], name="relu")
        node3 = helper.make_node("Transpose", ["Z"], ["Z1"], perm=[0, 3, 1, 2], name="trans_2")

        graph = helper.make_graph(
            [node1, node2, node3],
            "relu-test",
            [helper.make_tensor_value_info("X", TensorProto.FLOAT, (2, 3, 4, 5))],
            [helper.make_tensor_value_info("Z1", TensorProto.FLOAT, (2, 3, 4, 5))],
        )

        model_proto = helper.make_model(graph, producer_name="onnx-tests")
        self.run_transpose_compare(["Z1"], {"X": np.random.randn(2, 3, 4, 5).astype(np.float32)},
                                   model_proto, remaining_transpose_num=0)

    def test_transpose_leaky_relu(self):
        node1 = helper.make_node("Transpose", ["X"], ["Y"], perm=[0, 2, 3, 1], name="trans_1")
        node2 = helper.make_node("LeakyRelu", ["Y"], ["Z"], alpha=0.02, name="relu")
        node3 = helper.make_node("Transpose", ["Z"], ["Z1"], perm=[0, 3, 1, 2], name="trans_2")

        graph = helper.make_graph(
            [node1, node2, node3],
            "LeakyRelu-test",
            [helper.make_tensor_value_info("X", TensorProto.FLOAT, (2, 3, 4, 5))],
            [helper.make_tensor_value_info("Z1", TensorProto.FLOAT, (2, 3, 4, 5))],
        )

        model_proto = helper.make_model(graph, producer_name="onnx-tests")
        self.run_transpose_compare(["Z1"], {"X": np.random.randn(2, 3, 4, 5).astype(np.float32)},
                                   model_proto, remaining_transpose_num=0)

    def test_transpose_max(self):
        const_1_val = [2.0]
        const_1 = helper.make_tensor("const_1", TensorProto.FLOAT, (1,), const_1_val)
        const_1_node = helper.make_node("Constant", [], ["const_1"], value=const_1, name="const_1")

        const_2_val = np.random.randn(2, 4, 5, 3).astype(np.float32).reshape(120).tolist()
        const_2 = helper.make_tensor("const_2", TensorProto.FLOAT, (2, 4, 5, 3), const_2_val)
        const_2_node = helper.make_node("Constant", [], ["const_2"], value=const_2, name="const_2")

        const_3_val = np.random.randn(2, 4, 5, 3).astype(np.float32).reshape(120).tolist()
        const_3 = helper.make_tensor("const_3", TensorProto.FLOAT, (2, 4, 5, 3), const_3_val)
        const_3_node = helper.make_node("Constant", [], ["const_3"], value=const_3, name="const_3")

        node1 = helper.make_node("Transpose", ["X"], ["Y"], perm=[0, 2, 3, 1], name="trans_1")
        node2 = helper.make_node("Max", ["Y", "const_3", "const_2", "const_1"], ["Z"], name="max")
        node3 = helper.make_node("Transpose", ["Z"], ["Z1"], perm=[0, 3, 1, 2], name="trans_2")

        graph = helper.make_graph(
            [const_1_node, const_2_node, const_3_node, node1, node2, node3],
            "Max-test",
            [helper.make_tensor_value_info("X", TensorProto.FLOAT, (2, 3, 4, 5))],
            [helper.make_tensor_value_info("Z1", TensorProto.FLOAT, (2, 3, 4, 5))],
        )

        model_proto = helper.make_model(graph, producer_name="onnx-tests")
        self.run_transpose_compare(["Z1"], {"X": np.random.randn(2, 3, 4, 5).astype(np.float32)},
                                   model_proto, remaining_transpose_num=0)

    def test_transpose_merge(self):
        node0 = helper.make_node("Transpose", ["X"], ["Y"], perm=[0, 2, 3, 1], name="trans")
        node1 = helper.make_node("Transpose", ["X"], ["Y_1"], perm=[0, 2, 3, 1], name="trans_1")
        node2 = helper.make_node("Mul", ["Y", "Y_1"], ["OUT"], name="mul")

        graph = helper.make_graph(
            [node0, node1, node2],
            "transpose-merge-test",
            [helper.make_tensor_value_info("X", TensorProto.FLOAT, (2, 3, 4, 5))],
            [helper.make_tensor_value_info("OUT", TensorProto.FLOAT, (2, 4, 5, 3))],
        )

        model_proto = helper.make_model(graph, producer_name="onnx-tests")
        self.run_transpose_compare(["OUT"], {"X": np.random.randn(2, 3, 4, 5).astype(np.float32)},
                                   model_proto, remaining_transpose_num=1)

    def test_transpose_with_shape(self):
        node1 = helper.make_node("Transpose", ["X"], ["Y"], perm=[0, 2, 3, 1], name="trans")
        node2 = helper.make_node("Shape", ["Y"], ["Z"], name="shape")

        graph = helper.make_graph(
            [node1, node2],
            "transpose_with_shape",
            [helper.make_tensor_value_info("X", TensorProto.FLOAT, (2, 3, 4, 5))],
            [helper.make_tensor_value_info("Z", TensorProto.INT64, [4])],
        )

        model_proto = helper.make_model(graph, producer_name="onnx-tests")
        self.run_transpose_compare(["Z"], {"X": np.random.randn(2, 3, 4, 5).astype(np.float32)},
                                   model_proto, remaining_transpose_num=0)

    def test_transpose_with_identity(self):
        node1 = helper.make_node("Transpose", ["X"], ["Y"], perm=[0, 2, 3, 1], name="trans")
        node2 = helper.make_node("Identity", ["Y"], ["Z"], name="identity")

        graph = helper.make_graph(
            [node1, node2],
            "transpose_with_identity",
            [helper.make_tensor_value_info("X", TensorProto.FLOAT, (2, 3, 4, 5))],
            [helper.make_tensor_value_info("Z", TensorProto.FLOAT, (2, 4, 5, 3))],
        )

        model_proto = helper.make_model(graph, producer_name="onnx-tests")
        self.run_transpose_compare(["Z"], {"X": np.random.randn(2, 3, 4, 5).astype(np.float32)},
                                   model_proto, remaining_transpose_num=1)

    # Tranpose Optimizer Tests End

    # Identity Optimizer Tests Start

    def run_identity_compare(self, output_names_with_port, onnx_feed_dict, origin_proto,
                             remaining_identity_num=None, debug=False, rtol=1e-07):
        self.run_and_compare(output_names_with_port, onnx_feed_dict, origin_proto, op_type="Identity",
                             remaining_op_num=remaining_identity_num, debug=debug, rtol=rtol)

    def test_identity_non_graph_output(self):
        node1 = helper.make_node("Add", ["X", "X"], ["Y"], name="add")
        node2 = helper.make_node("Identity", ["Y"], ["Z"], name="identity")
        node3 = helper.make_node("Shape", ["Z"], ["Z1"], name="shape")

        graph = helper.make_graph(
            [node1, node2, node3],
            "identity-test",
            [helper.make_tensor_value_info("X", TensorProto.FLOAT, (2, 3, 4, 5))],
            [helper.make_tensor_value_info("Z1", TensorProto.INT64, [4])],
        )

        model_proto = helper.make_model(graph, producer_name="onnx-tests")
        self.run_identity_compare(["Z1"], {"X": np.random.randn(2, 3, 4, 5).astype(np.float32)},
                                  model_proto, remaining_identity_num=0)

    def test_identity_unremovable_identity(self):
        # should not remove!!
        node1 = helper.make_node("Identity", ["X"], ["Y"], name="identity")

        graph = helper.make_graph(
            [node1],
            "identity-test",
            [helper.make_tensor_value_info("X", TensorProto.FLOAT, (2, 3, 4, 5))],
            [helper.make_tensor_value_info("Y", TensorProto.FLOAT, (2, 3, 4, 5))],
        )

        model_proto = helper.make_model(graph, producer_name="onnx-tests")
        self.run_identity_compare(["Y"], {"X": np.random.randn(2, 3, 4, 5).astype(np.float32)},
                                  model_proto, remaining_identity_num=1)

    def test_identity_output_as_multiple_graph_outputs(self):
        # handle case like this, both Identity nodes are graph outputs,
        #            Add
        #           /   \
        #    Identity   Identity
        # We at most can remove one Identity for this case.
        node1 = helper.make_node("Add", ["X", "X"], ["Y"], name="identity")
        node2 = helper.make_node("Identity", ["Y"], ["Z1"], name="identity2")
        node3 = helper.make_node("Identity", ["Y"], ["Z2"], name="identity3")
        graph = helper.make_graph(
            [node1, node2, node3],
            "identity-test",
            [helper.make_tensor_value_info("X", TensorProto.FLOAT, (2, 3, 4, 5))],
            [helper.make_tensor_value_info("Z1", TensorProto.FLOAT, (2, 3, 4, 5)),
             helper.make_tensor_value_info("Z2", TensorProto.FLOAT, (2, 3, 4, 5))],
        )

        model_proto = helper.make_model(graph, producer_name="onnx-tests")
        self.run_identity_compare(["Z1", "Z2"], {"X": np.random.randn(2, 3, 4, 5).astype(np.float32)},
                                  model_proto, remaining_identity_num=1)

    def test_identity_in_subgraph_non_graph_output(self):
        node1 = helper.make_node("Add", ["X", "X"], ["Y"], name="add")

        iter_num_value = np.array(1, dtype=np.int64)
        node2 = helper.make_node(
            'Constant',
            inputs=[],
            outputs=['iterate_num_value'],
            value=helper.make_tensor(
                name='iterate_num_value',
                data_type=TensorProto.INT64,
                dims=iter_num_value.shape,
                vals=iter_num_value.flatten().astype(np.int64),
            ),
        )

        cond_value = np.array(True, dtype=np.bool)
        node3 = helper.make_node(
            'Constant',
            inputs=[],
            outputs=['cond_value'],
            value=helper.make_tensor(
                name='cond_value',
                data_type=TensorProto.BOOL,
                dims=iter_num_value.shape,
                vals=cond_value.flatten().astype(np.bool),
            ),
        )

        # sub graph
        sub_node1 = helper.make_node("Add", ["loop_var_1", "loop_var_1"], ["SubY"], name="sub_add")
        sub_node2 = helper.make_node("Identity", ["SubY"], ["SubIdentity1"], name="sub_identity_1")
        sub_node3 = helper.make_node("Identity", ["SubIdentity1"], ["loop_var_out_1"], name="sub_identity_2")
        sub_node4 = helper.make_node("Identity", ["loop_condition"], ["loop_cond_output"], name="sub_identity_3")
        sub_graph = helper.make_graph(
            [sub_node1, sub_node2, sub_node3, sub_node4],
            "identity_subgraph-test",
            [helper.make_tensor_value_info("loop_iter_num", TensorProto.INT64, (1,)),  # iteration_num
             helper.make_tensor_value_info("loop_condition", TensorProto.BOOL, ()),  # condition
             helper.make_tensor_value_info("loop_var_1", TensorProto.FLOAT, ()),  # loop-carried dependency
             ],
            [helper.make_tensor_value_info("loop_cond_output", TensorProto.BOOL, ()),
             helper.make_tensor_value_info("loop_var_out_1", TensorProto.FLOAT, ())
            ],
        )
        # sub graph ends

        loop_node = helper.make_node("Loop", ["iterate_num_value", "cond_value", "Y"], ["loop_var_1_output"],
                                     name="loop", body=sub_graph)

        node4 = helper.make_node("Identity", ["loop_var_1_output"], ["Z"], name="identity")
        node5 = helper.make_node("Shape", ["Z"], ["Z1"], name="shape")

        graph = helper.make_graph(
            [node1, node2, node3, loop_node, node4, node5],
            "identity-test",
            [helper.make_tensor_value_info("X", TensorProto.FLOAT, (2, 3, 4, 5))],
            [helper.make_tensor_value_info("Z1", TensorProto.INT64, [4])],
        )

        model_proto = helper.make_model(graph, producer_name="onnx-tests")
        self.run_identity_compare(["Z1"], {"X": np.random.randn(2, 3, 4, 5).astype(np.float32)},
                                  model_proto, remaining_identity_num=0)

    # Tranpose Optimizer Tests End

if __name__ == "__main__":
    unittest_main()
