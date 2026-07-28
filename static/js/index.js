// 2026-07-28 글 목록 + 분류 + 검색 + 페이지네이션 + 썸네일 미리보기
// 검색 UI가 없는 이전 index.html에서도 목록이 멈추지 않도록 필요한 요소를 자동 생성한다.

const PAGE_SIZE = 20;
const currentParams = new URLSearchParams(location.search);
const currentSlug = currentParams.get("category");
const currentQuery = (currentParams.get("q") || "").trim();
const parsedPage = Number.parseInt(currentParams.get("page") || "1", 10);
const currentPage = Number.isInteger(parsedPage) && parsedPage > 0 ? parsedPage : 1;

// 미리보기 판 하나를 만들어 재사용한다. 항목마다 만들면 DOM 이 불어난다.
const preview = document.createElement("div");
const previewImg = document.createElement("img");
preview.className = "hover-preview";
preview.hidden = true;
preview.append(previewImg);
document.body.append(preview);


/**
 * 이전 index.html에는 검색창과 페이지 영역이 없을 수 있다.
 * 그런 경우 게시글 목록 아래에 필요한 UI를 자동으로 만든다.
 */
function ensureListControls() {
    const list = document.getElementById("post-list");
    if (!list) {
        throw new Error("post-list element not found");
    }

    const section = list.closest("section") || list.parentElement;
    if (!section) {
        throw new Error("post list container not found");
    }

    let empty = document.getElementById("empty");
    if (!empty) {
        empty = document.createElement("p");
        empty.id = "empty";
        empty.className = "empty";
        empty.hidden = true;
        empty.textContent = "아직 글이 없습니다.";
        list.insertAdjacentElement("afterend", empty);
    }

    let form = document.getElementById("post-search");
    if (!form) {
        form = document.createElement("form");
        form.id = "post-search";
        form.className = "post-search";
        form.setAttribute("role", "search");

        const label = document.createElement("label");
        label.htmlFor = "post-search-input";
        label.textContent = "게시글 검색";

        const controls = document.createElement("div");
        controls.className = "post-search-controls";

        const input = document.createElement("input");
        input.id = "post-search-input";
        input.name = "q";
        input.type = "search";
        input.maxLength = 100;
        input.placeholder = "제목, 본문, 글쓴이 검색";
        input.autocomplete = "off";

        const submit = document.createElement("button");
        submit.type = "submit";
        submit.textContent = "검색";

        const clear = document.createElement("button");
        clear.id = "post-search-clear";
        clear.type = "button";
        clear.textContent = "초기화";
        clear.hidden = true;

        controls.append(input, submit, clear);
        form.append(label, controls);
        empty.insertAdjacentElement("afterend", form);
    }

    let pagination = document.getElementById("pagination");
    if (!pagination) {
        pagination = document.createElement("nav");
        pagination.id = "pagination";
        pagination.className = "pagination";
        pagination.setAttribute("aria-label", "게시글 페이지");
        form.insertAdjacentElement("afterend", pagination);
    }

    return {
        list,
        empty,
        form,
        input: document.getElementById("post-search-input"),
        clearButton: document.getElementById("post-search-clear"),
        pagination,
    };
}


async function loadCategories() {
    const list = document.getElementById("category-list");
    if (!list) return;

    try {
        const data = await api.get("/categories");
        const total = data.categories.reduce((sum, category) => {
            return sum + category.post_count;
        }, 0);

        list.replaceChildren();
        list.append(
            createCategoryItem({
                slug: null,
                name: "전체",
                post_count: total,
            })
        );

        for (const category of data.categories) {
            list.append(createCategoryItem(category));
        }
    } catch (error) {
        // 분류를 못 불러와도 글 목록은 보여야 하므로 여기서 멈추지는 않는다.
        // 다만 조용히 삼키면 "사이드바가 그냥 비어 있는" 상태와 구분이 안 된다.
        // 실패했다는 사실은 화면과 콘솔 양쪽에 남긴다
        console.error("category load failed:", error);

        const li = document.createElement("li");
        li.className = "load-error";
        li.textContent = error?.message || "분류를 불러오지 못했습니다.";
        list.replaceChildren(li);
    }
}


function createCategoryItem(category) {
    const li = document.createElement("li");
    const link = document.createElement("a");
    const params = new URLSearchParams(location.search);

    // 분류를 바꾸면 첫 페이지부터 본다.
    // 검색어는 유지해 선택한 분류 안에서 다시 검색한다.
    params.delete("page");

    if (category.slug) {
        params.set("category", category.slug);
    } else {
        params.delete("category");
    }

    const queryString = params.toString();
    link.href = queryString ? `/?${queryString}` : "/";

    if (category.slug === currentSlug) {
        link.classList.add("active");
    }

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

    if (!list || !empty) return;

    list.replaceChildren();
    empty.hidden = true;

    const params = new URLSearchParams({
        order: "desc",
        page: String(currentPage),
        size: String(PAGE_SIZE),
    });

    if (currentSlug) {
        params.set("category", currentSlug);
    }

    if (currentQuery) {
        params.set("q", currentQuery);
    }

    try {
        const data = await api.get(`/pages?${params.toString()}`);

        if (data.posts.length === 0) {
            empty.textContent = currentQuery
                ? `"${currentQuery}" 검색 결과가 없습니다.`
                : "아직 글이 없습니다.";
            empty.hidden = false;
        } else {
            for (const post of data.posts) {
                list.append(createPostItem(post));
            }
        }

        renderPagination(data);
    } catch (error) {
        empty.textContent = error?.message || "게시글 목록을 불러오지 못했습니다.";
        empty.hidden = false;
    }
}


