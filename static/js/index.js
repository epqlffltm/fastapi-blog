// 2026-07-24 글 목록 + 분류 사이드바

// 현재 분류는 URL 이 갖는다 → 뒤로가기·새로고침·링크 공유가 전부 동작한다
const currentSlug = new URLSearchParams(location.search).get("category");

async function loadCategories() {
    const list = document.getElementById("category-list");

    try {
        const data = await api.get("/categories");
        const total = data.categories.reduce((sum, c) => sum + c.post_count, 0);

        list.append(createCategoryItem({ slug: null, name: "전체", post_count: total }));
        for (const category of data.categories) {
            list.append(createCategoryItem(category));
        }
    } catch {
        // 분류를 못 불러와도 글 목록은 보여야 하므로 조용히 넘어간다
    }
}

function createCategoryItem(category) {
    const li = document.createElement("li");

    const link = document.createElement("a");
    link.href = category.slug ? `/?category=${encodeURIComponent(category.slug)}` : "/";
    if (category.slug === currentSlug) link.classList.add("active");

    const name = document.createElement("span");
    name.textContent = category.name;

    const count = document.createElement("span");
    count.className = "count";
    count.textContent = category.post_count;

    link.append(name, count);
    li.append(link);
    return li;
}

async function loadPosts() {
    const list = document.getElementById("post-list");
    const empty = document.getElementById("empty");

    let path = "/pages?order=desc";
    if (currentSlug) path += `&category=${encodeURIComponent(currentSlug)}`;

    try {
        const data = await api.get(path);

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

    const category = document.createElement("span");
    category.className = "category-tag";
    category.textContent = post.category.name;

    const rest = document.createElement("span");
    rest.textContent =
        ` · ${post.user.nickname} · ${formatDate(post.created_at)} · 댓글 ${post.comment_count}`;

    meta.append(category, rest);
    li.append(h2, meta);
    return li;
}

renderHeader();
loadCategories();
loadPosts();