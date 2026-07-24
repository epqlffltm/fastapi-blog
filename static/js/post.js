// 2026-07-24 글 상세 + 댓글 (본문은 마크다운 뷰어로 렌더, 답글은 1단계)

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

// 서버는 시간순 한 줄로 보낸다. 부모 아래 답글이 오도록 여기서 묶는다
function renderComments(comments) {
    const alive = comments.filter((c) => !c.is_deleted).length;
    commentCountEl.textContent = `댓글 ${alive}`;

    const repliesOf = new Map();
    for (const comment of comments) {
        if (comment.parent_id === null) continue;
        if (!repliesOf.has(comment.parent_id)) repliesOf.set(comment.parent_id, []);
        repliesOf.get(comment.parent_id).push(comment);
    }

    commentList.replaceChildren();
    for (const comment of comments) {
        if (comment.parent_id !== null) continue;      // 답글은 부모 차례에 붙는다
        commentList.append(createCommentItem(comment));
        for (const reply of repliesOf.get(comment.id) ?? []) {
            commentList.append(createCommentItem(reply));
        }
    }
}

function createCommentItem(comment) {
    const li = document.createElement("li");
    if (comment.parent_id !== null) li.classList.add("reply");

    // 자리표시자: 답글이 남아 있어 형태만 남긴 삭제된 원댓글
    if (comment.is_deleted) {
        const body = document.createElement("div");
        body.className = "comment-body deleted";
        body.textContent = "삭제된 댓글입니다.";
        li.append(body);
        return li;
    }

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
    li.append(createCommentActions(comment, li, body));
    return li;
}

function createCommentActions(comment, li, body) {
    const actions = document.createElement("div");
    actions.className = "actions";

    // 답글은 원댓글에만 달 수 있다 (깊이 1)
    if (comment.parent_id === null && currentUser && currentUser.is_verified) {
        const reply = document.createElement("button");
        reply.className = "ghost-btn";
        reply.textContent = "답글";
        reply.addEventListener("click", () => toggleReplyForm(comment, li, reply));
        actions.append(reply);
    }

    if (currentUser && currentUser.id === comment.user.id) {
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
                // 답글이 남아 있으면 자리표시자가 되므로 서버에서 다시 받아 그린다
                const post = await api.get(`/page/${postId}`);
                renderComments(post.comments);
            } catch (err) {
                alert(err.message);
            }
        });

        actions.append(edit, del);
    }
    return actions;
}

// 답글 입력창을 댓글 바로 아래에 폈다 접었다 한다
function toggleReplyForm(comment, li, button) {
    const existing = li.querySelector(".reply-form");
    if (existing) {
        existing.remove();
        button.textContent = "답글";
        return;
    }

    const wrap = document.createElement("div");
    wrap.className = "reply-form";

    const textarea = document.createElement("textarea");
    textarea.placeholder = "답글을 입력하세요";
    textarea.style.minHeight = "70px";

    const submit = document.createElement("button");
    submit.className = "ghost-btn";
    submit.textContent = "등록";

    submit.addEventListener("click", async () => {
        if (!textarea.value.trim()) return;
        submit.disabled = true;
        try {
            const post = await api.post(`/page/${postId}/comment`, {
                contents: textarea.value,
                parent_id: comment.id,
            });
            renderComments(post.comments);
        } catch (err) {
            alert(err.message);
            submit.disabled = false;
        }
    });

    wrap.append(textarea, submit);
    li.append(wrap);
    button.textContent = "취소";
    textarea.focus();
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