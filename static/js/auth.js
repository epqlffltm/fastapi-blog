// 2026-07-24 로그인 상태 확인 및 헤더 렌더링

// 쿠키는 JS가 읽을 수 없으므로, 로그인 여부는 서버에 물어봐야 안다
async function getCurrentUser() {
    try {
        return await api.get("/user/me");
    } catch {
        return null;      // 401 등 → 비로그인
    }
}

function isAdmin(user) {
    return user !== null && user.role === "admin";
}

async function renderHeader() {
    const nav = document.querySelector("header nav");
    if (!nav) return null;

    const user = await getCurrentUser();
    nav.replaceChildren();

    if (user) {
        // 글쓰기·관리는 관리자에게만 보인다. 실제 차단은 서버가 한다
        if (isAdmin(user)) {
            const write = document.createElement("a");
            write.href = "/write";
            write.textContent = "글쓰기";

            const admin = document.createElement("a");
            admin.href = "/admin";
            admin.textContent = "관리";

            nav.append(write, admin);
        }

        const name = document.createElement("span");
        name.className = "who";
        name.textContent = user.nickname;      // textContent: 태그가 실행되지 않는다

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