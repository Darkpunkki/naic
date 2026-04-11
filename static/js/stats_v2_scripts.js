let distributionChart = null;
let trendChart = null;
let historyChart = null;
let muscleChart = null;
let movementTrendChart = null;

const periodTabs = document.querySelectorAll('.period-tab');
const statsTabs = document.querySelectorAll('.stats-tab');
const sections = document.querySelectorAll('.stats-section');
const distributionEmpty = document.getElementById('distributionEmpty');
const trendEmpty = document.getElementById('trendEmpty');
const changeboardGrid = document.getElementById('changeboardGrid');
const exportWeeklyBtn = document.getElementById('exportWeeklyBtn');

const movementTableBody = document.getElementById('movementTableBody');
const movementEmpty = document.getElementById('movementEmpty');
const movementSearch = document.getElementById('movementSearch');
const movementSort = document.getElementById('movementSort');
const exportMovementsBtn = document.getElementById('exportMovementsBtn');

const muscleEmpty = document.getElementById('muscleEmpty');
const imbalanceEmpty = document.getElementById('imbalanceEmpty');
const imbalanceList = document.getElementById('imbalanceList');

const recordsList = document.getElementById('recordsList');
const recordsEmpty = document.getElementById('recordsEmpty');

const adherenceCompletion = document.getElementById('adherenceCompletion');
const adherenceSkipped = document.getElementById('adherenceSkipped');
const adherenceWorkouts = document.getElementById('adherenceWorkouts');
const adherenceList = document.getElementById('adherenceList');
const adherenceEmpty = document.getElementById('adherenceEmpty');

const colorCache = {};

function colorFor(label) {
    if (colorCache[label]) return colorCache[label];
    let hash = 0;
    for (let i = 0; i < label.length; i++) {
        hash = label.charCodeAt(i) + ((hash << 5) - hash);
    }
    const hue = Math.abs(hash) % 360;
    colorCache[label] = `hsl(${hue}, 70%, 55%)`;
    return colorCache[label];
}

function setActivePeriod(period) {
    periodTabs.forEach(tab => {
        tab.classList.toggle('active', tab.dataset.period === period);
    });
}

function setActiveSection(sectionName) {
    statsTabs.forEach(tab => {
        tab.classList.toggle('active', tab.dataset.section === sectionName);
    });
    sections.forEach(section => {
        section.classList.toggle('active', section.id === `section-${sectionName}`);
    });
}

function formatNumber(value) {
    if (value >= 1000000) return `${(value / 1000000).toFixed(1)}m`;
    if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
    return value.toFixed(1);
}

function updateKpis(data) {
    document.getElementById('kpiTotal').textContent = formatNumber(data.total_volume || 0);
    document.getElementById('kpiAverage').textContent = formatNumber(data.avg_per_day || 0);
    document.getElementById('kpiRange').textContent = `${data.range.start} -> ${data.range.end}`;

    if (data.top_movement) {
        document.getElementById('kpiTopMovement').textContent = data.top_movement.name;
        document.getElementById('kpiTopMovementValue').textContent = `${formatNumber(data.top_movement.volume)} volume`;
    } else {
        document.getElementById('kpiTopMovement').textContent = '-';
        document.getElementById('kpiTopMovementValue').textContent = '0 volume';
    }

    if (data.top_muscle) {
        document.getElementById('kpiTopMuscle').textContent = data.top_muscle.name;
        document.getElementById('kpiTopMuscleValue').textContent = `${formatNumber(data.top_muscle.volume)} volume`;
    } else {
        document.getElementById('kpiTopMuscle').textContent = '-';
        document.getElementById('kpiTopMuscleValue').textContent = '0 volume';
    }
}

