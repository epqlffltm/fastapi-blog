// 2026-07-28 설정 페이지
// 작성한 글/댓글 상단 + 페이지네이션
// 내 프로필 보기 → /user/{내id}

const PAGE_SIZE = 10;

const form = document.getElementById("profile-form");
const emailEl = document.getElementById("email");
const nicknameEl = document.getElementById("nickname");
const bioEl = document.getElementById("bio");
const errorEl = document.getElementById("profile-error");
const doneEl = document.getElementById("profile-done");
const submitBtn = document.getElementById("profile-submit");
const section = document.getElementById("profile");
const statusEl = document.getElementById("status");
const viewProfileLink = document.getElementById("view-profile-link");

const avatarPreview = document.getElementById("avatar-preview");
const avatarInput = document.getElementById("avatar-input");
const avatarBtn = document.getElementById("avatar-btn");
const avatarError = document.getElementById("avatar-error");

const passwordForm = document.getElementById("password-form");
const currentPwEl = document.getElementById("current-password");
const newPwEl = document.getElementById("new-password");
const pwErrorEl = document.getElementById("password-error");
const pwDoneEl = document.getElementById("password-done");
const pwSubmitBtn = document.getElementById("password-submit");
const otpEl = document.getElementById("otp");
const otpBtn = document.getElementById("otp-btn");
const otpHint = document.getElementById("otp-hint");

const postsEl = document.getElementById("my-posts");
const postsEmptyEl = document.getElementById("my-posts-empty");
const postsPaginationEl = document.getElementById("my-posts-pagination");
const commentsEl = document.getElementById("my-comments");
const commentsEmptyEl = document.getElementById("my-comments-empty");
const commentsPaginationEl = document.getElementById("my-comments-pagination");

let myId = null;

async function init() {
    const user = await renderHeader();

    if (!user) {
        statusEl.textContent = "로그인이 필요합니다.";
        return;
    }

    myId = user.id;
    emailEl.value = user.email;
    nicknameEl.value = user.nickname;
    bioEl.value = user.bio || "";
    renderAvatar(user.avatar_url);

    if (viewProfileLink) {
        viewProfileLink.href = `/user/${user.id}`;
    }

    statusEl.hidden = true;
    section.hidden = false;

    // 반드시 글/댓글 로드
    await loadPosts(1);
    await loadComments(1);
}

function createPostItem(post) {
    const li = document.createElement("li");
    const link = document.createElement("a");
    link.href = `/post?id=${post.id}`;
    link.textContent = post.title;

    if (post.is_deleted) {
        li.classList.add("deleted-post");
        const badge = document.createElement("span");
        badge.className = "deleted-badge";
        badge.textContent = "삭제됨";
        li.append(link, badge);
    } else {
        li.append(link);
    }

    const meta = document.createElement("span");
    meta.className = "meta";
    meta.textContent =
        ` · ${formatDate(post.created_at)}` +
        ` · 조회 ${post.view_count}` +
        ` · 좋아요 ${post.like_count}` +
        ` · 댓글 ${post.comment_count}`;
    li.append(meta);
    return li;
}

function createCommentItem(comment) {
    const li = document.createElement("li");
    if (comment.parent_id) li.classList.add("reply");
    if (comment.is_deleted) li.classList.add("deleted");

    const context = document.createElement("div");
    context.className = "meta";

    const postLink = document.createElement("a");
    postLink.href = `/post?id=${comment.post.id}`;
    postLink.textContent = comment.post.title || "(제목 없음)";
    context.append(postLink);

    const label = document.createElement("span");
    label.textContent = comment.parent_id ? " · 대댓글" : " · 댓글";
    context.append(label);

    const body = document.createElement("div");
    body.className = "comment-body";
    body.textContent = comment.is_deleted ? "삭제된 댓글입니다." : comment.contents;
    if (comment.is_deleted) body.classList.add("deleted");

    const date = document.createElement("div");
    date.className = "meta";
    date.textContent = formatDate(comment.created_at);

    li.append(context, body, date);
    return li;
}

function renderPagination(container, page, totalPages, onPage) {
    container.replaceChildren();
    if (!totalPages || totalPages <= 1) return;

    const prev = document.createElement("button");
    prev.type = "button";
    prev.textContent = "이전";
    prev.disabled = page <= 1;
    prev.addEventListener("click", () => onPage(page - 1));

    const status = document.createElement("span");
    status.className = "pagination-status";
    status.textContent = `${page} / ${totalPages}`;

    const next = document.createElement("button");
    next.type = "button";
    next.textContent = "다음";
    next.disabled = page >= totalPages;
    next.addEventListener("click", () => onPage(page + 1));

    container.append(prev, status, next);
}

