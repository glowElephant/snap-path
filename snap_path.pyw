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

HOTKEY = "Ctrl+Alt+S"
SAVE_DIR = Path.home() / "Pictures" / "SnapPath"

# RegisterHotKey 상수
MOD_CTRL = 0x0002
MOD_ALT = 0x0001
VK_S = 0x53
HOTKEY_ID = 1
WM_HOTKEY = 0x0312

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

def run_capture_sequence(root):
    """메인 스레드에서 실행될 실제 캡처 로직"""
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
            pyperclip.copy(str(filepath))
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
        pystray.MenuItem(f"SnapPath ({HOTKEY})", lambda: None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("재실행", restart_app),
        pystray.MenuItem("종료", quit_app)
    )
    icon = pystray.Icon("snap-path", icon_image, "SnapPath", menu)
    icon.run()

def hotkey_listener(root):
    """RegisterHotKey Win32 API로 글로벌 핫키 감지 (별도 스레드)"""
    user32 = ctypes.windll.user32

    if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_CTRL | MOD_ALT, VK_S):
        print(f"RegisterHotKey 실패 — 다른 프로그램이 {HOTKEY}를 사용 중일 수 있음")
        return

    msg = ctypes.wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
            root.after(0, run_capture_sequence, root)

    user32.UnregisterHotKey(None, HOTKEY_ID)

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
