// 2026-07-24 관리 화면 (분류 추가 / 회원 권한 · 제재)

const PERMISSION_LABELS = [
    ["can_comment", "댓글"],
    ["can_write_post", "글쓰기"],
    ["can_upload", "이미지 업로드"],
    ["can_manage_category", "분류 관리"],
    ["can_manage_user", "회원 관리"],
    ["can_manage_post", "글 관리"],
];

const adminEl = document.getElementById("admin");
const guard = document.getElementById("guard");

const categorySection = document.getElementById("category-section");
const categoryForm = document.getElementById("category-form");
const categoryError = document.getElementById("category-error");
const categorySubmit = document.getElementById("category-submit");
const categoryList = document.getElementById("category-list");

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
            const li = document.createElement("li");

            const label = document.createElement("span");
            label.textContent = `${category.name} (${category.slug})`;

            const count = document.createElement("span");
            count.className = "count";
            count.textContent = category.post_count;

            li.append(label, count);
            categoryList.append(li);
        }
    } catch (err) {
        categoryError.textContent = err.message;
    }
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