function renderDistribution(totals) {
    const sorted = Object.entries(totals).sort((a, b) => b[1] - a[1]);
    const top = sorted.slice(0, 10);

    if (!top.length) {
        distributionEmpty.style.display = 'block';
        if (distributionChart) distributionChart.destroy();
        return;
    }
    distributionEmpty.style.display = 'none';

    const labels = top.map(item => item[0]);
    const data = top.map(item => item[1]);
    const colors = labels.map(colorFor);

    if (distributionChart) distributionChart.destroy();
    distributionChart = new Chart(document.getElementById('distributionChart'), {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                data,
                backgroundColor: colors,
                borderRadius: 12,
            }]
        },
        options: {
            indexAxis: 'y',
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: context => ` ${context.raw.toFixed(2)} volume`
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255,255,255,0.06)' },
                    ticks: { color: '#e2e8f0' }
                },
                y: {
                    ticks: { color: '#e2e8f0' }
                }
            },
            onClick: (event, elements) => {
                if (!elements.length) return;
                const index = elements[0].index;
                const muscle = labels[index];
                fetchHistoricalData(muscle);
            }
        }
    });
}

function renderTrend(series) {
    if (!series.length) {
        trendEmpty.style.display = 'block';
        if (trendChart) trendChart.destroy();
        return;
    }
    trendEmpty.style.display = 'none';

    if (trendChart) trendChart.destroy();
    trendChart = new Chart(document.getElementById('trendChart'), {
        type: 'line',
        data: {
            labels: series.map(item => item.date),
            datasets: [{
                data: series.map(item => item.volume),
                borderColor: '#38bdf8',
                backgroundColor: 'rgba(56, 189, 248, 0.2)',
                fill: true,
                tension: 0.3,
                pointRadius: 2,
            }]
        },
        options: {
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { color: '#e2e8f0' }, grid: { display: false } },
                y: { ticks: { color: '#e2e8f0' }, grid: { color: 'rgba(255,255,255,0.06)' } }
            }
        }
    });
}

function renderChanges(changes) {
    changeboardGrid.innerHTML = '';
    if (!changes.length) {
        changeboardGrid.innerHTML = '<div class="empty-state">No change data available.</div>';
        return;
    }

    changes.slice(0, 6).forEach(change => {
        const card = document.createElement('div');
        card.className = 'change-card';
        const direction = change.status === 'up' ? '^' : change.status === 'down' ? 'v' : '-';
        const pctText = change.pct === null ? 'new' : `${change.pct}%`;
        card.innerHTML = `
            <h4>${change.muscle}</h4>
            <div class="change-delta">${direction} ${formatNumber(change.delta)} (${pctText})</div>
            <div class="change-meta">Prev ${formatNumber(change.previous)} -> Now ${formatNumber(change.current)}</div>
        `;
        changeboardGrid.appendChild(card);
    });
}

function fetchOverview(period) {
    return fetch(`/stats/overview?period=${period}`)
        .then(response => response.json())
        .then(data => updateKpis(data))
        .catch(err => console.error('Failed to load overview', err));
}

function fetchOverviewCharts(period) {
    return fetch(`/stats/data?period=${period}`)
        .then(response => response.json())
        .then(data => {
            renderDistribution(data.totals_by_muscle || {});
            renderTrend(data.series || []);
            renderChanges(data.changes || []);
        })
        .catch(err => console.error('Failed to load stats', err));
}

