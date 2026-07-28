// 2026-07-28 공개 프로필: 소개 박스 + 글/댓글 좌우 박스 + 페이지네이션
// 본인/타인 모두 글·댓글 표시. 본인일 때만 설정 버튼

const PAGE_SIZE = 10;

const statusEl = document.getElementById("status");
const section = document.getElementById("user-profile");
const avatarEl = document.getElementById("pub-avatar");
const nicknameEl = document.getElementById("pub-nickname");
const bioEl = document.getElementById("pub-bio");
const postsEl = document.getElementById("pub-posts");
const postsEmptyEl = document.getElementById("pub-posts-empty");
const postsPaginationEl = document.getElementById("posts-pagination");
const commentsEl = document.getElementById("pub-comments");
const commentsEmptyEl = document.getElementById("pub-comments-empty");
const commentsPaginationEl = document.getElementById("comments-pagination");
const commentsBox = document.getElementById("comments-box");
const actionsEl = document.getElementById("profile-actions");

let currentUserId = null;
let postsPage = 1;
let commentsPage = 1;

function getUserIdFromPath() {
    const parts = location.pathname.split("/").filter(Boolean);
    return parts[parts.length - 1];
}

function renderAvatar(url) {
    if (url) {
        avatarEl.src = url;
        avatarEl.classList.remove("empty");
    } else {
        avatarEl.removeAttribute("src");
        avatarEl.classList.add("empty");
    }
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
    if (totalPages <= 1) return;

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
    postsPage = page;
    postsEl.replaceChildren();
    postsEmptyEl.hidden = true;
    postsPaginationEl.replaceChildren();

    try {
        const data = await api.get(
            `/pages?author=${currentUserId}&order=desc&page=${page}&size=${PAGE_SIZE}`
        );
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
    commentsPage = page;
    commentsEl.replaceChildren();
    commentsEmptyEl.hidden = true;
    commentsPaginationEl.replaceChildren();

    try {
        const data = await api.get(
            `/user/${currentUserId}/comments?page=${page}&size=${PAGE_SIZE}`
        );
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

async function init() {
    let me = null;
    try {
        me = await renderHeader();
    } catch (err) {
        console.error("header render failed:", err);
    }

    currentUserId = getUserIdFromPath();
    if (!currentUserId) {
        statusEl.textContent = "잘못된 접근입니다.";
        return;
    }

    let user;
    try {
        user = await api.get(`/user/${currentUserId}/profile`);
    } catch (err) {
        statusEl.textContent =
            err.status === 404
                ? "존재하지 않는 사용자입니다."
                : err.message || "프로필을 불러오지 못했습니다.";
        return;
    }

    renderAvatar(user.avatar_url);
    nicknameEl.textContent = user.nickname;
    bioEl.textContent = user.bio || "";
    document.title = `${user.nickname} · blog`;

    // 본인일 때만 설정 버튼
    if (me !== null && me.id === user.id) {
        actionsEl.hidden = false;
    }

    // 댓글 박스는 모든 계정에 표시
    commentsBox.hidden = false;

    statusEl.hidden = true;
    section.hidden = false;

    await loadPosts(1);
    await loadComments(1);
}

init();