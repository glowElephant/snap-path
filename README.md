# snap-path

화면을 캡쳐하고 저장된 파일 경로를 클립보드에 자동 복사하는 Windows 유틸리티.

## 기능

- **단축키 한 번**으로 화면 캡쳐 → 저장 → 경로 클립보드 복사
- **화면 얼림(Freeze)** — 단축키를 누른 순간의 화면을 정지시켜 캡쳐 (영상 재생 중에도 정확한 순간 캡쳐 가능)
- **멀티 모니터 지원** — 모니터 개수에 상관없이 모든 화면에서 캡쳐 가능
- **고해상도(DPI) 대응** — 4K 등 고해상도 모니터에서도 정확한 좌표 캡쳐
- **백그라운드 실행** — 시스템 트레이에 상주, 콘솔 창 없음

## 사용법

### 설치

```bash
pip install -r requirements.txt
```

### 실행

```bash
# 콘솔 창 표시
python snap_path.py

# 콘솔 없이 백그라운드 실행
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

```powershell
powershell -ExecutionPolicy Bypass -File create_shortcut.ps1
```

실행하면 Windows 시작 폴더에 바로가기가 생성되어 부팅 시 자동 실행됩니다.

해제: `Win+R` → `shell:startup` → `snap-path.lnk` 삭제

## 의존성

- keyboard — 글로벌 단축키 감지
- Pillow — 스크린샷 캡쳐 및 이미지 처리
- pyperclip — 클립보드 복사
- pystray — 시스템 트레이 아이콘
- screeninfo — 멀티 모니터 정보 감지
