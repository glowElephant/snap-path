#!/usr/bin/env python3
"""snap-path 클립보드 헬퍼 (Linux/X11).

캡처 이미지 파일 하나를 받아 **이미지·경로·파일URL을 클립보드에 동시 탑재**하고
상주한다. 붙여넣는 앱이 자기가 받을 수 있는 포맷을 고른다:
  - image/*      → PPT·노션·카톡 등 이미지 받는 앱
  - text/plain   → CLI·메모장·에디터 등 텍스트만 받는 곳 (파일 경로)
  - text/uri-list→ 파일 매니저

X11 클립보드는 소유 프로세스가 죽으면 내용이 사라지므로(클립보드 매니저 없을 때),
이 프로세스가 상주하며 소유를 유지한다. 다른 앱이 새로 복사해 소유권을 잃으면 스스로 종료.

usage: snap_clip_helper.py <image_path>
"""
import sys
from pathlib import Path

from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtGui import QGuiApplication, QImage


def main():
    if len(sys.argv) < 2:
        print("usage: snap_clip_helper.py <image_path>", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    if not Path(path).is_file():
        print(f"파일 없음: {path}", file=sys.stderr)
        sys.exit(1)

    app = QGuiApplication(sys.argv)

    img = QImage(path)
    if img.isNull():
        print(f"이미지 로드 실패: {path}", file=sys.stderr)
        sys.exit(1)

    mime = QMimeData()
    mime.setImageData(img)                       # image/* (PPT·노션 등)
    mime.setText(path)                           # text/plain (CLI·메모장 등)
    mime.setUrls([QUrl.fromLocalFile(path)])     # text/uri-list (파일 매니저)

    clipboard = app.clipboard()
    clipboard.setMimeData(mime)

    # 다른 앱이 클립보드를 가져가 소유권을 잃으면 종료 (상주 정리)
    def on_changed():
        if not clipboard.ownsClipboard():
            app.quit()

    clipboard.dataChanged.connect(on_changed)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
