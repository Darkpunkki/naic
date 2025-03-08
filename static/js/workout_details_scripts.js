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

function showSpinnerWithMessage(message) {
    // Find the spinner container and text
    const spinner = document.getElementById('loadingSpinner');
    const spinnerText = document.getElementById('spinnerText');

    // Update the text
    spinnerText.textContent = message;

    // Show the spinner
    spinner.style.display = 'block';
}

function hideSpinner() {
    const spinner = document.getElementById('loadingSpinner');
    spinner.style.display = 'none';
}
