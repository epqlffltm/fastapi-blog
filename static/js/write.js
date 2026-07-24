// 2026-07-24 글 작성 (공통 조각은 post-form.js)

const form = document.getElementById("write-form");
const guard = document.getElementById("guard");
const errorEl = document.getElementById("error");
const submitBtn = document.getElementById("submit");
const categorySelect = document.getElementById("category");

let editor = null;

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

    // 에디터는 폼이 보이게 된 뒤에 만든다. 숨겨진 요소 위에 만들면 높이가 0이 된다
    editor = createEditor(document.getElementById("editor"));
}

bindSubmit(form, submitBtn, errorEl, async () => {
    const contents = editor.getMarkdown();     // 위지윅으로 썼어도 마크다운으로 꺼낸다
    if (!contents.trim()) {
        throw new Error("본문을 입력해 주세요.");
    }

    const post = await api.post("/page", {
        title: document.getElementById("title").value,
        contents,
        category_id: Number(categorySelect.value),
    });
    location.href = `/post?id=${post.id}`;
});

init();