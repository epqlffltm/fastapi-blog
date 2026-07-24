// 2026-07-24 글 수정 (공통 조각은 post-form.js)
// 분류·이미지는 백엔드 PATCH 가 받지 않으므로 제목·본문만 다룬다

const form = document.getElementById("edit-form");
const guard = document.getElementById("guard");
const errorEl = document.getElementById("error");
const submitBtn = document.getElementById("submit");
const titleEl = document.getElementById("title");
const contentsEl = document.getElementById("contents");

const postId = new URLSearchParams(location.search).get("id");

async function init() {
    const user = await requireVerifiedUser(guard);
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

    // 서버도 403으로 막지만, 남의 글 수정 화면을 띄울 이유가 없다
    if (post.user.id !== user.id) {
        guard.textContent = "내 글만 수정할 수 있습니다.";
        return;
    }

    titleEl.value = post.title;
    contentsEl.value = post.contents;

    guard.hidden = true;
    form.hidden = false;
}

bindSubmit(form, submitBtn, errorEl, async () => {
    await api.patch(`/page/${postId}`, {
        title: titleEl.value,
        contents: contentsEl.value,
    });
    location.href = `/post?id=${postId}`;
});

init();