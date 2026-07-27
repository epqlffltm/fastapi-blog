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

const avatarPreview = document.getElementById("avatar-preview");
const avatarInput = document.getElementById("avatar-input");
const avatarBtn = document.getElementById("avatar-btn");
const avatarError = document.getElementById("avatar-error");

const passwordForm = document.getElementById("password-form");
const currentPwEl = document.getElementById("current-password");
const newPwEl = document.getElementById("new-password");
const pwErrorEl = document.getElementById("password-error");
const pwDoneEl = document.getElementById("password-done");
const pwSubmitBtn = document.getElementById("password-submit");
const otpEl = document.getElementById("otp");
const otpBtn = document.getElementById("otp-btn");
const otpHint = document.getElementById("otp-hint");

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
    renderAvatar(user.avatar_url);

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

// "코드 받기" → 로그인된 이메일로 OTP 발송
otpBtn.addEventListener("click", async () => {
    pwErrorEl.textContent = "";
    otpHint.hidden = true;
    otpBtn.disabled = true;
    try {
        await api.post("/user/me/password/otp", {});
        otpHint.hidden = false;       // "이메일로 코드 보냄"
    } catch (err) {
        pwErrorEl.textContent = err.message;
    } finally {
        otpBtn.disabled = false;
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
            otp: Number(otpEl.value),
        });
        // 성공 → 입력 비우고 안내
        currentPwEl.value = "";
        newPwEl.value = "";
        otpEl.value = "";
        otpHint.hidden = true;
        pwDoneEl.hidden = false;
    } catch (err) {
        pwErrorEl.textContent = err.message;      // 현재 비번 불일치(403) 등
    } finally {
        pwSubmitBtn.disabled = false;
    }
});

// avatar_url 이 있으면 그 이미지, 없으면 기본 실루엣(빈 칸 스타일)
function renderAvatar(url) {
    if (url) {
        avatarPreview.src = url;
        avatarPreview.classList.remove("empty");
    } else {
        avatarPreview.removeAttribute("src");
        avatarPreview.classList.add("empty");
    }
}

// "이미지 변경" → 파일 선택창 열기
avatarBtn.addEventListener("click", () => avatarInput.click());

// 파일 고르면 바로 업로드
avatarInput.addEventListener("change", async () => {
    const file = avatarInput.files[0];
    if (!file) return;
    avatarError.textContent = "";
    avatarBtn.disabled = true;

    try {
        const form = new FormData();
        form.append("file", file);
        // api.post 는 JSON 을 보내므로, 파일은 fetch 로 직접 보낸다
        const res = await fetch("/user/me/avatar", { method: "POST", body: form });
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            throw new Error(data.detail || "업로드 실패");
        }
        const updated = await res.json();
        renderAvatar(updated.avatar_url);
        renderHeader();      // 헤더의 avatar 도 갱신
    } catch (err) {
        avatarError.textContent = err.message;
    } finally {
        avatarBtn.disabled = false;
        avatarInput.value = "";      // 같은 파일 다시 골라도 change 뜨게
    }
});

init();