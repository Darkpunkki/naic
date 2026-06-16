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

// Initialize state from template data, hydrating saved status from the server.
function initializeWorkoutState() {
    workoutState.movements = movementsData.map((m, idx) => {
        const sets = m.sets.map(s => ({
            ...s,
            status: s.status || 'pending',  // 'pending', 'completed', 'skipped'
            actualReps: s.reps,
            actualWeight: s.weight
        }));
        const hasSets = sets.length > 0;
        const allResolved = hasSets && sets.every(s => s.status === 'completed' || s.status === 'skipped');
        return {
            ...m,
            index: idx,
            status: allResolved ? 'completed' : 'pending',  // 'pending', 'in_progress', 'completed', 'skipped'
            sets: sets
        };
    });
}

// Call initialization and reflect any restored progress in the list UI.
initializeWorkoutState();
updateMovementListUI();

/* ========================================
   REST TIMER
   ======================================== */

let restTimeLeft = 0;
let restIntervalId = null;
let isTimerSoundEnabled = false;
let timerAudioContext = null;
const TIMER_SOUND_STORAGE_KEY = 'naic_rest_timer_sound_enabled';

setupTimerSoundToggle();

function setupTimerSoundToggle() {
    const toggle = document.getElementById('timerSoundToggle');
    if (!toggle) return;

    isTimerSoundEnabled = getStoredTimerSoundPreference();
    toggle.checked = isTimerSoundEnabled;

    toggle.addEventListener('change', () => {
        isTimerSoundEnabled = toggle.checked;
        persistTimerSoundPreference(isTimerSoundEnabled);

        if (isTimerSoundEnabled) {
            ensureTimerAudioContext();
        }
    });
}

function getStoredTimerSoundPreference() {
    try {
        return localStorage.getItem(TIMER_SOUND_STORAGE_KEY) === 'true';
    } catch (error) {
        return false;
    }
}

function persistTimerSoundPreference(enabled) {
    try {
        localStorage.setItem(TIMER_SOUND_STORAGE_KEY, String(enabled));
    } catch (error) {
        // Ignore storage failures (private mode, blocked storage, etc.)
    }
}

function ensureTimerAudioContext() {
    if (timerAudioContext) {
        if (timerAudioContext.state === 'suspended') {
            timerAudioContext.resume().catch(() => {});
        }
        return timerAudioContext;
    }

    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) {
        return null;
    }

    timerAudioContext = new AudioContextClass();
    if (timerAudioContext.state === 'suspended') {
        timerAudioContext.resume().catch(() => {});
    }

    return timerAudioContext;
}

function playRestTimerNotificationSound() {
    if (!isTimerSoundEnabled) return;

    const audioContext = ensureTimerAudioContext();
    if (!audioContext) return;

    const scheduleChime = () => {
        const now = audioContext.currentTime;
        const notes = [783.99, 987.77, 1174.66];

        notes.forEach((frequency, index) => {
            const startAt = now + (index * 0.14);
            const stopAt = startAt + 0.26;
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();

            oscillator.type = 'sine';
            oscillator.frequency.setValueAtTime(frequency, startAt);

            gainNode.gain.setValueAtTime(0.0001, startAt);
            gainNode.gain.exponentialRampToValueAtTime(0.08, startAt + 0.02);
            gainNode.gain.exponentialRampToValueAtTime(0.0001, stopAt);

            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);

            oscillator.start(startAt);
            oscillator.stop(stopAt);
        });
    };

    if (audioContext.state === 'suspended') {
        audioContext.resume().then(scheduleChime).catch(() => {});
    } else {
        scheduleChime();
    }
}

function startRestTimer(duration) {
    const restTimerContainer = document.getElementById('restTimerContainer');
    const restTimerElem = document.getElementById('restTimer');
    if (restIntervalId) {
        clearInterval(restIntervalId);
    }
    restTimeLeft = duration;
    restTimerElem.textContent = restTimeLeft;
    restTimerContainer.style.display = 'block';
    restIntervalId = setInterval(updateRestTimer, 1000);
}

function updateRestTimer() {
    restTimeLeft = Math.max(0, restTimeLeft - 1);
    document.getElementById('restTimer').textContent = restTimeLeft;
    if (restTimeLeft === 0) {
        finishRestTimer(true);
    }
}

function adjustRestTimer(delta) {
    restTimeLeft = Math.max(0, restTimeLeft + delta);
    document.getElementById('restTimer').textContent = restTimeLeft;

    if (restTimeLeft === 0 && restIntervalId) {
        finishRestTimer(true);
    }
}

