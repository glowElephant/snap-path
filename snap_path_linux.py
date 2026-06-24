#!/usr/bin/env python3
"""
snap-path (Linux) — 화면 영역을 캡쳐해 PNG로 저장하고, 저장 경로를 클립보드에 자동 복사.

Windows 원본(snap_path.pyw)의 리눅스 포팅 버전.
  - 글로벌 핫키: pynput (X11)
  - 멀티모니터 캡쳐: mss (가상 스크린 전체)
  - 영역 선택(얼림+드래그): tkinter (원본 로직 재사용)
  - 클립보드: pyperclip (xclip/xsel 백엔드)
  - 트레이 아이콘: pystray (있으면 사용, GNOME 등에서 실패해도 핵심 기능은 동작)

핫키 Ctrl+Alt+S → 화면 얼림 → 드래그로 영역 선택 → 저장 + 경로 클립보드 복사.
종료는 트레이 메뉴 또는 터미널에서 Ctrl+C.
"""
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import pyperclip
from PIL import Image, ImageTk
import tkinter as tk
import mss
from pynput import keyboard

HOTKEY = "Ctrl+Alt+S"
# pynput GlobalHotKeys 표기 (<ctrl>+<alt>+s)
HOTKEY_PYNPUT = "<ctrl>+<alt>+s"
SAVE_DIR = Path.home() / "Pictures" / "SnapPath"


def ensure_save_dir():
    SAVE_DIR.mkdir(parents=True, exist_ok=True)


def generate_filename():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return SAVE_DIR / f"screenshot_{timestamp}.png"


def grab_all_screens():
    """모든 모니터를 합친 가상 데스크톱 전체를 캡쳐.

    반환: (PIL.Image, left, top) — left/top은 가상 스크린의 좌상단 오프셋(음수 가능).
    """
    with mss.mss() as sct:
        # monitors[0] = 모든 모니터를 합친 가상 스크린 전체
        mon = sct.monitors[0]
        shot = sct.grab(mon)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        return img, mon["left"], mon["top"]


class FrozenScreenSelector:
    """
    핫키를 누른 순간의 화면을 얼려서 보여주고, 그 위에서 영역을 선택.
    (Windows 원본의 Toplevel 방식을 그대로 사용)
    """
    def __init__(self, master_root, frozen_screenshot, offset_x, offset_y):
        self.master = master_root
        self.frozen = frozen_screenshot
        self.offset_x = offset_x  # 가상 스크린 좌상단 오프셋 (창 배치용)
        self.offset_y = offset_y
        self.result_bbox = None  # frozen 이미지 기준 좌표
        self.rect = None
        self.dim_overlay = None

    def select(self):
        vw, vh = self.frozen.size

        self.top = tk.Toplevel(self.master)
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)
        self.top.configure(cursor="crosshair")

        # 가상 스크린 전체를 덮도록 배치 (오프셋이 음수면 tkinter가 +-100 형식 처리)
        self.top.geometry(f"{vw}x{vh}+{self.offset_x}+{self.offset_y}")

        self.canvas = tk.Canvas(self.top, highlightthickness=0, width=vw, height=vh, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 배경: 얼린 화면을 어둡게
        dimmed = self.frozen.convert("RGBA")
        overlay = Image.new("RGBA", dimmed.size, (0, 0, 0, 120))
        dimmed = Image.alpha_composite(dimmed, overlay).convert("RGB")

        self.bg_dimmed = ImageTk.PhotoImage(dimmed)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.bg_dimmed)

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.top.bind("<Escape>", lambda e: self.top.destroy())

        self.top.focus_force()
        self.master.wait_window(self.top)

        return self.result_bbox

    def _on_press(self, event):
        self.start_x, self.start_y = event.x, event.y

    def _on_drag(self, event):
        if self.rect:
            self.canvas.delete(self.rect)
        if self.dim_overlay:
            self.canvas.delete(self.dim_overlay)

        x1, y1 = min(self.start_x, event.x), min(self.start_y, event.y)
        x2, y2 = max(self.start_x, event.x), max(self.start_y, event.y)

        # 드래그 영역만 밝게 표시
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
    """메인 스레드(tkinter)에서 실행되는 실제 캡쳐 로직."""
    try:
        time.sleep(0.2)
        frozen, off_x, off_y = grab_all_screens()

        selector = FrozenScreenSelector(root, frozen, off_x, off_y)
        bbox = selector.select()

        if bbox:
            cropped = frozen.crop(bbox)
            ensure_save_dir()
            filepath = generate_filename()
            cropped.save(str(filepath))
            try:
                pyperclip.copy(str(filepath))
            except Exception as e:
                print(f"클립보드 복사 실패 (xclip/xsel 설치 필요): {e}")
            print(f"저장됨: {filepath}")
    except Exception as e:
        print(f"Error: {e}")


def create_icon_image():
    """SnapPath 트레이 아이콘 이미지 생성 (원본과 동일한 카메라 모양)."""
    from PIL import ImageDraw
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle([8, 18, 56, 52], radius=6, fill=(50, 120, 220), outline=(30, 80, 180), width=2)
    draw.rounded_rectangle([22, 10, 42, 22], radius=3, fill=(50, 120, 220), outline=(30, 80, 180), width=2)
    draw.ellipse([22, 26, 50, 50], fill=(20, 60, 140), outline=(30, 80, 180), width=2)
    draw.ellipse([28, 30, 44, 46], fill=(40, 100, 200), outline=(60, 140, 240), width=1)
    draw.ellipse([34, 33, 40, 39], fill=(140, 190, 255))
    draw.ellipse([12, 22, 20, 28], fill=(255, 220, 80))

    return img


def setup_tray_icon(root):
    """트레이 아이콘 (별도 스레드). 환경에 따라 실패할 수 있으므로 graceful 처리."""
    try:
        import pystray
    except Exception as e:
        print(f"트레이 비활성화 (pystray 없음): {e}")
        return

    icon_image = create_icon_image()

    def quit_app(icon):
        icon.stop()
        root.after(0, root.quit)

    def restart_app(icon):
        icon.stop()
        root.after(0, root.quit)
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
    try:
        icon.run()
    except Exception as e:
        # GNOME 등 트레이 미지원 환경 — 핵심 기능에는 영향 없음
        print(f"트레이 아이콘 표시 실패 (핫키는 정상 동작): {e}")


def main():
    print(f"SnapPath (Linux) 시작 — 핫키 {HOTKEY}로 캡쳐, Ctrl+C로 종료")

    # 메인 스레드: 숨겨진 tkinter 루트
    root = tk.Tk()
    root.withdraw()

    # 트레이 (별도 스레드, 실패해도 무방)
    threading.Thread(target=setup_tray_icon, args=(root,), daemon=True).start()

    # 글로벌 핫키 리스너 (별도 스레드)
    def on_hotkey():
        # pynput 스레드 → tkinter 메인 스레드로 위임
        root.after(0, run_capture_sequence, root)

    hotkey_listener = keyboard.GlobalHotKeys({HOTKEY_PYNPUT: on_hotkey})
    hotkey_listener.daemon = True
    hotkey_listener.start()

    # Ctrl+C(터미널)로 종료 가능하도록 주기적으로 인터프리터에 양보
    def keep_alive():
        root.after(200, keep_alive)
    keep_alive()

    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\n종료합니다.")
        hotkey_listener.stop()


if __name__ == "__main__":
    main()
