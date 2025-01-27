// Timer Logic
let startTime = null;
let elapsedTime = 0;
let timerInterval = null;

function updateTimerDisplay() {
    const totalTime = elapsedTime + (Date.now() - startTime);
    const time = new Date(totalTime);
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
    // Clear the current timer interval
    clearInterval(timerInterval);

    // Reset elapsed time and start time
    elapsedTime = 0;
    startTime = Date.now();

    // Update the timer display immediately
    document.getElementById('workoutTimer').textContent = '00:00:00';

    // Restart the timer
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

// Auto-start the timer on page load
startTimer();

// Highlight Current Set Logic
let currentSetIndex = 0;
const rows = Array.from(document.querySelectorAll('#workoutTableBody tr'));

function updateCurrentSet(index) {
    // Remove the highlight from the previous row
    rows.forEach(row => row.classList.remove('current-set-row'));

    // Highlight the current row
    if (rows[index]) {
        rows[index].classList.add('current-set-row');
    }

    // Update button states
    document.getElementById('prevSetBtn').disabled = index === 0;
    document.getElementById('nextSetBtn').disabled = index === rows.length - 1;
}

// Auto-highlight the first set on load
updateCurrentSet(currentSetIndex);

// Adjust Value Logic
function adjustValue(inputId, delta) {
    const input = document.querySelector(`input[name="${inputId}"]`);
    if (input) {
        const currentValue = parseFloat(input.value || 0);
        const newValue = Math.max(0, currentValue + delta); // Prevent negative values
        input.value = newValue.toFixed(input.step ? input.step.split('.')[1]?.length || 0 : 0);
    }
}

// Automatically set completion date when the form is submitted
document.getElementById('completeWorkoutForm').addEventListener('submit', () => {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('completionDate').value = today;
});
