// 2026-07-24 로그인

const form = document.getElementById("login-form");
const errorEl = document.getElementById("error");
const submitBtn = document.getElementById("submit");

form.addEventListener("submit", async (event) => {
    event.preventDefault();        // 폼 기본 제출(페이지 이동)을 막는다
    errorEl.textContent = "";
    submitBtn.disabled = true;

    try {
        await api.post("/user/log-in", {
            email: document.getElementById("email").value,
            password: document.getElementById("password").value,
        });
        // 토큰은 응답 본문이 아니라 httpOnly 쿠키로 왔다. 저장할 게 없다
        location.href = "/";
    } catch (err) {
        errorEl.textContent = err.message;
    } finally {
        submitBtn.disabled = false;
    }
});

renderHeader();