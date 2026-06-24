# snap-path

화면을 캡쳐하고 저장된 파일 경로를 클립보드에 자동 복사하는 유틸리티.

- **Windows**: `snap_path.pyw` (Win32 API 기반)
- **Linux (X11)**: `snap_path_linux.py` (pynput + mss 기반)

## 기능

- **단축키 한 번**으로 화면 캡쳐 → 저장 → 경로 클립보드 복사
- **화면 얼림(Freeze)** — 단축키를 누른 순간의 화면을 정지시켜 캡쳐 (영상 재생 중에도 정확한 순간 캡쳐 가능)
- **멀티 모니터 지원** — 모니터 개수에 상관없이 모든 화면에서 캡쳐 가능
- **고해상도(DPI) 대응** — 4K 등 고해상도 모니터에서도 정확한 좌표 캡쳐
- **백그라운드 실행** — 시스템 트레이에 상주, 콘솔 창 없음

## 사용법

### exe 빌드 (권장)

Python 없는 PC에서도 실행 가능한 단일 exe 파일을 생성합니다.

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name snap-path snap_path.pyw
```

빌드 완료 후 `dist/snap-path.exe`가 생성됩니다.

### 실행

```bash
# exe 실행 (Python 불필요)
dist\snap-path.exe

# 또는 Python으로 직접 실행
pyw snap_path.pyw
```

### 캡쳐

1. `Ctrl+Alt+S` — 화면이 얼리면서 어둡게 변함
2. 마우스 드래그로 영역 선택 (선택 영역만 밝게 표시)
3. 놓으면 자동 저장 + 경로 클립보드 복사
4. `Ctrl+V`로 경로 붙여넣기
5. `ESC` — 캡쳐 취소

### 종료

시스템 트레이 아이콘 우클릭 → 종료

## 저장 경로

```
C:\Users\{사용자}\Pictures\SnapPath\screenshot_YYYYMMDD_HHMMSS.png
```

## Windows 시작 프로그램 등록

[graph-RAG-study](https://github.com/glowElephant/graph-RAG-study)의 `setup.py`가 자동으로 시작 프로그램에 등록합니다.

해제: `Win+R` → `shell:startup` → `snap-path.lnk` 삭제

## 의존성 (Windows)

- keyboard — 글로벌 단축키 감지
- Pillow — 스크린샷 캡쳐 및 이미지 처리
- pyperclip — 클립보드 복사
- pystray — 시스템 트레이 아이콘
- screeninfo — 멀티 모니터 정보 감지

---

## Linux (X11)

리눅스 버전은 `snap_path_linux.py`입니다. **X11 세션에서 동작** (Wayland는 글로벌 핫키가 OS 레벨에서 차단되어 미지원).

### 설치

```bash
# 시스템 패키지 (tkinter, ImageTk, 클립보드 백엔드, 트레이)
sudo apt install python3-tk python3-pil.imagetk xclip gir1.2-ayatanaappindicator3-0.1

# Python 패키지
pip install -r requirements-linux.txt
```

### 실행

```bash
python3 snap_path_linux.py
```

`Ctrl+Alt+S` → 화면 얼림 → 드래그로 영역 선택 → 자동 저장 + 경로 클립보드 복사. 사용법은 Windows와 동일.

종료는 트레이 메뉴 또는 터미널에서 `Ctrl+C`.

### 저장 경로

```
~/Pictures/SnapPath/screenshot_YYYYMMDD_HHMMSS.png
```

### Windows 버전과의 구현 차이

| 기능 | Windows | Linux |
|------|---------|-------|
| 글로벌 핫키 | Win32 `RegisterHotKey` | pynput (X11) |
| 멀티모니터 캡쳐 | `ImageGrab.grab(all_screens=True)` | mss (가상 스크린 전체) |
| DPI 인식 | `ctypes.windll` | 불필요 (제거) |
| 트레이 | pystray (Win32) | pystray (AppIndicator) |

> **GNOME 주의**: GNOME은 기본 시스템 트레이가 없어 트레이 아이콘이 안 보일 수 있습니다. 트레이 표시에 실패해도 핫키·캡쳐·저장·클립보드 등 핵심 기능은 정상 동작합니다.

### 의존성 (Linux)

- mss — 멀티 모니터 스크린샷 캡쳐
- pynput — X11 글로벌 단축키 감지
- pyperclip — 클립보드 복사 (xclip/xsel 백엔드 필요)
- pystray — 시스템 트레이 아이콘 (선택)
- Pillow — 이미지 처리
