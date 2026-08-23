# -*- coding: utf-8 -*-
#"""三模块：危险区域报警、开发板计数、火灾报警（占位）。"""
from .danger_zone import DangerZoneModule
from .board_counter import BoardCounterModule
from .fire_placeholder import FirePlaceholderModule

__all__ = ['DangerZoneModule', 'BoardCounterModule', 'FirePlaceholderModule']
