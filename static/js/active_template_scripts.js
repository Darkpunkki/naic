/* Timer Logic */
let startTime = null;
let elapsedTime = 0;
let timerInterval = null;

function updateTimerDisplay() {
  const totalTime = elapsedTime + (Date.now() - startTime);
  document.getElementById('workoutTimer').textContent =
      new Date(totalTime).toISOString().substr(11, 8);
}

function startTimer() {
  startTime = Date.now();
  timerInterval = setInterval(updateTimerDisplay, 1000);
}

function pauseTimer() {
  elapsedTime += Date.now() - startTime;
  clearInterval(timerInterval);
  startTime = null;
}

function resetTimer() {
  clearInterval(timerInterval);
  elapsedTime = 0;
  startTime = Date.now();
  document.getElementById('workoutTimer').textContent = '00:00:00';
  timerInterval = setInterval(updateTimerDisplay, 1000);
}

document.getElementById('pauseResumeTimer').addEventListener('click', function() {
  if (startTime) {
    pauseTimer();
    this.textContent = 'Resume';
  } else {
    startTimer();
    this.textContent = 'Pause';
  }
});
document.getElementById('resetTimer').addEventListener('click', resetTimer);
startTimer();

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

// New variables to support flexible processing order
let processingOrder = []; // Array of movement indices in the order they will be processed.
let currentOrderIndex = 0; // Pointer into processingOrder for current movement.
let currentSetIndex = 0;

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
// The order will start with the selected movement, then continue with subsequent movements, wrapping around.
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

function confirmSet() {
  const currentMovement = movementsData[processingOrder[currentOrderIndex]];
  const currentSet = currentMovement.sets[currentSetIndex];

  // Save updated values from the inputs
  currentSet.reps = parseFloat(document.getElementById('currentReps').value);
  currentSet.weight = parseFloat(document.getElementById('currentWeight').value);

  // Save these values into hidden form inputs
  const hiddenInputsDiv = document.getElementById('hiddenInputs');

  // For reps
  let repInput = document.getElementById('hidden_rep_' + currentSet.setId);
  if (!repInput) {
    repInput = document.createElement('input');
    repInput.type = 'hidden';
    repInput.name = 'rep_' + currentSet.setId;
    repInput.id = 'hidden_rep_' + currentSet.setId;
    hiddenInputsDiv.appendChild(repInput);
  }
  repInput.value = currentSet.reps;

  // For weight
  let weightInput = document.getElementById('hidden_weight_' + currentSet.weightId);
  if (!weightInput) {
    weightInput = document.createElement('input');
    weightInput.type = 'hidden';
    weightInput.name = 'weight_' + currentSet.weightId;
    weightInput.id = 'hidden_weight_' + currentSet.weightId;
    hiddenInputsDiv.appendChild(weightInput);
  }
  weightInput.value = currentSet.weight;

  // If there are more sets in the current movement, move to the next set
  if (currentSetIndex < currentMovement.sets.length - 1) {
    currentSetIndex++;
    updateMovementDetail();
  } else {
    // Mark current movement as completed
    currentMovement.completed = true;
    addCompletedMovement(currentMovement.movementName);

    // Now look for the next uncompleted movement in the current processing order.
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

    // If no uncompleted movement is found in the remaining processingOrder,
    // rebuild processingOrder to include only uncompleted movements (if any).
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
        // All movements are completed. Show the completion form.
        document.getElementById('movementDetail').style.display = 'none';
        document.getElementById('completeWorkoutForm').style.display = 'block';
        return;
      }
    }
    updateMovementDetail();
  }
}


function goBackToMovements() {
  // Allow the user to return to the full list of movements at any time.
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
    // Optionally clear any client-side state here.
    window.location.href = "/"; // Redirect back to the main template.
  }
}

/* Set completion date on form submission */
document.getElementById('completeWorkoutForm').addEventListener('submit', () => {
  const today = new Date().toISOString().split('T')[0];
  document.getElementById('completionDate').value = today;
});
