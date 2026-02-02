function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}

function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = value ?? '';
    return div.innerHTML;
}

function formatTimestamp(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return isoString;
    return date.toLocaleString();
}

function formatCompactNumber(value) {
    const number = Number(value || 0);
    const absolute = Math.abs(number);

    if (absolute >= 1_000_000_000) return `${(number / 1_000_000_000).toFixed(1).replace(/\.0$/, '')}b`;
    if (absolute >= 1_000_000) return `${(number / 1_000_000).toFixed(1).replace(/\.0$/, '')}m`;
    if (absolute >= 1_000) return `${(number / 1_000).toFixed(1).replace(/\.0$/, '')}k`;
    return String(number);
}

function authorInitial(username) {
    if (!username || !String(username).trim()) return '?';
    return String(username).trim().charAt(0).toUpperCase();
}

function commentActions(workoutId, comment) {
    const actions = [];
    if (comment.can_edit) {
        actions.push(`<button type="button" class="btn btn-sm btn-outline-light" onclick="feedEditComment(${workoutId}, ${comment.comment_id})">Edit</button>`);
    }
    if (comment.can_delete) {
        actions.push(`<button type="button" class="btn btn-sm btn-outline-danger" onclick="feedDeleteComment(${workoutId}, ${comment.comment_id})">Delete</button>`);
    }
    return actions.join('');
}

function renderFeedComment(workoutId, comment) {
    const editedTag = comment.updated_at ? ' - edited' : '';
    const mutedClass = comment.is_deleted ? 'text-muted fst-italic' : '';
    return `
        <article class="comment-item" data-comment-id="${comment.comment_id}">
            <span class="comment-avatar">${escapeHtml(authorInitial(comment.author_username))}</span>
            <div class="comment-main">
                <div class="comment-head">
                    <div>
                        <span class="comment-author">${escapeHtml(comment.author_username || 'Unknown')}</span>
                        <span class="comment-time">${escapeHtml(formatTimestamp(comment.created_at))}${editedTag}</span>
                    </div>
                    <div class="comment-actions">${commentActions(workoutId, comment)}</div>
                </div>
                <p class="comment-text ${mutedClass}">${escapeHtml(comment.body || '').replace(/\n/g, '<br>')}</p>
            </div>
        </article>
    `;
}

function renderFeedComments(workoutId, comments) {
    const list = document.getElementById(`feedCommentsList-${workoutId}`);
    const count = document.getElementById(`feedCommentCount-${workoutId}`);
    if (!list || !count) return;

    const visibleCount = comments.filter((comment) => !comment.is_deleted).length;
    count.textContent = formatCompactNumber(visibleCount);

    if (!comments.length) {
        list.innerHTML = '<div class="comment-empty">No comments yet. Start the discussion.</div>';
        return;
    }

    const expanded = Boolean(expandedCommentLists[workoutId]);
    const previewComments = comments.slice(-PREVIEW_COMMENT_COUNT);
    const commentsToRender = expanded ? comments : previewComments;

    let html = commentsToRender.map((comment) => renderFeedComment(workoutId, comment)).join('');
    if (comments.length > PREVIEW_COMMENT_COUNT) {
        const toggleLabel = expanded
            ? `Show latest ${PREVIEW_COMMENT_COUNT}`
            : `Show all ${comments.length}`;
        html += `
            <div class="comment-toggle-wrap">
                <button type="button" class="btn btn-sm btn-outline-light" onclick="toggleFeedCommentView(${workoutId})">
                    ${toggleLabel}
                </button>
            </div>
        `;
    }

    list.innerHTML = html;
}

async function loadWorkoutComments(workoutId) {
    const response = await fetch(`/groups/${GROUP_ID}/workouts/${workoutId}/comments`, {
        headers: { Accept: 'application/json' },
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.error || 'Failed to load comments');
    }
    return data.comments || [];
}

async function createWorkoutComment(workoutId, body) {
    const response = await fetch(`/groups/${GROUP_ID}/workouts/${workoutId}/comments`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
            Accept: 'application/json',
        },
        body: JSON.stringify({ body }),
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.error || 'Failed to post comment');
    }
    return data.comment;
}

async function patchWorkoutComment(workoutId, commentId, body) {
    const response = await fetch(`/groups/${GROUP_ID}/workouts/${workoutId}/comments/${commentId}`, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
            Accept: 'application/json',
        },
        body: JSON.stringify({ body }),
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.error || 'Failed to update comment');
    }
    return data.comment;
}

async function deleteWorkoutComment(workoutId, commentId) {
    const response = await fetch(`/groups/${GROUP_ID}/workouts/${workoutId}/comments/${commentId}`, {
        method: 'DELETE',
        headers: {
            'X-CSRFToken': getCsrfToken(),
            Accept: 'application/json',
        },
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.error || 'Failed to delete comment');
    }
    return data.comment;
}

const feedCommentCache = {};
const expandedCommentLists = {};
const PREVIEW_COMMENT_COUNT = 3;

async function refreshFeedComments(workoutId) {
    const comments = await loadWorkoutComments(workoutId);
    feedCommentCache[workoutId] = comments;
    renderFeedComments(workoutId, comments);
}

document.addEventListener('DOMContentLoaded', function () {
    const forms = document.querySelectorAll('.feed-comment-form');
    forms.forEach((form) => {
        const workoutId = Number(form.getAttribute('data-workout-id'));
        const textarea = document.getElementById(`feedCommentBody-${workoutId}`);
        if (!workoutId || !textarea) return;

        form.addEventListener('submit', async function (event) {
            event.preventDefault();
            const body = (textarea.value || '').trim();
            if (!body) {
                alert('Comment cannot be empty.');
                return;
            }

            try {
                await createWorkoutComment(workoutId, body);
                textarea.value = '';
                expandedCommentLists[workoutId] = true;
                await refreshFeedComments(workoutId);
            } catch (error) {
                console.error(error);
                alert(error.message || 'Failed to post comment');
            }
        });

        refreshFeedComments(workoutId).catch((error) => {
            console.error(error);
        });
    });
});

async function feedEditComment(workoutId, commentId) {
    if (!feedCommentCache[workoutId]) {
        await refreshFeedComments(workoutId);
    }

    const comment = (feedCommentCache[workoutId] || []).find((item) => item.comment_id === commentId);
    if (!comment || comment.is_deleted) return;

    const nextBody = prompt('Edit your comment:', comment.body);
    if (nextBody === null) return;

    try {
        await patchWorkoutComment(workoutId, commentId, nextBody);
        await refreshFeedComments(workoutId);
    } catch (error) {
        console.error(error);
        alert(error.message || 'Failed to update comment');
    }
}

async function feedDeleteComment(workoutId, commentId) {
    if (!confirm('Delete this comment?')) return;

    try {
        await deleteWorkoutComment(workoutId, commentId);
        await refreshFeedComments(workoutId);
    } catch (error) {
        console.error(error);
        alert(error.message || 'Failed to delete comment');
    }
}

function toggleFeedCommentView(workoutId) {
    expandedCommentLists[workoutId] = !Boolean(expandedCommentLists[workoutId]);
    renderFeedComments(workoutId, feedCommentCache[workoutId] || []);
}
