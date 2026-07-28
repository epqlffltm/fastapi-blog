// 2026-07-24 글 상세 + 댓글 (본문은 마크다운 뷰어로 렌더, 답글은 1단계)
// 2026-07-25 관리자(can_manage_post) 수정·삭제 노출 / 삭제됨 뱃지 / 삭제 복구
// 2026-07-26 조회수 표시 / 좋아요 버튼
// 2026-07-27 작성자 닉네임 → 공개 프로필 링크
// 2026-07-28 작성자 클릭: 내 아이디면 /profile, 아니면 /user/{id}

const postId = new URLSearchParams(location.search).get("id");

const article = document.getElementById("post");
const status = document.getElementById("status");
const titleEl = document.getElementById("title");
const metaEl = document.getElementById("meta");
const viewerEl = document.getElementById("viewer");
const postActions = document.getElementById("post-actions");

const likeBtn = document.getElementById("like-btn");
const likeIcon = document.getElementById("like-icon");
const likeCount = document.getElementById("like-count");

const commentCountEl = document.getElementById("comment-count");
const commentList = document.getElementById("comment-list");
const commentForm = document.getElementById("comment-form");
const commentInput = document.getElementById("comment-input");
const commentError = document.getElementById("comment-error");
const commentSubmit = document.getElementById("comment-submit");
const commentGuard = document.getElementById("comment-guard");

let currentUser = null;

function canWriteComment() {
    return (
        currentUser !== null
        && currentUser.is_verified
        && isActive(currentUser)
        && can(currentUser, "can_comment")
    );
}

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

    try {
        render(post);
        renderCommentForm();
    } catch (err) {
        console.error("post render failed:", err);
        status.textContent = "글을 표시하는 중 문제가 생겼습니다.";
        status.hidden = false;
        article.hidden = false;
        return;
    }

    status.hidden = true;
    article.hidden = false;
}

function renderBody(contents) {
    try {
        toastui.Editor.factory({
            el: viewerEl,
            viewer: true,
            theme: "dark",
            initialValue: contents,
        });
    } catch (err) {
        console.error("markdown viewer unavailable, falling back to plain text:", err);

        const pre = document.createElement("pre");
        pre.className = "markdown-fallback";
        pre.textContent = contents;
        viewerEl.replaceChildren(pre);
    }
}

function render(post) {
    document.title = `${post.title} · blog`;
    titleEl.textContent = post.title;

    const canManage =
        currentUser &&
        (currentUser.id === post.user.id || currentUser.can_manage_post);
    if (canManage) {
        document.getElementById("edit-link").href = `/edit?id=${post.id}`;
        postActions.hidden = false;
        if (post.is_deleted) {
            document.getElementById("delete-btn").hidden = true;
        }
    }

    metaEl.replaceChildren();
    const category = document.createElement("span");
    category.className = "category-tag";
    category.textContent = post.category.name;

    const sep1 = document.createElement("span");
    sep1.textContent = " · ";

    // ★ 내 아이디면 /profile, 아니면 /user/{id}
    const authorLink = document.createElement("a");
    authorLink.href = authorHref(post.user.id);
    authorLink.className = "author-link";
    authorLink.textContent = post.user.nickname;

    const rest = document.createElement("span");
    rest.textContent = ` · ${formatDate(post.created_at)} · 조회 ${post.view_count}`;
    metaEl.append(category, sep1, authorLink, rest);

    if (post.is_deleted) {
        const badge = document.createElement("span");
        badge.className = "deleted-badge";
        badge.textContent = "삭제됨";
        titleEl.append(badge);

        const restore = document.createElement("button");
        restore.className = "ghost-btn";
        restore.textContent = "복구";
        restore.addEventListener("click", async () => {
            if (!confirm("이 글을 복구할까요?")) return;
            try {
                await api.post(`/page/${post.id}/restore`, {});
                location.reload();
            } catch (err) {
                alert(err.message);
            }
        });
        postActions.append(restore);
    }

    renderBody(post.contents);

    if (!post.is_deleted) {
        setupLikeBar(post.id);
    }

    renderComments(post.comments);
}

