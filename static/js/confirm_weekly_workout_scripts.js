/**
 * Confirm Weekly Workout Scripts
 * Handles date selection via FullCalendar and intensity adjustment controls.
 */

// Track selected dates
let selectedDates = [];
let calendar = null;

// ===================================
// FullCalendar Date Selection
// ===================================

document.addEventListener('DOMContentLoaded', function() {
    const calendarEl = document.getElementById('calendarContainer');
    if (!calendarEl) return;

    calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        initialDate: TODAY_STR,
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: ''
        },
        selectable: false,
        dateClick: function(info) {
            handleDateClick(info.dateStr);
        },
        dayCellDidMount: function(info) {
            // Style past dates
            const today = new Date(TODAY_STR);
            today.setHours(0, 0, 0, 0);
            const cellDate = new Date(info.date);
            cellDate.setHours(0, 0, 0, 0);

            if (cellDate < today) {
                info.el.classList.add('fc-day-past');
            }
        }
    });

    calendar.render();
    updateDateSelectionUI();
});

function handleDateClick(dateStr) {
    // Don't allow selecting past dates
    const today = new Date(TODAY_STR);
    today.setHours(0, 0, 0, 0);
    const clickedDate = new Date(dateStr);
    clickedDate.setHours(0, 0, 0, 0);

    if (clickedDate < today) {
        return; // Ignore past dates
    }

    const index = selectedDates.indexOf(dateStr);

    if (index > -1) {
        // Date already selected, remove it
        selectedDates.splice(index, 1);
    } else {
        // Check if we've reached the limit
        if (selectedDates.length >= REQUIRED_DATES) {
            // Remove the oldest date and add the new one
            selectedDates.shift();
        }
        selectedDates.push(dateStr);
    }

    // Sort dates chronologically
    selectedDates.sort((a, b) => new Date(a) - new Date(b));

    updateDateSelectionUI();
}

function updateDateSelectionUI() {
    // Update calendar visual highlighting
    document.querySelectorAll('.fc-daygrid-day').forEach(cell => {
        cell.classList.remove('selected-date');
    });

    selectedDates.forEach(dateStr => {
        const cell = document.querySelector(`[data-date="${dateStr}"]`);
        if (cell) {
            cell.classList.add('selected-date');
        }
    });

    // Update selected dates list
    const listEl = document.getElementById('selectedDatesList');
    if (listEl) {
        if (selectedDates.length === 0) {
            listEl.innerHTML = '<li class="placeholder-item">No dates selected yet</li>';
        } else {
            listEl.innerHTML = selectedDates.map((dateStr, idx) => {
                const date = new Date(dateStr + 'T00:00:00');
                const formatted = date.toLocaleDateString('en-US', {
                    weekday: 'short',
                    month: 'short',
                    day: 'numeric'
                });
                return `<li>
                    <span class="date-number">${idx + 1}</span>
                    <span class="date-text">${formatted}</span>
                    <button type="button" class="btn-remove-date" onclick="removeDate('${dateStr}')" title="Remove">
                        <i class="bi bi-x"></i>
                    </button>
                </li>`;
            }).join('');
        }
    }

    // Update status badge
    const statusEl = document.getElementById('dateSelectionStatus');
    if (statusEl) {
        const count = selectedDates.length;
        const badgeClass = count === REQUIRED_DATES ? 'bg-success' : 'bg-warning';
        statusEl.innerHTML = `<span class="badge ${badgeClass}">${count} / ${REQUIRED_DATES} dates selected</span>`;
    }

    // Update hidden form field
    const hiddenInput = document.getElementById('selectedDatesInput');
    if (hiddenInput) {
        hiddenInput.value = JSON.stringify(selectedDates);
    }

    // Enable/disable confirm button
    const confirmBtn = document.getElementById('confirmButton');
    if (confirmBtn) {
        confirmBtn.disabled = selectedDates.length !== REQUIRED_DATES;
    }
}

function removeDate(dateStr) {
    const index = selectedDates.indexOf(dateStr);
    if (index > -1) {
        selectedDates.splice(index, 1);
        updateDateSelectionUI();
    }
}

// ===================================
// Intensity Adjustment Controls
// ===================================

