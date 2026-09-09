#!/usr/bin/env bash
# snap-path 데모용 화면 녹화 → 고화질 GIF 자동 변환 (ffmpeg x11grab)
# x11grab은 루트 윈도우 픽셀을 통째로 캡쳐하므로 snap-path의 얼림/선택 오버레이도 찍힌다.
#
# 사용법:
#   ./record-gif.sh [duration_sec] [WxH+X+Y] [gif_width]
# 예:
#   ./record-gif.sh                     # 12초, 주 모니터 전체, GIF 폭 1000
#   ./record-gif.sh 15                  # 15초 녹화
#   ./record-gif.sh 12 1280x720+300+200 # 특정 영역만 (권장: 작고 집중된 GIF)
#   ./record-gif.sh 12 2560x1440+0+0 900

set -euo pipefail

DUR="${1:-12}"
REGION="${2:-2560x1440+0+0}"   # 주 모니터 DP-0
GIFW="${3:-1000}"
DISPLAY="${DISPLAY:-:1}"
export DISPLAY

# WxH+X+Y 파싱
SIZE="${REGION%%+*}"                     # 2560x1440
OFF="${REGION#*+}"; OFF="+${OFF}"        # +0+0
OUTDIR="$HOME/Pictures/SnapPath"
mkdir -p "$OUTDIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
RAW="/tmp/snap-rec-$STAMP.mp4"
GIF="$OUTDIR/snap-path-demo-$STAMP.gif"

echo "녹화 영역: ${SIZE}${OFF} | 시간: ${DUR}s | GIF 폭: ${GIFW}px"
echo "곧 녹화 시작합니다. 준비하세요 (터미널/에디터 미리 열어두기)."
for i in 3 2 1; do echo "  $i..."; sleep 1; done
echo "● 녹화 시작 — 지금 Ctrl+Alt+S 로 snap-path 시연하세요!"

ffmpeg -y -hide_banner -loglevel error \
  -f x11grab -framerate 20 -video_size "$SIZE" -i "${DISPLAY}.0${OFF}" \
  -t "$DUR" -pix_fmt yuv420p "$RAW"

echo "■ 녹화 끝. GIF 변환 중..."
ffmpeg -y -hide_banner -loglevel error -i "$RAW" \
  -filter_complex "fps=12,scale=${GIFW}:-1:flags=lanczos,split[s0][s1];[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=bayer" \
  "$GIF"

rm -f "$RAW"
SIZE_KB=$(du -k "$GIF" | cut -f1)
echo "✅ 완성: $GIF (${SIZE_KB}KB)"
