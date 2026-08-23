# -*- coding: utf-8 -*-
#"""开发板计数模块：统计画面中板卡数量并标注，并支持低库存报警。"""
import cv2
from datetime import datetime
from collections import Counter

# 板卡类别 ID：与你的模型类别顺序一致（fire=0, person=1, board card=2）
BOARD_CARD_CLASS_ID = 2


class BoardCounterModule:
    #"""开发板计数模块，按 class_id 过滤板卡并显示数量。"""

    def __init__(self, class_id=None, smooth_frames=3, alert_threshold=30, log_path="board_count_alerts.log"):
        if class_id is None:
            class_id = BOARD_CARD_CLASS_ID
        self.class_id = class_id
        self.smooth_frames = smooth_frames
        self._count_history = []
        self.alert_threshold = int(alert_threshold)
        self.log_path = log_path
        self._alert_active = False

    def process(self, frame, detections):
       
        board_detections = [d for d in detections if d['class_id'] == self.class_id]
        count = len(board_detections)
        if self.smooth_frames > 0:
            self._count_history.append(count)
            if len(self._count_history) > self.smooth_frames:
                self._count_history.pop(0)
            count = Counter(self._count_history).most_common(1)[0][0]

        alert_active = count < self.alert_threshold

        # 状态变化才写日志，避免每帧刷屏
        if alert_active != self._alert_active:
            self._alert_active = alert_active
            self._log_state_change(count, alert_active)

        # 顶部信息条：报警时为红色，否则绿色（优化：非报警时减少绘制频率）
        if alert_active or len(self._count_history) % 3 == 0:  # 非报警时每3帧绘制一次
            bar_fill = (0, 0, 200) if alert_active else (0, 200, 0)
            bar_border = (0, 0, 255) if alert_active else (0, 255, 0)
            cv2.rectangle(frame, (10, 10), (320, 78), bar_fill, -1)
            cv2.rectangle(frame, (10, 10), (320, 78), bar_border, 2)
            cv2.putText(frame, f"Board Count: {count}", (20, 44),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)
            cv2.putText(frame, f"Alert if < {self.alert_threshold}", (20, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

        # 移除了"LOW STOCK ALERT!"警告文字

        for det in board_detections:
            x1, y1, x2, y2 = det['bbox']
            color = (0, 0, 255) if alert_active else (0, 255, 0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            label = "Board"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
            label_x = x1
            label_y = y1 - 6
            if label_y - th < 0:
                label_y = y1 + th + 6
            cv2.rectangle(frame, (label_x, label_y - th - 4), (label_x + tw + 6, label_y), color, -1)
            cv2.putText(frame, label, (label_x + 3, label_y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

        return frame, count, alert_active

    def _log_state_change(self, count, alert_active):
        if not self.log_path:
            return
        try:
            state = "ALERT_ON" if alert_active else "ALERT_OFF"
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().isoformat()}] {state} board_count={count} threshold={self.alert_threshold}\n")
        except Exception:
            pass
