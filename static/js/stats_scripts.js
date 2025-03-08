document.addEventListener('DOMContentLoaded', function () {
    // Get the canvas context from the chart element
    const ctx = document.getElementById('muscleGroupChart').getContext('2d');

    // Initialize the Chart using the global variables (set via Jinja in the HTML template)
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: muscleGroupLabels,
            datasets: [{
                label: 'Change (%)',
                data: percentageChanges,
                backgroundColor: 'rgba(75, 192, 192, 0.6)',
                borderColor: 'rgba(75, 192, 192, 1)',
                borderWidth: 1
            }]
        },
        options: {
            scales: {
                x: {
                    ticks: {
                        color: '#000',
                        font: {
                            size: 14,
                            weight: 'bold'
                        }
                    }
                },
                y: {
                    beginAtZero: true,
                    ticks: {
                        color: '#000',
                        font: {
                            size: 14,
                            weight: 'bold'
                        }
                    },
                    title: {
                        display: true,
                        text: 'Change (%)',
                        color: '#000',
                        font: {
                            size: 16,
                            weight: 'bold'
                        }
                    }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: context => `${context.raw}%`
                    }
                }
            },
            onClick: (event, elements) => {
                if (elements.length > 0) {
                    const index = elements[0].index;
                    const muscleGroup = muscleGroupLabels[index];
                    fetchHistoricalData(muscleGroup);
                }
            }
        }
    });

    // Function to fetch and display historical data for a muscle group
    function fetchHistoricalData(muscleGroup) {
        fetch(`/historical_data/${muscleGroup}`)
            .then(response => response.json())
            .then(data => {
                const modalTitle = document.getElementById('historicalModalLabel');
                const modalBody = document.getElementById('historicalModalBody');

                if (data.length === 0) {
                    modalBody.innerHTML = `<p>No historical data available for ${muscleGroup}.</p>`;
                    return;
                }

                modalTitle.textContent = `Historical Data for ${muscleGroup}`;
                modalBody.innerHTML = `<ul>${data.map(entry => `<li>Date: ${entry.date}, Volume: ${entry.volume.toFixed(2)}</li>`).join('')}</ul>`;

                const modal = new bootstrap.Modal(document.getElementById('historicalModal'));
                modal.show();
            })
            .catch(error => {
                console.error('Error fetching historical data:', error);
            });
    }
});
