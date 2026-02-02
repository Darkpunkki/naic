/* Active Workout Scripts - State Management Rewrite */

/* ========================================
   WORKOUT STATE MANAGEMENT
   ======================================== */

// Initialize workout state from movementsData (injected from template)
const workoutState = {
    movements: [],
    currentMovementIndex: null,
    currentSetIndex: 0
};

// Initialize state from template data
function initializeWorkoutState() {
    workoutState.movements = movementsData.map((m, idx) => ({
        ...m,
        index: idx,
        status: 'pending',  // 'pending', 'in_progress', 'completed', 'skipped'
        sets: m.sets.map(s => ({
            ...s,
            status: 'pending',  // 'pending', 'completed', 'skipped'
            actualReps: s.reps,
            actualWeight: s.weight
        }))
    }));
}

// Call initialization
initializeWorkoutState();

/* ========================================
   REST TIMER
   ======================================== */

let restTimeLeft = 0;
let restIntervalId = null;

function startRestTimer(duration) {
    const restTimerContainer = document.getElementById('restTimerContainer');
    const restTimerElem = document.getElementById('restTimer');
    restTimeLeft = duration;
    restTimerElem.textContent = restTimeLeft;
    restTimerContainer.style.display = 'block';
    restIntervalId = setInterval(updateRestTimer, 1000);
}

function updateRestTimer() {
    restTimeLeft--;
    document.getElementById('restTimer').textContent = restTimeLeft;
    if (restTimeLeft <= 0) {
        clearInterval(restIntervalId);
        restIntervalId = null;
        document.getElementById('restTimerContainer').style.display = 'none';
        enableSetButtons();
        proceedAfterRest();
    }
}

function adjustRestTimer(delta) {
    restTimeLeft = Math.max(0, restTimeLeft + delta);
    document.getElementById('restTimer').textContent = restTimeLeft;
}

function skipRestTimer() {
    if (restIntervalId) {
        clearInterval(restIntervalId);
        restIntervalId = null;
    }
    document.getElementById('restTimerContainer').style.display = 'none';
    enableSetButtons();
    proceedAfterRest();
}

/* ========================================
   VALUE ADJUSTMENT
   ======================================== */

function adjustValue(fieldId, delta) {
    const input = document.getElementById(fieldId);
    if (input) {
        const currentValue = parseFloat(input.value || 0);
        const newValue = Math.max(0, currentValue + delta);
        const step = input.getAttribute('step');
        let decimals = 0;
        if (step && step.indexOf('.') >= 0) {
            decimals = step.split('.')[1].length;
        }
        input.value = newValue.toFixed(decimals);
    }
}

/* ========================================
   MOVEMENT LIST UI
   ======================================== */

function updateMovementListUI() {
    document.querySelectorAll('.movement-item').forEach((item, index) => {
        const movement = workoutState.movements[index];
        if (!movement) return;

        // Remove all status classes
        item.classList.remove('completed', 'skipped', 'in-progress');

        // Add appropriate status class
        if (movement.status === 'completed') {
            item.classList.add('completed');
        } else if (movement.status === 'skipped') {
            item.classList.add('skipped');
        } else if (movement.status === 'in_progress') {
            item.classList.add('in-progress');
        }

        // Update meta text with completed/skipped sets count
        const completedSets = movement.sets.filter(s => s.status === 'completed').length;
        const skippedSets = movement.sets.filter(s => s.status === 'skipped').length;
        const totalSets = movement.sets.length;

        const metaElem = item.querySelector('.movement-meta');
        if (metaElem) {
            if (movement.status === 'completed') {
                metaElem.textContent = `${totalSets} sets - Done`;
            } else if (movement.status === 'skipped') {
                metaElem.textContent = `${totalSets} sets - Skipped`;
            } else if (completedSets > 0 || skippedSets > 0) {
                metaElem.textContent = `${completedSets}/${totalSets} sets done`;
            } else {
                metaElem.textContent = `${totalSets} sets`;
            }
        }
    });

    // Update completed movements list
    updateCompletedMovementsList();
}