async function loadPosts(page = 1) {
    if (!myId) return;

    postsEl.replaceChildren();
    postsEmptyEl.hidden = true;
    postsPaginationEl.replaceChildren();

    try {
        const data = await api.get(
            `/pages?author=${myId}&order=desc&page=${page}&size=${PAGE_SIZE}`
        );
        console.log("posts response:", data);

        if (!data.posts || data.posts.length === 0) {
            postsEmptyEl.hidden = false;
            return;
        }
        for (const post of data.posts) {
            postsEl.append(createPostItem(post));
        }
        renderPagination(postsPaginationEl, data.page, data.total_pages, loadPosts);
    } catch (err) {
        console.error("post list load failed:", err);
        postsEmptyEl.textContent = err.message || "글 목록을 불러오지 못했습니다.";
        postsEmptyEl.hidden = false;
    }
}

async function loadComments(page = 1) {
    if (!myId) return;

    commentsEl.replaceChildren();
    commentsEmptyEl.hidden = true;
    commentsPaginationEl.replaceChildren();

    try {
        const data = await api.get(
            `/user/${myId}/comments?page=${page}&size=${PAGE_SIZE}`
        );
        console.log("comments response:", data);

        if (!data.comments || data.comments.length === 0) {
            commentsEmptyEl.hidden = false;
            return;
        }
        for (const c of data.comments) {
            commentsEl.append(createCommentItem(c));
        }
        renderPagination(commentsPaginationEl, data.page, data.total_pages, loadComments);
    } catch (err) {
        console.error("comment list load failed:", err);
        commentsEmptyEl.textContent = err.message || "댓글 목록을 불러오지 못했습니다.";
        commentsEmptyEl.hidden = false;
    }
}

form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorEl.textContent = "";
    doneEl.hidden = true;
    submitBtn.disabled = true;

    try {
        const updated = await api.patch("/user/me", {
            nickname: nicknameEl.value.trim(),
            bio: bioEl.value,
        });
        nicknameEl.value = updated.nickname;
        bioEl.value = updated.bio || "";
        doneEl.hidden = false;
    } catch (err) {
        errorEl.textContent = err.message;
    } finally {
        submitBtn.disabled = false;
    }
});

otpBtn.addEventListener("click", async () => {
    pwErrorEl.textContent = "";
    otpHint.hidden = true;
    otpBtn.disabled = true;
    try {
        await api.post("/user/me/password/otp", {});
        otpHint.hidden = false;
    } catch (err) {
        pwErrorEl.textContent = err.message;
    } finally {
        otpBtn.disabled = false;
    }
});

passwordForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    pwErrorEl.textContent = "";
    pwDoneEl.hidden = true;
    pwSubmitBtn.disabled = true;

    try {
        await api.patch("/user/me/password", {
            current_password: currentPwEl.value,
            new_password: newPwEl.value,
            otp: Number(otpEl.value),
        });
        currentPwEl.value = "";
        newPwEl.value = "";
        otpEl.value = "";
        otpHint.hidden = true;
        pwDoneEl.hidden = false;
    } catch (err) {
        pwErrorEl.textContent = err.message;
    } finally {
        pwSubmitBtn.disabled = false;
    }
});

function renderAvatar(url) {
    if (url) {
        avatarPreview.src = url;
        avatarPreview.classList.remove("empty");
    } else {
        avatarPreview.removeAttribute("src");
        avatarPreview.classList.add("empty");
    }
}

avatarBtn.addEventListener("click", () => avatarInput.click());

avatarInput.addEventListener("change", async () => {
    const file = avatarInput.files[0];
    if (!file) return;
    avatarError.textContent = "";
    avatarBtn.disabled = true;

    try {
        const formData = new FormData();
        formData.append("file", file);
        const res = await fetch("/user/me/avatar", { method: "POST", body: formData });
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            throw new Error(data.detail || "업로드 실패");
        }
        const updated = await res.json();
        renderAvatar(updated.avatar_url);
        renderHeader();
    } catch (err) {
        avatarError.textContent = err.message;
    } finally {
        avatarBtn.disabled = false;
        avatarInput.value = "";
    }
});

init();