function setupSearch() {
    const form = document.getElementById("post-search");
    const input = document.getElementById("post-search-input");
    const clearButton = document.getElementById("post-search-clear");

    // index.html 구조가 예상과 달라도 게시글 목록 로딩은 계속되어야 한다.
    if (!form || !input || !clearButton) return;

    input.value = currentQuery;
    clearButton.hidden = !currentQuery;

    form.addEventListener("submit", (event) => {
        event.preventDefault();

        const query = input.value.trim();
        const params = new URLSearchParams(location.search);
        params.delete("page");

        if (query) {
            params.set("q", query);
        } else {
            params.delete("q");
        }

        navigateWithParams(params);
    });

    clearButton.addEventListener("click", () => {
        const params = new URLSearchParams(location.search);
        params.delete("q");
        params.delete("page");
        navigateWithParams(params);
    });
}


function renderPagination(data) {
    const pagination = document.getElementById("pagination");
    if (!pagination) return;

    pagination.replaceChildren();

    const summary = document.createElement("span");
    summary.className = "pagination-summary";
    summary.textContent = `총 ${data.total}개`;
    pagination.append(summary);

    if (data.total_pages <= 1) return;

    const previous = document.createElement("button");
    previous.type = "button";
    previous.textContent = "이전";
    previous.disabled = data.page <= 1;
    previous.addEventListener("click", () => {
        navigateToPage(data.page - 1);
    });

    const status = document.createElement("span");
    status.className = "pagination-status";
    status.textContent = `${data.page} / ${data.total_pages}`;

    const next = document.createElement("button");
    next.type = "button";
    next.textContent = "다음";
    next.disabled = data.page >= data.total_pages;
    next.addEventListener("click", () => {
        navigateToPage(data.page + 1);
    });

    pagination.append(previous, status, next);
}


function navigateToPage(page) {
    const params = new URLSearchParams(location.search);

    if (page <= 1) {
        params.delete("page");
    } else {
        params.set("page", String(page));
    }

    navigateWithParams(params);
}


function navigateWithParams(params) {
    const queryString = params.toString();
    location.href = queryString ? `/?${queryString}` : "/";
}


function createPostItem(post) {
    const li = document.createElement("li");

    if (post.is_deleted) {
        li.classList.add("deleted-post");
    }

    const h2 = document.createElement("h2");
    const link = document.createElement("a");
    link.href = `/post?id=${post.id}`;
    link.textContent = post.title;
    h2.append(link);

    if (post.is_deleted) {
        const badge = document.createElement("span");
        badge.className = "deleted-badge";
        badge.textContent = "삭제됨";
        h2.append(badge);
    }

    const meta = document.createElement("div");
    meta.className = "meta";

    const category = document.createElement("span");
    category.className = "category-tag";
    category.textContent = post.category.name;

    const separator = document.createElement("span");
    separator.textContent = " · ";

    const authorLink = document.createElement("a");
    authorLink.href = `/user/${post.user.id}`;
    authorLink.className = "author-link";
    authorLink.textContent = post.user.nickname;

    const rest = document.createElement("span");
    rest.textContent =
        ` · ${formatDate(post.created_at)}` +
        ` · 조회 ${post.view_count}` +
        ` · 좋아요 ${post.like_count}` +
        ` · 댓글 ${post.comment_count}`;

    meta.append(category, separator, authorLink, rest);
    li.append(h2, meta);

    if (post.thumbnail_url) {
        attachPreview(li, post.thumbnail_url);
    }

    return li;
}


// 제목에 올리면 첫 이미지를 커서 옆에 작게 띄운다.
function attachPreview(li, url) {
    li.classList.add("has-preview");

    li.addEventListener("mouseenter", () => {
        previewImg.src = url;
        preview.hidden = false;
    });

    li.addEventListener("mousemove", (event) => {
        const margin = 16;
        const width = preview.offsetWidth;
        const height = preview.offsetHeight;

        let x = event.clientX + margin;
        let y = event.clientY + margin;

        if (x + width > window.innerWidth) {
            x = event.clientX - width - margin;
        }

        if (y + height > window.innerHeight) {
            y = event.clientY - height - margin;
        }

        preview.style.left = `${Math.max(margin, x)}px`;
        preview.style.top = `${Math.max(margin, y)}px`;
    });

    li.addEventListener("mouseleave", () => {
        preview.hidden = true;
        previewImg.removeAttribute("src");
    });
}


// 검색 UI가 없는 이전 HTML도 먼저 보완한다.
// 여기서 예외가 그대로 올라가면 아래 목록 로딩까지 통째로 죽는다
try {
    ensureListControls();
} catch (error) {
    console.error("list controls setup failed:", error);
}

// renderHeader 는 async 라 try/catch 로는 안 잡힌다 (동기 구간에서 끝나 버린다).
// 실패는 반환된 Promise 로 오므로 catch 를 붙여야 한다
renderHeader().catch((error) => {
    console.error("header render failed:", error);
});

setupSearch();
loadCategories();
loadPosts();