function fetchMovements(period) {
    const search = movementSearch.value.trim();
    const sort = movementSort.value;
    const params = new URLSearchParams({ period, sort });
    if (search) params.set('search', search);

    return fetch(`/stats/movements?${params.toString()}`)
        .then(response => response.json())
        .then(data => {
            movementTableBody.innerHTML = '';
            if (!data.movements || !data.movements.length) {
                movementEmpty.style.display = 'block';
                return;
            }
            movementEmpty.style.display = 'none';
            data.movements.forEach(movement => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${movement.movement_name}</td>
                    <td>${movement.e1rm_max ? movement.e1rm_max.toFixed(1) : '-'}</td>
                    <td>${formatNumber(movement.total_volume)}</td>
                    <td>${formatNumber(movement.total_tonnage)}</td>
                    <td>${movement.sessions}</td>
                    <td>${movement.last_performed || '-'}</td>
                `;
                row.addEventListener('click', () => openMovementModal(movement.movement_id, movement.movement_name, period));
                movementTableBody.appendChild(row);
            });
        })
        .catch(err => console.error('Failed to load movements', err));
}

function fetchMuscles(period) {
    return fetch(`/stats/muscles?period=${period}`)
        .then(response => response.json())
        .then(data => {
            if (!data.distribution || !data.distribution.length) {
                muscleEmpty.style.display = 'block';
                if (muscleChart) muscleChart.destroy();
            } else {
                muscleEmpty.style.display = 'none';
                renderMuscleChart(data.distribution);
            }

            if (!data.imbalances || !data.imbalances.length) {
                imbalanceEmpty.style.display = 'block';
                imbalanceList.innerHTML = '';
            } else {
                imbalanceEmpty.style.display = 'none';
                imbalanceList.innerHTML = '';
                data.imbalances.forEach(item => {
                    const div = document.createElement('div');
                    div.className = 'imbalance-item';
                    div.innerHTML = `<strong>${item.dominant}</strong> dominating ${item.pair.join(' vs ')} (${item.ratio})`;
                    imbalanceList.appendChild(div);
                });
            }
        })
        .catch(err => console.error('Failed to load muscles', err));
}

function renderMuscleChart(distribution) {
    const labels = distribution.map(item => item.muscle);
    const data = distribution.map(item => item.volume);
    const colors = labels.map(colorFor);

    if (muscleChart) muscleChart.destroy();
    muscleChart = new Chart(document.getElementById('muscleChart'), {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                data,
                backgroundColor: colors,
                borderRadius: 10,
            }]
        },
        options: {
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { color: '#e2e8f0' }, grid: { display: false } },
                y: { ticks: { color: '#e2e8f0' }, grid: { color: 'rgba(255,255,255,0.06)' } }
            }
        }
    });
}

function fetchRecords() {
    return fetch('/stats/records')
        .then(response => response.json())
        .then(data => {
            recordsList.innerHTML = '';
            if (!data.records || !data.records.length) {
                recordsEmpty.style.display = 'block';
                return;
            }
            recordsEmpty.style.display = 'none';
            data.records.forEach(record => {
                const div = document.createElement('div');
                div.className = 'record-item';
                div.innerHTML = `
                    <div>
                        <strong>${record.movement_name}</strong>
                        <span class="record-type">${record.record_type}</span>
                    </div>
                    <div class="record-value">${record.value}</div>
                    <div class="record-date">${record.achieved_at || ''}</div>
                `;
                recordsList.appendChild(div);
            });
        })
        .catch(err => console.error('Failed to load records', err));
}

function fetchAdherence(period) {
    return fetch(`/stats/adherence?period=${period}`)
        .then(response => response.json())
        .then(data => {
            adherenceCompletion.textContent = `${Math.round((data.avg_completion_rate || 0) * 100)}%`;
            adherenceSkipped.textContent = `${Math.round((data.skipped_set_rate || 0) * 100)}%`;
            adherenceWorkouts.textContent = data.workouts || 0;

            adherenceList.innerHTML = '';
            if (!data.movement_adherence || !data.movement_adherence.length) {
                adherenceEmpty.style.display = 'block';
                return;
            }
            adherenceEmpty.style.display = 'none';
            data.movement_adherence.forEach(item => {
                const row = document.createElement('div');
                row.className = 'adherence-item';
                row.innerHTML = `
                    <span>${item.movement_name}</span>
                    <span>${Math.round((item.completion_rate || 0) * 100)}%</span>
                `;
                adherenceList.appendChild(row);
            });
        })
        .catch(err => console.error('Failed to load adherence', err));
}

function fetchHistoricalData(muscleGroup) {
    fetch(`/historical_data/${encodeURIComponent(muscleGroup)}`)
        .then(response => response.json())
        .then(data => {
            const modalTitle = document.getElementById('historicalModalLabel');
            const historyEmpty = document.getElementById('historyEmpty');
            modalTitle.textContent = `${muscleGroup} History`;

            if (!data.length) {
                historyEmpty.style.display = 'block';
                if (historyChart) historyChart.destroy();
            } else {
                historyEmpty.style.display = 'none';
                if (historyChart) historyChart.destroy();
                historyChart = new Chart(document.getElementById('historyChart'), {
                    type: 'line',
                    data: {
                        labels: data.map(item => item.date),
                        datasets: [{
                            data: data.map(item => item.volume),
                            borderColor: colorFor(muscleGroup),
                            backgroundColor: 'rgba(248, 113, 113, 0.15)',
                            fill: true,
                            tension: 0.35,
                            pointRadius: 2,
                        }]
                    },
                    options: {
                        plugins: { legend: { display: false } },
                        scales: {
                            x: { ticks: { color: '#e2e8f0' }, grid: { display: false } },
                            y: { ticks: { color: '#e2e8f0' }, grid: { color: 'rgba(255,255,255,0.08)' } }
                        }
                    }
                });
            }

            const modal = new bootstrap.Modal(document.getElementById('historicalModal'));
            modal.show();
        })
        .catch(error => {
            console.error('Error fetching historical data:', error);
        });
}

function openMovementModal(movementId, movementName, period) {
    fetch(`/stats/movements/${movementId}/series?period=${period}`)
        .then(response => response.json())
        .then(data => {
            document.getElementById('movementModalLabel').textContent = movementName;
            renderMovementTrend(data.series || []);
            renderMovementRecent(data.recent_sessions || []);

            const modal = new bootstrap.Modal(document.getElementById('movementModal'));
            modal.show();
        })
        .catch(err => console.error('Failed to load movement detail', err));
}

function renderMovementTrend(series) {
    if (movementTrendChart) movementTrendChart.destroy();
    if (!series.length) return;

    movementTrendChart = new Chart(document.getElementById('movementTrendChart'), {
        type: 'line',
        data: {
            labels: series.map(item => item.date),
            datasets: [{
                label: 'e1RM',
                data: series.map(item => item.e1rm || 0),
                borderColor: '#facc15',
                backgroundColor: 'rgba(250, 204, 21, 0.18)',
                fill: true,
                tension: 0.35,
                pointRadius: 2,
            }]
        },
        options: {
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { color: '#e2e8f0' }, grid: { display: false } },
                y: { ticks: { color: '#e2e8f0' }, grid: { color: 'rgba(255,255,255,0.08)' } }
            }
        }
    });
}

function renderMovementRecent(sessions) {
    const container = document.getElementById('movementRecent');
    container.innerHTML = '';
    if (!sessions.length) {
        container.innerHTML = '<div class="empty-state">No recent sessions.</div>';
        return;
    }
    sessions.forEach(session => {
        const div = document.createElement('div');
        div.className = 'movement-recent-item';
        div.innerHTML = `
            <div>
                <strong>${session.workout_date || ''}</strong>
                <span>${formatNumber(session.total_volume)} volume</span>
            </div>
            <div>e1RM ${session.e1rm ? session.e1rm.toFixed(1) : '-'}</div>
        `;
        container.appendChild(div);
    });
}

function fetchAll(period) {
    setActivePeriod(period);
    Promise.all([
        fetchOverview(period),
        fetchOverviewCharts(period),
        fetchMovements(period),
        fetchMuscles(period),
        fetchRecords(),
        fetchAdherence(period),
    ]).catch(() => {});
}

periodTabs.forEach(tab => {
    tab.addEventListener('click', () => fetchAll(tab.dataset.period));
});

statsTabs.forEach(tab => {
    tab.addEventListener('click', () => setActiveSection(tab.dataset.section));
});

movementSearch?.addEventListener('input', () => fetchMovements(getCurrentPeriod()));
movementSort?.addEventListener('change', () => fetchMovements(getCurrentPeriod()));

exportMovementsBtn?.addEventListener('click', () => {
    const period = getCurrentPeriod();
    window.location.href = `/stats/export/movements?period=${period}`;
});

exportWeeklyBtn?.addEventListener('click', () => {
    const period = getCurrentPeriod();
    window.location.href = `/stats/export/weekly?period=${period}`;
});

function getCurrentPeriod() {
    const active = document.querySelector('.period-tab.active');
    return active ? active.dataset.period : 'all';
}

fetchAll(INITIAL_PERIOD || 'all');
