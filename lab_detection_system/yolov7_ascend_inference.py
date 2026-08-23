# -*- coding: utf-8 -*-
#"""
#YOLOv7 •NÌÚ ACL ÍÆÀí·â×°£¨µ¥Ä£ÐÍ£ºfire/person/board card£©¡£

#ËµÃ÷£º
#- Ä¿±êÀà±ðË³ÐòÔ¼¶¨£ºfire=0, person=1, board card=2
#- ±¾ÎÄ¼þ¾¡Á¿ÓÃ¡°YOLOv5 ÀàÊä³ö¡±ºó´¦ÀíÂß¼­½âÎö£¨(1, N, 5+nc) µÄºòÑ¡ÐÎÌ¬£©
#- ÈôÄãµÄ .om Êä³öÐÎÌ¬Óë¼ÙÉè²»Ò»ÖÂ£¬¿ÉÏÈ°Ñ debug ´òÓ¡Êä³ö·¢ÎÒ£¬ÎÒÔÙ°ïÄã°Ñ postprocess ÊÊÅäµ½ÄãµÄÄ£ÐÍ
#"""
import acl
import numpy as np
import cv2
import os

from acl_shared import acl_init_ref, acl_finalize_ref


CLASSES = ["fire", "person", "board card"]
FIRE_CLASS_ID = 0
PERSON_CLASS_ID = 1
BOARD_CLASS_ID = 2


