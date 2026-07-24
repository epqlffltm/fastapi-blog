// 2026-07-24 글 작성

const form = document.getElementById("write-form");
const guard = document.getElementById("guard");
const errorEl = document.getElementById("error");
const submitBtn = document.getElementById("submit");
const categorySelect = document.getElementById("category");

// 화면을 먼저 그리고 나서 권한을 확인하면 폼이 잠깐 보였다 사라진다.
// 확인이 끝날 때까지 폼을 숨겨두고 판단이 선 뒤에 연다
async function guardAndInit() {
    const user = await renderHeader();

    if (!user) {
        guard.textContent = "로그인이 필요합니다.";
        guard.append(document.createTextNode(" "));
        const link = document.createElement("a");
        link.href = "/login";
        link.textContent = "로그인하기";
        guard.append(link);
        return;
    }

    if (!user.is_verified) {
        // 서버가 403으로 막지만, 다 써놓고 거절당하는 것보다 미리 알리는 편이 낫다
        guard.textContent = "이메일 인증을 마쳐야 글을 쓸 수 있습니다.";
        guard.append(document.createTextNode(" "));
        const link = document.createElement("a");
        link.href = "/signup";
        link.textContent = "인증하기";
        guard.append(link);
        return;
    }

    await loadCategories();
    guard.hidden = true;
    form.hidden = false;
}

async function loadCategories() {
    try {
        const data = await api.get("/categories");
        for (const category of data.categories) {
            const option = document.createElement("option");
            option.value = category.id;
            option.textContent = category.name;
            categorySelect.append(option);
        }
    } catch (err) {
        errorEl.textContent = `분류를 불러오지 못했습니다: ${err.message}`;
    }
}

// 여러 줄 입력 → 문자열 배열. 빈 줄과 앞뒤 공백은 버린다
function parseImageUrls(text) {
    return text
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line.length > 0);
}

form.addEventListener("submit", async (event) => {
    event.preventDefault();        // 폼 기본 제출(페이지 이동)을 막는다
    errorEl.textContent = "";
    submitBtn.disabled = true;

    try {
        const post = await api.post("/page", {
            title: document.getElementById("title").value,
            contents: document.getElementById("contents").value,
            category_id: Number(categorySelect.value),
            image: parseImageUrls(document.getElementById("images").value),
        });
        location.href = `/post?id=${post.id}`;
    } catch (err) {
        errorEl.textContent = err.message;
        submitBtn.disabled = false;
    }
    // 성공 시엔 페이지가 넘어가므로 버튼을 되돌리지 않는다 (중복 제출 방지)
});

guardAndInit();