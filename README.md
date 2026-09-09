# snap-path

화면을 캡쳐하고 저장된 파일 경로를 클립보드에 자동 복사하는 유틸리티.

- **Windows**: `snap_path.pyw` (Win32 API 기반)
- **Linux (X11)**: `snap_path_linux.py` (pynput + mss 기반)

## 기능

- **단축키 한 번**으로 화면 캡쳐 → 저장 → 클립보드 복사
- **경로 / 이미지 단축키 분리** (Windows) — `Ctrl+Alt+S`는 저장 경로만, `Ctrl+Alt+Shift+S`는 이미지만 복사
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

1. `Ctrl+Alt+S`(경로) 또는 `Ctrl+Alt+Shift+S`(이미지) — 화면이 얼리면서 어둡게 변함
2. 마우스 드래그로 영역 선택 (선택 영역만 밝게 표시)
3. 놓으면 자동 저장 + 클립보드 복사
4. `Ctrl+V`로 붙여넣기
5. `ESC` — 캡쳐 취소

### 클립보드 동작 (Windows)

두 단축키 모두 파일은 저장하고, **클립보드에 올리는 내용만 다릅니다.**

| 단축키 | 클립보드 포맷 | 쓰는 곳 |
|--------|--------------|---------|
| `Ctrl+Alt+S` | `CF_UNICODETEXT` (저장 경로) | 터미널, 주소창, AI 프롬프트 |
| `Ctrl+Alt+Shift+S` | `CF_DIB` (이미지 비트맵) | 카카오톡, 워드, 파워포인트 |

**한 번에 한 포맷만 올립니다.** 경로와 이미지를 함께 올리면 카카오톡·워드처럼 둘 다 받는 앱이 이미지에 경로 텍스트까지 붙여넣습니다.

`win32clipboard`(pywin32) 대신 `ctypes`로 Win32 API를 직접 호출합니다 — 기존 `RegisterHotKey` 코드와 방식을 맞추고 exe 크기를 늘리지 않기 위함입니다. 경로 복사가 실패하면 `pyperclip`으로 폴백합니다.

#### 시도했다가 되돌린 것: 지연 렌더링 자동 판별

붙여넣는 앱에 따라 자동으로 포맷을 고르게 하려고 **지연 렌더링**(`SetClipboardData(fmt, NULL)`로 포맷만 광고하고 `WM_RENDERFORMAT`에서 요청받은 하나만 채우는 방식)을 구현했다가 되돌렸습니다. 실패 이유:

- Windows 클립보드 히스토리 등 **시스템 클립보드 모니터가 등록 직후 `CF_DIB` 렌더를 즉시 유발**합니다. 한 번 렌더되면 실제 데이터가 클립보드에 박혀서, 이후 앱의 요청은 `WM_RENDERFORMAT` 없이 그대로 읽힙니다. "한 번에 한 포맷만 준다"는 제어가 무력화됩니다.
- 클립보드는 수동적이라 **누가 붙여넣는지 알 방법이 없습니다.** 시간 창(예: 0.4초)으로 같은 붙여넣기를 묶는 방식은 시스템 모니터의 선행 렌더 때문에 신뢰할 수 없습니다.
- 지연 렌더링은 **프로세스가 살아있어야** 유지됩니다. 앱이 죽으면 클립보드 내용이 사라집니다.

구현 중 만난 함정도 기록해 둡니다: `SetClipboardData(fmt, NULL)`은 **성공해도 NULL을 반환**하므로 반환값으로 실패를 판단하면 안 됩니다 (`SetLastError(0)` 후 `GetLastError()`로 확인). 이걸 오판해서 두 번째 포맷이 등록되지 않는 버그가 있었습니다.

> **리눅스는 경로 텍스트만** 복사합니다. X11 클립보드는 소유 프로세스가 `TARGETS`로 여러 MIME 타입을 광고해야 하는데, `xclip`은 실행당 한 타깃(`-t`)만 서빙합니다.

### 종료

시스템 트레이 아이콘 우클릭 → 종료

## 저장 경로

```
C:\Users\{사용자}\Pictures\SnapPath\screenshot_YYYYMMDD_HHMMSS.png
```

## Windows 시작 프로그램 등록

바로가기는 **exe를 직접** 가리켜야 합니다. Python 런처(`pyw.exe`)를 거치면 Python을 재설치·업그레이드할 때 경로가 깨져서 부팅 시 조용히 실행 실패합니다. 실제로 `...\Python313\pyw.exe`를 가리키던 바로가기가 그 파일이 사라지면서 동작을 멈춘 적이 있습니다 (Python 3.13 폴더에는 `python.exe`만 있고 런처는 `C:\WINDOWS\pyw.exe`에 있음).