function updateCompletedMovementsList() {
    const container = document.getElementById('completedMovements');
    if (!container) return;

    container.innerHTML = '';

    workoutState.movements.forEach(movement => {
        if (movement.status === 'completed' || movement.status === 'skipped') {
            const li = document.createElement('li');
            li.classList.add('list-group-item');
            if (movement.status === 'skipped') {
                li.innerHTML = `<span class="text-warning">${movement.movementName}</span> <small class="text-muted">(Skipped)</small>`;
            } else {
                li.innerHTML = `<span class="text-success">${movement.movementName}</span> <small class="text-muted">(${movement.sets.length} sets)</small>`;
            }
            container.appendChild(li);
        }
    });
}

/* ========================================
   MOVEMENT SELECTION
   ======================================== */

// Movement click handler
document.querySelectorAll('.movement-item').forEach(item => {
    item.addEventListener('click', function() {
        const chosenIndex = parseInt(this.getAttribute('data-index'));
        const movement = workoutState.movements[chosenIndex];

        if (movement.status === 'completed') {
            // Ask confirmation to redo completed movement
            if (confirm(`"${movement.movementName}" is already completed. Do you want to redo it?`)) {
                // Reset movement status
                movement.status = 'pending';
                movement.sets.forEach(s => {
                    s.status = 'pending';
                });
                selectMovement(chosenIndex);
            }
        } else if (movement.status === 'skipped') {
            // Ask confirmation to do skipped movement
            if (confirm(`"${movement.movementName}" was skipped. Do you want to do it now?`)) {
                movement.status = 'pending';
                movement.sets.forEach(s => {
                    s.status = 'pending';
                });
                selectMovement(chosenIndex);
            }
        } else {
            selectMovement(chosenIndex);
        }
    });
});

function selectMovement(movementIndex) {
    workoutState.currentMovementIndex = movementIndex;
    const movement = workoutState.movements[movementIndex];
    movement.status = 'in_progress';

    // Find first incomplete set
    const firstIncompleteSet = movement.sets.findIndex(s => s.status === 'pending');
    workoutState.currentSetIndex = firstIncompleteSet >= 0 ? firstIncompleteSet : 0;

    updateMovementListUI();
    showMovementDetail();
}

/* ========================================
   MOVEMENT DETAIL VIEW
   ======================================== */

function showMovementDetail() {
    document.getElementById('movementsList').style.display = 'none';
    document.getElementById('movementDetail').style.display = 'block';
    updateMovementDetail();
}

function updateMovementDetail() {
    const movement = workoutState.movements[workoutState.currentMovementIndex];
    if (!movement) return;

    const currentSet = movement.sets[workoutState.currentSetIndex];
    if (!currentSet) return;

    document.getElementById('currentMovementName').textContent = movement.movementName;
    document.getElementById('totalSets').textContent = movement.sets.length;
    document.getElementById('currentSetOrder').textContent = currentSet.setOrder;
    document.getElementById('currentReps').value = currentSet.actualReps;
    document.getElementById('currentWeight').value = currentSet.actualWeight;

    // Update progress indicator
    const completedCount = movement.sets.filter(s => s.status === 'completed').length;
    const progressText = completedCount > 0 ? ` (${completedCount} done)` : '';
    document.getElementById('totalSets').textContent = movement.sets.length + progressText;
}

function goBackToMovements() {
    // Cancel any active rest timer
    if (restIntervalId) {
        clearInterval(restIntervalId);
        restIntervalId = null;
        document.getElementById('restTimerContainer').style.display = 'none';
    }

    enableSetButtons();
    document.getElementById('movementDetail').style.display = 'none';
    document.getElementById('movementsList').style.display = 'block';
    updateMovementListUI();
}