function skipRestTimer() {
    finishRestTimer(false);
}

function finishRestTimer(shouldPlayNotification) {
    if (restIntervalId) {
        clearInterval(restIntervalId);
        restIntervalId = null;
    }
    document.getElementById('restTimerContainer').style.display = 'none';

    if (shouldPlayNotification) {
        playRestTimerNotificationSound();
    }

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

// Single delegated click handler so original and dynamically-added movements behave identically.
function resetMovementToPending(movement) {
    movement.status = 'pending';
    movement.sets.forEach(s => { s.status = 'pending'; });
}

function handleMovementClick(chosenIndex) {
    const movement = workoutState.movements[chosenIndex];
    if (!movement) return;

    if (movement.status === 'completed') {
        // Ask confirmation to redo completed movement
        if (confirm(`"${movement.movementName}" is already completed. Do you want to redo it?`)) {
            resetMovementToPending(movement);
            selectMovement(chosenIndex);
        }
    } else if (movement.status === 'skipped') {
        // Ask confirmation to do skipped movement
        if (confirm(`"${movement.movementName}" was skipped. Do you want to do it now?`)) {
            resetMovementToPending(movement);
            selectMovement(chosenIndex);
        }
    } else {
        selectMovement(chosenIndex);
    }
}

const movementListContainer = document.querySelector('.movement-list');
if (movementListContainer) {
    movementListContainer.addEventListener('click', function(event) {
        const item = event.target.closest('.movement-item');
        if (!item || !movementListContainer.contains(item)) return;
        const chosenIndex = parseInt(item.getAttribute('data-index'));
        if (Number.isNaN(chosenIndex)) return;
        handleMovementClick(chosenIndex);
    });
}

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

    // Persist immediately - the server is the source of truth for the session.
    persistSet(currentSet, 'completed');

    // Disable buttons during rest
    disableSetButtons();

    // Start rest timer
    startRestTimer(60);
}

function persistSet(set, status) {
    return fetch(`/active_workout/${workoutId}/sets/${set.setId}/log`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({
            reps: set.actualReps,
            weight: set.actualWeight,
            status: status
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Save failed');
        }
        return response.json();
    })
    .catch(error => {
        console.error('Failed to save set:', error);
        alert('Could not save this set to the server. Check your connection and try again.');
    });
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

    // Mark set as skipped and persist immediately.
    currentSet.status = 'skipped';
    persistSet(currentSet, 'skipped');

    // Proceed immediately without rest timer
    proceedAfterRest();
}

function skipMovement() {
    if (!confirm('Skip the entire movement? All remaining sets will be marked as skipped.')) {
        return;
    }

    const movement = workoutState.movements[workoutState.currentMovementIndex];

    // Mark all pending sets as skipped and persist each immediately.
    movement.sets.forEach(set => {
        if (set.status === 'pending') {
            set.status = 'skipped';
            persistSet(set, 'skipped');
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
            'X-CSRFToken': getCsrfToken()
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

            // Update UI (detail + movement list meta)
            updateMovementDetail();
            updateMovementListUI();
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
            'X-CSRFToken': getCsrfToken()
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

    // Click handled by the delegated listener on .movement-list
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

function getCsrfToken() {
    const tokenInput = document.querySelector('input[name="csrf_token"]');
    return tokenInput ? tokenInput.value : '';
}

function shouldAutoCleanupEmptyWorkout() {
    return Boolean(autoCleanupEmptyWorkout) && workoutState.movements.length === 0;
}

async function cleanupEmptyQuickWorkout() {
    if (!shouldAutoCleanupEmptyWorkout()) return;

    try {
        await fetch(`/delete_if_empty/${workoutId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({}),
            keepalive: true
        });
    } catch (error) {
        // Best-effort cleanup only.
    }
}

function beaconCleanupEmptyQuickWorkout() {
    if (!shouldAutoCleanupEmptyWorkout()) return;

    if (typeof navigator.sendBeacon === 'function') {
        const payload = new URLSearchParams();
        const csrfToken = getCsrfToken();
        if (csrfToken) {
            payload.append('csrf_token', csrfToken);
        }
        navigator.sendBeacon(`/delete_if_empty/${workoutId}`, payload);
        return;
    }

    cleanupEmptyQuickWorkout();
}

async function abandonWorkout() {
    if (confirm("Are you sure you want to abandon this workout? All progress will be lost.")) {
        await cleanupEmptyQuickWorkout();
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

window.addEventListener('pagehide', () => {
    beaconCleanupEmptyQuickWorkout();
});
