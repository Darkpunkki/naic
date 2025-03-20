/* Adjust Value Logic */
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

/* Interactive Workout Logic */
let processingOrder = [];      // Array of movement indices in the order they will be processed.
let currentOrderIndex = 0;       // Pointer into processingOrder for current movement.
let currentSetIndex = 0;

// For rest timer handling.
let restTimeLeft = 0;
let totalRestDuration = 60;      // Full duration for rest (in seconds)
let restIntervalId = null;

// For debugging: container to display completed movements.
function addCompletedMovement(movementName) {
  const container = document.getElementById('completedMovements');
  if (container) {
    const li = document.createElement('li');
    li.classList.add('list-group-item');
    li.textContent = movementName;
    container.appendChild(li);
  }
}

// When a movement is clicked, build a custom processing order.
document.querySelectorAll('.movement-item').forEach(item => {
  item.addEventListener('click', function() {
    const chosenIndex = parseInt(this.getAttribute('data-index'));
    processingOrder = [];
    for (let i = chosenIndex; i < movementsData.length; i++) {
      processingOrder.push(i);
    }
    for (let i = 0; i < chosenIndex; i++) {
      processingOrder.push(i);
    }
    currentOrderIndex = 0;
    currentSetIndex = 0;
    showMovementDetail();
  });
});

function showMovementDetail() {
  // Hide movements list and show movement detail by toggling classes.
  document.getElementById('movementsList').classList.add('d-none');
  document.getElementById('movementDetail').classList.remove('d-none');
  updateMovementDetail();
}

function updateMovementDetail() {
  const currentMovement = movementsData[processingOrder[currentOrderIndex]];
  if (!currentMovement) return;
  document.getElementById('currentMovementName').textContent = currentMovement.movementName;
  document.getElementById('totalSets').textContent = currentMovement.sets.length;
  const currentSet = currentMovement.sets[currentSetIndex];
  document.getElementById('currentSetOrder').textContent = currentSet.setOrder;
  document.getElementById('currentReps').value = currentSet.reps;
  document.getElementById('currentWeight').value = currentSet.weight;
}

/* Modified confirmSet: now starts a 60-second rest timer when a set is marked done */
function confirmSet() {
  const currentMovement = movementsData[processingOrder[currentOrderIndex]];
  const currentSet = currentMovement.sets[currentSetIndex];

  // Save updated values from the inputs.
  currentSet.reps = parseFloat(document.getElementById('currentReps').value);
  currentSet.weight = parseFloat(document.getElementById('currentWeight').value);

  // Save these values into hidden form inputs.
  const hiddenInputsDiv = document.getElementById('hiddenInputs');
  let repInput = document.getElementById('hidden_rep_' + currentSet.setId);
  if (!repInput) {
    repInput = document.createElement('input');
    repInput.type = 'hidden';
    repInput.name = 'rep_' + currentSet.setId;
    repInput.id = 'hidden_rep_' + currentSet.setId;
    hiddenInputsDiv.appendChild(repInput);
  }
  repInput.value = currentSet.reps;

  let weightInput = document.getElementById('hidden_weight_' + currentSet.weightId);
  if (!weightInput) {
    weightInput = document.createElement('input');
    weightInput.type = 'hidden';
    weightInput.name = 'weight_' + currentSet.weightId;
    weightInput.id = 'hidden_weight_' + currentSet.weightId;
    hiddenInputsDiv.appendChild(weightInput);
  }
  weightInput.value = currentSet.weight;

  // Disable the Done button to prevent multiple clicks during rest.
  document.querySelector('#setDetail button.btn-success').disabled = true;
  // Start a 60-second rest timer.
  startRestTimer(60);
}

// Helper: update the circular timer display.
function updateRestTimerDisplay() {
  const timerTextElem = document.getElementById('timerText');
  timerTextElem.textContent = restTimeLeft;
  const progressCircle = document.getElementById('progressCircle');
  const circumference = 2 * Math.PI * 45; // r = 45, so circumference ≈ 282.743
  const progress = restTimeLeft / totalRestDuration; // fraction remaining
  // As time decreases, stroke-dashoffset increases.
  progressCircle.style.strokeDashoffset = circumference * (1 - progress);
}

// Start the rest timer with a given duration (in seconds).
function startRestTimer(duration) {
  totalRestDuration = duration;
  restTimeLeft = duration;
  const restTimerContainer = document.getElementById('restTimerContainer');
  restTimerContainer.classList.remove('d-none');
  updateRestTimerDisplay();
  restIntervalId = setInterval(updateRestTimer, 1000);
}

// Update the rest timer every second.
function updateRestTimer() {
  restTimeLeft--;
  updateRestTimerDisplay();
  if (restTimeLeft <= 0) {
    clearInterval(restIntervalId);
    restIntervalId = null;
    document.getElementById('restTimerContainer').classList.add('d-none');
    document.querySelector('#setDetail button.btn-success').disabled = false;

    // Play audio cue when rest is over.
    document.getElementById('whistleSound').play();

    proceedAfterRest();
  }
}

// Function to adjust the remaining rest time by delta seconds.
function adjustRestTimer(delta) {
  restTimeLeft = Math.max(0, restTimeLeft + delta);
  updateRestTimerDisplay();
}

function proceedAfterRest() {
  const currentMovement = movementsData[processingOrder[currentOrderIndex]];
  if (currentSetIndex < currentMovement.sets.length - 1) {
    currentSetIndex++;
    updateMovementDetail();
  } else {
    currentMovement.completed = true;
    addCompletedMovement(currentMovement.movementName);
    let nextFound = false;
    while (currentOrderIndex < processingOrder.length - 1) {
      currentOrderIndex++;
      const candidate = movementsData[processingOrder[currentOrderIndex]];
      if (!candidate.completed) {
        currentSetIndex = 0;
        nextFound = true;
        break;
      }
    }
    if (!nextFound) {
      let newOrder = [];
      for (let i = 0; i < movementsData.length; i++) {
        if (!movementsData[i].completed) {
          newOrder.push(i);
        }
      }
      if (newOrder.length > 0) {
        processingOrder = newOrder;
        currentOrderIndex = 0;
        currentSetIndex = 0;
      } else {
        document.getElementById('movementDetail').classList.add('d-none');
        document.getElementById('completeWorkoutForm').classList.remove('d-none');
        return;
      }
    }
    updateMovementDetail();
  }
}

function goBackToMovements() {
  // Hide the movement detail view.
  document.getElementById('movementDetail').classList.add('d-none');

  // Iterate through all movement list items and remove those that are completed.
  const movementItems = document.querySelectorAll('#movementsList .movement-item');
  movementItems.forEach(item => {
    const idx = parseInt(item.getAttribute('data-index'));
    if (movementsData[idx].completed) {
      item.remove();
    }
  });

  // Show the (updated) movements list.
  document.getElementById('movementsList').classList.remove('d-none');
}


/* Function to show movement info using fetchInstructions() */
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

function showSpinnerWithMessage(message) {
  const spinner = document.getElementById('loadingSpinner');
  const spinnerText = document.getElementById('spinnerText');
  spinnerText.textContent = message;
  spinner.style.display = 'block';
}

function hideSpinner() {
  document.getElementById('loadingSpinner').style.display = 'none';
}

function abandonWorkout() {
  if (confirm("Are you sure you want to abandon this workout? All progress will be lost.")) {
    window.location.href = "/";
  }
}

document.getElementById('completeWorkoutForm').addEventListener('submit', () => {
  const today = new Date().toISOString().split('T')[0];
  document.getElementById('completionDate').value = today;
});
