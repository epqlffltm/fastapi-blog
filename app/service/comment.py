#app/service/comment.py

'''
2026-07-24
댓글 표시 규칙

2026-09-30
글 상세 응답을 스키마로 조립 (ORM 관계 컬렉션을 덮어쓰지 않음)
'''

from ..database.orm import Comment, Post
from ..schema.response import CommentSchema, PostDetailSchema


def visible_comments(comments: list[Comment]) -> list[Comment]:
    """화면에 남길 댓글을 고른다.

    삭제된 원댓글은 답글이 하나라도 살아 있으면 자리표시자로 남긴다.
    지워버리면 답글이 무엇에 대한 답인지 알 수 없게 되기 때문이다.
    삭제된 답글은 남길 이유가 없으므로 그냥 뺀다.
    """
    # 살아 있는 답글이 매달린 부모의 id
    parents_in_use = {
        c.parent_id for c in comments if not c.is_deleted and c.parent_id is not None
    }

    result = [
        c for c in comments
        if not c.is_deleted or (c.parent_id is None and c.id in parents_in_use)
    ]
    return sorted(result, key=lambda c: c.created_at)

def build_post_detail(post: Post) -> PostDetailSchema:
    """표시 규칙을 적용한 글 상세 응답을 만든다.

    예전처럼 post.comments 에 걸러낸 목록을 대입하면, 세션이 추적 중인
    관계 컬렉션을 바꾼 것이 된다. 빠진 댓글은 '관계에서 떨어져 나감'으로
    기록되어 다음 flush 때 post_id 가 NULL 로 바뀔 수 있다.
    ORM 객체는 읽기만 하고, 거르는 일은 응답 스키마 위에서 한다.
    """
    comments = [CommentSchema.model_validate(c) for c in visible_comments(post.comments)]
    return PostDetailSchema.model_validate(post).model_copy(update={"comments": comments})
