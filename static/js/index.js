// 2026-07-24 글 목록

async function loadPosts() {
    const list = document.getElementById("post-list");
    const empty = document.getElementById("empty");

    try {
        const data = await api.get("/pages?order=desc");

        if (data.posts.length === 0) {
            empty.hidden = false;
            return;
        }

        for (const post of data.posts) {
            list.append(createPostItem(post));
        }
    } catch (err) {
        empty.textContent = err.message;
        empty.hidden = false;
    }
}

function createPostItem(post) {
    const li = document.createElement("li");

    const h2 = document.createElement("h2");
    const link = document.createElement("a");
    link.href = `/post?id=${post.id}`;
    link.textContent = post.title;          // 사용자 입력이므로 textContent
    h2.append(link);

    const meta = document.createElement("div");
    meta.className = "meta";
    meta.textContent =
        `${post.user.nickname} · ${formatDate(post.created_at)} · 댓글 ${post.comment_count}`;

    li.append(h2, meta);
    return li;
}

renderHeader();
loadPosts();