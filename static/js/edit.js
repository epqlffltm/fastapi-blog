// 2026-07-24 글 수정 (공통 조각은 post-form.js)
// 분류는 백엔드 PATCH 가 받지 않으므로 제목·본문만 다룬다

const form = document.getElementById("edit-form");
const guard = document.getElementById("guard");
const errorEl = document.getElementById("error");
const submitBtn = document.getElementById("submit");
const titleEl = document.getElementById("title");

const postId = new URLSearchParams(location.search).get("id");
let editor = null;

async function init() {
    // 수정은 권한이 꺼져도 자기 글이면 되므로, 제재 여부만 확인한다
    const user = await requirePermission(guard, "is_verified", "수정할 수 없습니다.");
    if (!user) return;

    if (!postId) {
        guard.textContent = "잘못된 주소입니다.";
        return;
    }

    let post;
    try {
        post = await api.get(`/page/${postId}`);
    } catch (err) {
        guard.textContent = err.message;
        return;
    }
    
    // 서버도 403으로 막지만, 남의 글 수정 화면을 띄울 이유가 없다.
    // 관리자(can_manage_post)는 남의 글도 수정할 수 있다
    if (post.user.id !== user.id && !user.can_manage_post) {
        guard.textContent = "내 글만 수정할 수 있습니다.";
        return;
    }
    titleEl.value = post.title;

    guard.hidden = true;
    form.hidden = false;

    // 저장돼 있던 마크다운을 그대로 넣으면 위지윅이 알아서 렌더한다
    editor = createEditor(document.getElementById("editor"), post.contents);
}

bindSubmit(form, submitBtn, errorEl, async () => {
    const contents = editor.getMarkdown();
    if (!contents.trim()) {
        throw new Error("본문을 입력해 주세요.");
    }

    await api.patch(`/page/${postId}`, {
        title: titleEl.value,
        contents,
    });
    location.href = `/post?id=${postId}`;
});

init();