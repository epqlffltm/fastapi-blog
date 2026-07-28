// 2026-07-24 로그인 상태 확인 및 헤더 렌더링
// 2026-07-26 닉네임 → 내 정보(/profile) 링크 / 헤더 avatar 표시

// 쿠키는 JS가 읽을 수 없으므로, 로그인 여부는 서버에 물어봐야 안다
async function getCurrentUser() {
    try {
        return await api.get("/user/me");
    } catch {
        return null;      // 401 등 → 비로그인
    }
}

// 화면 표시용 판단. 실제 차단은 언제나 서버가 한다
function can(user, permission) {
    return user !== null && user[permission] === true;
}

function isActive(user) {
    return user !== null && !user.is_banned && !user.is_suspended;
}

function canManage(user) {
    return can(user, "can_manage_user") || can(user, "can_manage_category");
}

async function renderHeader() {
    const nav = document.querySelector("header nav");
    if (!nav) return null;

    const user = await getCurrentUser();
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

        // 제재 상태는 숨기지 않는다. 본인이 알아야 문의할 수 있다
        if (!isActive(user)) {
            const state = document.createElement("span");
            state.className = "state-banner";
            state.textContent = user.is_banned
                ? "이용 정지"
                : `정지 ~${formatDate(user.suspended_until)}`;
            nav.append(state);
        }

        // 닉네임을 누르면 내 프로필로 간다.
        // 남의 프로필과 같은 화면이라 "남에게 어떻게 보이는지"를 그대로 확인할 수 있다.
        // 설정(닉네임·소개·아바타·비밀번호)은 그 화면의 설정 버튼으로 들어간다
        const name = document.createElement("a");
        name.className = "who";
        name.href = `/user/${user.id}`;
        // avatar 가 있으면 닉네임 앞에 작은 원형 이미지
        if (user.avatar_url) {
            const av = document.createElement("img");
            av.className = "who-avatar";
            av.src = user.avatar_url;
            av.alt = "";
            name.append(av);
        }
        name.append(document.createTextNode(user.nickname));   // 태그 실행 안 되게 텍스트 노드

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