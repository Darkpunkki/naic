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

document.getElementById('pauseResumeTimer').addEventListener('click', function () {
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
let currentMovementIndex = null;
let currentSetIndex = null;

// When a movement is clicked, show the zoomed-in movement detail
document.querySelectorAll('.movement-item').forEach(item => {
    item.addEventListener('click', function () {
        currentMovementIndex = parseInt(this.getAttribute('data-index'));
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
    const movement = movementsData[currentMovementIndex];
    if (!movement) return;
    // Update movement name
    document.getElementById('currentMovementName').textContent = movement.movementName;
    // Update set numbers
    document.getElementById('totalSets').textContent = movement.sets.length;
    const currentSet = movement.sets[currentSetIndex];
    document.getElementById('currentSetOrder').textContent = currentSet.setOrder;
    // Set the current values in the inputs
    document.getElementById('currentReps').value = currentSet.reps;
    document.getElementById('currentWeight').value = currentSet.weight;
}

function confirmSet() {
    const movement = movementsData[currentMovementIndex];
    const currentSet = movement.sets[currentSetIndex];
    // Save updated values from inputs
    currentSet.reps = parseFloat(document.getElementById('currentReps').value);
    currentSet.weight = parseFloat(document.getElementById('currentWeight').value);

    // Save values into hidden form inputs
    let hiddenInputsDiv = document.getElementById('hiddenInputs');

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

    // Move to next set or movement
    if (currentSetIndex < movement.sets.length - 1) {
        currentSetIndex++;
        updateMovementDetail();
    } else {
        if (currentMovementIndex < movementsData.length - 1) {
            currentMovementIndex++;
            currentSetIndex = 0;
            updateMovementDetail();
        } else {
            // All movements completed: hide detail and show form
            document.getElementById('movementDetail').style.display = 'none';
            document.getElementById('completeWorkoutForm').style.display = 'block';
        }
    }
}

function goBackToMovements() {
    document.getElementById('movementDetail').style.display = 'none';
    document.getElementById('movementsList').style.display = 'block';
}

function fetchInstructions(movementName) {
    console.log("Fetching instructions for:", movementName);

    fetch(`/get_instructions?movement_name=${encodeURIComponent(movementName)}`)
      .then(response => {
          if (!response.ok) {
              throw new Error('Failed to fetch instructions');
          }
          return response.json();
      })
      .then(data => {
          console.log("API Response:", data);
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
          console.error('Error fetching instructions:', error);
          alert('Failed to fetch instructions. Please try again later.');
      });
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


/* Set completion date on form submission */
document.getElementById('completeWorkoutForm').addEventListener('submit', () => {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('completionDate').value = today;
});
