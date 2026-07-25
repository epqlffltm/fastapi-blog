// 2026-07-24 관리 화면 (분류 추가 / 회원 권한 · 제재)
// 2026-07-25 분류 이름변경·삭제 / 미분류 글 정리 / 글 관리 권한 체크박스

const PERMISSION_LABELS = [
    ["can_comment", "댓글"],
    ["can_write_post", "글쓰기"],
    ["can_upload", "이미지 업로드"],
    ["can_manage_category", "분류 관리"],
    ["can_manage_post", "글 관리"],
    ["can_manage_user", "회원 관리"],
];

const adminEl = document.getElementById("admin");
const guard = document.getElementById("guard");

const categorySection = document.getElementById("category-section");
const categoryForm = document.getElementById("category-form");
const categoryError = document.getElementById("category-error");
const categorySubmit = document.getElementById("category-submit");
const categoryList = document.getElementById("category-list");

const uncatSection = document.getElementById("uncat-section");
const uncatError = document.getElementById("uncat-error");
const uncatList = document.getElementById("uncat-list");

const userSection = document.getElementById("user-section");
const userError = document.getElementById("user-error");
const userList = document.getElementById("user-list");

let currentUser = null;

async function init() {
    currentUser = await renderHeader();

    if (!currentUser) {
        guard.replaceChildren(document.createTextNode("로그인이 필요합니다. "));
        const link = document.createElement("a");
        link.href = "/login";
        link.textContent = "로그인하기";
        guard.append(link);
        return;
    }
    if (!isActive(currentUser) || !canManage(currentUser)) {
        guard.textContent = "관리 권한이 없습니다.";
        return;
    }

    guard.hidden = true;
    adminEl.hidden = false;

    // 권한별로 필요한 구역만 보인다
    if (can(currentUser, "can_manage_category")) {
        categorySection.hidden = false;
        await loadCategories();
    }
    // 미분류 청소는 글을 옮기는 일이라 글 관리 권한이 필요하다
    if (can(currentUser, "can_manage_post")) {
        uncatSection.hidden = false;
        await loadUncategorizedPosts();
    }
    if (can(currentUser, "can_manage_user")) {
        userSection.hidden = false;
        await loadUsers();
    }
}

// ---------- 분류 ----------

async function loadCategories() {
    categoryList.replaceChildren();
    try {
        const data = await api.get("/categories");
        for (const category of data.categories) {
            categoryList.append(createCategoryRow(category));
        }
    } catch (err) {
        categoryError.textContent = err.message;
    }
}

function createCategoryRow(category) {
    const li = document.createElement("li");
    li.style.display = "flex";
    li.style.alignItems = "center";
    li.style.gap = "8px";

    const label = document.createElement("span");
    label.style.flex = "1";
    label.textContent = `${category.name} (${category.slug})`;

    const count = document.createElement("span");
    count.className = "count";
    count.textContent = category.post_count;

    li.append(label, count);

    // 이름 변경 (미분류 포함 허용)
    const rename = document.createElement("button");
    rename.className = "ghost-btn";
    rename.textContent = "이름 변경";
    rename.addEventListener("click", async () => {
        const name = prompt("새 이름", category.name);
        if (name === null || !name.trim()) return;      // 취소/빈값
        categoryError.textContent = "";
        try {
            await api.patch(`/categories/${category.id}`, { name: name.trim() });
            await loadCategories();
        } catch (err) {
            categoryError.textContent = err.message;
        }
    });
    li.append(rename);

    // 미분류는 안전망이라 삭제 버튼을 두지 않는다
    if (category.slug !== "uncategorized") {
        const del = document.createElement("button");
        del.className = "ghost-btn danger";
        del.textContent = "삭제";
        del.addEventListener("click", async () => {
            const msg = category.post_count > 0
                ? `"${category.name}" 을(를) 삭제하면 글 ${category.post_count}개가 미분류로 이동합니다. 계속할까요?`
                : `"${category.name}" 을(를) 삭제할까요?`;
            if (!confirm(msg)) return;
            categoryError.textContent = "";
            try {
                await api.del(`/categories/${category.id}`);
                await loadCategories();
                // 미분류로 옮겨온 글을 정리 목록에 반영
                if (!uncatSection.hidden) await loadUncategorizedPosts();
            } catch (err) {
                categoryError.textContent = err.message;
            }
        });
        li.append(del);
    }

    return li;
}

// ---------- 미분류 글 정리 ----------

async function loadUncategorizedPosts() {
    uncatList.replaceChildren();
    uncatError.textContent = "";
    try {
        // 미분류 글 + 옮길 대상 분류를 함께 가져온다
        const [posts, cats] = await Promise.all([
            api.get("/pages?category=uncategorized"),
            api.get("/categories"),
        ]);

        // 옮길 대상에서 미분류 자신은 뺀다
        const targets = cats.categories.filter((c) => c.slug !== "uncategorized");

        if (posts.posts.length === 0) {
            const empty = document.createElement("p");
            empty.className = "meta";
            empty.textContent = "미분류 글이 없습니다.";
            uncatList.append(empty);
            return;
        }

        for (const post of posts.posts) {
            uncatList.append(createUncatRow(post, targets));
        }
    } catch (err) {
        uncatError.textContent = err.message;
    }
}

