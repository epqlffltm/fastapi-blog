// 2026-07-24 로그인 상태 확인 및 헤더 렌더링
// 2026-07-26 닉네임 → 내 정보(/profile) 링크 / 헤더 avatar 표시
// 2026-07-28 헤더 닉네임은 항상 /profile 로 이동

async function getCurrentUser() {
    try {
        return await api.get("/user/me");
    } catch {
        return null;
    }
}

function can(user, permission) {
    return user !== null && user[permission] === true;
}

function isActive(user) {
    return user !== null && !user.is_banned && !user.is_suspended;
}

function canManage(user) {
    return can(user, "can_manage_user") || can(user, "can_manage_category");
}

// 전역으로 현재 로그인 유저 보관 (다른 스크립트에서 작성자 링크 판단용)
window.currentUser = null;

async function renderHeader() {
    const nav = document.querySelector("header nav");
    if (!nav) return null;

    const user = await getCurrentUser();
    window.currentUser = user;
    nav.replaceChildren();

    if (user) {
        if (can(user, "can_write_post") && isActive(user)) {
            const write = document.createElement("a");
            write.href = "/write";
            write.textContent = "글쓰기";
            nav.append(write);
        }

        if (canManage(user) && isActive(user)) {
            const admin = document.createElement("a");
            admin.href = "/admin";
            admin.textContent = "관리";
            nav.append(admin);
        }

        if (!isActive(user)) {
            const state = document.createElement("span");
            state.className = "state-banner";
            state.textContent = user.is_banned
                ? "이용 정지"
                : `정지 ~${formatDate(user.suspended_until)}`;
            nav.append(state);
        }

        // ★ 헤더 닉네임은 항상 /profile 로
        const name = document.createElement("a");
        name.className = "who";
        name.href = "/profile";

        if (user.avatar_url) {
            const av = document.createElement("img");
            av.className = "who-avatar";
            av.src = user.avatar_url;
            av.alt = "";
            name.append(av);
        }
        name.append(document.createTextNode(user.nickname));

        const logout = document.createElement("button");
        logout.textContent = "로그아웃";
        logout.addEventListener("click", async () => {
            await api.post("/user/log-out");
            location.href = "/";
        });

        nav.append(name, logout);
    } else {
        const login = document.createElement("a");
        login.href = "/login";
        login.textContent = "로그인";

        const signup = document.createElement("a");
        signup.href = "/signup";
        signup.textContent = "회원가입";

        nav.append(login, signup);
    }
    return user;
}

function formatDate(iso) {
    const d = new Date(iso);
    return d.toLocaleDateString("ko-KR", {
        year: "numeric", month: "2-digit", day: "2-digit",
    });
}

// 작성자 링크 헬퍼: 내 아이디면 /profile, 아니면 /user/{id}
function authorHref(userId) {
    if (window.currentUser && window.currentUser.id === userId) {
        return "/profile";
    }
    return `/user/${userId}`;
}