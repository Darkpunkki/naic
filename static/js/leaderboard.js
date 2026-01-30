let stackedChart = null;
const stackedEmpty = document.getElementById('stackedEmpty');
const deltaList = document.getElementById('deltaList');
const leaderTableBody = document.querySelector('#leaderTable tbody');
const heroBand = document.getElementById('heroBand');

const periodTabs = document.querySelectorAll('.period-tab');
const groupFilter = document.getElementById('groupFilter');

const state = {
    period: INITIAL_PERIOD || 'week',
    groupId: INITIAL_GROUP || ''
};

function isCompact() {
    return window.matchMedia('(max-width: 768px)').matches;
}

function truncateLabel(label, max) {
    if (!label) return '';
    return label.length > max ? `${label.slice(0, max - 1)}…` : label;
}

function setActiveControls() {
    periodTabs.forEach(tab => tab.classList.toggle('active', tab.dataset.period === state.period));
    groupFilter.value = state.groupId;
}

function formatNumber(value) {
    if (value >= 1000000) return `${(value / 1000000).toFixed(1)}m`;
    if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
    return value.toFixed(1);
}

function distributionFor(user) {
    return user.distribution;
}

function pickTopMuscles(users, muscleGroups, limit = 8) {
    const totals = {};
    muscleGroups.forEach(mg => totals[mg] = 0);
    users.forEach(user => {
        muscleGroups.forEach(mg => {
            totals[mg] += user.distribution[mg] || 0;
        });
    });
    return Object.entries(totals)
        .sort((a, b) => b[1] - a[1])
        .slice(0, limit)
        .map(entry => entry[0]);
}

function colorFor(label) {
    let hash = 0;
    for (let i = 0; i < label.length; i++) {
        hash = label.charCodeAt(i) + ((hash << 5) - hash);
    }
    const hue = Math.abs(hash) % 360;
    return `hsl(${hue}, 70%, 55%)`;
}

function renderStackedChart(users, muscleGroups) {
    if (!users.length || !muscleGroups.length) {
        stackedEmpty.style.display = 'block';
        if (stackedChart) stackedChart.destroy();
        return;
    }
    stackedEmpty.style.display = 'none';

    const compact = isCompact();
    const sortedUsers = compact
        ? [...users].sort((a, b) => (b.total_volume || 0) - (a.total_volume || 0)).slice(0, 5)
        : users;
    const topMuscles = pickTopMuscles(sortedUsers, muscleGroups, compact ? 5 : 8);
    const labels = sortedUsers.map(user => user.username);

    const datasets = topMuscles.map(mg => {
        return {
            label: mg,
            data: sortedUsers.map(user => (distributionFor(user)[mg] || 0)),
            backgroundColor: colorFor(mg),
            borderWidth: 0,
        };
    });

    if (stackedChart) stackedChart.destroy();
    const stackedCanvas = document.getElementById('stackedChart');
    if (stackedCanvas && compact) {
        const rowHeight = 64;
        const minHeight = 280;
        stackedCanvas.style.height = `${Math.max(minHeight, sortedUsers.length * rowHeight)}px`;
    } else if (stackedCanvas) {
        stackedCanvas.style.height = '';
    }
    stackedChart = new Chart(stackedCanvas, {
        type: 'bar',
        data: { labels, datasets },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: !compact,
            plugins: {
                legend: {
                    display: !compact,
                    position: 'bottom',
                    labels: {
                        color: '#e2e8f0',
                        boxWidth: compact ? 10 : 14,
                        font: { size: compact ? 10 : 12 }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: ctx => ` ${ctx.dataset.label}: ${formatNumber(ctx.raw)}`
                    }
                }
            },
            scales: {
                x: {
                    stacked: true,
                    ticks: {
                        color: '#e2e8f0',
                        maxTicksLimit: compact ? 3 : 6,
                        callback: value => formatNumber(value)
                    },
                    grid: { color: 'rgba(255,255,255,0.06)' }
                },
                y: {
                    stacked: true,
                    ticks: {
                        color: '#e2e8f0',
                        autoSkip: false,
                        callback: function(value) {
                            const label = this.getLabelForValue(value);
                            return truncateLabel(label, compact ? 10 : 18);
                        }
                    }
                }
            }
        }
    });

    return topMuscles;
}