function createUncatRow(post, targets) {
    const row = document.createElement("div");
    row.style.display = "flex";
    row.style.alignItems = "center";
    row.style.gap = "12px";
    row.style.padding = "6px 0";

    const title = document.createElement("a");
    title.href = `/post?id=${post.id}`;
    title.textContent = post.title;
    title.style.flex = "1";

    const select = document.createElement("select");
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "분류 선택…";
    select.append(placeholder);
    for (const c of targets) {
        const opt = document.createElement("option");
        opt.value = c.id;
        opt.textContent = c.name;
        select.append(opt);
    }

    // 분류를 고르면 바로 옮긴다
    select.addEventListener("change", async () => {
        if (!select.value) return;
        select.disabled = true;
        uncatError.textContent = "";
        try {
            await api.patch(`/page/${post.id}/category`, {
                category_id: Number(select.value),
            });
            row.remove();      // 옮겨졌으니 미분류 목록에서 뺀다
        } catch (err) {
            uncatError.textContent = err.message;
            select.disabled = false;
            select.value = "";
        }
    });

    row.append(title, select);
    return row;
}

categoryForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    categoryError.textContent = "";
    categorySubmit.disabled = true;

    try {
        await api.post("/categories", {
            slug: document.getElementById("slug").value,
            name: document.getElementById("name").value,
            display_order: Number(document.getElementById("order").value),
        });
        categoryForm.reset();
        document.getElementById("order").value = "0";
        await loadCategories();
    } catch (err) {
        categoryError.textContent = err.message;
    } finally {
        categorySubmit.disabled = false;
    }
});

// ---------- 회원 ----------

async function loadUsers() {
    userList.replaceChildren();
    try {
        const data = await api.get("/user/list");
        for (const user of data.users) {
            userList.append(createUserCard(user));
        }
    } catch (err) {
        userError.textContent = err.message;
    }
}

function createUserCard(user) {
    const card = document.createElement("div");
    card.className = "user-card";

    const self = user.id === currentUser.id;
    if (self) card.classList.add("self");

    card.append(createUserHead(user, self));
    card.append(createPermissionRow(user, self));
    if (!self) card.append(createSanctionRow(user, card));

    return card;
}

function createUserHead(user, self) {
    const head = document.createElement("div");
    head.className = "user-head";

    const nickname = document.createElement("span");
    nickname.className = "user-nickname";
    nickname.textContent = user.nickname + (self ? " (나)" : "");

    const email = document.createElement("span");
    email.className = "meta";
    email.textContent = user.email;

    const state = document.createElement("span");
    state.className = "user-state";
    if (user.is_banned) {
        state.textContent = "강퇴";
        state.classList.add("bad");
    } else if (user.is_suspended) {
        state.textContent = `정지 ~${formatDate(user.suspended_until)}`;
        state.classList.add("bad");
    } else if (!user.is_verified) {
        state.textContent = "미인증";
        state.classList.add("bad");
    } else {
        state.textContent = "정상";
    }

    head.append(nickname, email, state);
    return head;
}

function createPermissionRow(user, self) {
    const row = document.createElement("div");
    row.className = "permission-row";

    for (const [name, label] of PERMISSION_LABELS) {
        const wrap = document.createElement("label");
        wrap.className = "check";

        const box = document.createElement("input");
        box.type = "checkbox";
        box.checked = user[name];
        // 자기 권한은 서버가 막는다. 화면에서도 잠가 둔다
        box.disabled = self;
        if (self) wrap.title = "자신의 권한은 바꿀 수 없습니다";

        box.addEventListener("change", async () => {
            const previous = !box.checked;
            box.disabled = true;
            userError.textContent = "";

            try {
                const updated = await api.patch(`/user/${user.id}/permissions`, {
                    [name]: box.checked,
                });
                user[name] = updated[name];
            } catch (err) {
                userError.textContent = err.message;
                box.checked = previous;      // 실패하면 화면도 되돌린다
            } finally {
                box.disabled = false;
            }
        });

        wrap.append(box, document.createTextNode(label));
        row.append(wrap);
    }
    return row;
}

function createSanctionRow(user, card) {
    const row = document.createElement("div");
    row.className = "sanction-row";

    const days = document.createElement("input");
    days.type = "number";
    days.className = "days-input";
    days.min = "1";
    days.max = "3650";
    days.value = "7";

    const suspend = document.createElement("button");
    suspend.className = "ghost-btn";
    suspend.textContent = "정지";
    suspend.addEventListener("click", () => {
        applySanction(user, card, `/user/${user.id}/suspend`, {
            days: Number(days.value),
        });
    });

    const release = document.createElement("button");
    release.className = "ghost-btn";
    release.textContent = "정지 해제";
    release.addEventListener("click", () => {
        applySanction(user, card, `/user/${user.id}/suspend`, { days: 0 });
    });

    const ban = document.createElement("button");
    ban.className = "ghost-btn danger";
    ban.textContent = user.is_banned ? "강퇴 해제" : "강퇴";
    ban.addEventListener("click", () => {
        if (!user.is_banned && !confirm(`${user.nickname} 을(를) 강퇴할까요?`)) return;
        applySanction(user, card, `/user/${user.id}/ban`, { banned: !user.is_banned });
    });

    const label = document.createElement("span");
    label.className = "meta";
    label.textContent = "일";

    row.append(days, label, suspend, release, ban);
    return row;
}

// 제재는 상태 표시와 버튼 문구가 함께 바뀌므로 카드를 통째로 다시 그린다
async function applySanction(user, card, path, body) {
    userError.textContent = "";
    try {
        const updated = await api.patch(path, body);
        card.replaceWith(createUserCard(updated));
    } catch (err) {
        userError.textContent = err.message;
    }
}

init();