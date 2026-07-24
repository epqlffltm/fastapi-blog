// 2026-07-24 비밀번호 재설정 (이메일 → 코드 + 새 비번)

const stepRequest = document.getElementById("step-request");
const stepVerify = document.getElementById("step-verify");
const stepDone = document.getElementById("step-done");

const requestForm = document.getElementById("request-form");
const requestError = document.getElementById("request-error");
const requestSubmit = document.getElementById("request-submit");

const verifyForm = document.getElementById("verify-form");
const verifyError = document.getElementById("verify-error");
const verifySubmit = document.getElementById("verify-submit");
const verifyNotice = document.getElementById("verify-notice");

let targetEmail = "";      // 2단계에서 다시 보내야 하므로 들고 있는다

function showStep(section) {
    for (const el of [stepRequest, stepVerify, stepDone]) {
        el.hidden = el !== section;
    }
}

requestForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    requestError.textContent = "";
    requestSubmit.disabled = true;

    targetEmail = document.getElementById("email").value;

    try {
        await api.post("/user/password/reset", { email: targetEmail });
        // 서버는 계정 유무를 알려주지 않는다. 화면도 똑같이 다음 단계로 넘어간다
        verifyNotice.textContent =
            `${targetEmail} 이 가입된 주소라면 인증 코드를 보냈습니다. 3분 안에 입력해 주세요.`;
        showStep(stepVerify);
    } catch (err) {
        requestError.textContent = err.message;
    } finally {
        requestSubmit.disabled = false;
    }
});

verifyForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    verifyError.textContent = "";
    verifySubmit.disabled = true;

    try {
        await api.post("/user/password/reset/verify", {
            email: targetEmail,
            otp: Number(document.getElementById("otp").value),
            new_password: document.getElementById("new-password").value,
        });
        showStep(stepDone);
    } catch (err) {
        verifyError.textContent = err.message;
        verifySubmit.disabled = false;
    }
});

renderHeader();