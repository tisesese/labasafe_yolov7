# -*- coding: utf-8 -*-
import base64
import json
import os
import sys
import threading
import time
import queue

import cv2

# ³¢ÊÔÊ¹ÓÃ Pillow ×öäÖÈ¾£¨±È Tk PhotoImage(data=...) ¸üÎÈ£©
try:
    from PIL import Image, ImageTk  # type: ignore
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

MODULES_DIR = os.path.join(ROOT, "modules")
if MODULES_DIR not in sys.path:
    sys.path.insert(0, MODULES_DIR)

from yolov7_ascend_inference import (
    YOLOv7AscendInference,
    CLASSES as YOLOV7_CLASSES,
    PERSON_CLASS_ID,
    BOARD_CLASS_ID,
    FIRE_CLASS_ID,
)

from danger_zone import DangerZoneModule
from board_counter import BoardCounterModule
from fire_placeholder import FirePlaceholderModule


def _scale_detections_for_preview(detections, sx, sy):
    #"""ÔÚÔ­Í¼×ø±êÏÂµÄ¼ì²â¿òÁÐ±í£¬Ëõ·Åµ½Ô¤ÀÀ·Ö±æÂÊ£¨ÐÂ dict£¬²»ÐÞ¸ÄÈë²Î£©¡£"""
    out = []
    for d in detections:
        x1, y1, x2, y2 = d["bbox"]
        nd = dict(d)
        nd["bbox"] = [
            int(round(x1 * sx)),
            int(round(y1 * sy)),
            int(round(x2 * sx)),
            int(round(y2 * sy)),
        ]
        out.append(nd)
    return out

def _scale_zone_rects_for_preview(zones, sx, sy):
    out = []
    for z in zones:
        if not isinstance(z, (list, tuple)) or len(z) != 4:
            continue
        x1, y1, x2, y2 = z
        out.append(
            [
                int(round(x1 * sx)),
                int(round(y1 * sy)),
                int(round(x2 * sx)),
                int(round(y2 * sy)),
            ]
        )
    return out


def _scale_intruders_for_preview(intruders, sx, sy):
    out = []
    for det, z, ratio in intruders:
        nd = dict(det)
        x1, y1, x2, y2 = det["bbox"]
        nd["bbox"] = [
            int(round(x1 * sx)),
            int(round(y1 * sy)),
            int(round(x2 * sx)),
            int(round(y2 * sy)),
        ]
        out.append((nd, z, ratio))
    return out


#
# Ö»Ê¹ÓÃÒ»¸ö yolov7 µ¥Ä£ÐÍ£ºÇëÔÚ´Ë´¦ÌîÈëÄãµÄ .om ÍêÕûÂ·¾¶£¨Ò²¿ÉÒÔÍ¨¹ý»·¾³±äÁ¿ YOLO_MODEL_PATH ¸²¸Ç£©¡£
#
YOLOV7_MODEL_PATH_PLACEHOLDER = "/home/HwHiAiUser/lab_detection_system/model/best_aipp_new.om"  


