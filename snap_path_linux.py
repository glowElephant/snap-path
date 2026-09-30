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
캡쳐 직후 화면 위쪽에 [✏ 편집] 버튼이 EDIT_OFFER_SEC 초 떠 있다 — 누르면 펜·네모로 표시하는 창이 열리고,
[확인](Enter)이면 표시한 이미지(`*_edit.png`)가 클립보드에, [취소](Esc)·버튼 안 누름이면 원본이 그대로 남는다.
종료는 트레이 메뉴 또는 터미널에서 Ctrl+C.
"""
import os
import subprocess
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
EDIT_OFFER_SEC = 3.0          # 캡쳐 후 [편집] 버튼이 떠 있는 시간
PEN_COLORS = ["#ff3b30", "#ffcc00", "#34c759", "#0a84ff", "#000000", "#ffffff"]
PEN_WIDTHS = [3, 6, 10]


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


def copy_to_clipboard(filepath):
    """이미지+경로+파일URL을 클립보드에 동시 탑재 (PySide6 헬퍼 상주 프로세스).

    붙여넣는 앱에 따라: 이미지 앱→그림, 텍스트 앱(CLI/메모장)→경로.
    헬퍼가 없으면 경로만 복사(pyperclip)로 폴백.
    """
    helper = Path(__file__).parent / "snap_clip_helper.py"
    if helper.is_file():
        # 이전 헬퍼 정리 ([s] 브래킷 = pkill 자기매칭 방지)
        subprocess.run(["pkill", "-f", "[s]nap_clip_helper.py"], check=False)
        subprocess.Popen([sys.executable, str(helper), filepath])
    else:
        pyperclip.copy(filepath)  # 폴백: 경로만


class EditOffer:
    """캡쳐 직후 화면 위쪽 가운데에 잠깐 뜨는 [✏ 편집] 버튼. 포커스를 뺏지 않고, 시간이 지나면 스스로 사라진다."""
    def __init__(self, root, on_edit, cx, top_y):
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        b = tk.Button(self.win, text="✏  편집", font=("Sans", 12, "bold"), bg="#0a84ff", fg="white",
                      activebackground="#0060df", activeforeground="white", relief="flat", padx=18, pady=6,
                      command=lambda: (self.close(), on_edit()))
        b.pack()
        self.win.update_idletasks()
        w = self.win.winfo_reqwidth()
        self.win.geometry(f"+{int(cx - w / 2)}+{int(top_y + 12)}")
        self.win.after(int(EDIT_OFFER_SEC * 1000), self.close)

    def close(self):
        if self.win.winfo_exists():
            self.win.destroy()


class Annotator:
    """펜·네모로 캡쳐 이미지에 표시. 화면엔 캔버스로 그리고, 같은 획을 원본 해상도 PIL 이미지에도 그린다."""
    def __init__(self, root, image):
        from PIL import ImageDraw
        self.root, self.base = root, image.convert("RGB")
        self.color, self.width, self.tool = PEN_COLORS[0], PEN_WIDTHS[1], "pen"
        self.strokes = []      # [(tool, color, width, [(x,y) 원본좌표...])]
        self.cur = None
        self.result = None
        self._draw_mod = ImageDraw

        self.top = tk.Toplevel(root)
        self.top.title("SnapPath 편집 — 확인 Enter · 취소 Esc · 되돌리기 Ctrl+Z")
        self.top.attributes("-topmost", True)
        # 화면보다 크면 줄여서 보여준다(좌표는 scale 로 되돌린다)
        sw, sh = self.top.winfo_screenwidth() * 0.9, self.top.winfo_screenheight() * 0.85
        self.scale = min(1.0, sw / self.base.width, sh / self.base.height)
        dw, dh = int(self.base.width * self.scale), int(self.base.height * self.scale)
        shown = self.base if self.scale == 1.0 else self.base.resize((dw, dh))
        self._tkimg = ImageTk.PhotoImage(shown)

        bar = tk.Frame(self.top, bg="#222")
        bar.pack(fill=tk.X)
        self.tool_btns = {}
        for key, label in (("pen", "✏ 펜"), ("rect", "▭ 네모")):
            btn = tk.Button(bar, text=label, command=lambda k=key: self._set_tool(k), relief="flat", padx=10)
            btn.pack(side=tk.LEFT, padx=2, pady=4)
            self.tool_btns[key] = btn
        tk.Label(bar, text="  ", bg="#222").pack(side=tk.LEFT)
        self.color_btns = {}
        for c in PEN_COLORS:
            btn = tk.Button(bar, bg=c, activebackground=c, width=2, relief="flat", command=lambda c=c: self._set_color(c))
            btn.pack(side=tk.LEFT, padx=2, pady=4)
            self.color_btns[c] = btn
        tk.Label(bar, text="  ", bg="#222").pack(side=tk.LEFT)
        for wd in PEN_WIDTHS:
            tk.Button(bar, text=f"{wd}px", relief="flat", command=lambda w=wd: self._set_width(w)).pack(side=tk.LEFT, padx=1)
        tk.Button(bar, text="확인", bg="#34c759", fg="white", relief="flat", padx=14,
                  command=self._ok).pack(side=tk.RIGHT, padx=4, pady=4)
        tk.Button(bar, text="취소", relief="flat", padx=10, command=self._cancel).pack(side=tk.RIGHT, padx=2)
        tk.Button(bar, text="↶ 되돌리기", relief="flat", command=self._undo).pack(side=tk.RIGHT, padx=2)

        self.canvas = tk.Canvas(self.top, width=dw, height=dh, highlightthickness=0, cursor="pencil")
        self.canvas.pack()
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self._tkimg)
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.top.bind("<Return>", lambda e: self._ok())
        self.top.bind("<Escape>", lambda e: self._cancel())
        self.top.bind("<Control-z>", lambda e: self._undo())
        self.top.protocol("WM_DELETE_WINDOW", self._cancel)
        self._set_tool("pen"); self._set_color(self.color)
        self.top.focus_force()

    def run(self):
        self.root.wait_window(self.top)
        return self.result

    def _set_tool(self, t):
        self.tool = t
        for k, b in self.tool_btns.items():
            b.configure(relief="sunken" if k == t else "flat")

    def _set_color(self, c):
        self.color = c
        for k, b in self.color_btns.items():
            b.configure(relief="sunken" if k == c else "flat", bd=3 if k == c else 1)

    def _set_width(self, w):
        self.width = w

    def _press(self, e):
        self.cur = [self.tool, self.color, self.width, [(e.x, e.y)], []]   # 화면좌표, 캔버스 id 들

    def _drag(self, e):
        if not self.cur:
            return
        tool, color, width, pts, ids = self.cur
        w = max(1, width * self.scale)
        if tool == "pen":
            x0, y0 = pts[-1]
            ids.append(self.canvas.create_line(x0, y0, e.x, e.y, fill=color, width=w, capstyle=tk.ROUND, smooth=True))
            pts.append((e.x, e.y))
        else:
            for i in ids:
                self.canvas.delete(i)
            ids[:] = [self.canvas.create_rectangle(*pts[0], e.x, e.y, outline=color, width=w)]
            pts[1:] = [(e.x, e.y)]

    def _release(self, e):
        if self.cur and len(self.cur[3]) > 1:
            self.strokes.append(self.cur)
        elif self.cur:
            for i in self.cur[4]:
                self.canvas.delete(i)
        self.cur = None

    def _undo(self):
        if self.strokes:
            for i in self.strokes.pop()[4]:
                self.canvas.delete(i)

    def render(self):
        """획을 원본 해상도에 다시 그린 이미지."""
        img = self.base.copy()
        d = self._draw_mod.Draw(img)
        k = 1 / self.scale
        for tool, color, width, pts, _ in self.strokes:
            full = [(x * k, y * k) for x, y in pts]
            if tool == "pen":
                d.line(full, fill=color, width=width, joint="curve")
                r = width / 2
                for x, y in (full[0], full[-1]):           # 선 끝을 둥글게
                    d.ellipse((x - r, y - r, x + r, y + r), fill=color)
            else:
                (x0, y0), (x1, y1) = full[0], full[-1]
                d.rectangle((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)), outline=color, width=width)
        return img

    def _ok(self):
        self.result = self.render() if self.strokes else None   # 아무것도 안 그렸으면 원본 유지
        self.top.destroy()

    def _cancel(self):
        self.result = None
        self.top.destroy()


def offer_edit(root, filepath, cx, top_y):
    """[편집] 버튼을 띄우고, 누르면 편집 → 확인 시 *_edit.png 저장 + 클립보드 교체."""
    def on_edit():
        edited = Annotator(root, Image.open(filepath)).run()
        if edited is None:
            return                                   # 원본이 이미 클립보드에 있다
        out = Path(filepath).with_name(Path(filepath).stem + "_edit.png")
        edited.save(str(out))
        copy_to_clipboard(str(out))
        print(f"편집본: {out}")
    EditOffer(root, on_edit, cx, top_y)


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
                copy_to_clipboard(str(filepath))
            except Exception as e:
                print(f"클립보드 복사 실패: {e}")
            print(f"저장됨: {filepath}")
            # 편집 버튼은 캡쳐한 영역이 있던 모니터의 위쪽 가운데에
            mcx = off_x + (bbox[0] + bbox[2]) / 2
            mcy = off_y + (bbox[1] + bbox[3]) / 2
            with mss.mss() as sct:
                mon = next((m for m in sct.monitors[1:] if m["left"] <= mcx < m["left"] + m["width"]
                            and m["top"] <= mcy < m["top"] + m["height"]), sct.monitors[0])
            offer_edit(root, str(filepath), mon["left"] + mon["width"] / 2, mon["top"])
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