function adjustValue(button, field, delta) {
    const row = button.closest('tr');
    const input = row.querySelector(`.${field}-input`);

    if (!input) return;

    let currentValue = parseFloat(input.value) || 0;
    let newValue = currentValue + delta;

    // Apply constraints
    const min = parseFloat(input.min) || 0;
    const max = parseFloat(input.max) || Infinity;

    newValue = Math.max(min, Math.min(max, newValue));

    // Round weight to nearest 0.5
    if (field === 'weight') {
        newValue = Math.round(newValue * 2) / 2;
    } else {
        newValue = Math.round(newValue);
    }

    input.value = newValue;

    // Trigger the update
    updateWeeklyMovement(input);
}

async function updateWeeklyMovement(input) {
    const row = input.closest('tr');
    const dayIndex = parseInt(row.dataset.dayIndex);
    const movementIndex = parseInt(row.dataset.movementIndex);

    const sets = row.querySelector('.sets-input').value;
    const reps = row.querySelector('.reps-input').value;
    const weight = row.querySelector('.weight-input').value;

    try {
        const response = await fetch('/pending_weekly/update_movement', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                day_index: dayIndex,
                movement_index: movementIndex,
                sets: sets,
                reps: reps,
                weight: weight
            })
        });

        const data = await response.json();
        if (!data.success) {
            console.error('Failed to update movement:', data.error);
        }
    } catch (error) {
        console.error('Error updating movement:', error);
    }
}

async function removeWeeklyMovement(dayIndex, movementIndex) {
    if (!confirm('Remove this movement from the workout?')) return;

    try {
        const response = await fetch('/pending_weekly/remove_movement', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                day_index: dayIndex,
                movement_index: movementIndex
            })
        });

        const data = await response.json();
        if (data.success) {
            location.reload();
        } else {
            alert(data.error || 'Failed to remove movement');
        }
    } catch (error) {
        console.error('Error removing movement:', error);
        alert('Failed to remove movement');
    }
}

// ===================================
// Add Movement to Day
// ===================================

function toggleAddMovementForDay(dayIndex) {
    const form = document.getElementById(`addMovementForm_${dayIndex}`);
    if (form) {
        form.style.display = form.style.display === 'none' ? 'block' : 'none';
    }
}

async function addWeeklyMovement(dayIndex) {
    const form = document.getElementById(`addMovementForm_${dayIndex}`);
    if (!form) return;

    const movementSelect = form.querySelector('.add-movement-select');
    const setsInput = form.querySelector('.add-sets-input');
    const repsInput = form.querySelector('.add-reps-input');
    const weightInput = form.querySelector('.add-weight-input');

    const movementId = movementSelect.value;
    const sets = setsInput.value;
    const reps = repsInput.value;
    const weight = weightInput.value;

    if (!movementId) {
        alert('Please select a movement');
        return;
    }

    try {
        const response = await fetch('/pending_weekly/add_movement', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                day_index: dayIndex,
                movement_id: movementId,
                sets: sets,
                reps: reps,
                weight: weight
            })
        });

        const data = await response.json();
        if (data.success) {
            location.reload();
        } else {
            alert(data.error || 'Failed to add movement');
        }
    } catch (error) {
        console.error('Error adding movement:', error);
        alert('Failed to add movement');
    }
}

// ===================================
// Utility Functions
// ===================================

function showSpinnerWithMessage(message) {
    const spinner = document.getElementById('loadingSpinner');
    const spinnerText = document.getElementById('spinnerText');

    if (spinnerText) spinnerText.textContent = message;
    if (spinner) spinner.style.display = 'flex';
}

function hideSpinner() {
    const spinner = document.getElementById('loadingSpinner');
    if (spinner) spinner.style.display = 'none';
}

// ===================================
// Cancel Confirmation Handler
// ===================================

document.addEventListener('DOMContentLoaded', function() {
    const cancelButton = document.getElementById('cancelWeeklyButton');
    if (cancelButton) {
        cancelButton.addEventListener('click', function(e) {
            e.preventDefault();

            if (confirm('Are you sure you want to cancel? The generated weekly plan will not be saved.')) {
                // Clear pending weekly plan from session and redirect
                fetch('/cancel_pending_weekly', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                }).then(() => {
                    window.location.href = '/';
                }).catch(() => {
                    // Redirect anyway even if clear fails
                    window.location.href = '/';
                });
            }
        });
    }
});
