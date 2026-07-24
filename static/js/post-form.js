// 2026-07-24 글 작성·수정이 공유하는 조각들
//
// 변하는 부분(무엇을 불러오고 무엇을 보낼지)은 호출하는 쪽이 함수로 넘긴다.
// 뼈대만 여기 두고, 각 페이지는 그 뼈대에 자기 동작을 꽂는다.

// 안내문 + 링크를 guard 자리에 그린다
function showGuard(guardEl, message, href, linkText) {
    guardEl.replaceChildren();
    guardEl.append(document.createTextNode(`${message} `));

    const link = document.createElement("a");
    link.href = href;
    link.textContent = linkText;
    guardEl.append(link);
}

// 로그인·이메일 인증 확인. 통과하면 user, 아니면 안내를 그리고 null
async function requireVerifiedUser(guardEl) {
    const user = await renderHeader();

    if (!user) {
        showGuard(guardEl, "로그인이 필요합니다.", "/login", "로그인하기");
        return null;
    }
    if (!user.is_verified) {
        // 서버가 403으로 막지만, 다 써놓고 거절당하는 것보다 미리 알리는 편이 낫다
        showGuard(guardEl, "이메일 인증이 필요합니다.", "/signup", "인증하기");
        return null;
    }
    return user;
}

// 분류 셀렉트 채우기 (작성에서만 쓴다 — PATCH는 분류를 바꾸지 않는다)
async function loadCategoryOptions(selectEl) {
    const data = await api.get("/categories");
    for (const category of data.categories) {
        const option = document.createElement("option");
        option.value = category.id;
        option.textContent = category.name;
        selectEl.append(option);
    }
}

// 여러 줄 입력 → 문자열 배열. 빈 줄과 앞뒤 공백은 버린다
function parseImageUrls(text) {
    return text
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line.length > 0);
}

// 제출의 공통 골격: 기본 동작 차단, 중복 제출 방지, 에러 표시.
// 실제로 무엇을 보낼지는 handler 로 주입받는다
function bindSubmit(form, submitBtn, errorEl, handler) {
    form.addEventListener("submit", async (event) => {
        event.preventDefault();        // 폼 기본 제출(페이지 이동)을 막는다
        errorEl.textContent = "";
        submitBtn.disabled = true;

        try {
            await handler();
            // 성공하면 페이지가 넘어가므로 버튼을 되돌리지 않는다
        } catch (err) {
            errorEl.textContent = err.message;
            submitBtn.disabled = false;
        }
    });
}