function renderDelta(users, averages) {
    deltaList.innerHTML = '';
    if (!users.length) {
        deltaList.innerHTML = '<div class="empty-state" style="display:block;">No delta data available.</div>';
        return;
    }
    const avgValue = averages.total_volume || 0;
    const deltas = users.map(user => ({
        username: user.username,
        delta: (user.total_volume || 0) - avgValue,
        value: user.total_volume || 0
    }));
    const maxDelta = Math.max(...deltas.map(d => Math.abs(d.delta)), 1);

    deltas.forEach(item => {
        const compact = isCompact();
        const row = document.createElement('div');
        row.className = 'delta-row';
        const label = document.createElement('div');
        if (!compact) {
            label.style.minWidth = '120px';
        }
        label.textContent = item.username;

        const bar = document.createElement('div');
        bar.className = 'delta-bar';
        const fill = document.createElement('div');
        fill.className = 'delta-fill';
        const width = (Math.abs(item.delta) / maxDelta) * 100;
        fill.style.width = `${width}%`;
        fill.style.background = item.delta >= 0
            ? 'linear-gradient(90deg, rgba(52,211,153,0.8), rgba(14,165,233,0.9))'
            : 'linear-gradient(90deg, rgba(251,113,133,0.9), rgba(244,63,94,0.9))';
        bar.appendChild(fill);

        const value = document.createElement('div');
        value.textContent = `${formatNumber(item.value)} (${item.delta >= 0 ? '+' : ''}${formatNumber(item.delta)})`;
        row.appendChild(label);
        row.appendChild(bar);
        row.appendChild(value);
        deltaList.appendChild(row);
    });
}

function renderTable(users) {
    leaderTableBody.innerHTML = '';
    if (!users.length) return;
    const sorted = [...users].sort((a, b) => b.total_volume - a.total_volume);

    sorted.forEach((user, index) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${index + 1}</td>
            <td>${user.username}</td>
            <td>${user.workouts}</td>
            <td>${formatNumber(user.total_volume)}</td>
            <td>${user.balance}</td>
        `;
        leaderTableBody.appendChild(tr);
    });
}

function renderHeroBand(users, data) {
    if (!users.length) {
        heroBand.textContent = 'No activity logged for this period.';
        return;
    }
    const topUser = [...users].sort((a, b) => b.total_volume - a.total_volume)[0];
    let groupLabel = 'Global Leaderboard';
    if (groupFilter && groupFilter.options && groupFilter.selectedIndex >= 0) {
        groupLabel = groupFilter.options[groupFilter.selectedIndex].text;
    }
    heroBand.innerHTML = `Scope: <strong>${groupLabel}</strong> | Top performer: <strong>${topUser.username}</strong> | Avg volume ${formatNumber(data.group_averages.total_volume || 0)} | Period ${data.range.start} -> ${data.range.end}`;
}



function fetchLeaderboard() {
    setActiveControls();
    const params = new URLSearchParams();
    params.set('period', state.period);
    if (state.groupId) params.set('group_id', state.groupId);

    fetch(`/leaderboard/data?${params.toString()}`)
        .then(response => response.json())
        .then(data => {
            const users = data.users || [];
            const muscles = data.muscle_groups || [];
            const activeUsers = users.filter(user => (user.total_volume || 0) > 0);
            renderStackedChart(activeUsers, muscles);
            renderDelta(activeUsers, data.group_averages || {});
            renderTable(users);
            renderHeroBand(users, data);
        })
        .catch(err => {
            console.error('Failed to load leaderboard data', err);
        });
}

periodTabs.forEach(tab => {
    tab.addEventListener('click', () => {
        state.period = tab.dataset.period;
        fetchLeaderboard();
    });
});

groupFilter.addEventListener('change', () => {
    state.groupId = groupFilter.value;
    fetchLeaderboard();
});

fetchLeaderboard();
