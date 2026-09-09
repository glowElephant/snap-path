import io
import os
import sys
import ctypes
import ctypes.wintypes
import threading
import time
from datetime import datetime
from pathlib import Path

import pyperclip
from PIL import ImageGrab, Image, ImageTk
import pystray
import tkinter as tk
from screeninfo import get_monitors

# 1. Windows DPI 인식 설정 (고해상도/멀티 모니터 필수)
def set_dpi_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2) # Per-Monitor DPI Aware
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

set_dpi_awareness()

HOTKEY_PATH = "Ctrl+Alt+S"
HOTKEY_IMAGE = "Ctrl+Alt+Shift+S"
SAVE_DIR = Path.home() / "Pictures" / "SnapPath"

# RegisterHotKey 상수
MOD_ALT = 0x0001
MOD_CTRL = 0x0002
MOD_SHIFT = 0x0004
VK_S = 0x53
HOTKEY_ID_PATH = 1
HOTKEY_ID_IMAGE = 2
WM_HOTKEY = 0x0312

# 클립보드 상수
CF_UNICODETEXT = 13
CF_DIB = 8
GMEM_MOVEABLE = 0x0002

# 64비트에서 핸들이 32비트로 잘리지 않도록 시그니처를 명시해야 한다
_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32
_kernel32.GlobalAlloc.restype = ctypes.c_void_p
_kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
_kernel32.GlobalLock.restype = ctypes.c_void_p
_kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
_kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
_kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
_kernel32.GlobalFree.restype = ctypes.c_void_p
_user32.OpenClipboard.argtypes = [ctypes.c_void_p]
_user32.SetClipboardData.restype = ctypes.c_void_p
_user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
def _alloc_global(data: bytes):
    """클립보드에 넘길 GMEM_MOVEABLE 버퍼를 만들어 데이터를 채운다."""
    handle = _kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not handle:
        raise OSError("GlobalAlloc 실패")
    ptr = _kernel32.GlobalLock(handle)
    if not ptr:
        _kernel32.GlobalFree(handle)
        raise OSError("GlobalLock 실패")
    ctypes.memmove(ptr, data, len(data))
    _kernel32.GlobalUnlock(handle)
    return handle

def set_clipboard_single(fmt, data):
    """클립보드를 비우고 포맷 하나만 올린다.

    텍스트와 이미지를 함께 올리면 카톡·워드처럼 둘 다 받는 앱에서
    이미지에 경로까지 딸려 붙는다. 그래서 한 번에 하나만 올린다.
    """
    # 다른 앱이 클립보드를 쥐고 있을 수 있어 잠깐 재시도
    for _ in range(10):
        if _user32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        raise OSError("클립보드 열기 실패")

    try:
        _user32.EmptyClipboard()
        handle = _alloc_global(data)
        if not _user32.SetClipboardData(fmt, handle):
            # 소유권이 넘어가지 않았으니 직접 해제
            _kernel32.GlobalFree(handle)
            raise OSError(f"SetClipboardData 실패 (format={fmt})")
    finally:
        _user32.CloseClipboard()

def copy_path_to_clipboard(filepath):
    """저장 경로만 복사 — 터미널·주소창·AI 프롬프트용."""
    try:
        set_clipboard_single(CF_UNICODETEXT, str(filepath).encode("utf-16-le") + b"\x00\x00")
    except Exception as e:
        print(f"경로 복사 실패, pyperclip으로 재시도: {e}")
        try:
            pyperclip.copy(str(filepath))
        except Exception as e2:
            print(f"클립보드 복사 실패: {e2}")

def copy_image_to_clipboard(image):
    """이미지만 복사 — 카톡·워드·파워포인트용."""
    # CF_DIB는 BMP에서 BITMAPFILEHEADER(14바이트)를 뗀 나머지
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "BMP")
    try:
        set_clipboard_single(CF_DIB, buffer.getvalue()[14:])
    except Exception as e:
        print(f"이미지 복사 실패: {e}")

def ensure_save_dir():
    SAVE_DIR.mkdir(parents=True, exist_ok=True)

