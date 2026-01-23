let distributionChart = null;
let trendChart = null;
let historyChart = null;

const periodTabs = document.querySelectorAll('.period-tab');
const distributionEmpty = document.getElementById('distributionEmpty');
const trendEmpty = document.getElementById('trendEmpty');
const changeboardGrid = document.getElementById('changeboardGrid');

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

function setActiveTab(period) {
    periodTabs.forEach(tab => {
        tab.classList.toggle('active', tab.dataset.period === period);
    });
}

function formatNumber(value) {
    if (value >= 1000000) return `${(value / 1000000).toFixed(1)}m`;
    if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
    return value.toFixed(1);
}

function updateKpis(totals, series, range) {
    const totalValue = Object.values(totals).reduce((sum, v) => sum + v, 0);
    const average = series.length ? totalValue / series.length : 0;

    const topEntry = Object.entries(totals).sort((a, b) => b[1] - a[1])[0];
    document.getElementById('kpiTotal').textContent = formatNumber(totalValue);
    document.getElementById('kpiAverage').textContent = formatNumber(average);
    document.getElementById('kpiRange').textContent = `${range.start} -> ${range.end}`;

    if (topEntry) {
        document.getElementById('kpiTop').textContent = topEntry[0];
        document.getElementById('kpiTopValue').textContent = `${formatNumber(topEntry[1])} volume`;
    } else {
        document.getElementById('kpiTop').textContent = '-';
        document.getElementById('kpiTopValue').textContent = '0 volume';
    }
}

function renderDistribution(totals) {
    const sorted = Object.entries(totals).sort((a, b) => b[1] - a[1]);
    const top = sorted.slice(0, 8);

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

function fetchStats(period) {
    setActiveTab(period);
    fetch(`/stats/data?period=${period}`)
        .then(response => response.json())
        .then(data => {
            renderDistribution(data.totals_by_muscle || {});
            renderTrend(data.series || []);
            renderChanges(data.changes || []);
            updateKpis(data.totals_by_muscle || {}, data.series || [], data.range || {start: '', end: ''});
        })
        .catch(err => {
            console.error('Failed to load stats', err);
        });
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

periodTabs.forEach(tab => {
    tab.addEventListener('click', () => fetchStats(tab.dataset.period));
});

fetchStats(INITIAL_PERIOD || 'all');
