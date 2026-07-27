// 2026-07-27 남의 공개 프로필 페이지 (닉네임·소개·이미지 + 그 사람 글 목록)

const statusEl = document.getElementById("status");
const section = document.getElementById("user-profile");
const avatarEl = document.getElementById("pub-avatar");
const nicknameEl = document.getElementById("pub-nickname");
const bioEl = document.getElementById("pub-bio");
const postsEl = document.getElementById("pub-posts");
const postsEmptyEl = document.getElementById("pub-posts-empty");

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

    const meta = document.createElement("span");
    meta.className = "meta";
    meta.textContent =
        ` · 조회 ${post.view_count} · 좋아요 ${post.like_count} · 댓글 ${post.comment_count}`;

    li.append(link, meta);
    return li;
}

async function init() {
    // 헤더는 로그인 여부와 무관하게 그린다 (공개 페이지)
    renderHeader();

    const id = getUserIdFromPath();
    if (!id) {
        statusEl.textContent = "잘못된 접근입니다.";
        return;
    }

    try {
        // 공개 프로필 + 그 사람 글 목록을 함께 가져온다
        const [user, posts] = await Promise.all([
            api.get(`/user/${id}/profile`),
            api.get(`/pages?author=${id}&order=desc`),
        ]);

        renderAvatar(user.avatar_url);
        nicknameEl.textContent = user.nickname;
        bioEl.textContent = user.bio || "";

        if (posts.posts.length === 0) {
            postsEmptyEl.hidden = false;
        } else {
            for (const post of posts.posts) {
                postsEl.append(createPostItem(post));
            }
        }

        statusEl.hidden = true;
        section.hidden = false;
    } catch (err) {
        // 없는 유저면 404 → 안내
        statusEl.textContent = "존재하지 않는 사용자입니다.";
    }
}

init();