document.addEventListener('DOMContentLoaded', function () {
    const calendarEl = document.getElementById('calendar');
    const calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridWeek',
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,dayGridWeek'
        },
        firstDay: 1, // Monday
        locale: 'en-gb',
        events: workoutEvents, // use the global variable defined in the HTML
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

    // Optional styling for the FullCalendar toolbar
    const toolbar = document.querySelector('.fc-toolbar');
    if (toolbar) {
        toolbar.style.display = 'block';
        toolbar.style.textAlign = 'center';
    }
    const chunks = document.querySelectorAll('.fc-toolbar-chunk');
    chunks.forEach(chunk => {
        chunk.style.display = 'flex';
        chunk.style.margin = '10px';
    });
});
