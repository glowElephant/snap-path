import os
import sys
import ctypes
import threading
from datetime import datetime
from pathlib import Path
from io import BytesIO

import keyboard
import pyperclip
from PIL import ImageGrab, Image, ImageTk, ImageDraw
import pystray
import tkinter as tk
from screeninfo import get_monitors


# Windows DPI 인식 설정 (고해상도 모니터 대응)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor DPI Aware
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


# 설정
HOTKEY = "ctrl+alt+s"
SAVE_DIR = Path.home() / "Pictures" / "SnapPath"


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


def capture_full_screen():
    """모든 모니터를 포함한 전체 화면을 즉시 캡쳐 (얼림)"""
    return ImageGrab.grab(all_screens=True)


class FrozenScreenSelector:
    """
    단축키를 누른 순간의 화면을 얼려서 보여주고,
    그 위에서 영역을 선택하는 클래스 (멀티 모니터 지원)
    """

    def __init__(self, frozen_screenshot):
        self.frozen = frozen_screenshot  # 얼린 전체 스크린샷
        self.start_x = 0
        self.start_y = 0
        self.end_x = 0
        self.end_y = 0
        self.rect = None
        self.dim_overlay = None
        self.result_bbox = None

    def select(self):
        # 가상 데스크톱 전체 영역 계산
        vx, vy, vx2, vy2 = get_virtual_screen_bbox()
        self.vx = vx
        self.vy = vy
        vw = vx2 - vx
        vh = vy2 - vy

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(cursor="crosshair")

        # 모든 모니터를 합친 영역으로 창 배치
        self.root.geometry(f"{vw}x{vh}+{vx}+{vy}")

        self.canvas = tk.Canvas(
            self.root, highlightthickness=0,
            width=vw, height=vh
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 얼린 스크린샷을 어둡게 처리해서 배경으로 표시
        dimmed = self.frozen.copy()
        dark_overlay = Image.new("RGBA", dimmed.size, (0, 0, 0, 120))
        dimmed = dimmed.convert("RGBA")
        dimmed = Image.alpha_composite(dimmed, dark_overlay)
        dimmed = dimmed.convert("RGB")

        self.bg_dimmed = ImageTk.PhotoImage(dimmed)
        self.bg_original = ImageTk.PhotoImage(self.frozen)

        # 어두운 배경 표시
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.bg_dimmed)

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.root.bind("<Escape>", self._on_escape)

        self.root.mainloop()
        return self.result_bbox

    def _on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        # 기존 선택 영역 제거
        if self.rect:
            self.canvas.delete(self.rect)
        if self.dim_overlay:
            self.canvas.delete(self.dim_overlay)

    def _on_drag(self, event):
        cur_x = event.x
        cur_y = event.y

        # 기존 밝은 영역, 선택 사각형 제거
        if self.rect:
            self.canvas.delete(self.rect)
        if self.dim_overlay:
            self.canvas.delete(self.dim_overlay)

        # 선택 영역만 원본(밝은) 이미지로 표시
        sx = min(self.start_x, cur_x)
        sy = min(self.start_y, cur_y)
        ex = max(self.start_x, cur_x)
        ey = max(self.start_y, cur_y)

        # 선택 영역을 원본 밝기로 보여주기 위해 crop
        if ex - sx > 1 and ey - sy > 1:
            crop_region = self.frozen.crop((sx, sy, ex, ey))
            self._bright_photo = ImageTk.PhotoImage(crop_region)
            self.dim_overlay = self.canvas.create_image(
                sx, sy, anchor=tk.NW, image=self._bright_photo
            )

        # 선택 영역 테두리
        self.rect = self.canvas.create_rectangle(
            sx, sy, ex, ey,
            outline="#00aaff", width=2
        )

    def _on_release(self, event):
        end_x = event.x
        end_y = event.y

        # 너무 작은 영역은 무시
        if abs(end_x - self.start_x) > 5 and abs(end_y - self.start_y) > 5:
            x1 = min(self.start_x, end_x)
            y1 = min(self.start_y, end_y)
            x2 = max(self.start_x, end_x)
            y2 = max(self.start_y, end_y)
            self.result_bbox = (x1, y1, x2, y2)

        self.root.destroy()

    def _on_escape(self, event):
        self.result_bbox = None
        self.root.destroy()


def on_hotkey():
    """단축키가 눌렸을 때 실행"""
    # 1. 누른 순간 전체 화면을 즉시 캡쳐 (얼림)
    frozen = capture_full_screen()

    # 2. 얼린 화면 위에서 영역 선택
    selector = FrozenScreenSelector(frozen)
    bbox = selector.select()

    if bbox:
        # 3. 얼린 스크린샷에서 선택 영역만 잘라내기
        x1, y1, x2, y2 = bbox
        cropped = frozen.crop((x1, y1, x2, y2))

        # 4. 파일 저장
        ensure_save_dir()
        filepath = generate_filename()
        cropped.save(str(filepath))

        # 5. 경로 클립보드 복사
        path_str = str(filepath)
        pyperclip.copy(path_str)


def create_tray_icon():
    """시스템 트레이 아이콘 생성"""
    icon_image = Image.new("RGB", (64, 64), color=(70, 130, 230))

    def on_quit(icon, item):
        icon.stop()
        keyboard.unhook_all()
        os._exit(0)

    menu = pystray.Menu(
        pystray.MenuItem(f"단축키: {HOTKEY}", lambda: None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("종료", on_quit),
    )

    icon = pystray.Icon("snap-path", icon_image, "snap-path", menu)
    return icon


def main():
    keyboard.add_hotkey(HOTKEY, lambda: threading.Thread(target=on_hotkey).start())

    icon = create_tray_icon()
    icon.run()


if __name__ == "__main__":
    main()