async function setupLikeBar(postId) {
    likeBtn.hidden = false;

    try {
        renderLike(await api.get(`/page/${postId}/like`));
    } catch (err) {
        // 상태 조회 실패해도 버튼은 0으로 남겨둔다
    }

    likeBtn.addEventListener("click", async () => {
        if (!currentUser) {
            alert("로그인이 필요합니다.");
            return;
        }
        try {
            renderLike(await api.post(`/page/${postId}/like`, {}));
        } catch (err) {
            alert(err.message);
        }
    });
}

function renderLike(status) {
    likeIcon.textContent = status.liked ? "♥" : "♡";
    likeCount.textContent = status.like_count;
    likeBtn.classList.toggle("liked", status.liked);
}

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
        if (comment.parent_id !== null) continue;
        commentList.append(createCommentItem(comment));
        for (const reply of repliesOf.get(comment.id) ?? []) {
            commentList.append(createCommentItem(reply));
        }
    }
}

function createCommentItem(comment) {
    const li = document.createElement("li");
    if (comment.parent_id !== null) li.classList.add("reply");

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
    body.textContent = comment.contents;

    li.append(head, body);
    li.append(createCommentActions(comment, li, body));
    return li;
}

function createCommentActions(comment, li, body) {
    const actions = document.createElement("div");
    actions.className = "actions";

    if (comment.parent_id === null && canWriteComment()) {
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
        del.className = "ghost-btn";
        del.textContent = "삭제";
        del.addEventListener("click", async () => {
            if (!confirm("댓글을 삭제할까요?")) return;
            try {
                await api.del(`/comment/${comment.id}`);
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

function toggleReplyForm(parent, li, replyBtn) {
    const existing = li.querySelector(".reply-form");
    if (existing) {
        existing.remove();
        replyBtn.textContent = "답글";
        return;
    }

    replyBtn.textContent = "취소";

    const form = document.createElement("form");
    form.className = "reply-form";

    const textarea = document.createElement("textarea");
    textarea.rows = 3;
    textarea.required = true;
    textarea.placeholder = "답글을 입력하세요";

    const submit = document.createElement("button");
    submit.type = "submit";
    submit.className = "primary";
    submit.textContent = "등록";

    form.append(textarea, submit);
    li.append(form);

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        submit.disabled = true;
        try {
            const post = await api.post(`/page/${postId}/comment`, {
                contents: textarea.value,
                parent_id: parent.id,
            });
            renderComments(post.comments);
        } catch (err) {
            alert(err.message);
            submit.disabled = false;
        }
    });
}

function startEdit(comment, li, body, actions) {
    const textarea = document.createElement("textarea");
    textarea.rows = 3;
    textarea.value = comment.contents;

    const editActions = document.createElement("div");
    editActions.className = "actions";

    const save = document.createElement("button");
    save.className = "primary";
    save.textContent = "저장";

    const cancel = document.createElement("button");
    cancel.className = "ghost-btn";
    cancel.textContent = "취소";

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

function renderCommentForm() {
    if (canWriteComment()) {
        commentForm.hidden = false;
        return;
    }

    commentGuard.hidden = false;

    if (!currentUser) {
        commentGuard.append(document.createTextNode("댓글을 쓰려면 "));
        const link = document.createElement("a");
        link.href = "/login";
        link.textContent = "로그인";
        commentGuard.append(link, document.createTextNode("이 필요합니다."));
        return;
    }
    if (!currentUser.is_verified) {
        commentGuard.append(document.createTextNode("댓글을 쓰려면 "));
        const link = document.createElement("a");
        link.href = "/signup";
        link.textContent = "이메일 인증";
        commentGuard.append(link, document.createTextNode("이 필요합니다."));
        return;
    }
    if (currentUser.is_banned) {
        commentGuard.textContent = "이용이 정지된 계정입니다.";
        return;
    }
    if (currentUser.is_suspended) {
        commentGuard.textContent =
            `${formatDate(currentUser.suspended_until)} 까지 댓글을 쓸 수 없습니다.`;
        return;
    }
    commentGuard.textContent = "댓글 권한이 없습니다.";
}

commentForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    commentError.textContent = "";
    commentSubmit.disabled = true;

    try {
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