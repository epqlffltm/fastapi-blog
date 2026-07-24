// 2026-07-24 글 상세 + 댓글 (본문은 마크다운 뷰어로 렌더)

const postId = new URLSearchParams(location.search).get("id");

const article = document.getElementById("post");
const status = document.getElementById("status");
const titleEl = document.getElementById("title");
const metaEl = document.getElementById("meta");
const viewerEl = document.getElementById("viewer");
const postActions = document.getElementById("post-actions");

const commentCountEl = document.getElementById("comment-count");
const commentList = document.getElementById("comment-list");
const commentForm = document.getElementById("comment-form");
const commentInput = document.getElementById("comment-input");
const commentError = document.getElementById("comment-error");
const commentSubmit = document.getElementById("comment-submit");
const commentGuard = document.getElementById("comment-guard");

let currentUser = null;

async function init() {
    currentUser = await renderHeader();

    if (!postId) {
        status.textContent = "잘못된 주소입니다.";
        return;
    }

    let post;
    try {
        post = await api.get(`/page/${postId}`);
    } catch (err) {
        status.textContent = err.message;
        return;
    }

    render(post);
    renderCommentForm();

    status.hidden = true;
    article.hidden = false;
}

function render(post) {
    document.title = `${post.title} · blog`;
    titleEl.textContent = post.title;          // 사용자 입력이므로 textContent

    metaEl.replaceChildren();
    const category = document.createElement("span");
    category.className = "category-tag";
    category.textContent = post.category.name;
    const rest = document.createElement("span");
    rest.textContent = ` · ${post.user.nickname} · ${formatDate(post.created_at)}`;
    metaEl.append(category, rest);

    // 저장된 건 마크다운 텍스트. 뷰어가 HTML 로 바꿔 그린다
    toastui.Editor.factory({
        el: viewerEl,
        viewer: true,
        theme: "dark",
        initialValue: post.contents,
    });

    // 내 글에만 수정·삭제를 보인다 (실제 차단은 서버가 한다)
    if (currentUser && currentUser.id === post.user.id) {
        document.getElementById("edit-link").href = `/edit?id=${post.id}`;
        postActions.hidden = false;
    }

    renderComments(post.comments);
}

function renderComments(comments) {
    commentCountEl.textContent = `댓글 ${comments.length}`;
    commentList.replaceChildren();
    for (const comment of comments) {
        commentList.append(createCommentItem(comment));
    }
}

function createCommentItem(comment) {
    const li = document.createElement("li");

    const head = document.createElement("div");
    head.className = "comment-head";

    const author = document.createElement("span");
    author.className = "comment-author";
    author.textContent = comment.user.nickname;

    const when = document.createElement("span");
    when.className = "meta";
    when.textContent = formatDate(comment.created_at);

    head.append(author, when);

    const body = document.createElement("div");
    body.className = "comment-body";
    body.textContent = comment.contents;       // 댓글은 마크다운이 아니라 평문

    li.append(head, body);

    if (currentUser && currentUser.id === comment.user.id) {
        li.append(createCommentActions(comment, li, body));
    }
    return li;
}

function createCommentActions(comment, li, body) {
    const actions = document.createElement("div");
    actions.className = "actions";

    const edit = document.createElement("button");
    edit.className = "ghost-btn";
    edit.textContent = "수정";
    edit.addEventListener("click", () => startEdit(comment, li, body, actions));

    const del = document.createElement("button");
    del.className = "ghost-btn danger";
    del.textContent = "삭제";
    del.addEventListener("click", async () => {
        if (!confirm("댓글을 삭제할까요?")) return;
        try {
            await api.del(`/comment/${comment.id}`);
            li.remove();
            updateCommentCount();
        } catch (err) {
            alert(err.message);
        }
    });

    actions.append(edit, del);
    return actions;
}

// 읽기 모드 → 입력 모드. 저장하거나 취소하면 되돌린다
function startEdit(comment, li, body, actions) {
    const textarea = document.createElement("textarea");
    textarea.value = comment.contents;
    textarea.style.minHeight = "80px";

    const save = document.createElement("button");
    save.className = "ghost-btn";
    save.textContent = "저장";

    const cancel = document.createElement("button");
    cancel.className = "ghost-btn";
    cancel.textContent = "취소";

    const editActions = document.createElement("div");
    editActions.className = "actions";
    editActions.append(save, cancel);

    body.replaceWith(textarea);
    actions.replaceWith(editActions);

    function restore(contents) {
        body.textContent = contents;
        textarea.replaceWith(body);
        editActions.replaceWith(actions);
        comment.contents = contents;
    }

    save.addEventListener("click", async () => {
        save.disabled = true;
        try {
            const updated = await api.patch(`/comment/${comment.id}`, {
                contents: textarea.value,
            });
            restore(updated.contents);
        } catch (err) {
            alert(err.message);
            save.disabled = false;
        }
    });

    cancel.addEventListener("click", () => restore(comment.contents));
}

function updateCommentCount() {
    commentCountEl.textContent = `댓글 ${commentList.children.length}`;
}

// 로그인·인증 상태에 따라 댓글 폼 또는 안내를 보인다
function renderCommentForm() {
    if (currentUser && currentUser.is_verified) {
        commentForm.hidden = false;
        return;
    }

    commentGuard.hidden = false;
    const href = currentUser ? "/signup" : "/login";
    const text = currentUser ? "이메일 인증" : "로그인";

    commentGuard.append(document.createTextNode("댓글을 쓰려면 "));
    const link = document.createElement("a");
    link.href = href;
    link.textContent = text;
    commentGuard.append(link, document.createTextNode("이 필요합니다."));
}

commentForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    commentError.textContent = "";
    commentSubmit.disabled = true;

    try {
        // 댓글 생성은 갱신된 글 전체를 돌려준다 → 목록을 통째로 다시 그린다
        const post = await api.post(`/page/${postId}/comment`, {
            contents: commentInput.value,
        });
        renderComments(post.comments);
        commentInput.value = "";
    } catch (err) {
        commentError.textContent = err.message;
    } finally {
        commentSubmit.disabled = false;
    }
});

document.getElementById("delete-btn").addEventListener("click", async () => {
    if (!confirm("글을 삭제할까요?")) return;
    try {
        await api.del(`/page/${postId}`);
        location.href = "/";
    } catch (err) {
        alert(err.message);
    }
});

init();