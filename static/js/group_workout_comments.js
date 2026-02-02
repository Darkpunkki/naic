function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}

function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = value ?? '';
    return div.innerHTML;
}

function formatAbsoluteTimestamp(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return isoString;
    return date.toLocaleString();
}

function formatRelativeTimestamp(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return '';
    if (typeof Intl === 'undefined' || typeof Intl.RelativeTimeFormat !== 'function') return '';

    const deltaMs = date.getTime() - Date.now();
    const seconds = Math.round(deltaMs / 1000);
    const absSeconds = Math.abs(seconds);
    const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });

    if (absSeconds < 60) return rtf.format(seconds, 'second');
    const minutes = Math.round(seconds / 60);
    if (Math.abs(minutes) < 60) return rtf.format(minutes, 'minute');
    const hours = Math.round(minutes / 60);
    if (Math.abs(hours) < 24) return rtf.format(hours, 'hour');
    const days = Math.round(hours / 24);
    return rtf.format(days, 'day');
}

function formatTimestamp(isoString) {
    const absolute = formatAbsoluteTimestamp(isoString);
    const relative = formatRelativeTimestamp(isoString);
    if (!absolute) return '';
    if (!relative) return absolute;
    return `${absolute} (${relative})`;
}

function formatCommentBody(body) {
    return escapeHtml(body).replace(/\n/g, '<br>');
}

function authorInitial(username) {
    if (!username || !String(username).trim()) return '?';
    return String(username).trim().charAt(0).toUpperCase();
}

function buildCommentActions(comment) {
    const actions = [];
    if (comment.can_edit) {
        actions.push(`<button type="button" class="btn btn-sm btn-outline-light" onclick="editComment(${comment.comment_id})">Edit</button>`);
    }
    if (comment.can_delete) {
        actions.push(`<button type="button" class="btn btn-sm btn-outline-danger" onclick="deleteComment(${comment.comment_id})">Delete</button>`);
    }
    return actions.join('');
}

function renderComment(comment) {
    const mutedClass = comment.is_deleted ? 'text-muted fst-italic' : '';
    const editedTag = comment.updated_at ? ' - edited' : '';
    const timestamp = `${escapeHtml(formatTimestamp(comment.created_at))}${editedTag}`;

    return `
        <article class="comment-item" data-comment-id="${comment.comment_id}">
            <span class="comment-avatar">${escapeHtml(authorInitial(comment.author_username))}</span>
            <div class="comment-main">
                <div class="comment-head">
                    <div>
                        <span class="comment-author">${escapeHtml(comment.author_username || 'Unknown')}</span>
                        <span class="comment-time">${timestamp}</span>
                    </div>
                    <div class="comment-actions">${buildCommentActions(comment)}</div>
                </div>
                <p class="comment-text ${mutedClass}">${formatCommentBody(comment.body || '')}</p>
            </div>
        </article>
    `;
}

function renderComments(comments) {
    const commentsList = document.getElementById('commentsList');
    const commentCount = document.getElementById('commentCount');
    if (!commentsList || !commentCount) return;

    commentCount.textContent = String(comments.length);
    if (!comments.length) {
        commentsList.innerHTML = '<div id="commentsEmptyState" class="comment-empty">No comments yet. Start the discussion.</div>';
        return;
    }

    commentsList.innerHTML = comments.map(renderComment).join('');
}

let currentComments = [];

async function refreshComments() {
    const response = await fetch(`/groups/${GROUP_ID}/workouts/${WORKOUT_ID}/comments`, {
        headers: { 'Accept': 'application/json' },
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.error || 'Failed to load comments');
    }
    currentComments = data.comments || [];
    renderComments(currentComments);
}

async function createComment(body) {
    const response = await fetch(`/groups/${GROUP_ID}/workouts/${WORKOUT_ID}/comments`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
            'Accept': 'application/json',
        },
        body: JSON.stringify({ body }),
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.error || 'Failed to post comment');
    }
    return data.comment;
}

async function patchComment(commentId, body) {
    const response = await fetch(`/groups/${GROUP_ID}/workouts/${WORKOUT_ID}/comments/${commentId}`, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
            'Accept': 'application/json',
        },
        body: JSON.stringify({ body }),
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.error || 'Failed to update comment');
    }
    return data.comment;
}

async function removeComment(commentId) {
    const response = await fetch(`/groups/${GROUP_ID}/workouts/${WORKOUT_ID}/comments/${commentId}`, {
        method: 'DELETE',
        headers: {
            'X-CSRFToken': getCsrfToken(),
            'Accept': 'application/json',
        },
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.error || 'Failed to delete comment');
    }
    return data.comment;
}

document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('newCommentForm');
    const bodyField = document.getElementById('commentBody');
    if (!form || !bodyField) return;

    form.addEventListener('submit', async function (event) {
        event.preventDefault();
        const body = (bodyField.value || '').trim();
        if (!body) {
            alert('Comment cannot be empty.');
            return;
        }

        try {
            await createComment(body);
            bodyField.value = '';
            await refreshComments();
        } catch (error) {
            console.error(error);
            alert(error.message || 'Failed to post comment');
        }
    });

    refreshComments().catch((error) => {
        console.error(error);
    });
});

async function editComment(commentId) {
    const comment = currentComments.find((item) => item.comment_id === commentId);
    if (!comment || comment.is_deleted) return;

    const nextBody = prompt('Edit your comment:', comment.body);
    if (nextBody === null) return;

    try {
        await patchComment(commentId, nextBody);
        await refreshComments();
    } catch (error) {
        console.error(error);
        alert(error.message || 'Failed to update comment');
    }
}

async function deleteComment(commentId) {
    if (!confirm('Delete this comment?')) return;
    try {
        await removeComment(commentId);
        await refreshComments();
    } catch (error) {
        console.error(error);
        alert(error.message || 'Failed to delete comment');
    }
}
