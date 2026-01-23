/* --- Removed old global timer functions --- */

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
}

);

function showMovementDetail() {
  document.getElementById('movementsList').style.display = 'none';
  document.getElementById('movementDetail').style.display = 'block';
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

// Start the rest timer with a given duration (in seconds).
function startRestTimer(duration) {
  const restTimerContainer = document.getElementById('restTimerContainer');
  const restTimerElem = document.getElementById('restTimer');
  restTimeLeft = duration;
  restTimerElem.textContent = restTimeLeft;
  restTimerContainer.style.display = 'block';
  restIntervalId = setInterval(updateRestTimer, 1000);
}

// Update the rest timer every second.
function updateRestTimer() {
  restTimeLeft--;
  document.getElementById('restTimer').textContent = restTimeLeft;
  if (restTimeLeft <= 0) {
    clearInterval(restIntervalId);
    restIntervalId = null;
    document.getElementById('restTimerContainer').style.display = 'none';
    document.querySelector('#setDetail button.btn-success').disabled = false;
    proceedAfterRest();
  }
}

// Function to adjust the remaining rest time by delta seconds.
function adjustRestTimer(delta) {
  restTimeLeft = Math.max(0, restTimeLeft + delta);
  document.getElementById('restTimer').textContent = restTimeLeft;
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
        document.getElementById('movementDetail').style.display = 'none';
        document.getElementById('completeWorkoutForm').style.display = 'block';
        return;
      }
    }
    updateMovementDetail();
  }
}

function goBackToMovements() {
  document.getElementById('movementDetail').style.display = 'none';
  document.getElementById('movementsList').style.display = 'block';
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

/* Set completion date on form submission */
document.getElementById('completeWorkoutForm').addEventListener('submit', () => {
  const today = new Date().toISOString().split('T')[0];
  document.getElementById('completionDate').value = today;
});
