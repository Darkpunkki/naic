document.addEventListener('DOMContentLoaded', function () {
    const calendarEl = document.getElementById('calendar');
    const isMobile = window.innerWidth < 768;

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
        firstDay: 1, // Monday
        locale: 'en-gb',
        events: workoutEvents, // use the global variable defined in the HTML
        editable: true, // Enable drag-and-drop
        height: isMobile ? 700 : 'auto', // Taller calendar on mobile
        contentHeight: isMobile ? 650 : 600,
        expandRows: true, // Use full height available
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
                alert("Workout ID is missing!");
            }
        },
        eventDrop: async function (info) {
            const workoutId = info.event.extendedProps.workout_id;
            const newDate = info.event.startStr; // Format: YYYY-MM-DD

            try {
                const response = await fetch(`/update_workout_date/${workoutId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ new_date: newDate })
                });

                if (response.ok) {
                    const data = await response.json();
                    if (!data.success) {
                        // Revert the drag if update failed
                        info.revert();
                        alert(data.error || 'Failed to update workout date.');
                    }
                } else {
                    info.revert();
                    const data = await response.json();
                    alert(data.error || 'Failed to update workout date.');
                }
            } catch (error) {
                console.error('Error updating workout date:', error);
                info.revert();
                alert('An error occurred while updating the workout date.');
            }
        },
        dateClick: async function (info) {
            const date = info.dateStr;
            // Make a POST request to create a new workout
            try {
                const response = await fetch('/new_workout', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ workoutDate: date })
                });
                if (response.ok) {
                    const data = await response.json();
                    const workoutId = data.workout_id;
                    if (workoutId) {
                        window.location.href = `/workout/${workoutId}`;
                    } else {
                        alert('Workout creation failed: No workout ID returned.');
                    }
                } else {
                    alert('Failed to create workout. Please try again.');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('An unexpected error occurred.');
            }
        }
    });

    calendar.render();

    // Handle window resize - no view switching needed since we use dayGridWeek for all screen sizes
    // Removed automatic view switching on resize
});