/* ========================================
   SET CONFIRMATION
   ======================================== */

function disableSetButtons() {
    const doneBtn = document.querySelector('#setDetail .btn-success');
    const skipSetBtn = document.querySelector('#setDetail .btn-skip-set');
    if (doneBtn) doneBtn.disabled = true;
    if (skipSetBtn) skipSetBtn.disabled = true;
}

function enableSetButtons() {
    const doneBtn = document.querySelector('#setDetail .btn-success');
    const skipSetBtn = document.querySelector('#setDetail .btn-skip-set');
    if (doneBtn) doneBtn.disabled = false;
    if (skipSetBtn) skipSetBtn.disabled = false;
}

function confirmSet() {
    const movement = workoutState.movements[workoutState.currentMovementIndex];
    const currentSet = movement.sets[workoutState.currentSetIndex];

    // Save updated values from the inputs
    currentSet.actualReps = parseFloat(document.getElementById('currentReps').value);
    currentSet.actualWeight = parseFloat(document.getElementById('currentWeight').value);
    currentSet.status = 'completed';

    // Save values into hidden form inputs
    saveSetToHiddenInputs(currentSet);

    // Disable buttons during rest
    disableSetButtons();

    // Start rest timer
    startRestTimer(60);
}

function saveSetToHiddenInputs(currentSet) {
    const hiddenInputsDiv = document.getElementById('hiddenInputs');

    // Rep input
    let repInput = document.getElementById('hidden_rep_' + currentSet.setId);
    if (!repInput) {
        repInput = document.createElement('input');
        repInput.type = 'hidden';
        repInput.name = 'rep_' + currentSet.setId;
        repInput.id = 'hidden_rep_' + currentSet.setId;
        hiddenInputsDiv.appendChild(repInput);
    }
    repInput.value = currentSet.actualReps;

    // Weight input
    let weightInput = document.getElementById('hidden_weight_' + currentSet.weightId);
    if (!weightInput) {
        weightInput = document.createElement('input');
        weightInput.type = 'hidden';
        weightInput.name = 'weight_' + currentSet.weightId;
        weightInput.id = 'hidden_weight_' + currentSet.weightId;
        hiddenInputsDiv.appendChild(weightInput);
    }
    weightInput.value = currentSet.actualWeight;
}

function proceedAfterRest() {
    const movement = workoutState.movements[workoutState.currentMovementIndex];

    // Find next incomplete set
    const nextIncompleteIndex = movement.sets.findIndex((s, idx) =>
        idx > workoutState.currentSetIndex && s.status === 'pending'
    );

    if (nextIncompleteIndex >= 0) {
        // Move to next incomplete set
        workoutState.currentSetIndex = nextIncompleteIndex;
        updateMovementDetail();
    } else {
        // All sets completed - mark movement as completed
        movement.status = 'completed';
        updateMovementListUI();

        // Find next incomplete movement
        const nextMovement = findNextIncompleteMovement();
        if (nextMovement !== null) {
            selectMovement(nextMovement);
        } else {
            // All movements done - show completion form
            showCompletionForm();
        }
    }
}

function findNextIncompleteMovement() {
    // First try movements after current one
    for (let i = workoutState.currentMovementIndex + 1; i < workoutState.movements.length; i++) {
        if (workoutState.movements[i].status === 'pending' || workoutState.movements[i].status === 'in_progress') {
            return i;
        }
    }
    // Then check from beginning
    for (let i = 0; i < workoutState.currentMovementIndex; i++) {
        if (workoutState.movements[i].status === 'pending' || workoutState.movements[i].status === 'in_progress') {
            return i;
        }
    }
    return null;
}

function showCompletionForm() {
    document.getElementById('movementDetail').style.display = 'none';
    document.getElementById('movementsList').style.display = 'none';
    document.getElementById('completeWorkoutForm').style.display = 'block';
}

/* ========================================
   SKIP FUNCTIONALITY
   ======================================== */

