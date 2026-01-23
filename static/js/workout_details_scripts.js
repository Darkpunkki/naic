document.addEventListener('DOMContentLoaded', function () {
    // Only set completion_date if it's empty.
    const completionDateInput = document.getElementById('completion_date');
    if (completionDateInput && !completionDateInput.value) {
        const today = new Date().toISOString().split('T')[0];
        completionDateInput.value = today;
    }
});

// Toggle "Add a Movement" form
function toggleNewMovement() {
    const form = document.getElementById('newMovementForm');
    const displayState = form.style.display;
    form.style.display = (displayState === 'none' || displayState === '')
        ? 'block'
        : 'none';
}

function toggleMovementFields() {
    const existingSection = document.getElementById('existingMovementSection');
    const newSection = document.getElementById('newMovementSection');
    const optionExisting = document.getElementById('optionExisting');

    if (optionExisting.checked) {
        existingSection.style.display = 'block';
        newSection.style.display = 'none';
    } else {
        existingSection.style.display = 'none';
        newSection.style.display = 'block';
    }
}

// Show/hide muscle group details
function updateMuscleGroups() {
    const movementSelect = document.getElementById('movement_id');
    const selectedOption = movementSelect.options[movementSelect.selectedIndex];
    const muscleGroups = JSON.parse(selectedOption.getAttribute('data-muscles') || '[]');

    const muscleGroupSummary = document.getElementById('muscleGroupSummary');
    const muscleGroupList = document.getElementById('muscleGroupList');

    muscleGroupList.innerHTML = ''; // Clear previous entries

    if (muscleGroups.length > 0) {
        muscleGroups.forEach(mg => {
            const listItem = document.createElement('li');
            listItem.className = 'list-group-item';
            listItem.textContent = `${mg.muscle_group.muscle_group_name}: ${mg.target_percentage}%`;
            muscleGroupList.appendChild(listItem);
        });
        muscleGroupSummary.style.display = 'block';
    } else {
        muscleGroupSummary.style.display = 'none';
    }
}

// Toggle workout management
document.addEventListener('DOMContentLoaded', function () {
    const manageWorkoutToggle = document.getElementById('manageWorkoutToggle');
    if (manageWorkoutToggle) {
        manageWorkoutToggle.addEventListener('click', function () {
            const container = document.querySelector('.workout-management-container');
            container.style.display = (container.style.display === 'none' || container.style.display === '')
                ? 'block'
                : 'none';
        });
    }
});

// Toggle generate workout section
document.addEventListener('DOMContentLoaded', function () {
    const toggleGenerateWorkout = document.getElementById('toggleGenerateWorkout');
    if (toggleGenerateWorkout) {
        toggleGenerateWorkout.addEventListener('click', function () {
            const section = document.getElementById('generateWorkoutSection');
            section.style.display = (section.style.display === 'none' || section.style.display === '')
                ? 'block'
                : 'none';
        });
    }
});

// Hide the generate workout section when the close button is clicked
function hideGenerateWorkoutSection() {
    const section = document.getElementById('generateWorkoutSection');
    if (section) {
        section.style.display = 'none';
    }
}

// Example instruction fetch
function fetchInstructions(movementName) {
    showSpinnerWithMessage('Fetching instructions...');

    fetch(`/get_instructions?movement_name=${encodeURIComponent(movementName)}`)
        .then(response => {
            hideSpinner();
            if (!response.ok) {
                throw new Error('Failed to fetch instructions');
            }
            return response.json();
        })
        .then(data => {
            if (data.instructions) {
                const modalTitle = document.getElementById('instructionsModalLabel');
                const modalBody = document.getElementById('instructionsModalBody');

                modalTitle.textContent = `Instructions for ${movementName}`;
                modalBody.textContent = data.instructions;

                // Show the modal
                const modal = new bootstrap.Modal(document.getElementById('instructionsModal'));
                modal.show();
            } else {
                alert('No instructions found for this movement.');
            }
        })
        .catch(error => {
            hideSpinner();
            console.error('Error fetching instructions:', error);
            alert('Failed to fetch instructions. Please try again later.');
        });
}

// Example row highlight for "done" movements
function toggleRowStatus(rowId, isChecked) {
    const rowElement = document.getElementById(`row_${rowId}`);
    if (isChecked) {
        rowElement.classList.add('done-row');
    } else {
        rowElement.classList.remove('done-row');
    }
}

// Example validation before completing workout
function validateWorkoutCompletion() {
    // Implement your logic here, e.g., ensure at least 1 movement is done
    return true;
}

// ===================================
// Workout Duplication Functions
// ===================================