def _try_get_tk_photoimage_from_bgr(tk, bgr, out_w, out_h):
    #"""¸ßÐÔÄÜäÖÈ¾£ºÊ¹ÓÃË«»º³åºÍÓÅ»¯µÄ¸ñÊ½"""
    if bgr is None:
        return None

    # ¿ìËÙÂ·¾¶£ºÈç¹ûÒÑ¾­ÊÇÄ¿±ê³ß´ç£¬Ö±½Ó×ª»»
    if bgr.shape[1] == out_w and bgr.shape[0] == out_h:
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    else:
        # Ê¹ÓÃÏßÐÔ²åÖµÌæ´ú×î½üÁÚ£¬Æ½ºâÖÊÁ¿ºÍËÙ¶È
        frame = cv2.resize(bgr, (out_w, out_h), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # 0) Pillow£¨ÓÅÏÈÊ¹ÓÃ£¬ÐÔÄÜ×îºÃ£©
    if PIL_AVAILABLE:
        try:
            img = Image.fromarray(rgb)
            return ImageTk.PhotoImage(img)
        except Exception:
            pass

    # 1) ÓÅ»¯µÄPPM¸ñÊ½£¨Ö±½ÓÄÚ´æ¿½±´£©
    try:
        rgb_bytes = rgb.tobytes()
        header = f"P6 {out_w} {out_h} 255\n".encode("ascii")
        ppm_bytes = header + rgb_bytes
        b64 = base64.b64encode(ppm_bytes).decode("ascii")
        return tk.PhotoImage(data=b64, format="ppm")
    except Exception:
        pass

    # 2) PNG (base64) - ×îºó±¸Ñ¡£¬Ñ¹ËõÂÊ¸ßµ«±àÂëÂý
    try:
        ok, buf = cv2.imencode(".png", rgb, [cv2.IMWRITE_PNG_COMPRESSION, 1])  # Çá¶ÈÑ¹Ëõ
        if ok:
            b64 = base64.b64encode(buf.tobytes()).decode("ascii")
            return tk.PhotoImage(data=b64, format="png")
    except Exception:
        pass

    return None


class LEDWidget:
    def __init__(self, parent, x, y, r=12, on_color="#ff0000", off_color="#330000"):
        import tkinter as tk

        self.on_color = on_color
        self.off_color = off_color
        self._active = False
        self._phase = 0

        self.canvas = tk.Canvas(parent, width=2 * r + 2, height=2 * r + 2, highlightthickness=0, bg=parent["bg"])
        self.oval = self.canvas.create_oval(1, 1, 2 * r + 1, 2 * r + 1, fill=self.off_color, outline="")
        self.canvas.place(x=x, y=y)

    def set_active_and_phase(self, active, phase_on):
        self._active = active
        fill = self.on_color if (active and phase_on) else self.off_color
        self.canvas.itemconfig(self.oval, fill=fill)


class VideoWorker:
    def __init__(
        self,
        model_path,
        source_type,
        danger_zone: DangerZoneModule,
        board_counter: BoardCounterModule,
        fire_placeholder: FirePlaceholderModule,
        selected_mode_ref,
        frame_queue: "queue.Queue",
        state_queue: "queue.Queue",
        stop_event: threading.Event,
        camera_id=None,
        video_path=None,
        image_path=None,
        board_threshold=30,
        cam_width=640,
        cam_height=480,
        cam_fps=30,
        preview_render_wh=None,
    ):
        self.model_path = model_path
        self.yolo = None
        self.source_type = source_type
        self.camera_id = camera_id
        self.video_path = video_path
        self.image_path = image_path
        self.danger_zone = danger_zone
        self.board_counter = board_counter
        self.fire_placeholder = fire_placeholder

        self.selected_mode_ref = selected_mode_ref
        self.frame_queue = frame_queue
        self.state_queue = state_queue
        self.stop_event = stop_event

        self.board_threshold = board_threshold
        self.cam_width = cam_width
        self.cam_height = cam_height
        self.cam_fps = cam_fps
        # (¿í, ¸ß)£ºÏÈËõ·Åµ½Óë UI Ò»ÖÂÔÙ»­¿ò£¬¼õÇá¸ß·Ö±æÂÊÏÂµÄ copy + OpenCV »æÖÆ¿ªÏú£»None ±íÊ¾Õû·ùÔ­Í¼»æÖÆ
        self.preview_render_wh = preview_render_wh

        # ×´Ì¬ÉÏÉýÑØ
        self._prev_danger = False
        self._prev_board_low = False
        self._prev_fire = False

        self._last_trigger = ""
        self._last_capture_hint_ts = 0.0
        self._latest_frame = None
        self._latest_frame_seq = 0
        self._last_inferred_seq = -1
        self._latest_frame_lock = threading.Lock()
        self._last_infer_done_ts = 0.0
        self._infer_thread_started = False
        self._infer_stage = "not_started"
        # ÌøÖ¡»úÖÆ£ºµ±ÍÆÀí¸ú²»ÉÏÊ±£¬Ã¿¸ô¼¸Ö¡²ÅÍÆÀíÒ»´Î
        self._skip_frame_count = 0
        self._max_skip_frames = int(os.environ.get("VIDEO_SKIP_FRAMES", "3"))
        # ¼¤½øÌøÖ¡Ä£Ê½£ºµ±ÆôÓÃÊ±£¬ÔÚÍÆÀíÂýÊ±»áÌø¹ý¸ü¶àÖ¡
        self._aggressive_skip = os.environ.get("VIDEO_AGGRESSIVE_SKIP", "true").lower() == "true"
        # ÐÔÄÜ¼à¿Ø
        self._frame_count = 0
        self._last_fps_time = time.time()
        self._display_fps = 0.0
    def _ensure_yolo_loaded(self):
        if self.yolo is not None:
            return True
        try:
            self._infer_stage = "loading_model"
            self.yolo = YOLOv7AscendInference(self.model_path)
            self.yolo.load_model()
            self._infer_stage = "model_loaded"
            return True
        except Exception as e:
            self._infer_stage = "model_load_failed"
            self._put_latest(self.state_queue, {"error": f"Model init/load failed: {e}"})
            return False

    def _set_latest_frame(self, frame):
        with self._latest_frame_lock:
            self._latest_frame = frame
            if frame is not None:
                self._latest_frame_seq += 1

    def _get_latest_frame_and_seq(self):
        with self._latest_frame_lock:
            return self._latest_frame, self._latest_frame_seq

    def _run_infer_with_timeout(self, frame, timeout_s=2.5):
        # ÓÅ»¯µôÔ­ÓÐµÄ threading.Thread(target=_target) Ø¬ÃÎ°ãµÄÉè¼Æ£¡
        # Ã¿Ö¡¶¯Ì¬´´½¨¡¢Ïú»ÙÒ»¸öÏµÍ³¼¶Ïß³Ì£¬»á¸ø ARM åîÈõµÄ CPU ´øÀ´ÔÖÄÑÐÔµÄÉÏÏÂÎÄÇÐ»»¿ªÏú¡£
        # ´ËÇ°¼ÓÈë³¬Ê±»úÖÆ¿ÉÄÜÊÇÎªÁË·ÀÖ¹Í¼Ïñ³ß´ç²»Æ¥Åäµ¼ÖÂµÄµ×²ãµ×²ã acl ¿¨ËÀ£¬
        # µ«ÎÒÃÇÒÑ¾­ÔÚµ×²ã¼ÓÁË×Ö½ÚÊýÓ²Ð£Ñé£¬Òò´Ë²»»áÔÙÄ¬Ä¬¿¨ËÀÁË£¬´Ë´¦¿ÉÒÔÖ±½ÓÍ¬²½µ÷ÓÃ£¡
        try:
            detections = self.yolo.process_frame(frame)
            return True, detections, None
        except Exception as e:
            return False, None, str(e)


    def _put_latest(self, q, item):
        try:
            if q.full():
                try:
                    q.get_nowait()
                except Exception:
                    pass
            q.put_nowait(item)
        except Exception:
            pass

    def _prepare_mode_metrics(self, selected_mode, detections, frame_shape):
        person_dets = []
        board_dets = []
        fire_dets = []
        intrusion_active = False
        intruders = []
        board_count = 0
        board_low = False
        fire_count = 0
        fire_active = False

        if selected_mode == "danger_zone":
            person_dets = [d for d in (detections or []) if d.get("class_id") == PERSON_CLASS_ID]
            intrusion_active, intruders = self.danger_zone.check_intrusion(person_dets, frame_shape=frame_shape)
        elif selected_mode == "board_count":
            board_dets = [d for d in (detections or []) if d.get("class_id") == BOARD_CLASS_ID]
            board_count = len(board_dets)
            board_low = board_count < self.board_threshold
        elif selected_mode == "fire":
            fire_dets = [d for d in (detections or []) if d.get("class_id") == FIRE_CLASS_ID]
            fire_count = len(fire_dets)
            fire_active = fire_count > 0

        return {
            "person_dets": person_dets,
            "board_dets": board_dets,
            "fire_dets": fire_dets,
            "intrusion_active": intrusion_active,
            "intruders": intruders,
            "board_count": board_count,
            "board_low": board_low,
            "fire_count": fire_count,
            "fire_active": fire_active,
        }

    def _get_video_capture(self):
        if self.source_type == "camera":
            src = self.camera_id
        else:
            # video
            src = self.video_path
        # Linux °å¿¨ÉÏÓÅÏÈ×ß V4L2£¬¼æÈÝÐÔ¸üºÃ£»ÈôÊ§°ÜÔÙÍË»ØÄ¬ÈÏºó¶Ë
        cap = None
        if self.source_type == "camera":
            try:
                cap = cv2.VideoCapture(src, cv2.CAP_V4L2)
            except Exception:
                cap = None
        if cap is None:
            cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            return None

        # ¼õÉÙÑÓ³Ù£º¾¡Á¿¸øÐ¡ buffer
        try:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cam_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cam_height)
            cap.set(cv2.CAP_PROP_FPS, self.cam_fps)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        return cap

    def run(self):
        if self.source_type == "image":
            return self._run_image_once()

        cap = self._get_video_capture()
        if cap is None:
            self._put_latest(self.state_queue, {"error": "Cannot open camera/video"})
            return

        # ÍÆÀíÏß³Ì£ºÓë²É¼¯Ïß³Ì½âñî£¬±ÜÃâ yolo.process_frame ¿¨×¡Ê± UI Í£ÔÚÄ³Ò»Ö¡
        if not self._infer_thread_started:
            self._infer_thread_started = True
            t_infer = threading.Thread(target=self._infer_loop, daemon=True)
            t_infer.start()

        # danger_zone Óë board_counter/fire »æÖÆÄ£¿é£¨ÊÓÆµ/camera£©
        while not self.stop_event.is_set():
            # ±ßÔµÉè±¸Í¨³£Ó¦Ë³Æä×ÔÈ»µØ¶ÁÈ¡Ö¡
            pass

            ret, frame = cap.read()
            if not ret:
                self._put_latest(self.state_queue, {"error": "Cannot read frame from camera/video"})
                break
            self._set_latest_frame(frame)
            
            # Õë¶ÔÅÜ±¾µØÊÓÆµÎÄ¼þ£º±ØÐë×öÎïÀíÏÞËÙ£¬·ñÔòÊÓÆµ»á°´°å¿¨¼«ÏÞËÙ¶È£¨±ÈÈçÒ»ÃëÉÏ°ÙÖ¡£©¿ñ±¼
            if self.source_type == "video" and self.cam_fps > 0:
                time.sleep(0.9 / self.cam_fps)
                
            # ½öÌáÊ¾£¬²»Òª¸ßÆµË¢ state_queue£¨·ñÔò»á¸²¸ÇÕæÊµÍÆÀí×´Ì¬£©
            now_ts = time.time()
            if now_ts - self._last_capture_hint_ts >= 1.0:
                self._last_capture_hint_ts = now_ts
                since_infer = now_ts - self._last_infer_done_ts if self._last_infer_done_ts > 0 else None
                if since_infer is None:
                    hint = f"Capturing... (waiting first inference, stage={self._infer_stage})"
                else:
                    hint = f"Capturing... (last inference {since_infer:.1f}s ago, stage={self._infer_stage})"
                self._put_latest(
                    self.state_queue,
                    {
                        "mode": self.selected_mode_ref[0],
                        "last_trigger": hint,
                        "__partial__": True,
                    },
                )

        cap.release()
        try:
            if self.yolo is not None:
                self.yolo.release_resource()
        except Exception:
            pass

    def _infer_loop(self):
        # µ¥¶ÀÏß³Ì×öÍÆÀíÓëäÖÈ¾£¬±ÜÃâ×èÈû²É¼¯
        self._infer_stage = "infer_thread_started"
        self._put_latest(
            self.state_queue,
            {
                "mode": self.selected_mode_ref[0],
                "last_trigger": "Infer thread started",
                "__partial__": True,
            },
        )

        while not self.stop_event.is_set():
            if self.yolo is None:
                if not self._ensure_yolo_loaded():
                    time.sleep(1.0)
                    continue
                self._put_latest(
                    self.state_queue,
                    {
                        "mode": self.selected_mode_ref[0],
                        "last_trigger": "Model loaded. Waiting frames...",
                        "__partial__": True,
                    },
                )

            frame, seq = self._get_latest_frame_and_seq()
            if frame is None:
                self._infer_stage = "waiting_frame"
                time.sleep(0.02)
                continue

            # ÍÆÀí¿ìÓÚ²É¼¯Ê±±ÜÃâ¶ÔÍ¬Ò»Ö¡ÖØ¸´ acl.mdl.execute£¬°Ñ NPU Áô¸øÏÂÒ»Ö¡
            if seq == self._last_inferred_seq:
                time.sleep(0.005)
                continue

            # ÌøÖ¡»úÖÆ£ºµ±ÍÆÀí¸ú²»ÉÏÊ±£¬Ìø¹ýÒ»Ð©Ö¡ÒÔÌá¸ßÏÔÊ¾Ö¡ÂÊ
            self._skip_frame_count += 1
            
            # ¼¤½øÌøÖ¡Ä£Ê½£ºÃ¿NÖ¡Ö»ÍÆÀí1´Î£¬È·±£ÏÔÊ¾Ö¡ÂÊÎÈ¶¨
            # Ä¿±ê£ºÏÔÊ¾Ö¡ÂÊ = ÊÓÆµÖ¡ÂÊ / (ÌøÖ¡Êý + 1)
            # ÀýÈç£º30FPSÊÓÆµ£¬ÌøÖ¡=2£¬ÔòÏÔÊ¾Ö¡ÂÊÔ¼Îª10FPS
            if self._skip_frame_count < self._max_skip_frames:
                # ¸´ÖÆÉÏÒ»Ö¡µÄÍÆÀí½á¹ûÓÃÓÚÏÔÊ¾£¬µ«²»½øÐÐÐÂµÄÍÆÀí
                self._infer_stage = "skipping_frame"
                time.sleep(0.001)  # ¶ÌÔÝÐÝÃß±ÜÃâCPUÕ¼ÓÃ¹ý¸ß
                continue
            self._skip_frame_count = 0  # ÖØÖÃÌøÖ¡¼ÆÊýÆ÷

            start = time.time()
            self._infer_stage = "executing_inference"
            ok, detections, err = self._run_infer_with_timeout(frame, timeout_s=2.5)
            if not ok:
                self._infer_stage = "inference_error"
                self._put_latest(self.state_queue, {"error": f"Inference error: {err}"})
                # ³¬Ê±Í¨³£ÒâÎ¶×Åµ×²ãÖ´ÐÐ¿¨×¡£¬Í£Ö¹¸ÃÍÆÀíÏß³Ì£¬±ÜÃâ´´½¨¹ý¶à¹ÒÆðÏß³Ì
                if err and "timeout" in err:
                    break
                time.sleep(0.05)
                continue

            selected_mode = self.selected_mode_ref[0]
            metrics = self._prepare_mode_metrics(selected_mode, detections, frame.shape)
            person_dets = metrics["person_dets"]
            board_dets = metrics["board_dets"]
            fire_dets = metrics["fire_dets"]
            intrusion_active = metrics["intrusion_active"]
            intruders = metrics["intruders"]
            board_count = metrics["board_count"]
            board_low = metrics["board_low"]
            fire_count = metrics["fire_count"]
            fire_active = metrics["fire_active"]
            intrusion_count = len(intruders)

            now_str = time.strftime("%H:%M:%S")
            if selected_mode == "danger_zone" and intrusion_active and not self._prev_danger:
                self._last_trigger = f"[{now_str}] Danger Zone: person entered ({intrusion_count})"
            if selected_mode == "board_count" and board_low and not self._prev_board_low:
                self._last_trigger = f"[{now_str}] Board Counter: low count {board_count} (<{self.board_threshold})"
            if selected_mode == "fire" and fire_active and not self._prev_fire:
                self._last_trigger = f"[{now_str}] Fire Alarm: fire={fire_count}"
            self._prev_danger = intrusion_active if selected_mode == "danger_zone" else self._prev_danger
            self._prev_board_low = board_low if selected_mode == "board_count" else self._prev_board_low
            self._prev_fire = fire_active if selected_mode == "fire" else self._prev_fire

            show_frame = self._render_for_mode(
                base_frame=frame,
                selected_mode_ref=self.selected_mode_ref,
                person_dets=person_dets,
                board_dets=board_dets,
                fire_dets=fire_dets,
                intrusion_active=intrusion_active,
                intruders=intruders,
            )

            elapsed = time.time() - start
            fps = 1.0 / elapsed if elapsed > 0 else 0.0
            self._last_infer_done_ts = time.time()
            self._infer_stage = "inference_ok"

            ui_state = {
                "fps": fps,
                "display_fps": self._display_fps,
                "mode": selected_mode,
                "last_trigger": self._last_trigger,
            }
            if selected_mode == "danger_zone":
                ui_state.update({
                    "intrusion_count": intrusion_count,
                    "intrusion_active": intrusion_active,
                })
            elif selected_mode == "board_count":
                ui_state.update({
                    "board_count": board_count,
                    "board_low": board_low,
                })
            elif selected_mode == "fire":
                ui_state.update({
                    "fire_count": fire_count,
                    "fire_active": fire_active,
                })
            self._last_reported_state = ui_state

            self._put_latest(self.state_queue, ui_state)
            self._put_latest(self.frame_queue, {"frame": show_frame})
            self._last_inferred_seq = seq

            # ¼ÆËãÏÔÊ¾Ö¡ÂÊ
            self._frame_count += 1
            current_time = time.time()
            if current_time - self._last_fps_time >= 1.0:
                self._display_fps = self._frame_count / (current_time - self._last_fps_time)
                self._frame_count = 0
                self._last_fps_time = current_time

    def _render_for_mode(
        self,
        base_frame,
        selected_mode_ref,
        person_dets,
        board_dets,
        fire_dets,
        intrusion_active=False,
        intruders=None,
    ):
        selected_mode = selected_mode_ref[0]
        intruders = intruders or []
        pwph = self.preview_render_wh

        if pwph:
            pw, ph = pwph
            oh, ow = base_frame.shape[:2]
            sx = pw / float(ow)
            sy = ph / float(oh)
            show_frame = cv2.resize(base_frame, (pw, ph), interpolation=cv2.INTER_NEAREST)
            zones_scaled = None
            intruders_scaled = None
            if selected_mode == "danger_zone":
                person_draw = _scale_detections_for_preview(person_dets, sx, sy)
                zones_orig = self.danger_zone._zones_for_frame(base_frame.shape)
                zones_scaled = _scale_zone_rects_for_preview(zones_orig, sx, sy)
                intruders_scaled = _scale_intruders_for_preview(intruders, sx, sy)
            elif selected_mode == "board_count":
                board_draw = _scale_detections_for_preview(board_dets, sx, sy)
            else:
                fire_draw = _scale_detections_for_preview(fire_dets, sx, sy)
        else:
            show_frame = base_frame.copy()
            zones_scaled = None
            intruders_scaled = None
            if selected_mode == "danger_zone":
                person_draw = person_dets
            elif selected_mode == "board_count":
                board_draw = board_dets
            else:
                fire_draw = fire_dets

        if selected_mode == "danger_zone":
            if pwph:
                show_frame, _ = self.danger_zone.process(
                    show_frame,
                    person_draw,
                    precomputed_intrusion=(intrusion_active, intruders_scaled),
                    zones_pixel=zones_scaled,
                )
            else:
                show_frame, _ = self.danger_zone.process(
                    show_frame,
                    person_dets,
                    precomputed_intrusion=(intrusion_active, intruders),
                )
        elif selected_mode == "board_count":
            show_frame, _, _ = self.board_counter.process(show_frame, board_draw)
        else:
            show_frame, _ = self.fire_placeholder.process(show_frame, fire_draw)

        return show_frame

    def _run_image_once(self):
        if not self._ensure_yolo_loaded():
            return
        if not self.image_path:
            self._put_latest(self.state_queue, {"error": "Image path missing"})
            return
        frame = cv2.imread(self.image_path)
        if frame is None:
            self._put_latest(self.state_queue, {"error": f"Cannot read image: {self.image_path}"})
            return

        # ÏÈ°ÑÔ­Ê¼Í¼Æ¬ÏÔÊ¾³öÀ´£¬±ÜÃâÍÆÀí¿¨×¡µ¼ÖÂÒ»Ö±ºÚÆÁ
        self._put_latest(self.frame_queue, {"frame": frame})
        self._put_latest(
            self.state_queue,
            {
                "mode": self.selected_mode_ref[0],
                "last_trigger": "Loaded image. (running inference)",
                "__partial__": True,
            },
        )

        # ÍÆÀíÒ»´Î£¨Ö»ÍÆÀíÒ»´Î£©
        start = time.time()
        try:
            detections = self.yolo.process_frame(frame)
        except Exception as e:
            self._put_latest(self.state_queue, {"error": f"Inference error: {e}"})
            return
        elapsed = time.time() - start
        fps = 1.0 / elapsed if elapsed > 0 else 0.0

        selected_mode = self.selected_mode_ref[0]
        metrics = self._prepare_mode_metrics(selected_mode, detections, frame.shape)
        person_dets = metrics["person_dets"]
        board_dets = metrics["board_dets"]
        fire_dets = metrics["fire_dets"]
        board_count = metrics["board_count"]
        board_low = metrics["board_low"]
        intrusion_active = metrics["intrusion_active"]
        intruders = metrics["intruders"]
        intrusion_count = len(intruders)
        fire_count = metrics["fire_count"]
        fire_active = metrics["fire_active"]

        now_str = time.strftime("%H:%M:%S")
        if selected_mode == "danger_zone" and intrusion_active:
            self._last_trigger = f"[{now_str}] Danger Zone: person entered ({intrusion_count})"
        if selected_mode == "board_count" and board_low:
            self._last_trigger = f"[{now_str}] Board Counter: low count {board_count} (<{self.board_threshold})"
        if selected_mode == "fire" and fire_active:
            self._last_trigger = f"[{now_str}] Fire Alarm: fire={fire_count}"

        last_mode = None
        while not self.stop_event.is_set():
            selected_mode = self.selected_mode_ref[0]
            if selected_mode != last_mode:
                show_frame = self._render_for_mode(
                    base_frame=frame,
                    selected_mode_ref=self.selected_mode_ref,
                    person_dets=person_dets,
                    board_dets=board_dets,
                    fire_dets=fire_dets,
                    intrusion_active=intrusion_active,
                    intruders=intruders,
                )
                ui_state = {
                    "fps": fps,
                    "mode": selected_mode,
                    "last_trigger": self._last_trigger,
                }
                if selected_mode == "danger_zone":
                    ui_state.update({
                        "intrusion_count": intrusion_count,
                        "intrusion_active": intrusion_active,
                    })
                elif selected_mode == "board_count":
                    ui_state.update({
                        "board_count": board_count,
                        "board_low": board_low,
                    })
                elif selected_mode == "fire":
                    ui_state.update({
                        "fire_count": fire_count,
                        "fire_active": fire_active,
                    })
                self._put_latest(self.state_queue, ui_state)
                self._put_latest(self.frame_queue, {"frame": show_frame})
                last_mode = selected_mode
            time.sleep(0.15)

        try:
            if self.yolo is not None:
                self.yolo.release_resource()
        except Exception:
            pass


