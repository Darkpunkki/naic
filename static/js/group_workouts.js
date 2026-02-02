document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('feedFiltersForm') || document.querySelector('form[action*="/workouts"]');
    if (!form) return;

    const groupFeedSelector = document.getElementById('groupFeedSelector');
    if (groupFeedSelector && !groupFeedSelector.disabled) {
        groupFeedSelector.addEventListener('change', () => {
            const groupId = groupFeedSelector.value;
            if (!groupId) return;
            window.location.href = `/groups/feed?group_id=${encodeURIComponent(groupId)}`;
        });
    }

    const autoSubmitIds = ['memberFilter', 'fromDate', 'toDate'];
    autoSubmitIds.forEach((id) => {
        const element = document.getElementById(id);
        if (!element) return;
        element.addEventListener('change', () => form.submit());
    });
});
