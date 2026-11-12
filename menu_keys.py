"""Interactive loading-menu keys through the verified native VPAD mailbox.
Never constructed for --no-input. No mouse polling, cursor movement or capture.
"""
import ctypes
import struct
import time
from ctypes import wintypes as W

class MenuKeys:
    KEYS={13:0x8000,8:0x4000,38:0x0200,40:0x0100,37:0x0800,39:0x0400}
    def __init__(self,pid,user=None,clock=time.monotonic):
        self.pid=pid;self.clock=clock;self.until={};self.held={};self.active=False
        self.user=user or ctypes.WinDLL('user32',use_last_error=True)
        if user is None:
            self.user.GetForegroundWindow.restype=W.HWND
            self.user.GetWindowThreadProcessId.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)]
            self.user.GetAsyncKeyState.argtypes=[ctypes.c_int]
            self.user.GetAsyncKeyState.restype=ctypes.c_short
    def release(self,process):
        if self.active:
            process.set(0x3c,0);process.set(0x198,0)
        self.active=False;self.until.clear();self.held.clear()
    def update(self,process):
        owner=W.DWORD()
        self.user.GetWindowThreadProcessId(self.user.GetForegroundWindow(),ctypes.byref(owner))
        if owner.value!=self.pid:
            self.release(process);return
        now=self.clock();mask=0
        for key,button in self.KEYS.items():
            raw=self.user.GetAsyncKeyState(key)
            down=bool(raw&0x8000)
            if raw&1 or (down and not self.held.get(key,False)):self.until[key]=now+.15
            self.held[key]=down
            if raw&0x8000 or self.until.get(key,0)>now:mask|=button
        if mask:
            if not self.active:process.put(0x48,struct.pack('>ffff',0.,0.,0.,0.))
            process.set(0x3c,mask);process.set(0x198,1);self.active=True
        else:self.release(process)
