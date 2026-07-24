// 2026-07-24 관리 화면 (분류 추가 / 회원 등급)

const adminEl = document.getElementById("admin");
const guard = document.getElementById("guard");

const categoryForm = document.getElementById("category-form");
const categoryError = document.getElementById("category-error");
const categorySubmit = document.getElementById("category-submit");
const categoryList = document.getElementById("category-list");

const userError = document.getElementById("user-error");
const userBody = document.getElementById("user-body");

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
    if (!isAdmin(currentUser)) {
        guard.textContent = "관리자만 볼 수 있는 화면입니다.";
        return;
    }

    guard.hidden = true;
    adminEl.hidden = false;

    await loadCategories();
    await loadUsers();
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

// ---------- 회원 등급 ----------

async function loadUsers() {
    userBody.replaceChildren();
    try {
        const data = await api.get("/user/list");
        for (const user of data.users) {
            userBody.append(createUserRow(user));
        }
    } catch (err) {
        userError.textContent = err.message;
    }
}

function createUserRow(user) {
    const tr = document.createElement("tr");

    const nickname = document.createElement("td");
    nickname.textContent = user.nickname;

    const email = document.createElement("td");
    email.className = "meta";
    email.textContent = user.email;

    const verified = document.createElement("td");
    verified.textContent = user.is_verified ? "완료" : "미인증";
    if (!user.is_verified) verified.className = "unverified";

    const roleCell = document.createElement("td");
    roleCell.append(createRoleSelect(user));

    tr.append(nickname, email, verified, roleCell);
    return tr;
}

function createRoleSelect(user) {
    const select = document.createElement("select");
    select.className = "role-select";

    for (const [value, label] of [["admin", "관리자"], ["member", "회원"]]) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        option.selected = user.role === value;
        select.append(option);
    }

    // 자기 등급은 서버가 막는다. 바꿀 수 없다는 걸 화면에서도 보인다
    if (user.id === currentUser.id) {
        select.disabled = true;
        select.title = "자신의 등급은 바꿀 수 없습니다";
        return select;
    }

    select.addEventListener("change", async () => {
        const previous = user.role;
        select.disabled = true;
        userError.textContent = "";

        try {
            const updated = await api.patch(`/user/${user.id}/role`, {
                role: select.value,
            });
            user.role = updated.role;
        } catch (err) {
            userError.textContent = err.message;
            select.value = previous;      // 실패하면 화면도 되돌린다
        } finally {
            select.disabled = false;
        }
    });

    return select;
}

init();