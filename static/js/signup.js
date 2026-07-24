// 2026-07-24 회원가입 + 이메일 인증 (한 화면 3단계)

const stepSignup = document.getElementById("step-signup");
const stepVerify = document.getElementById("step-verify");
const stepDone = document.getElementById("step-done");

const signupForm = document.getElementById("signup-form");
const signupError = document.getElementById("signup-error");
const signupSubmit = document.getElementById("signup-submit");

const verifyForm = document.getElementById("verify-form");
const verifyError = document.getElementById("verify-error");
const verifySubmit = document.getElementById("verify-submit");
const verifyNotice = document.getElementById("verify-notice");
const resendLink = document.getElementById("resend");

function showStep(section) {
    for (const el of [stepSignup, stepVerify, stepDone]) {
        el.hidden = el !== section;
    }
}

// OTP 발급은 인증(쿠키)이 필요하므로, 가입 직후 자동으로 로그인시킨다
async function requestOtp(email) {
    const result = await api.post("/user/email/otp");
    verifyNotice.textContent = `${result.email} 로 인증 코드를 보냈습니다. 3분 안에 입력해 주세요.`;
}

signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    signupError.textContent = "";
    signupSubmit.disabled = true;

    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;

    try {
        await api.post("/user/sign-up", {
            email,
            password,
            nickname: document.getElementById("nickname").value,
        });
        await api.post("/user/log-in", { email, password });   // 쿠키 발급
        await renderHeader();

        showStep(stepVerify);
        await requestOtp(email);
    } catch (err) {
        signupError.textContent = err.message;
        signupSubmit.disabled = false;
    }
});

verifyForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    verifyError.textContent = "";
    verifySubmit.disabled = true;

    try {
        await api.post("/user/email/otp/verify", {
            otp: Number(document.getElementById("otp").value),
        });
        await renderHeader();
        showStep(stepDone);
    } catch (err) {
        verifyError.textContent = err.message;
        verifySubmit.disabled = false;
    }
});

resendLink.addEventListener("click", async (event) => {
    event.preventDefault();
    verifyError.textContent = "";

    try {
        const user = await getCurrentUser();
        if (!user) throw new Error("로그인이 필요합니다.");
        await requestOtp(user.email);
    } catch (err) {
        verifyError.textContent = err.message;      // 1분 안에 다시 누르면 429
    }
});

// 이미 로그인했는데 인증만 안 된 상태로 들어온 경우 2단계부터 시작한다
async function init() {
    const user = await renderHeader();
    if (user && !user.is_verified) {
        showStep(stepVerify);
        verifyNotice.textContent =
            "이메일 인증이 필요합니다. '코드 다시 보내기'를 눌러 코드를 받으세요.";
    } else if (user) {
        showStep(stepDone);
    }
}

init();