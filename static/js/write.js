// 2026-07-24 글 작성 (공통 조각은 post-form.js)

const form = document.getElementById("write-form");
const guard = document.getElementById("guard");
const errorEl = document.getElementById("error");
const submitBtn = document.getElementById("submit");
const categorySelect = document.getElementById("category");

// 확인이 끝날 때까지 폼을 숨겨둔다. 먼저 그리면 잠깐 보였다 사라진다
async function init() {
    const user = await requireVerifiedUser(guard);
    if (!user) return;

    try {
        await loadCategoryOptions(categorySelect);
    } catch (err) {
        guard.textContent = `분류를 불러오지 못했습니다: ${err.message}`;
        return;
    }

    guard.hidden = true;
    form.hidden = false;
}

bindSubmit(form, submitBtn, errorEl, async () => {
    const post = await api.post("/page", {
        title: document.getElementById("title").value,
        contents: document.getElementById("contents").value,
        category_id: Number(categorySelect.value),
        image: parseImageUrls(document.getElementById("images").value),
    });
    location.href = `/post?id=${post.id}`;
});

init();