class YOLOv7AscendInference:
    def __init__(self, model_path, device_id=0, conf_threshold=0.25, iou_threshold=0.45):
        self.device_id = device_id
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold

        self.context = None
        self.stream = None
        self.model_id = None
        self.model_desc = None

        self.input_size = 0
        self.output_size = 0
        self.input_buffer = None
        self.output_buffer = None

        # ¶¯Ì¬Ä£ÐÍÊäÈë³ß´ç
        self.model_size = int(os.environ.get("MODEL_INPUT_SIZE", "640"))

        # ¸´ÓÃ dataset / data buffer£¬¼õÉÙÃ¿Ö¡¿ªÏú
        self.input_dataset = None
        self.output_dataset = None
        self.input_data = None
        self.output_data = None

        self.output_host = None
        self._coord_is_normalized = None
        self._input_mode = None

        self._init_acl()

    def _init_acl(self):
        # ¹²Ïí init£¬±ÜÃâ¶àÄ£ÐÍÖØ¸´ acl.init() ±¨´í
        acl_init_ref(self.device_id)
        self.context = None
        self.stream = None

        ret = acl.rt.set_device(self.device_id)
        if ret != 0:
            raise Exception(f"Set device failed: {ret}")
        self.context, ret = acl.rt.create_context(self.device_id)
        if ret != 0:
            raise Exception(f"Create context failed: {ret}")
        self.stream, ret = acl.rt.create_stream()
        if ret != 0:
            raise Exception(f"Create stream failed: {ret}")

    def load_model(self):
        self.model_id, ret = acl.mdl.load_from_file(self.model_path)
        if ret != 0:
            raise Exception(f"Load model failed ({self.model_path}), error={ret}")

        self.model_desc = acl.mdl.create_desc()
        ret = acl.mdl.get_desc(self.model_desc, self.model_id)
        if ret != 0:
            raise Exception(f"Get model desc failed, error={ret}")

        self.input_size = acl.mdl.get_input_size_by_index(self.model_desc, 0)
        self.output_size = acl.mdl.get_output_size_by_index(self.model_desc, 0)
        
        self.input_buffer, ret = acl.rt.malloc(self.input_size, 0)
        if ret != 0:
            raise Exception(f"Allocate input buffer failed, error={ret}")
        self.output_buffer, ret = acl.rt.malloc(self.output_size, 0)
        if ret != 0:
            raise Exception(f"Allocate output buffer failed, error={ret}")

        # ¸´ÓÃÊä³ö host£¨float32£©
        num_floats = self.output_size // 4
        self.output_host = np.zeros(num_floats, dtype=np.float32)

        # ¸´ÓÃ dataset/data buffer
        self.input_dataset = acl.mdl.create_dataset()
        self.output_dataset = acl.mdl.create_dataset()

        self.input_data = acl.create_data_buffer(self.input_buffer, self.input_size)
        ret_val = acl.mdl.add_dataset_buffer(self.input_dataset, self.input_data)
        if isinstance(ret_val, tuple):
            _, ec = ret_val
            if ec != 0:
                raise Exception(f"Add input dataset buffer failed, error={ec}")
        elif ret_val is not None and ret_val != 0:
            raise Exception(f"Add input dataset buffer failed, error={ret_val}")

        self.output_data = acl.create_data_buffer(self.output_buffer, self.output_size)
        ret_val = acl.mdl.add_dataset_buffer(self.output_dataset, self.output_data)
        if isinstance(ret_val, tuple):
            _, ec = ret_val
            if ec != 0:
                raise Exception(f"Add output dataset buffer failed, error={ec}")
        elif ret_val is not None and ret_val != 0:
            raise Exception(f"Add output dataset buffer failed, error={ret_val}")

    def preprocess_frame(self, frame):
        if frame is None:
            return None, None
        orig_h, orig_w = frame.shape[:2]
        # Ê¹ÓÃ×î¿ìµÄÍ¼ÏñËõ·Å·½·¨£¬ÎþÉüÒ»Ð©ÖÊÁ¿»»È¡ËÙ¶È
        import time
        start = time.time()
        resized = cv2.resize(frame, (self.model_size, self.model_size), interpolation=cv2.INTER_NEAREST)
        pre_time = time.time() - start
        if pre_time > 0.05:  # Èç¹ûÔ¤´¦ÀíÊ±¼ä³¬¹ý50ms£¬´òÓ¡¾¯¸æ
            print(f"Warning: Preprocessing time too long: {pre_time*1000:.2f}ms")
        return (orig_w, orig_h), resized

    def _to_model_input(self, bgr_resized):
        # ¶¯Ì¬¼ÆËãÄ£ÐÍÊäÈë³ß´ç
        model_size = bgr_resized.shape[0]  # ¼ÙÉèÊÇÕý·½ÐÎ
        h = model_size
        w = model_size
        yuv420_size = h * w * 3 // 2
        chw_u8_size = h * w * 3
        chw_f16_size = h * w * 3 * 2
        chw_f32_size = h * w * 3 * 4

        if self.input_size == yuv420_size:
            self._input_mode = "yuv420_i420"
            yuv = cv2.cvtColor(bgr_resized, cv2.COLOR_BGR2YUV_I420)
            return yuv

        rgb = cv2.cvtColor(bgr_resized, cv2.COLOR_BGR2RGB)

        if self.input_size == chw_u8_size:
            self._input_mode = "hwc_uint8"
            # µ± AIPP ÅäÖÃÎª RGB888_U8 Ê±£¬NPU Ó²¼þ³Ô HWC ÅÅ²¼¡£
            # cvtColor ³öÀ´µÄ¾ÍÊÇÁ¬Ðø¡¢ÍêÃÀµÄ uint8 ÄÚ´æ£¬²»ÒªÔÙ»­ÉßÌí×ã .astype() ºÍ ascontiguousarray ÀË·Ñ CPU Éî¶È¿½±´£¡
            return rgb
            
        chw = np.transpose(rgb, (2, 0, 1))

        if self.input_size == chw_f16_size:
            self._input_mode = "nchw_float16"
            return np.ascontiguousarray((chw.astype(np.float32) / 255.0).astype(np.float16))

        if self.input_size == chw_f32_size:
            self._input_mode = "nchw_float32"
            return np.ascontiguousarray((chw.astype(np.float32) / 255.0))

        raise Exception(
            f"Unsupported model input_size={self.input_size}. "
            f"Supported byte sizes for {model_size}x{model_size} are: "
            f"YUV420={yuv420_size}, NCHW-u8={chw_u8_size}, "
            f"NCHW-f16={chw_f16_size}, NCHW-f32={chw_f32_size}. "
            f"Please verify ATC input shape/format."
        )

    def process_frame(self, frame):
        import time

        if frame is None:
            return []

        start_total = time.time()

        if self.context is not None:
            acl.rt.set_context(self.context)

        # Ô¤´¦Àí
        start_pre = time.time()
        (orig_w, orig_h), resized = self.preprocess_frame(frame)
        inp = self._to_model_input(resized)
        img_buffer_size = int(inp.nbytes)
        pre_time = time.time() - start_pre

        # ÏÔÊ½Ð£ÑéÊäÈë×Ö½ÚÊý£¬±ÜÃâÊäÈë¸ñÊ½/³ß´ç²»Æ¥ÅäÊ±¿¨×¡
        if self.input_size != img_buffer_size:
            raise Exception(
                f"Input size mismatch: model expects {self.input_size} bytes, "
                f"but current preprocessed frame is {img_buffer_size} bytes (mode={self._input_mode})."
            )

        # ÄÚ´æ¿½±´µ½Éè±¸
        start_memcpy_h2d = time.time()
        ret = acl.rt.memcpy(self.input_buffer, self.input_size, inp.ctypes.data, img_buffer_size, 0)
        if ret != 0:
            raise Exception(f"Memcpy to device failed, error={ret}")
        memcpy_h2d_time = time.time() - start_memcpy_h2d

        # Ä£ÐÍÖ´ÐÐ
        start_infer = time.time()
        ret = acl.mdl.execute(self.model_id, self.input_dataset, self.output_dataset)
        if ret != 0:
            raise Exception(f"Model execute failed, error={ret}")
        infer_time = time.time() - start_infer

        # ÄÚ´æ¿½±´»ØÖ÷»ú
        start_memcpy_d2h = time.time()
        ret = acl.rt.memcpy(self.output_host.ctypes.data, self.output_host.nbytes, self.output_buffer, self.output_size, 1)
        if ret != 0:
            raise Exception(f"Memcpy from device failed, error={ret}")
        memcpy_d2h_time = time.time() - start_memcpy_d2h

        # ºó´¦Àí
        start_post = time.time()
        detections = self._postprocess(self.output_host, orig_w, orig_h)
        post_time = time.time() - start_post

        return detections

    def _postprocess(self, output_host, orig_w, orig_h):
        nc = len(CLASSES)
        vec_len = 5 + nc
        total = output_host.size
        # Èô×Ü³¤¶È²»±»Õû³ý£¬ÕâÅúÊä³ö¿ÉÄÜÓÐ´íÎ»
        if total % vec_len != 0:
            return []

        pred_n = total // vec_len
        preds = output_host.reshape(pred_n, vec_len)

        # 1. µÚÒ»²½ÏòÁ¿»¯¹ýÂË£ºÓÃ´¿ C++ C Á¬ÐøÄÚ´æ¼«ËÙ¹ýÂËµôËùÓÐÖÃÐÅ¶È¹ýµÍµÄºòÑ¡¿ò
        # ÕâÖ±½ÓÈ¡´úÁËÔ­À´µÄ for det in preds (Ã¿´Î¼¸Ê®Íò´Î Python if)
        valid_mask = preds[:, 4] > self.conf_threshold
        valid_preds = preds[valid_mask]

        if len(valid_preds) == 0:
            return []

        # 2. µÚ¶þ²½ÏòÁ¿»¯ÌáÀà±ð£ºNumPy Ò»´ÎÐÔÈ«²¿×ö argmax
        obj_conf_valid = valid_preds[:, 4]
        cls_probs = valid_preds[:, 5:5 + nc]
        class_ids = np.argmax(cls_probs, axis=1)
        class_confs = np.max(cls_probs, axis=1)
        final_confs = obj_conf_valid * class_confs

        # 3. ½á¹ûºÏ²¢¹ýÂË
        final_mask = final_confs > self.conf_threshold
        final_preds = valid_preds[final_mask]
        final_confs = final_confs[final_mask]
        class_ids = class_ids[final_mask]

        if len(final_preds) == 0:
            return []

        # ÅÐ¶Ï×ø±ê¹éÒ»»¯
        if self._coord_is_normalized is None:
            mx = float(np.max(final_preds[:, :4]))
            self._coord_is_normalized = (mx <= 2.5)

        boxes = final_preds[:, :4].copy()

        # 4. ÏòÁ¿»¯×ø±ê»¹Ô­
        if self._coord_is_normalized:
            boxes[:, 0] *= orig_w
            boxes[:, 1] *= orig_h
            boxes[:, 2] *= orig_w
            boxes[:, 3] *= orig_h
        else:
            boxes[:, 0] = boxes[:, 0] / self.model_size * orig_w
            boxes[:, 1] = boxes[:, 1] / self.model_size * orig_h
            boxes[:, 2] = boxes[:, 2] / self.model_size * orig_w
            boxes[:, 3] = boxes[:, 3] / self.model_size * orig_h

        # OpenAI CvÒªÇóµÄ NMSBoxes ¸ñÊ½£º [x1, y1, w, h] ×óÉÏ½Çµã
        x1 = boxes[:, 0] - boxes[:, 2] / 2
        y1 = boxes[:, 1] - boxes[:, 3] / 2
        w = boxes[:, 2]
        h = boxes[:, 3]

        cv_boxes = np.stack([x1, y1, w, h], axis=1).tolist()
        confs_list = final_confs.tolist()

        # 5. ¡¾ºËÐÄÐÔÄÜÊÍ·Åµã¡¿£ºÍêÈ«ÉáÆúÔ­±¾ Python _nms ÖÐÄÇ¼¸°ÙÍò´Î while nets ºÍ _iou Ïà½»¼ÆËã£¡
        # Ö±½Ó°ÑËùÓÐ¾ØÕó¶ªÈë opencv µ×²ãµÄ C++ NMS ´¦Àí¡£ºÄÊ±´Ó½ü 200 ºÁÃëËõ¼õÎª²»µ½ 1 ºÁÃë£¡
        # ÓÅ»¯NMS²ÎÊý£ºÊ¹ÓÃ¸ü´óµÄiou_threshold¼õÉÙ¼ÆËãÁ¿
        import time
        start_nms = time.time()
        indices = cv2.dnn.NMSBoxes(cv_boxes, confs_list, self.conf_threshold, min(self.iou_threshold, 0.6))
        nms_time = time.time() - start_nms
        if nms_time > 0.01:  # Èç¹ûNMSÊ±¼ä³¬¹ý10ms£¬´òÓ¡¾¯¸æ
            print(f"Warning: NMS time too long: {nms_time*1000:.2f}ms")

        detections = []
        if len(indices) > 0:
            # ÅúÁ¿´¦Àí×ø±ê×ª»»
            for i in indices.flatten():
                bx = cv_boxes[i]
                # ÓÅ»¯×ø±ê¼ÆËã
                cx1 = int(max(0, bx[0]))
                cy1 = int(max(0, bx[1]))
                cx2 = int(min(orig_w, bx[0] + bx[2]))
                cy2 = int(min(orig_h, bx[1] + bx[3]))
                detections.append({
                    "bbox": [cx1, cy1, cx2, cy2],
                    "class_id": int(class_ids[i]),
                    "confidence": float(confs_list[i]),
                })

        return detections

    def release_resource(self):
        try:
            if self.input_buffer:
                acl.rt.free(self.input_buffer)
            if self.output_buffer:
                acl.rt.free(self.output_buffer)
            if self.model_id:
                acl.mdl.unload(self.model_id)
            if self.model_desc:
                acl.mdl.destroy_desc(self.model_desc)
            if self.stream:
                acl.rt.destroy_stream(self.stream)
            if self.context:
                acl.rt.destroy_context(self.context)
        finally:
            acl_finalize_ref()