function skipSet() {
    const movement = workoutState.movements[workoutState.currentMovementIndex];
    const currentSet = movement.sets[workoutState.currentSetIndex];

    // Mark set as skipped
    currentSet.status = 'skipped';

    // Add hidden input for skipped set
    const hiddenInputsDiv = document.getElementById('hiddenInputs');
    let skippedInput = document.getElementById('hidden_skipped_' + currentSet.setId);
    if (!skippedInput) {
        skippedInput = document.createElement('input');
        skippedInput.type = 'hidden';
        skippedInput.name = 'skipped_' + currentSet.setId;
        skippedInput.id = 'hidden_skipped_' + currentSet.setId;
        skippedInput.value = '1';
        hiddenInputsDiv.appendChild(skippedInput);
    }

    // Proceed immediately without rest timer
    proceedAfterRest();
}

function skipMovement() {
    if (!confirm('Skip the entire movement? All remaining sets will be marked as skipped.')) {
        return;
    }

    const movement = workoutState.movements[workoutState.currentMovementIndex];

    // Mark all pending sets as skipped
    movement.sets.forEach(set => {
        if (set.status === 'pending') {
            set.status = 'skipped';

            // Add hidden input for skipped set
            const hiddenInputsDiv = document.getElementById('hiddenInputs');
            let skippedInput = document.getElementById('hidden_skipped_' + set.setId);
            if (!skippedInput) {
                skippedInput = document.createElement('input');
                skippedInput.type = 'hidden';
                skippedInput.name = 'skipped_' + set.setId;
                skippedInput.id = 'hidden_skipped_' + set.setId;
                skippedInput.value = '1';
                hiddenInputsDiv.appendChild(skippedInput);
            }
        }
    });

    // Mark movement as skipped
    movement.status = 'skipped';
    updateMovementListUI();

    // Find next incomplete movement
    const nextMovement = findNextIncompleteMovement();
    if (nextMovement !== null) {
        selectMovement(nextMovement);
    } else {
        showCompletionForm();
    }
}

/* ========================================
   ADD SET FUNCTIONALITY
   ======================================== */

