// 2026-07-24 글 목록 + 분류 사이드바 + 썸네일 미리보기

// 현재 분류는 URL 이 갖는다 → 뒤로가기·새로고침·링크 공유가 전부 동작한다
const currentSlug = new URLSearchParams(location.search).get("category");

// 미리보기 판 하나를 만들어 재사용한다. 항목마다 만들면 DOM 이 불어난다
const preview = document.createElement("div");
const previewImg = document.createElement("img");
preview.className = "hover-preview";
preview.hidden = true;
preview.append(previewImg);
document.body.append(preview);

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

    if (post.thumbnail_url) {
        attachPreview(li, post.thumbnail_url);
    }
    return li;
}

// 제목에 올리면 첫 이미지를 커서 옆에 작게 띄운다
function attachPreview(li, url) {
    li.classList.add("has-preview");

    li.addEventListener("mouseenter", () => {
        previewImg.src = url;
        preview.hidden = false;
    });

    li.addEventListener("mousemove", (event) => {
        // 화면 밖으로 나가지 않도록 오른쪽·아래 여유가 없으면 반대편에 붙인다
        const margin = 16;
        const width = preview.offsetWidth;
        const height = preview.offsetHeight;

        let x = event.clientX + margin;
        let y = event.clientY + margin;

        if (x + width > window.innerWidth) x = event.clientX - width - margin;
        if (y + height > window.innerHeight) y = event.clientY - height - margin;

        preview.style.left = `${Math.max(margin, x)}px`;
        preview.style.top = `${Math.max(margin, y)}px`;
    });

    li.addEventListener("mouseleave", () => {
        preview.hidden = true;
        previewImg.removeAttribute("src");   // 숨긴 뒤에도 남아 있으면 다음 이미지가 겹쳐 보인다
    });
}

renderHeader();
loadCategories();
loadPosts();