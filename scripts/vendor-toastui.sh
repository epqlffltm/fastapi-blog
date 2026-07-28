#!/usr/bin/env bash
#
# TOAST UI Editor 자산을 static/vendor/toastui/ 로 내려받는다.
#
# CDN 의 latest 를 직접 물면 두 가지가 문제다.
#   1. 라이브러리가 breaking change 를 내면 커밋 하나 없이 사이트가 깨진다.
#   2. CDN 이 오염되면 임의 JS 가 우리 오리진에서 실행된다.
#      인증이 쿠키라서 그 스크립트는 로그인한 사용자로 행세할 수 있다.
#
# 자체 호스팅하면 둘 다 사라진다. 받은 파일은 저장소에 커밋한다 (재현성).
#
# 사용법:  ./scripts/vendor-toastui.sh 3.2.2
#          버전은 https://github.com/nhn/tui.editor/releases 에서 확인

set -euo pipefail

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
    echo "사용법: $0 <version>   예) $0 3.2.2" >&2
    exit 1
fi

BASE="https://uicdn.toast.com/editor/${VERSION}"
DEST="$(cd "$(dirname "$0")/.." && pwd)/static/vendor/toastui"

FILES=(
    "toastui-editor-all.min.js"
    "toastui-editor.min.css"
    "toastui-editor-viewer.min.css"
    "theme/toastui-editor-dark.css"
    "i18n/ko-kr.js"
)

mkdir -p "$DEST/theme" "$DEST/i18n"

echo "TOAST UI Editor ${VERSION} → ${DEST}"
echo

for path in "${FILES[@]}"; do
    url="${BASE}/${path}"
    out="${DEST}/${path}"

    # 존재하지 않는 버전이나 바뀐 경로를 조용히 넘기지 않는다.
    # 여기서 안 잡으면 빈 파일이 커밋되고 배포 후에야 발견된다
    code=$(curl -sS -o "$out" -w "%{http_code}" "$url")
    if [[ "$code" != "200" ]]; then
        rm -f "$out"
        echo "  실패 ($code): $url" >&2
        echo "  버전 번호나 경로를 확인하세요." >&2
        exit 1
    fi

    size=$(wc -c < "$out")
    if [[ "$size" -lt 100 ]]; then
        echo "  의심스러움: $path 가 ${size}바이트뿐입니다" >&2
        exit 1
    fi

    printf "  %-40s %8s bytes\n" "$path" "$size"
done

echo
echo "완료. static/vendor/ 를 커밋하세요."
echo "업그레이드할 때는 이 스크립트를 새 버전으로 다시 돌리면 됩니다."