def generate_filename():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return SAVE_DIR / f"screenshot_{timestamp}.png"

def get_virtual_screen_bbox():
    """모든 모니터를 합친 가상 데스크톱 전체 영역 계산"""
    monitors = get_monitors()
    min_x = min(m.x for m in monitors)
    min_y = min(m.y for m in monitors)
    max_x = max(m.x + m.width for m in monitors)
    max_y = max(m.y + m.height for m in monitors)
    return min_x, min_y, max_x, max_y

class FrozenScreenSelector:
    """
    단축키를 누른 순간의 화면을 얼려서 보여주고,
    그 위에서 영역을 선택하는 클래스 (Toplevel 사용)
    """
    def __init__(self, master_root, frozen_screenshot):
        self.master = master_root # 메인 루트 윈도우 참조
        self.frozen = frozen_screenshot
        self.result_bbox = None
        self.rect = None
        self.dim_overlay = None

    def select(self):
        vx, vy, vx2, vy2 = get_virtual_screen_bbox()
        vw, vh = vx2 - vx, vy2 - vy

        # [중요] 새로운 Tk() 대신 Toplevel() 사용
        self.top = tk.Toplevel(self.master)
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)
        self.top.configure(cursor="crosshair")

        # 모든 모니터를 합친 영역으로 창 배치
        self.top.geometry(f"{vw}x{vh}+{vx}+{vy}")

        self.canvas = tk.Canvas(self.top, highlightthickness=0, width=vw, height=vh, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 배경 이미지 설정
        dimmed = self.frozen.convert("RGBA")
        overlay = Image.new("RGBA", dimmed.size, (0, 0, 0, 120))
        dimmed = Image.alpha_composite(dimmed, overlay).convert("RGB")

        self.bg_dimmed = ImageTk.PhotoImage(dimmed)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.bg_dimmed)

        # 이벤트 바인딩
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.top.bind("<Escape>", lambda e: self.top.destroy())

        # 포커스 강제 및 메인 루프 대기
        self.top.focus_force()
        # [중요] 메인 루프가 멈추지 않도록 wait_window 사용
        self.master.wait_window(self.top)

        return self.result_bbox

    def _on_press(self, event):
        self.start_x, self.start_y = event.x, event.y

    def _on_drag(self, event):
        # 기존 그래픽 삭제
        if self.rect: self.canvas.delete(self.rect)
        if self.dim_overlay: self.canvas.delete(self.dim_overlay)

        x1, y1 = min(self.start_x, event.x), min(self.start_y, event.y)
        x2, y2 = max(self.start_x, event.x), max(self.start_y, event.y)

        # 드래그 영역 밝게 표시
        if x2 - x1 > 0 and y2 - y1 > 0:
            crop = self.frozen.crop((x1, y1, x2, y2))
            self._bright_img = ImageTk.PhotoImage(crop)
            self.dim_overlay = self.canvas.create_image(x1, y1, anchor=tk.NW, image=self._bright_img)

        self.rect = self.canvas.create_rectangle(x1, y1, x2, y2, outline="#00aaff", width=2)

    def _on_release(self, event):
        x1, y1 = min(self.start_x, event.x), min(self.start_y, event.y)
        x2, y2 = max(self.start_x, event.x), max(self.start_y, event.y)

        if (x2 - x1) > 5 and (y2 - y1) > 5:
            self.result_bbox = (x1, y1, x2, y2)
        self.top.destroy()

def run_capture_sequence(root, as_image=False):
    """메인 스레드에서 실행될 실제 캡처 로직

    as_image=False면 저장 경로를, True면 이미지를 클립보드에 올린다.
    파일은 어느 쪽이든 저장한다.
    """
    try:
        # 1. 캡처 (잠시 대기 후)
        time.sleep(0.2)
        frozen = ImageGrab.grab(all_screens=True)

        # 2. 선택 창 띄우기 (root 전달)
        selector = FrozenScreenSelector(root, frozen)
        bbox = selector.select()

        # 3. 저장
        if bbox:
            cropped = frozen.crop(bbox)
            ensure_save_dir()
            filepath = generate_filename()
            cropped.save(str(filepath))
            if as_image:
                copy_image_to_clipboard(cropped)
            else:
                copy_path_to_clipboard(filepath)
    except Exception as e:
        print(f"Error: {e}")

