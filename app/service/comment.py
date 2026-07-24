#app/service/comment.py

'''
2026-07-24
댓글 표시 규칙
'''

from ..database.orm import Comment


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