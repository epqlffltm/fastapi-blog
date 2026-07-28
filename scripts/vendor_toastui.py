#scripts/vendor_toastui.py

'''
2026-07-28
TOAST UI Editor 자산 내려받기 (CDN latest → 자체 호스팅)

CDN 의 latest 를 직접 물면 두 가지가 문제다.
  1. 라이브러리가 breaking change 를 내면 커밋 하나 없이 사이트가 깨진다.
  2. CDN 이 오염되면 임의 JS 가 우리 오리진에서 실행된다.
     인증이 쿠키라서 그 스크립트는 로그인한 사용자로 행세할 수 있다.

자체 호스팅하면 둘 다 사라진다. 받은 파일은 저장소에 커밋한다 (재현성).

사용법:
    uv run python scripts/vendor_toastui.py 3.2.2

버전은 https://github.com/nhn/tui.editor/releases 에서 확인.
'''

import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://uicdn.toast.com/editor"
DEST = Path(__file__).resolve().parent.parent / "static" / "vendor" / "toastui"

FILES = (
    "toastui-editor-all.min.js",
    "toastui-editor.min.css",
    "toastui-editor-viewer.min.css",
    "theme/toastui-editor-dark.css",
    "i18n/ko-kr.js",
)

# 이보다 작으면 정상 파일일 리 없다. 빈 파일이 커밋되고
# 배포 후에야 발견되는 상황을 막는다
MIN_BYTES = 100


def vendor(version: str) -> None:
    print(f"TOAST UI Editor {version} → {DEST}\n")

    for name in FILES:
        url = f"{BASE}/{version}/{name}"
        target = DEST / name
        target.parent.mkdir(parents=True, exist_ok=True)

        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                data = response.read()
        except urllib.error.HTTPError as exc:
            # 없는 버전이나 바뀐 경로를 조용히 넘기지 않는다
            raise SystemExit(
                f"  실패 ({exc.code}): {url}\n"
                f"  버전 번호나 경로를 확인하세요."
            ) from exc
        except urllib.error.URLError as exc:
            raise SystemExit(f"  연결 실패: {url}\n  {exc.reason}") from exc

        if len(data) < MIN_BYTES:
            raise SystemExit(f"  의심스러움: {name} 이 {len(data)}바이트뿐입니다")

        target.write_bytes(data)
        print(f"  {name:<40} {len(data):>8,} bytes")

    print("\n완료. static/vendor/ 를 커밋하세요.")
    print("업그레이드할 때는 새 버전으로 다시 돌리면 됩니다.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: uv run python scripts/vendor_toastui.py <version>")
        print("  예)   uv run python scripts/vendor_toastui.py 3.2.2")
        sys.exit(1)

    vendor(sys.argv[1])