def run_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox

    model_path = os.environ.get("YOLO_MODEL_PATH", YOLOV7_MODEL_PATH_PLACEHOLDER).strip()
    if not model_path:
        messagebox.showerror(
            "Model Path Missing",
            "Please set YOLO_MODEL_PATH env var or fill YOLOV7_MODEL_PATH_PLACEHOLDER with your yolov7 .om path.",
        )
        return
    if not os.path.isfile(model_path):
        messagebox.showerror(
            "Model Path Invalid",
            f"Model file not found: {model_path}\nPlease check the path and copy the .om to the board.",
        )
        return



    video_path = os.environ.get("TEST_VIDEO_PATH", "/home/HwHiAiUser/yolov5_inference/data/test_video/1.mp4")

    # ²»ÒªÔÚÆô¶¯Ê±É¨ÃèÉãÏñÍ·£º»áÔÚÎÞÉãÏñÍ·»·¾³Ë¢ÆÁ£¨cap_v4l.cpp warning£©
    default_camera_id = None

    # ¼ÓÔØÏµÍ³ÅäÖÃÎÄ¼þ
    system_config_path = os.path.join(ROOT, "config", "system_config.json")
    try:
        with open(system_config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"Warning: Could not load system config: {e}, using defaults")
        config = {
            "alert_threshold": 30,
            "overlap_threshold": 0.2
        }

    danger_zone_config = os.path.join(ROOT, "config", "danger_zones.json")
    danger_zone = DangerZoneModule(
        config_path=danger_zone_config,
        overlap_threshold=config["overlap_threshold"]
    )
    board_counter = BoardCounterModule(
        class_id=BOARD_CLASS_ID,
        alert_threshold=config["alert_threshold"]
    )
    fire_placeholder = FirePlaceholderModule(log_path="fire_alerts.log")

    selected_mode_ref = ["board_count"]
    input_confirmed = [False]
    start_after_mode_click = [False]
    source_config_ref = {
        "type": None,  # "image" | "video" | "camera"
        "camera_id": default_camera_id,
        "video_path": video_path,
        "image_path": None,
    }
    stop_event = threading.Event()
    frame_queue = queue.Queue(maxsize=1)
    state_queue = queue.Queue(maxsize=1)
    # ÓëÓÒ²àÊÓÆµÏÔÊ¾ÇøÒ»ÖÂ£»ÍÆÀíÏß³ÌÄÚÏÈËõ·Åµ½´Ë³ß´çÔÙ»­¿ò£¬½µµÍ CPU ¸ºµ£
    # ¿ÉÍ¨¹ý»·¾³±äÁ¿ VIDEO_PREVIEW_WIDTH ºÍ VIDEO_PREVIEW_HEIGHT µ÷Õû
    VIDEO_DISP_W = max(int(os.environ.get("VIDEO_PREVIEW_WIDTH", "720")), 720)
    VIDEO_DISP_H = max(int(os.environ.get("VIDEO_PREVIEW_HEIGHT", "480")), 480)
    
    # ¸ßÐÔÄÜÄ£Ê½£ºÆôÓÃ¸ü¼¤½øµÄÓÅ»¯£¬µ«ÈÔ±£³Ö×îµÍÔ¤ÀÀ·Ö±æÂÊ
    HIGH_PERF_MODE = os.environ.get("VIDEO_HIGH_PERF", "false").lower() == "true"
    if HIGH_PERF_MODE:
        VIDEO_DISP_W = max(VIDEO_DISP_W, 720)
        VIDEO_DISP_H = max(VIDEO_DISP_H, 480)

    worker = None
    worker_thread = None

    root = tk.Tk()
    root.geometry("1280x780")
    root.minsize(1200, 740)
    root.configure(bg="#e8ebf0")

    tk.Label(
        root,
        text="Embedded Laboratory Video Monitoring System",
        font=("Arial", 22, "bold"),
        bg="#e8ebf0",
    ).place(x=0, y=15, relwidth=1.0)

    panel_bg = "#f5f7fb"
    left_panel = tk.Frame(root, bg=panel_bg, bd=1, relief="solid")
    left_panel.place(x=20, y=70, width=400, height=650)
    tk.Label(left_panel, text="Control Panel", font=("Arial", 14, "bold"), bg=panel_bg).place(x=18, y=10)

    input_top_y = 55
    left_x = 24
    top_y = 320
    btn_w = 18
    btn_h = 2

    status_font = ("Arial", 12)

    def _drain_queue(q):
        try:
            while True:
                q.get_nowait()
        except Exception:
            pass

    def _stop_worker():
        nonlocal worker, worker_thread
        stop_event.set()
        try:
            if worker_thread is not None and worker_thread.is_alive():
                worker_thread.join(timeout=0.6)
        except Exception:
            pass
        worker = None
        worker_thread = None
        _drain_queue(frame_queue)
        _drain_queue(state_queue)

    def _start_worker():
        nonlocal worker, worker_thread
        if worker_thread is not None and worker_thread.is_alive():
            _stop_worker()
        src_type = source_config_ref.get("type")
        cam_id = source_config_ref.get("camera_id")
        v_path = source_config_ref.get("video_path")
        img_path = source_config_ref.get("image_path")
        stop_event.clear()
        worker = VideoWorker(
            model_path=model_path,
            source_type=src_type,
            camera_id=cam_id,
            video_path=v_path,
            image_path=img_path,
            danger_zone=danger_zone,
            board_counter=board_counter,
            fire_placeholder=fire_placeholder,
            selected_mode_ref=selected_mode_ref,
            frame_queue=frame_queue,
            state_queue=state_queue,
            stop_event=stop_event,
            board_threshold=config["alert_threshold"],
            preview_render_wh=(VIDEO_DISP_W, VIDEO_DISP_H),
        )

        worker_thread = threading.Thread(target=worker.run, daemon=True)
        worker_thread.start()

    def _set_mode(mode):
        selected_mode_ref[0] = mode
        if not input_confirmed[0]:
            info["last"].set("Please confirm input source first.")
            return
        # Ã¿´Î Confirm ºó£¬±ØÐëÓÉ¡°Ä£¿éµã»÷¡±´¥·¢±¾´Î¼ì²âÆô¶¯
        if start_after_mode_click[0]:
            _start_worker()
            start_after_mode_click[0] = False
            info["last"].set(f"Detection started. Mode={mode}")
            return

        # ¼æÈÝ£ºÈôÒì³£ÍË³öµ¼ÖÂÏß³Ì²»ÔÚ£¬Ò²ÔÊÐíÍ¨¹ýÄ£¿éµã»÷À­Æð
        if worker_thread is None or (not worker_thread.is_alive()):
            _start_worker()
            info["last"].set(f"Detection resumed. Mode={mode}")

    # ÊäÈëÔ´Ãæ°å
    left_x = 20
    input_top_y = 55

    tk.Label(left_panel, text="Input Source", font=("Arial", 14, "bold"), bg=panel_bg).place(x=left_x, y=input_top_y)
    source_type_var = tk.StringVar(value=source_config_ref["type"] or "camera")

    tk.Radiobutton(left_panel, text="Camera", variable=source_type_var, value="camera", bg=panel_bg).place(x=left_x, y=input_top_y + 35)
    tk.Radiobutton(left_panel, text="Video", variable=source_type_var, value="video", bg=panel_bg).place(x=left_x + 90, y=input_top_y + 35)
    tk.Radiobutton(left_panel, text="Image", variable=source_type_var, value="image", bg=panel_bg).place(x=left_x + 180, y=input_top_y + 35)

    img_path_var = tk.StringVar(value="")
    vid_path_var = tk.StringVar(value=video_path or "")

    def _choose_image():
        p = filedialog.askopenfilename(title="Choose Image", filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp")])
        if p:
            img_path_var.set(p)

    def _choose_video():
        p = filedialog.askopenfilename(title="Choose Video", filetypes=[("Videos", "*.mp4 *.avi *.mkv")])
        if p:
            vid_path_var.set(p)

    def _confirm_input():
        if worker_thread is not None and worker_thread.is_alive():
            _stop_worker()

        src_type = source_type_var.get()
        if src_type == "camera":
            source_config_ref["type"] = "camera"
            try:
                source_config_ref["camera_id"] = int(cam_index_var.get())
            except Exception:
                source_config_ref["camera_id"] = default_camera_id if default_camera_id is not None else 0
            source_config_ref["video_path"] = ""
            source_config_ref["image_path"] = None
        elif src_type == "video":
            path = vid_path_var.get().strip()
            if not path:
                messagebox.showwarning("Video Path Required", "Please select a video file before confirming.")
                return
            source_config_ref["type"] = "video"
            source_config_ref["video_path"] = path
            source_config_ref["image_path"] = None
            source_config_ref["camera_id"] = default_camera_id
        else:
            path = img_path_var.get().strip()
            if not path:
                messagebox.showwarning("Image Path Required", "Please select an image file before confirming.")
                return
            source_config_ref["type"] = "image"
            source_config_ref["image_path"] = path
            source_config_ref["video_path"] = ""
            source_config_ref["camera_id"] = default_camera_id

        input_confirmed[0] = True
        btn_danger.config(state=tk.NORMAL)
        btn_board.config(state=tk.NORMAL)
        btn_fire.config(state=tk.NORMAL)
        start_after_mode_click[0] = True
        info["last"].set(f"Input confirmed: {src_type}. Select a mode to start.")

    tk.Label(left_panel, text="Image Path:", font=("Arial", 10), bg=panel_bg).place(x=left_x, y=input_top_y + 70)
    tk.Entry(left_panel, width=25, textvariable=img_path_var).place(x=left_x + 95, y=input_top_y + 68)
    tk.Button(left_panel, text="Browse", width=8, command=_choose_image).place(x=left_x + 290, y=input_top_y + 66)

    tk.Label(left_panel, text="Video Path:", font=("Arial", 10), bg=panel_bg).place(x=left_x, y=input_top_y + 105)
    tk.Entry(left_panel, width=25, textvariable=vid_path_var).place(x=left_x + 95, y=input_top_y + 103)
    tk.Button(left_panel, text="Browse", width=8, command=_choose_video).place(x=left_x + 290, y=input_top_y + 101)

    tk.Label(left_panel, text="Camera Index:", font=("Arial", 10), bg=panel_bg).place(x=left_x, y=input_top_y + 140)
    cam_index_var = tk.StringVar(value=str(default_camera_id if default_camera_id is not None else 0))
    tk.Entry(left_panel, width=5, textvariable=cam_index_var).place(x=left_x + 125, y=input_top_y + 138)

    confirm_btn = tk.Button(left_panel, text="Confirm", width=20, font=("Arial", 12), command=_confirm_input)
    confirm_btn.place(x=left_x + 80, y=input_top_y + 170)

    # --- ×ó±ß£ºÈý´ó¹¦ÄÜÇÐ»»°´Å¥ ---
    top_y = 290
    btn_w = 24
    btn_font = ("Arial", 13)
    btn_gap = 120

    btn_danger = tk.Button(left_panel, text="Danger Zone Alarm", width=btn_w, height=3, font=btn_font, command=lambda: _set_mode("danger_zone"))
    btn_board = tk.Button(left_panel, text="Board Counter", width=btn_w, height=3, font=btn_font, command=lambda: _set_mode("board_count"))
    btn_fire = tk.Button(left_panel, text="Fire Alarm", width=btn_w, height=3, font=btn_font, command=lambda: _set_mode("fire"))
    btn_danger.config(state=tk.DISABLED)
    btn_board.config(state=tk.DISABLED)
    btn_fire.config(state=tk.DISABLED)

    btn_danger.place(x=left_x, y=top_y)
    btn_board.place(x=left_x, y=top_y + btn_gap)
    btn_fire.place(x=left_x, y=top_y + btn_gap * 2)

    # LEDs£º·ÅÖÃÔÚ¸÷°´Å¥ÓÒ²à£¬Óë°´Å¥´¹Ö±¾ÓÖÐ¶ÔÆë
    led_offset = 28
    led_danger = LEDWidget(left_panel, x=left_x + 280, y=top_y + led_offset)
    led_board = LEDWidget(left_panel, x=left_x + 280, y=top_y + btn_gap + led_offset)
    led_fire = LEDWidget(left_panel, x=left_x + 280, y=top_y + btn_gap * 2 + led_offset)

    # --- ÖÐÉÏ£º×´Ì¬Ãæ°å (ÖÃÓÚ½çÃæÓÒÉÏ½Ç) ---
    panel_x = 420
    panel_y = 70

    status_frame = tk.Frame(root, bg=panel_bg, bd=1, relief="solid")
    status_frame.place(x=panel_x, y=panel_y, width=780, height=170)
    tk.Label(status_frame, text="System Status", font=("Arial", 14, "bold"), bg=panel_bg).place(x=16, y=12)
    status_font = ("Arial", 12)
    
    info = {
        "fps": tk.StringVar(value="FPS: -"),
        "display_fps": tk.StringVar(value="Display FPS: -"),
        "mode": tk.StringVar(value="Mode: -"),
        "board": tk.StringVar(value="Board: -"),
        "danger": tk.StringVar(value="Danger: -"),
        "fire": tk.StringVar(value="Fire: -"),
        "cursor": tk.StringVar(value=f"Cursor: -"),
        "last": tk.StringVar(value="-"),
    }

    # Á½ÐÐËÄÁÐÕûÆëÅÅÁÐ
    tk.Label(status_frame, textvariable=info["mode"], font=status_font, anchor="w", justify="left", bg=panel_bg).place(x=16, y=42)
    tk.Label(status_frame, textvariable=info["board"], font=status_font, anchor="w", justify="left", bg=panel_bg).place(x=260, y=42)
    tk.Label(status_frame, textvariable=info["fire"], font=status_font, anchor="w", justify="left", bg=panel_bg).place(x=520, y=42)
    
    tk.Label(status_frame, textvariable=info["fps"], font=status_font, anchor="w", justify="left", bg=panel_bg).place(x=16, y=72)
    tk.Label(status_frame, textvariable=info["display_fps"], font=status_font, anchor="w", justify="left", bg=panel_bg).place(x=260, y=72)
    tk.Label(status_frame, textvariable=info["danger"], font=status_font, anchor="w", justify="left", bg=panel_bg).place(x=520, y=72)
    
    tk.Label(status_frame, text="Last Trigger:", font=("Arial", 12, "bold"), anchor="w", justify="left", bg=panel_bg).place(x=16, y=100)
    tk.Label(
        status_frame, textvariable=info["last"], font=("Arial", 11),
        anchor="w", justify="left", fg="blue", bg=panel_bg, width=82
    ).place(x=110, y=102)

    # --- ÓÒÏÂ£ººËÐÄÊÓÆµÏÔÊ¾Çø (ÃÀ¹Û²¼¾Ö£¬×ó²à¿ØÖÆÓëÓÒ²à×´Ì¬·Ö¿ª) ---
    video_w = VIDEO_DISP_W
    video_h = VIDEO_DISP_H
    video_x = panel_x + max(0, (780 - video_w) // 2)
    video_y = 260

    video_label = tk.Label(root, bg="black")
    video_label.place(x=video_x, y=video_y, width=video_w, height=video_h)
    video_label.image = None

    def _on_video_mouse_move(event):
        x = max(0, min(video_w - 1, int(event.x)))
        y = max(0, min(video_h - 1, int(event.y)))
        info["cursor"].set(f"Cursor: ({x}, {y})")

    def _on_video_mouse_leave(_event):
        info["cursor"].set("Cursor: -")

    video_label.bind("<Motion>", _on_video_mouse_move)  
    video_label.bind("<Leave>", _on_video_mouse_leave)

    last_state = {"intrusion_active": False, "board_low": False, "fire_active": False, "last_error": ""}

    def update_leds():
        # µÆÖ»ÔÚ¡°¶ÔÓ¦µ±Ç°Ä£Ê½¡±ÏÂ²ÅÔÊÐíµãÁÁ£¬ÇÒÎª³£ÁÁ£¨²»ÉÁË¸£©
        mode = last_state.get("mode", "")
        danger_active = bool(last_state.get("intrusion_active", False))
        board_active = bool(last_state.get("board_low", False))
        fire_active = bool(last_state.get("fire_active", False))

        led_danger_active = (mode == "danger_zone") and danger_active
        led_board_active = (mode == "board_count") and board_active
        led_fire_active = (mode == "fire") and fire_active

        # ÁÁ 0.1s Ãð 0.1s£¬ÖÜÆÚ 0.2s
        phase_on = (time.time() % 0.2) < 0.1
        led_danger.set_active_and_phase(led_danger_active, phase_on)
        led_board.set_active_and_phase(led_board_active, phase_on)
        led_fire.set_active_and_phase(led_fire_active, phase_on)

    def poll_ui():
        nonlocal last_state
        # state
        try:
            while True:
                st = state_queue.get_nowait()
                if isinstance(st, dict) and "error" in st:
                    # ¼ÇÂ¼´íÎó£¬²»ÒªÁ¢¿Ì±» last_trigger ¸²¸Çµô
                    last_state["last_error"] = str(st.get("error", "")).strip()
                elif isinstance(st, dict):
                    # Õý³£×´Ì¬£ºÇå¿Õ´íÎó£¬²¢¸üÐÂ last_state
                    # ×¢Òâ£º¿ÉÄÜÓÐ¡°²¿·Ö×´Ì¬¡±£¨Èç Capturing...£©£¬²»ÄÜÕû°ü¸²¸ÇµôÒÑÓÐµÄ fps/¼ÆÊýµÈ×Ö¶Î
                    is_partial = bool(st.get("__partial__", False))
                    if is_partial:
                        st = dict(st)
                        st.pop("__partial__", None)
                        last_state.update(st)
                    else:
                        last_state = st
                        # Ö»ÓÐÊÕµ½ÍêÕûÍÆÀí×´Ì¬Ê±²ÅÇå³ý´íÎó
                        last_state["last_error"] = ""
        except queue.Empty:
            pass

        info["fps"].set(f"FPS: {last_state.get('fps', '-'):.2f}" if isinstance(last_state.get("fps"), (int, float)) else f"FPS: -")
        info["display_fps"].set(f"Display: {last_state.get('display_fps', '-'):.1f}" if isinstance(last_state.get("display_fps"), (int, float)) else f"Display: -")
        info["mode"].set(f"Mode: {last_state.get('mode', '-')}")
        info["board"].set(f"Board: {last_state.get('board_count', '-')}" + (" (LOW)" if last_state.get("board_low") else ""))
        danger_active = last_state.get("intrusion_active", False)
        info["danger"].set(f"Danger: {last_state.get('intrusion_count', 0)}" + (" (INTRUSION)" if danger_active else ""))
        fire_active = last_state.get("fire_active", False)
        info["fire"].set(
            f"Fire: {last_state.get('fire_count', 0)}" + (" (ALARM)" if fire_active else "")
        )
        # ¸üÐÂÐÔÄÜ¼à¿ØÊý¾Ý
        last_error = (last_state.get("last_error") or "").strip()
        if last_error:
            info["last"].set(last_error)
        else:
            info["last"].set(last_state.get("last_trigger", "-"))

        # LED ³£ÁÁ£¨ÔÚ poll_ui Àï¸üÐÂ£©
        try:
            update_leds()
        except Exception:
            pass

        # frame
        try:
            pkt = frame_queue.get_nowait()
            fr = pkt.get("frame")
            # ×¢Òâ£ºÕâÀïÐèÒª´«Èë tkinter Ä£¿é£¨°üº¬ PhotoImage£©£¬¶ø²»ÊÇ root ¶ÔÏó
            photo = _try_get_tk_photoimage_from_bgr(tk, fr, video_w, video_h)
            if photo is not None:
                video_label.configure(image=photo)
                video_label.image = photo
        except queue.Empty:
            pass
        except Exception as e:
            # ²»ÒªÍÌÒì³££º·ñÔòÖ»ÄÜ¿´µ½ºÚÆÁ£¬²»ÖªµÀÄÄÀï»µÁË
            try:
                info["last"].set(f"Render error: {e}")
            except Exception:
                pass

        # ½« GUI Ì½ÕëÆµÂÊ¸ÄÎª 40ms (Ô¼Ëø¶¨ÔÚ 25 FPS µÄË¢ÐÂ¼«ÏÞ)
        # Õâµã¼«ÆäÖØÒª£¬ÕâÄÜÈÃÕ¼ÓÃ CPU ÌØ±ðºÝµÄ Tkinter ¶®µÃ¸øµ×²ãµÄ YOLOv7 ÍÆÀíÏß³Ì¡°ÈÃÂ·¡±£¬²»ÇÀ×ßÈ«²¿Ð¾Æ¬¡£
        # ¸ßÐÔÄÜÄ£Ê½ÏÂÊ¹ÓÃ¸ü¿ìµÄË¢ÐÂ¼ä¸ô
        refresh_interval = 8 if HIGH_PERF_MODE else 12
        root.after(refresh_interval, poll_ui)

    def on_close():
        stop_event.set()
        try:
            if worker_thread is not None and worker_thread.is_alive():
                worker_thread.join(timeout=0.6)
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass

    root.protocol("WM_DELETE_WINDOW", on_close)
    poll_ui()

    root.mainloop()

    # ÍË³ö£ºÊÍ·Å×ÊÔ´
    stop_event.set()
    try:
        if worker is not None:
            pass
    except Exception:
        pass


if __name__ == "__main__":
    run_gui()