def create_icon_image():
    """SnapPath 트레이 아이콘 이미지 생성"""
    from PIL import ImageDraw
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 카메라 본체 (둥근 사각형)
    draw.rounded_rectangle([8, 18, 56, 52], radius=6, fill=(50, 120, 220), outline=(30, 80, 180), width=2)

    # 카메라 상단 돌출부
    draw.rounded_rectangle([22, 10, 42, 22], radius=3, fill=(50, 120, 220), outline=(30, 80, 180), width=2)

    # 렌즈 (바깥 원)
    draw.ellipse([22, 26, 50, 50], fill=(20, 60, 140), outline=(30, 80, 180), width=2)

    # 렌즈 (안쪽 원)
    draw.ellipse([28, 30, 44, 46], fill=(40, 100, 200), outline=(60, 140, 240), width=1)

    # 렌즈 하이라이트
    draw.ellipse([34, 33, 40, 39], fill=(140, 190, 255))

    # 플래시
    draw.ellipse([12, 22, 20, 28], fill=(255, 220, 80))

    return img

def setup_tray_icon(root):
    """트레이 아이콘을 별도 스레드에서 실행"""
    icon_image = create_icon_image()

    def quit_app(icon):
        icon.stop()
        root.after(0, root.quit)

    def restart_app(icon):
        icon.stop()
        root.after(0, root.quit)
        # 현재 스크립트를 다시 실행
        python = sys.executable
        script = os.path.abspath(__file__)
        os.execv(python, [python, script])

    menu = pystray.Menu(
        pystray.MenuItem(f"{HOTKEY_PATH} — 경로 복사", lambda: None, enabled=False),
        pystray.MenuItem(f"{HOTKEY_IMAGE} — 이미지 복사", lambda: None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("재실행", restart_app),
        pystray.MenuItem("종료", quit_app)
    )
    icon = pystray.Icon("snap-path", icon_image, "SnapPath", menu)
    icon.run()

def hotkey_listener(root):
    """RegisterHotKey Win32 API로 글로벌 핫키 감지 (별도 스레드)"""
    user32 = ctypes.windll.user32

    hotkeys = (
        (HOTKEY_ID_PATH, MOD_CTRL | MOD_ALT, HOTKEY_PATH),
        (HOTKEY_ID_IMAGE, MOD_CTRL | MOD_ALT | MOD_SHIFT, HOTKEY_IMAGE),
    )
    registered = []
    for hotkey_id, mods, label in hotkeys:
        if user32.RegisterHotKey(None, hotkey_id, mods, VK_S):
            registered.append(hotkey_id)
        else:
            print(f"RegisterHotKey 실패 — 다른 프로그램이 {label}를 사용 중일 수 있음")

    if not registered:
        return

    msg = ctypes.wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message == WM_HOTKEY:
            if msg.wParam == HOTKEY_ID_PATH:
                root.after(0, run_capture_sequence, root, False)
            elif msg.wParam == HOTKEY_ID_IMAGE:
                root.after(0, run_capture_sequence, root, True)

    for hotkey_id in registered:
        user32.UnregisterHotKey(None, hotkey_id)

def main():
    # 1. 메인 스레드에서 Tkinter 루트 생성 (숨김 상태)
    root = tk.Tk()
    root.withdraw() # 창을 숨겨둠

    # 2. 트레이 아이콘은 별도 스레드로 분리 (메인 스레드 양보)
    threading.Thread(target=setup_tray_icon, args=(root,), daemon=True).start()

    # 3. RegisterHotKey 리스너 (별도 스레드, OS 레벨 핫키)
    threading.Thread(target=hotkey_listener, args=(root,), daemon=True).start()

    # 4. 메인 스레드는 오직 GUI 루프만 돌림 (안정성 확보)
    root.mainloop()

if __name__ == "__main__":
    main()
