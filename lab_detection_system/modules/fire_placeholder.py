# -*- coding: utf-8 -*-
#"""火灾报警模块：只检测火焰 fire=0，检测到火焰即报警（红框、日志）。"""
import cv2
from datetime import datetime


def on_fire_detection_result(bbox_list):
  
    pass


class FirePlaceholderModule:
    #"""火灾报警：有火焰检测结果则画框并报警；无火焰时直接放行不画任何占位符。"""

    def __init__(self, log_path="fire_alerts.log"):
        self.log_path = log_path
        self._last_alert = False

    def process(self, frame, detections=None):
  
        # 你的模型类别顺序：fire=0, person=1, board card=2
        FIRE_CLASS_ID = 0

        detections = detections or []
        fire_count = sum(1 for d in detections if d.get("class_id", -1) == FIRE_CLASS_ID)
        alert_triggered = fire_count > 0

        if alert_triggered:
            if not self._last_alert:
                self._log_alert(len(detections))
            self._last_alert = True

            # detections 理论上已经是 fire_dets，但这里仍按 class_id 保护一次
            for det in detections:
                if det.get("class_id", -1) != FIRE_CLASS_ID:
                    continue
                x1, y1, x2, y2 = det["bbox"]
                box_color = (0, 0, 255)
                label = "FIRE!"
                cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 3)
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw, y1), box_color, -1)
                cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # 移除了顶部红色警示横幅
        else:
            # 取消原来的黑色底栏 "Fire Alarm Module - No fire detected"
            # 也就意味着如果没有火灾，画面上不再被任何杂物遮挡
            self._last_alert = False

        return frame, alert_triggered

    def _log_alert(self, count):
        if not self.log_path:
            return
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().isoformat()}] FIRE_ALERT count={count}\n")
        except Exception:
            pass
