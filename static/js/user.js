// 2026-07-27 남의 공개 프로필 페이지 (닉네임·소개·이미지 + 그 사람 글 목록)
// 2026-07-28 본인/타인 구분 — 본인이면 설정 버튼. 공개 항목은 누가 보든 동일하다.
//            실패 원인을 뭉뚱그리지 않도록 오류 처리 분리

const statusEl = document.getElementById("status");
const section = document.getElementById("user-profile");
const avatarEl = document.getElementById("pub-avatar");
const nicknameEl = document.getElementById("pub-nickname");
const bioEl = document.getElementById("pub-bio");
const postsEl = document.getElementById("pub-posts");
const postsEmptyEl = document.getElementById("pub-posts-empty");
const actionsEl = document.getElementById("profile-actions");

// URL 이 /user/3 이면 마지막 조각(3)이 유저 id
function getUserIdFromPath() {
    const parts = location.pathname.split("/").filter(Boolean);   // ["user", "3"]
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
    link.textContent = post.title;            // 사용자 입력이므로 textContent

    // 삭제 글은 글 관리 권한자에게만 내려온다.
    // 표시가 없으면 살아 있는 글과 구분이 안 되므로 인덱스와 같은 뱃지를 붙인다
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

function renderPosts(posts) {
    postsEl.replaceChildren();

    if (posts.length === 0) {
        postsEmptyEl.hidden = false;
        return;
    }

    postsEmptyEl.hidden = true;
    for (const post of posts) {
        postsEl.append(createPostItem(post));
    }
}

async function init() {
    // 공개 페이지라 비로그인도 통과한다. 반환값으로 본인 여부를 판단한다
    let me = null;
    try {
        me = await renderHeader();
    } catch (err) {
        console.error("header render failed:", err);
    }

    const id = getUserIdFromPath();
    if (!id) {
        statusEl.textContent = "잘못된 접근입니다.";
        return;
    }

    // 프로필과 글 목록은 실패 이유가 다르다.
    // 하나로 묶어 catch 하면 글 목록이 터져도 "없는 사용자"라고 뜬다
    let user;
    try {
        user = await api.get(`/user/${id}/profile`);
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

    // 본인일 때만 설정으로 가는 길을 연다.
    // 화면에 보이는 정보 자체는 남이 볼 때와 똑같다 — 여기서 이메일·권한은 다루지 않는다
    if (me !== null && me.id === user.id) {
        actionsEl.hidden = false;
    }

    // 프로필은 이미 그렸다. 글 목록만 실패해도 프로필은 남는다
    try {
        const data = await api.get(`/pages?author=${id}&order=desc`);
        renderPosts(data.posts);
    } catch (err) {
        console.error("post list load failed:", err);
        postsEmptyEl.textContent = err.message || "글 목록을 불러오지 못했습니다.";
        postsEmptyEl.hidden = false;
    }

    statusEl.hidden = true;
    section.hidden = false;
}

init();