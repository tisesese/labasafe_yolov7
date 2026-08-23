# -*- coding: utf-8 -*-

import acl
import threading

_lock = threading.Lock()
_ref_count = 0
_device_set = False
_device_id = None
_acl_inited_once = False


def acl_init_ref(device_id=0):
   
    global _ref_count, _device_set, _device_id, _acl_inited_once
    with _lock:
        if _ref_count == 0:
            # GUI 长时间运行且会重复切换输入源/模块时，避免反复 init/finalize 触发 ACL 状态冲突
            if not _acl_inited_once:
                ret = acl.init()
                # 100002 在部分环境表示 ACL 已初始化，按成功处理
                if ret not in (0, 100002):
                    raise Exception(f"ACL init failed with error code: {ret}")
                _acl_inited_once = True
            if not _device_set:
                ret = acl.rt.set_device(device_id)
                if ret != 0:
                    raise Exception(f"Set device failed with error code: {ret}")
                _device_set = True
                _device_id = device_id
        _ref_count += 1


def acl_finalize_ref():
   
    global _ref_count, _device_set, _device_id
    with _lock:
        if _ref_count <= 0:
            return
        _ref_count -= 1
        if _ref_count == 0:
            # 为了稳定支持 GUI 中反复切换，不在运行期做 reset/finalize。
            # 进程退出时由系统回收，避免重复 init/finalize 引发 100002 等错误。
            pass