async function duplicateWorkout() {
    const targetDate = document.getElementById('duplicate_date').value;

    if (!targetDate) {
        alert('Please select a target date');
        return;
    }

    if (typeof WORKOUT_ID === 'undefined' || WORKOUT_ID === null) {
        alert('No workout to duplicate');
        return;
    }

    showSpinnerWithMessage('Duplicating workout...');

    try {
        const response = await fetch(`/duplicate_workout/${WORKOUT_ID}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target_date: targetDate })
        });

        const data = await response.json();
        hideSpinner();

        if (data.success) {
            if (confirm(`Workout duplicated successfully! Would you like to view the new workout?`)) {
                window.location.href = `/workout/${data.workout_id}`;
            }
        } else {
            alert(data.error || 'Failed to duplicate workout');
        }
    } catch (error) {
        hideSpinner();
        console.error('Error duplicating workout:', error);
        alert('Failed to duplicate workout. Please try again.');
    }
}

async function duplicateWorkoutGroup() {
    const startDate = document.getElementById('duplicate_week_start_date').value;

    if (!startDate) {
        alert('Please select a start date');
        return;
    }

    if (typeof WORKOUT_GROUP_ID === 'undefined' || WORKOUT_GROUP_ID === null) {
        alert('This workout is not part of a weekly group');
        return;
    }

    showSpinnerWithMessage('Duplicating weekly workout plan...');

    try {
        const response = await fetch(`/duplicate_workout_group/${WORKOUT_GROUP_ID}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ start_date: startDate })
        });

        const data = await response.json();
        hideSpinner();

        if (data.success) {
            alert(`Successfully duplicated ${data.workout_count} workouts!`);
            window.location.href = '/all_workouts';
        } else {
            alert(data.error || 'Failed to duplicate workout group');
        }
    } catch (error) {
        hideSpinner();
        console.error('Error duplicating workout group:', error);
        alert('Failed to duplicate workout group. Please try again.');
    }
}

function showSpinnerWithMessage(message) {
    // Find the spinner container and text
    const spinner = document.getElementById('loadingSpinner');
    const spinnerText = document.getElementById('spinnerText');

    // Update the text
    spinnerText.textContent = message;

    // Show the spinner
    spinner.style.display = 'flex';
}

function hideSpinner() {
    const spinner = document.getElementById('loadingSpinner');
    spinner.style.display = 'none';
}

// ===================================
// Empty Workout Cleanup Handlers
// ===================================

// Track if movements were added during this session
let movementsAddedDuringSession = false;
// Track if a form is being submitted (to avoid deleting workout during form submission)
let formSubmissionInProgress = false;

// Helper function to delete empty workout
async function deleteEmptyWorkout() {
    if (typeof WORKOUT_ID === 'undefined' || WORKOUT_ID === null || IS_CONFIRM_MODE) {
        return false;
    }

    try {
        const response = await fetch(`/delete_if_empty/${WORKOUT_ID}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        return data.deleted === true;
    } catch (error) {
        console.error('Error deleting empty workout:', error);
        return false;
    }
}

// Initialize empty workout cleanup handlers
document.addEventListener('DOMContentLoaded', function() {
    // Only set up handlers if we have a workout and it's not confirm mode
    if (typeof WORKOUT_ID === 'undefined' || WORKOUT_ID === null || IS_CONFIRM_MODE) {
        return;
    }

    // Track form submissions to avoid deleting workout during form submit
    document.querySelectorAll('form').forEach(function(form) {
        form.addEventListener('submit', function() {
            formSubmissionInProgress = true;
        });
    });

    // Track movements being added via MutationObserver
    const movementsList = document.getElementById('movementsList');
    if (movementsList) {
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.addedNodes.length > 0) {
                    movementsAddedDuringSession = true;
                }
            });
        });
        observer.observe(movementsList, { childList: true, subtree: true });
    }

    // Handle Go Back button click
    const goBackButton = document.getElementById('goBackButton');
    if (goBackButton) {
        goBackButton.addEventListener('click', async function(e) {
            e.preventDefault();

            // Check if workout is still empty and we haven't added movements
            if (WORKOUT_IS_EMPTY && !movementsAddedDuringSession) {
                await deleteEmptyWorkout();
            }

            // Navigate to home
            window.location.href = '/';
        });
    }

    // Handle browser back button / page unload for empty workouts
    if (WORKOUT_IS_EMPTY) {
        window.addEventListener('beforeunload', function(e) {
            // Don't delete if form submission is in progress or movements were added
            if (formSubmissionInProgress || movementsAddedDuringSession) {
                return;
            }
            // Use sendBeacon for reliable delivery during page unload
            navigator.sendBeacon(`/delete_if_empty/${WORKOUT_ID}`);
        });
    }
});
