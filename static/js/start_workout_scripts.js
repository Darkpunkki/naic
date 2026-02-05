document.addEventListener('DOMContentLoaded', function () {
    const calendarEl = document.getElementById('calendar');
    const isMobile = window.innerWidth < 768;
    const csrf = typeof csrfToken !== 'undefined' ? csrfToken : '';
    const searchInput = document.getElementById('workoutSearchInput');
    const existingWorkoutList = document.getElementById('existingWorkoutList');
    const existingWorkoutItems = document.querySelectorAll('.existing-workout-item');
    const toggleExistingWorkoutsButton = document.getElementById('toggleExistingWorkouts');
    const quickStartButton = document.getElementById('quickStartButton');
    const initialVisibleCount = parseInt(existingWorkoutList?.dataset.initialVisible || '10', 10);
    let isExpanded = false;

    function jsonHeaders() {
        const headers = { 'Content-Type': 'application/json' };
        if (csrf) {
            headers['X-CSRFToken'] = csrf;
        }
        return headers;
    }

    async function parseJsonSafely(response) {
        try {
            return await response.json();
        } catch (error) {
            return {};
        }
    }

    function toggleButtonBusy(button, busy, busyLabel) {
        if (!button) return;
        if (!button.dataset.defaultLabel) {
            button.dataset.defaultLabel = button.textContent.trim();
        }
        button.disabled = busy;
        button.textContent = busy ? busyLabel : button.dataset.defaultLabel;
    }

    async function startWorkoutNow(workoutId, button) {
        toggleButtonBusy(button, true, 'Starting...');
        try {
            const response = await fetch(`/workout/${workoutId}/start_now`, {
                method: 'POST',
                headers: jsonHeaders(),
                body: JSON.stringify({})
            });
            const data = await parseJsonSafely(response);
            if (!response.ok || !data.workout_id) {
                throw new Error(data.error || 'Failed to start workout.');
            }
            window.location.href = `/active_workout/${data.workout_id}`;
        } catch (error) {
            alert(error.message || 'Failed to start workout.');
            toggleButtonBusy(button, false, '');
        }
    }

    async function quickStartWorkout(button) {
        toggleButtonBusy(button, true, 'Creating...');
        try {
            const response = await fetch('/workouts/quick_start', {
                method: 'POST',
                headers: jsonHeaders(),
                body: JSON.stringify({})
            });
            const data = await parseJsonSafely(response);
            if (!response.ok || !data.workout_id) {
                throw new Error(data.error || 'Failed to create quick workout.');
            }
            window.location.href = `/active_workout/${data.workout_id}`;
        } catch (error) {
            alert(error.message || 'Failed to create quick workout.');
            toggleButtonBusy(button, false, '');
        }
    }

    function filterExistingWorkouts(query) {
        const normalized = query.trim().toLowerCase();
        let visibleCount = 0;

        existingWorkoutItems.forEach(item => {
            const workoutName = item.dataset.workoutName || '';
            const workoutDate = item.dataset.workoutDate || '';
            const matchesSearch = !normalized
                || workoutName.includes(normalized)
                || workoutDate.includes(normalized);

            if (!matchesSearch) {
                item.style.display = 'none';
                return;
            }

            if (!normalized && !isExpanded && visibleCount >= initialVisibleCount) {
                item.style.display = 'none';
                return;
            }

            item.style.display = '';
            visibleCount += 1;
        });

        if (toggleExistingWorkoutsButton) {
            if (normalized) {
                toggleExistingWorkoutsButton.style.display = 'none';
            } else if (existingWorkoutItems.length > initialVisibleCount) {
                toggleExistingWorkoutsButton.style.display = '';
                toggleExistingWorkoutsButton.textContent = isExpanded ? 'Show Less' : 'Show More';
            } else {
                toggleExistingWorkoutsButton.style.display = 'none';
            }
        }
    }

    document.querySelectorAll('.start-now-btn').forEach(button => {
        button.addEventListener('click', () => {
            const workoutId = button.dataset.workoutId;
            if (!workoutId) {
                alert('Workout ID is missing.');
                return;
            }
            startWorkoutNow(workoutId, button);
        });
    });

    if (quickStartButton) {
        quickStartButton.addEventListener('click', () => quickStartWorkout(quickStartButton));
    }

    if (searchInput) {
        searchInput.addEventListener('input', (event) => {
            filterExistingWorkouts(event.target.value);
        });
    }

    if (toggleExistingWorkoutsButton) {
        toggleExistingWorkoutsButton.addEventListener('click', () => {
            isExpanded = !isExpanded;
            filterExistingWorkouts(searchInput ? searchInput.value : '');
        });
    }

    filterExistingWorkouts('');

    const calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: isMobile ? 'dayGridWeek' : 'dayGridWeek',
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'timeGridDay,dayGridWeek,dayGridMonth'
        },
        views: {
            timeGridDay: {
                type: 'timeGrid',
                duration: { days: 1 },
                buttonText: 'Day',
                allDaySlot: true,
                slotMinTime: '06:00:00',
                slotMaxTime: '22:00:00'
            }
        },
        firstDay: 1,
        locale: 'en-gb',
        events: workoutEvents,
        editable: true,
        height: isMobile ? 700 : 'auto',
        contentHeight: isMobile ? 650 : 600,
        expandRows: true,
        eventContent: function (info) {
            const title = document.createElement('div');
            title.innerHTML = info.event.title;
            title.style.textAlign = 'center';
            return { domNodes: [title] };
        },
        eventClick: function (info) {
            const workoutId = info.event.extendedProps.workout_id;
            if (workoutId) {
                window.location.href = `/workout/${workoutId}`;
            } else {
                alert('Workout ID is missing!');
            }
        },
        eventDrop: async function (info) {
            const workoutId = info.event.extendedProps.workout_id;
            const newDate = info.event.startStr;

            try {
                const response = await fetch(`/update_workout_date/${workoutId}`, {
                    method: 'POST',
                    headers: jsonHeaders(),
                    body: JSON.stringify({ new_date: newDate })
                });

                const data = await parseJsonSafely(response);
                if (!response.ok || !data.success) {
                    info.revert();
                    alert(data.error || 'Failed to update workout date.');
                }
            } catch (error) {
                info.revert();
                alert('An error occurred while updating the workout date.');
            }
        },
        dateClick: function () {
            window.location.href = '/generate_workout';
        }
    });

    calendar.render();
});
