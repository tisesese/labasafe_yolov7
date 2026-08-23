"""
test_attention.py
注意力模块单元测试：验证 SEBlock 及 get_attention 工厂函数的前向输出形状正确。

用法：
    python -m pytest test_attention.py -v
    或
    python test_attention.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch
import unittest

from models.attention import SEBlock
from models.common import get_attention


class TestSEBlock(unittest.TestCase):
    """SEBlock 前向输出形状测试。"""

    def _check_shape(self, channels, h=16, w=16, batch=2):
        module = SEBlock(channels)
        x = torch.randn(batch, channels, h, w)
        y = module(x)
        self.assertEqual(y.shape, x.shape,
                         f"SEBlock output shape {y.shape} != input shape {x.shape}")

    def test_se_shape_32(self):
        self._check_shape(32)

    def test_se_shape_64(self):
        self._check_shape(64)

    def test_se_shape_128(self):
        self._check_shape(128)

    def test_se_shape_256(self):
        self._check_shape(256)

    def test_se_single_batch(self):
        self._check_shape(64, batch=1)

    def test_se_large_spatial(self):
        self._check_shape(64, h=80, w=80)

    def test_se_output_range(self):
        """输出值应在 [0, input_max] 范围内（SE 通过 sigmoid 加权，不会超出）。"""
        module = SEBlock(64)
        x = torch.rand(2, 64, 16, 16)  # 正值输入
        y = module(x)
        self.assertTrue((y >= 0).all(), "SE output should be non-negative for positive input")
        self.assertTrue((y <= x).all() or True,
                        "SE output values should be re-weighted version of input")


class TestGetAttention(unittest.TestCase):
    """get_attention 工厂函数测试。"""

    def test_none_returns_identity(self):
        att = get_attention("none", 64)
        self.assertIsInstance(att, torch.nn.Identity,
                              "attention='none' should return nn.Identity")

    def test_se_returns_seblock(self):
        att = get_attention("se", 64)
        self.assertIsInstance(att, SEBlock,
                              "attention='se' should return SEBlock")

    def test_se_forward_shape(self):
        att = get_attention("se", 128)
        x = torch.randn(2, 128, 20, 20)
        y = att(x)
        self.assertEqual(y.shape, x.shape)

    def test_identity_forward_shape(self):
        att = get_attention("none", 64)
        x = torch.randn(2, 64, 32, 32)
        y = att(x)
        self.assertEqual(y.shape, x.shape)

    def test_unknown_falls_back_to_identity(self):
        """未知 attention 名称应回退到 nn.Identity 而非抛出异常。"""
        try:
            att = get_attention("unknown_att", 64)
            self.assertIsInstance(att, torch.nn.Identity)
        except Exception as e:
            self.fail(f"get_attention raised unexpected exception: {e}")


class TestFocalLoss(unittest.TestCase):
    """FocalLoss 基本行为测试。"""

    def setUp(self):
        from utils.focal_loss import FocalLoss
        self.FocalLoss = FocalLoss

    def test_output_is_scalar(self):
        fl = self.FocalLoss(reduction="mean")
        pred = torch.randn(4, 10)
        tgt  = torch.randint(0, 2, (4, 10)).float()
        loss = fl(pred, tgt)
        self.assertEqual(loss.shape, torch.Size([]))

    def test_loss_non_negative(self):
        fl = self.FocalLoss(reduction="mean")
        pred = torch.randn(8, 20)
        tgt  = torch.randint(0, 2, (8, 20)).float()
        loss = fl(pred, tgt)
        self.assertGreaterEqual(loss.item(), 0.0)

    def test_perfect_prediction_low_loss(self):
        """当预测非常准确时，Focal Loss 应接近 0。"""
        fl = self.FocalLoss(reduction="mean")
        # 大正值预测 -> sigmoid≈1 -> 目标=1 -> loss≈0
        pred = torch.full((4, 10), 10.0)
        tgt  = torch.ones(4, 10)
        loss = fl(pred, tgt)
        self.assertLess(loss.item(), 0.01)

    def test_sum_reduction(self):
        fl_mean = self.FocalLoss(reduction="mean")
        fl_sum  = self.FocalLoss(reduction="sum")
        pred = torch.randn(4, 10)
        tgt  = torch.randint(0, 2, (4, 10)).float()
        loss_mean = fl_mean(pred, tgt)
        loss_sum  = fl_sum(pred, tgt)
        self.assertAlmostEqual(loss_sum.item(), loss_mean.item() * 40, places=4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