```powershell
$startup = [Environment]::GetFolderPath('Startup')
$exe = "$PWD\dist\snap-path.exe"
$sh = New-Object -ComObject WScript.Shell
$lnk = $sh.CreateShortcut("$startup\snap-path.lnk")
$lnk.TargetPath = $exe
$lnk.WorkingDirectory = Split-Path $exe
$lnk.IconLocation = "$exe,0"
$lnk.Save()
```

확인: `$sh.CreateShortcut("$startup\snap-path.lnk").TargetPath` 가 실제 존재하는지 `Test-Path`로 검증

해제: `Win+R` → `shell:startup` → `snap-path.lnk` 삭제

> 소스를 고친 뒤에는 **exe를 다시 빌드**해야 반영됩니다. 시작 프로그램은 exe를 실행하므로 `.pyw`만 수정하면 부팅 시에는 옛 동작이 그대로입니다.

## 의존성 (Windows)

- Pillow — 스크린샷 캡쳐 및 이미지 처리
- pyperclip — 클립보드 복사 폴백 (주 경로는 `ctypes` Win32 호출)
- pystray — 시스템 트레이 아이콘
- screeninfo — 멀티 모니터 정보 감지

글로벌 단축키와 클립보드는 표준 라이브러리 `ctypes`로 Win32 API를 직접 호출합니다 (`keyboard` 라이브러리는 f0da606에서 제거).

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

`Ctrl+Alt+S` → 화면 얼림 → 드래그로 영역 선택 → 자동 저장 + 클립보드 복사.

종료는 트레이 메뉴 또는 터미널에서 `Ctrl+C`.

### 클립보드 — Windows 와 방식이 다르다

Windows 는 단축키를 둘로 갈라 **한 번에 한 포맷만** 올린다(둘 다 올리면 카톡·워드에서
이미지에 경로까지 딸려 붙기 때문). Linux 는 반대로 `snap_clip_helper.py` 가
**이미지·경로·파일URL 을 한 번에 탑재**하고 붙여넣는 앱이 고르게 한다.

| 포맷 | 받는 곳 |
|---|---|
| `image/*` | PPT · 노션 · 카톡 |
| `text/plain` | 터미널 · 에디터 (경로 문자열) |
| `text/uri-list` | 파일 매니저 |

X11 클립보드는 **소유 프로세스가 죽으면 내용이 사라진다**(클립보드 매니저가 없을 때).
그래서 헬퍼가 상주하며 소유를 유지하고, 다른 앱이 새로 복사해 소유권을 잃으면 스스로 종료한다.
헬퍼가 없으면 `pyperclip` 으로 경로만 복사하는 폴백으로 떨어진다.

⚠ **아직 실사용 검증 전이다.** Windows 가 같은 방식을 넣었다가 되돌린 이력이 있으므로
(`6d5e516` → `6c22217`), 리눅스에서도 같은 증상이 나면 단축키 분리로 바꿀 것.

### 데모 GIF 녹화

`record-gif.sh` — ffmpeg x11grab 으로 화면을 녹화해 GIF 로 변환한다. x11grab 은 루트
윈도우를 통째로 찍으므로 snap-path 의 얼림·선택 오버레이도 그대로 담긴다.

```bash
./record-gif.sh                     # 12초, 주 모니터 전체, GIF 폭 1000
./record-gif.sh 12 1280x720+300+200 # 특정 영역만 (권장 — 작고 집중된 GIF)
```

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
| 클립보드 | 경로/이미지 단축키 분리 (`CF_UNICODETEXT` 또는 `CF_DIB`) | 헬퍼 상주, 세 포맷 동시 (`snap_clip_helper.py`) |

> **GNOME 주의**: GNOME은 기본 시스템 트레이가 없어 트레이 아이콘이 안 보일 수 있습니다. 트레이 표시에 실패해도 핫키·캡쳐·저장·클립보드 등 핵심 기능은 정상 동작합니다.

### 의존성 (Linux)

- mss — 멀티 모니터 스크린샷 캡쳐
- pynput — X11 글로벌 단축키 감지
- pyperclip — 클립보드 복사 (xclip/xsel 백엔드 필요)
- pystray — 시스템 트레이 아이콘 (선택)
- Pillow — 이미지 처리
- PySide6 — 클립보드 헬퍼(`snap_clip_helper.py`) 전용. 없으면 경로만 복사로 폴백
