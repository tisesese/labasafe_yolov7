# -*- coding: utf-8 -*-
import json
import os
import cv2
from datetime import datetime

# 与 yolov7_ascend_inference / UI 一致：fire=0, person=1, board card=2
PERSON_CLASS_ID = 1


def _bbox_center(bbox):
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def _point_in_rect(px, py, x1, y1, x2, y2):
    return x1 <= px <= x2 and y1 <= py <= y2


def _rect_overlap(bbox, zone):
    x1, y1, x2, y2 = bbox
    zx1, zy1, zx2, zy2 = zone
    return not (x2 < zx1 or x1 > zx2 or y2 < zy1 or y1 > zy2)


def _intersection_area(box_a, box_b):
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0, ix2 - ix1)
    ih = max(0, iy2 - iy1)
    return iw * ih


def _area(box):
    x1, y1, x2, y2 = box
    return max(0, x2 - x1) * max(0, y2 - y1)


class DangerZoneModule:

    def __init__(self, config_path=None, log_path=None, overlap_threshold=0.2, person_class_id=None):
        self.zones = []
        self.config_path = config_path
        self.log_path = log_path or "danger_zone_alerts.log"
        # 报警阈值：人员检测框与危险区交集面积 / 该人员框面积（50% 即 0.5）
        self.overlap_threshold = float(overlap_threshold)
        self.person_class_id = int(person_class_id) if person_class_id is not None else PERSON_CLASS_ID
        self._alert_active = False
        if config_path and os.path.isfile(config_path):
            self.load_zones(config_path)

    def load_zones(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 1) 直接像素坐标（原有格式）
                # {
                #   "zones": [[x1,y1,x2,y2], ...]
                # }
                zones = data.get('zones', None)
                if isinstance(zones, list):
                    self.zones = zones
                    return

                # 2) JSON 内换算：用窗口坐标标注，再转换到目标坐标
                # {
                #   "zones_window": [[x1,y1,x2,y2], ...],
                #   "window_size": [960, 640],
                #   "target_size": [1920, 1080]
                # }
                zones_window = data.get('zones_window', [])
                window_size = data.get('window_size', [])
                target_size = data.get('target_size', [])
                if (
                    isinstance(zones_window, list)
                    and len(window_size) == 2
                    and len(target_size) == 2
                ):
                    ww, wh = float(window_size[0]), float(window_size[1])
                    tw, th = float(target_size[0]), float(target_size[1])
                    if ww > 0 and wh > 0 and tw > 0 and th > 0:
                        sx = tw / ww
                        sy = th / wh
                        converted = []
                        for z in zones_window:
                            if not isinstance(z, (list, tuple)) or len(z) != 4:
                                continue
                            x1, y1, x2, y2 = [float(v) for v in z]
                            cx1 = int(round(x1 * sx))
                            cy1 = int(round(y1 * sy))
                            cx2 = int(round(x2 * sx))
                            cy2 = int(round(y2 * sy))
                            converted.append([cx1, cy1, cx2, cy2])
                        self.zones = converted
                        return

                # 不匹配时回退为空
                self.zones = []
        except Exception as e:
            print(f"[WARNING] Load danger zones failed: {e}, using empty zones")

    def save_zones(self, path=None):
        path = path or self.config_path
        if not path:
            return
        try:
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({'zones': self.zones}, f, indent=2)
        except Exception as e:
            print(f"[WARNING] Save danger zones failed: {e}")

    def set_zones(self, zones):
        #"""zones: list of [x1, y1, x2, y2]"""
        self.zones = list(zones)

    def add_zone(self, x1, y1, x2, y2):
        self.zones.append([int(x1), int(y1), int(x2), int(y2)])

    def _zone_to_pixels(self, zone, frame_w, frame_h):
        """仅支持像素坐标: [x1, y1, x2, y2]"""
        if len(zone) != 4:
            return None
        x1, y1, x2, y2 = zone
        px1, py1, px2, py2 = [int(float(v)) for v in [x1, y1, x2, y2]]

        # 规范化并裁剪到图像范围
        px1, px2 = sorted([max(0, min(frame_w - 1, px1)), max(0, min(frame_w - 1, px2))])
        py1, py2 = sorted([max(0, min(frame_h - 1, py1)), max(0, min(frame_h - 1, py2))])
        if px2 <= px1 or py2 <= py1:
            return None
        return [px1, py1, px2, py2]

    def _zones_for_frame(self, frame_shape):
        if frame_shape is None or len(frame_shape) < 2:
            return []
        frame_h, frame_w = frame_shape[:2]
        zones_px = []
        for z in self.zones:
            zp = self._zone_to_pixels(z, frame_w, frame_h)
            if zp is not None:
                zones_px.append(zp)
        return zones_px

    def _person_detections(self, detections):
        return [d for d in (detections or []) if d.get("class_id", -1) == self.person_class_id]

    def check_intrusion(self, detections, frame_shape=None):
        """仅人员框参与判定：人员框与危险区交集面积 / 人员框面积 >= overlap_threshold 则视为该人员入侵。"""
        zones = self._zones_for_frame(frame_shape) if frame_shape is not None else self.zones
        if not zones:
            return False, []
        intruders = []
        for det in self._person_detections(detections):
            bbox = det['bbox']
            det_area = _area(bbox)
            if det_area <= 0:
                continue
            for z in zones:
                inter = _intersection_area(bbox, z)
                ratio = inter / float(det_area)
                if ratio >= self.overlap_threshold:
                    intruders.append((det, z, ratio))
                    break
        return len(intruders) > 0, intruders

    def log_alert(self, msg):
        if not self.log_path:
            return
        try:
            with open(self.log_path, 'a', encoding='utf-8') as f:
                f.write(f"[{datetime.now().isoformat()}] {msg}\n")
        except Exception:
            pass

    def process(self, frame, detections, precomputed_intrusion=None, zones_pixel=None):
        """绘制危险区与入侵提示。

        precomputed_intrusion: 若为 (alert: bool, intruders: list)，则不再调用 check_intrusion
            （用于已在原分辨率上算好入侵、仅在预览分辨率上绘制的场景）。
        zones_pixel: 若非 None，则直接使用该矩形列表绘制危险区（坐标须与 frame 一致），
            否则按 frame.shape 从配置换算危险区。
        """
        alert_triggered = False
        intruders = []

        if zones_pixel is not None:
            zones = zones_pixel
        else:
            zones = self._zones_for_frame(frame.shape)
        for z in zones:
            x1, y1, x2, y2 = z
            if x2 > x1 and y2 > y1:
                # 取消极度拖拽帧数的半透明填充，改为纯画线处理！画边框时间为 0 毫秒！
                pass
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(frame, "Danger Zone", (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

        persons = self._person_detections(detections)

        if precomputed_intrusion is not None:
            alert_triggered, intruders = precomputed_intrusion
        else:
            alert_triggered, intruders = self.check_intrusion(persons, frame_shape=frame.shape)

        # 先标注所有「人员」检测框（绿色）；入侵者后续用红框叠加
        for det in persons:
            x1, y1, x2, y2 = det["bbox"]
            conf = float(det.get("confidence", 0.0))
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 0), 2)
            label = f"person:{conf:.2f}"
            cv2.putText(
                frame,
                label,
                (x1, max(0, y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 200, 0),
                2,
            )

        # 只在报警状态发生变化时写日志/提示，避免每帧刷日志
        if alert_triggered and not self._alert_active:
            self.log_alert("Danger zone intrusion detected.")
        self._alert_active = alert_triggered

        if alert_triggered:
            for det, _, ratio in intruders:
                x1, y1, x2, y2 = det['bbox']
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                cv2.putText(
                    frame,
                    f"INTRUSION {ratio * 100:.0f}% (area>={self.overlap_threshold:.0%})",
                    (x1, max(0, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (0, 0, 255),
                    2,
                )

        return frame, alert_triggered

    def draw_zones(self, frame):
        """仅绘制危险区域框，不做报警判定。"""
        if frame is None:
            return frame
        zones = self._zones_for_frame(frame.shape)
        for z in zones:
            x1, y1, x2, y2 = z
            if x2 > x1 and y2 > y1:
                pass
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(frame, "Danger Zone", (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        return frame
