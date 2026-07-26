// 2026-07-26 내 정보 페이지 (보기 / 수정)

const form = document.getElementById("profile-form");
const emailEl = document.getElementById("email");
const nicknameEl = document.getElementById("nickname");
const bioEl = document.getElementById("bio");
const errorEl = document.getElementById("profile-error");
const doneEl = document.getElementById("profile-done");
const submitBtn = document.getElementById("profile-submit");
const section = document.getElementById("profile");
const statusEl = document.getElementById("status");

const passwordForm = document.getElementById("password-form");
const currentPwEl = document.getElementById("current-password");
const newPwEl = document.getElementById("new-password");
const pwErrorEl = document.getElementById("password-error");
const pwDoneEl = document.getElementById("password-done");
const pwSubmitBtn = document.getElementById("password-submit");

async function init() {
    const user = await renderHeader();

    // 로그인 안 했으면 접근 불가
    if (!user) {
        statusEl.textContent = "로그인이 필요합니다.";
        return;
    }

    // 현재 값 채우기
    emailEl.value = user.email;
    nicknameEl.value = user.nickname;
    bioEl.value = user.bio || "";      // bio 가 null 이면 빈 칸

    statusEl.hidden = true;
    section.hidden = false;
}

form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorEl.textContent = "";
    doneEl.hidden = true;
    submitBtn.disabled = true;

    try {
        // bio 는 빈 문자열이면 소개를 지운다 (서버가 그렇게 처리)
        const updated = await api.patch("/user/me", {
            nickname: nicknameEl.value.trim(),
            bio: bioEl.value,
        });
        // 저장된 값으로 화면 갱신
        nicknameEl.value = updated.nickname;
        bioEl.value = updated.bio || "";
        doneEl.hidden = false;
    } catch (err) {
        errorEl.textContent = err.message;      // 닉네임 중복(409) 등
    } finally {
        submitBtn.disabled = false;
    }
});

passwordForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    pwErrorEl.textContent = "";
    pwDoneEl.hidden = true;
    pwSubmitBtn.disabled = true;

    try {
        await api.patch("/user/me/password", {
            current_password: currentPwEl.value,
            new_password: newPwEl.value,
        });
        // 성공 → 입력 비우고 안내
        currentPwEl.value = "";
        newPwEl.value = "";
        pwDoneEl.hidden = false;
    } catch (err) {
        pwErrorEl.textContent = err.message;      // 현재 비번 불일치(403) 등
    } finally {
        pwSubmitBtn.disabled = false;
    }
});

init();