function addSetToCurrentMovement() {
    const movement = workoutState.movements[workoutState.currentMovementIndex];
    if (!movement) return;

    // Get workout_movement_id from template data
    const workoutMovementId = movement.workoutMovementId;
    if (!workoutMovementId) {
        alert('Unable to add set: missing workout movement ID');
        return;
    }

    showSpinnerWithMessage('Adding set...');

    fetch(`/add_set/${workoutMovementId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({})
    })
    .then(response => response.json())
    .then(data => {
        hideSpinner();
        if (data.success) {
            // Add new set to state
            const newSet = {
                setId: data.set.setId,
                setOrder: data.set.setOrder,
                reps: data.set.reps,
                weight: data.set.weight,
                weightId: data.set.weightId,
                status: 'pending',
                actualReps: data.set.reps,
                actualWeight: data.set.weight
            };
            movement.sets.push(newSet);

            // Update UI
            updateMovementDetail();
            alert(`Set ${data.set.setOrder} added!`);
        } else {
            alert('Failed to add set: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        hideSpinner();
        console.error('Error adding set:', error);
        alert('Failed to add set. Please try again.');
    });
}

/* ========================================
   ADD MOVEMENT FUNCTIONALITY
   ======================================== */

function filterMovements() {
    const searchTerm = document.getElementById('movementSearch').value.toLowerCase();
    const muscleGroupFilter = document.getElementById('muscleGroupFilter').value;
    const select = document.getElementById('newMovementId');

    // Filter options based on search and muscle group
    Array.from(select.options).forEach(option => {
        if (option.value === '') {
            option.style.display = '';
            return;
        }

        const movementName = option.textContent.toLowerCase();
        const muscleGroups = option.dataset.muscleGroups || '';

        const matchesSearch = movementName.includes(searchTerm);
        const matchesMuscle = !muscleGroupFilter || muscleGroups.includes(muscleGroupFilter);

        option.style.display = (matchesSearch && matchesMuscle) ? '' : 'none';
    });
}

function addMovementToWorkout() {
    const movementId = document.getElementById('newMovementId').value;
    const sets = parseInt(document.getElementById('newMovementSets').value) || 3;
    const reps = parseInt(document.getElementById('newMovementReps').value) || 10;
    const weight = parseFloat(document.getElementById('newMovementWeight').value) || 0;

    if (!movementId) {
        alert('Please select a movement');
        return;
    }

    showSpinnerWithMessage('Adding movement...');

    fetch(`/active_workout/${workoutId}/add_movement`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            movement_id: movementId,
            sets: sets,
            reps: reps,
            weight: weight
        })
    })
    .then(response => response.json())
    .then(data => {
        hideSpinner();
        if (data.success) {
            // Add new movement to state
            const newMovement = {
                movementName: data.movement.movementName,
                workoutMovementId: data.movement.workout_movement_id,
                index: workoutState.movements.length,
                status: 'pending',
                sets: data.movement.sets.map(s => ({
                    setId: s.setId,
                    setOrder: s.setOrder,
                    reps: s.reps,
                    weight: s.weight,
                    weightId: s.weightId,
                    status: 'pending',
                    actualReps: s.reps,
                    actualWeight: s.weight
                }))
            };
            workoutState.movements.push(newMovement);

            // Add to movement list UI
            addMovementToList(newMovement);

            // Collapse the panel
            const panel = document.getElementById('addMovementPanel');
            if (panel) {
                const bsCollapse = bootstrap.Collapse.getInstance(panel);
                if (bsCollapse) bsCollapse.hide();
            }

            // Reset form
            document.getElementById('newMovementId').value = '';
            document.getElementById('newMovementSets').value = '3';
            document.getElementById('newMovementReps').value = '10';
            document.getElementById('newMovementWeight').value = '0';

            alert(`${data.movement.movementName} added to workout!`);
        } else {
            alert('Failed to add movement: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        hideSpinner();
        console.error('Error adding movement:', error);
        alert('Failed to add movement. Please try again.');
    });
}

function addMovementToList(movement) {
    const movementList = document.querySelector('.movement-list');
    if (!movementList) return;

    const li = document.createElement('li');
    li.className = 'movement-item';
    li.setAttribute('data-index', movement.index);
    li.innerHTML = `
        <div class="movement-info">
            <span class="movement-title">${movement.movementName}</span>
            <span class="movement-meta">${movement.sets.length} sets</span>
        </div>
        <span class="movement-arrow"><i class="bi bi-chevron-right"></i></span>
    `;

    // Add click handler
    li.addEventListener('click', function() {
        const chosenIndex = parseInt(this.getAttribute('data-index'));
        selectMovement(chosenIndex);
    });

    movementList.appendChild(li);
}

/* ========================================
   INSTRUCTIONS MODAL
   ======================================== */

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
                modalBody.style.whiteSpace = 'pre-line';
                modalBody.textContent = data.instructions;
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

/* ========================================
   UTILITY FUNCTIONS
   ======================================== */

function showSpinnerWithMessage(message) {
    const spinner = document.getElementById('loadingSpinner');
    const spinnerText = document.getElementById('spinnerText');
    spinnerText.textContent = message;
    spinner.style.display = 'flex';
}

function hideSpinner() {
    document.getElementById('loadingSpinner').style.display = 'none';
}

function abandonWorkout() {
    if (confirm("Are you sure you want to abandon this workout? All progress will be lost.")) {
        window.location.href = "/";
    }
}

/* ========================================
   FORM SUBMISSION
   ======================================== */

document.getElementById('completeWorkoutForm').addEventListener('submit', () => {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('completionDate').value = today;
});
