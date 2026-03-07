// Arch Terminal Tiling UI - JS Logic

// 1. Chart.js Config for Terminal Aesthetic
Chart.defaults.color = '#7c6f64'; // muted
Chart.defaults.font.family = "'JetBrains Mono', monospace";
Chart.defaults.font.size = 12;

const termGreen = '#466600';
const termGreenBright = '#8ab800';
const termBlue = '#458588';
const bgWindow = 'rgba(10, 10, 10, 0.8)';
const borderMuted = 'rgba(70, 102, 0, 0.3)';

const ctxThroughput = document.getElementById('throughputChart').getContext('2d');

// Initialize empty arrays for waterfall/heatmap style chart
const maxDataPoints = 20;
const labels = Array.from({length: maxDataPoints}, (_, i) => i.toString());
const tpmData = Array.from({length: maxDataPoints}, () => Math.floor(Math.random() * 5000));

const throughputData = {
    labels: labels,
    datasets: [{
        label: 'TPM_USAGE',
        data: tpmData,
        backgroundColor: function(context) {
            const chart = context.chart;
            const {ctx, chartArea} = chart;
            if (!chartArea) return null;
            // Create a gradient to look like a heatmap/waterfall
            const gradient = ctx.createLinearGradient(0, chartArea.bottom, 0, chartArea.top);
            gradient.addColorStop(0, 'rgba(70, 102, 0, 0.2)'); // Safe
            gradient.addColorStop(0.7, 'rgba(215, 153, 33, 0.5)'); // Warning
            gradient.addColorStop(1, 'rgba(204, 36, 29, 0.8)'); // Danger
            return gradient;
        },
        borderColor: termGreenBright,
        borderWidth: 1,
        fill: true,
        tension: 0.1,
        pointRadius: 0 // Hide points for waterfall look
    }]
};

const throughputConfig = {
    type: 'line', // Line with fill acts like a solid area/waterfall chart
    data: throughputData,
    options: {
        responsive: true,
        animation: {
            duration: 0 // Disable initial animation for snappier real-time feel
        },
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false },
            tooltip: {
                backgroundColor: bgWindow,
                titleColor: termGreenBright,
                bodyColor: '#a0a0a0',
                borderColor: termGreen,
                borderWidth: 1,
                padding: 8,
                titleFont: { family: "'JetBrains Mono', monospace", size: 12 },
                bodyFont: { family: "'JetBrains Mono', monospace", size: 12 },
                displayColors: false,
                cornerRadius: 0, // Sharp tooltips
                callbacks: {
                    label: function(context) {
                        return '> ' + context.parsed.y + ' pgs';
                    }
                }
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                max: 30000, // TPM Max Limit
                grid: {
                    color: borderMuted,
                    drawBorder: false,
                },
                ticks: { padding: 8, color: termGreen }
            },
            x: {
                display: false // Hide X axis for continuous flow
            }
        },
        interaction: { intersect: false, mode: 'index' },
    }
};

const liveThroughputChart = new Chart(ctxThroughput, throughputConfig);

// Simulate real-time waterfall data
setInterval(() => {
    let lastVal = liveThroughputChart.data.datasets[0].data[liveThroughputChart.data.datasets[0].data.length - 1];
    let newVal = lastVal + (Math.random() * 4000 - 2000); // Random walk
    if (newVal < 0) newVal = 0;
    if (newVal > 30000) {
        newVal = 30000;
        triggerRedAlert(); // Trigger visual warning if TPM maxes out
    }

    liveThroughputChart.data.datasets[0].data.shift();
    liveThroughputChart.data.datasets[0].data.push(newVal);
    liveThroughputChart.update('none'); // Update without animation
}, 1000);


// 1b. Radar Chart (Task Distribution) replacing Doughnut
const ctxApi = document.getElementById('apiChart');
let apiChartInstance = null;
if (ctxApi) {
    const apiData = {
        labels: ['PDF_PROC', 'DOCX_PROC', 'TXT_PROC', 'OCR_WAIT', 'API_ERR', 'DB_SYNC'],
        datasets: [{
            label: 'Task Distribution',
            data: [65, 59, 20, 11, 5, 40],
            backgroundColor: 'rgba(70, 102, 0, 0.2)', // Transparent green
            borderColor: termGreenBright,
            pointBackgroundColor: termGreenBright,
            pointBorderColor: '#fff',
            pointHoverBackgroundColor: '#fff',
            pointHoverBorderColor: termGreenBright,
            borderWidth: 1
        }]
    };

    apiChartInstance = new Chart(ctxApi.getContext('2d'), {
        type: 'radar',
        data: apiData,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    angleLines: { color: borderMuted },
                    grid: { color: borderMuted },
                    pointLabels: {
                        color: termGreenBright,
                        font: { family: "'ThedusCondensedLight-Regular', monospace", size: 10 }
                    },
                    ticks: { display: false } // Hide numbers on radar lines
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: bgWindow,
                    titleColor: termGreenBright,
                    bodyColor: '#a0a0a0',
                    borderColor: termGreen,
                    borderWidth: 1,
                    cornerRadius: 0,
                    bodyFont: { family: "'ThedusCondensedLight-Regular', monospace", size: 12 },
                }
            }
        }
    });

    // Simulate Radar data changes
    setInterval(() => {
        apiChartInstance.data.datasets[0].data = apiChartInstance.data.datasets[0].data.map(v => {
            let n = v + (Math.random() * 10 - 5);
            return n < 0 ? 0 : (n > 100 ? 100 : n);
        });
        apiChartInstance.update();
    }, 2500);
}

// ==========================================
// CORE ASOST FRONTEND API (FOR REAL DATA)
// ==========================================

// ==========================================
// CORE ASOST FRONTEND API (FOR REAL DATA)
// ==========================================

// 2. Terminal Log Output
const terminalBody = document.getElementById('terminal-output');

let currentLogLevel = 'ALL';

function getTimestamp() {
    const now = new Date();
    return `[${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}]`;
}

/**
 * Adds a log to the terminal window.
 * @param {string} msg - The log message (can include HTML for syntax highlighting).
 * @param {string} type - 'info', 'sys', 'warn', 'err'
 */
function asostAddLog(msg, type = 'INFO') {
    if (!terminalBody) return;
    const logEl = document.createElement('div');
    logEl.dataset.level = type.toUpperCase();

    let colorClass = 'log-info';
    let prefix = '';

    const upperType = type.toUpperCase();
    if (upperType === 'SYS')  { colorClass = 'log-sys'; }
    if (upperType === 'WARN') { colorClass = 'log-warn'; prefix = 'WARN: '; }
    if (upperType === 'ERR')  { colorClass = 'log-err'; prefix = 'ERR: '; }

    logEl.innerHTML = `<span class="log-time">${getTimestamp()}</span> <span class="${colorClass}">${prefix}${msg}</span>`;

    // Apply initial filter visibility
    if (currentLogLevel !== 'ALL' && upperType !== currentLogLevel) {
        logEl.style.display = 'none';
    }

    terminalBody.appendChild(logEl);

    // Auto-scroll to bottom if near bottom
    if (terminalBody.scrollHeight - terminalBody.scrollTop - terminalBody.clientHeight < 50) {
        terminalBody.scrollTop = terminalBody.scrollHeight;
    }
}

// Log Filtering Logic
document.querySelectorAll('.log-filter').forEach(btn => {
    btn.addEventListener('click', (e) => {
        // Reset actives
        document.querySelectorAll('.log-filter').forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');

        currentLogLevel = e.target.dataset.level;

        const logs = terminalBody.children;
        for (let log of logs) {
            if (currentLogLevel === 'ALL' || log.dataset.level === currentLogLevel) {
                log.style.display = 'block';
            } else {
                log.style.display = 'none';
            }
        }
    });
});

// 3. Live ASCII Progress Bars (htop style)
const jobsBody = document.getElementById('jobs-output');
const activeJobs = new Map();

/**
 * Updates or creates an ASCII progress bar for a task.
 * @param {string} taskId - Unique identifier for the file/task.
 * @param {string} filename - The name of the file being processed.
 * @param {number} percentage - Integer 0-100.
 */
function asostUpdateJobProgress(taskId, filename, percentage) {
    if (!jobsBody) return;

    const barWidth = 20;
    const filledCount = Math.floor((percentage / 100) * barWidth);
    const emptyCount = barWidth - filledCount;

    // Using blocks: █ and ░
    const filledBar = '<span class="string">' + '█'.repeat(filledCount) + '</span>';
    const emptyBar = '<span class="comment">' + '░'.repeat(emptyCount) + '</span>';

    const percentStr = percentage.toString().padStart(3, ' ') + '%';

    let jobEl = activeJobs.get(taskId);
    if (!jobEl) {
        jobEl = document.createElement('div');
        jobEl.className = 'job-row';
        jobsBody.appendChild(jobEl);
        activeJobs.set(taskId, jobEl);
    }

    // Format: 1 [████████░░] 45% filename.pdf
    jobEl.innerHTML = `<span class="keyword">${taskId.padStart(3, '0')}</span> <span class="punct">[</span>${filledBar}${emptyBar}<span class="punct">]</span> <span class="number">${percentStr}</span> <span class="log-info">${filename}</span>`;

    // Remove if 100% after a short delay
    if (percentage >= 100) {
        setTimeout(() => {
            if (activeJobs.has(taskId)) {
                activeJobs.get(taskId).remove();
                activeJobs.delete(taskId);
                asostAddLog(`<span class="keyword">finished</span> <span class="punct">-></span> <span class="string">"${filename}"</span>`, 'sys');
            }
        }, 3000);
    }
}

// ==========================================
// DUMMY DATA INJECTION (FOR MOCKUP DEMO)
// ==========================================

// Initial burst of logs
setTimeout(() => asostAddLog('asost-daemon v2.4.1 starting...', 'sys'), 500);
setTimeout(() => asostAddLog('connecting to main sqlite db [OK]', 'info'), 1000);
setTimeout(() => asostAddLog('worker pool initialized (12 threads)', 'info'), 1500);
setTimeout(() => asostAddLog('tpm limit near for key: AIzaSyCq9', 'warn'), 2000);
setTimeout(() => asostAddLog('listening on port 8080', 'sys'), 2500);

// Simulate continuous background tasks
function simulateBackend() {
    // 1. Logs
    if (Math.random() > 0.5) {
        const operations = ['extract_pdf', 'chunk_text', 'gemini_req', 'save_db'];
        const files = ['Neuro_Ch1.pdf', 'Quantum.docx', 'BladeRunner.pdf'];
        const op = operations[Math.floor(Math.random() * operations.length)];
        const file = files[Math.floor(Math.random() * files.length)];

        const r = Math.random();
        let logType = 'INFO';
        let statusText = 'OK';
        let statusClass = 'log-sys';

        if (r > 0.95) {
            logType = 'ERR'; statusText = 'FAILED'; statusClass = 'log-err';
        } else if (r > 0.85) {
            logType = 'WARN'; statusText = 'DELAY'; statusClass = 'number';
        }

        const formattedMsg = `<span class="keyword">${op}</span> <span class="punct">-></span> <span class="string">"${file}"</span> <span class="punct">[</span><span class="${statusClass}">${statusText}</span><span class="punct">]</span>`;

        asostAddLog(formattedMsg, logType);
    }

    // 2. Live Progress
    ['001', '002', '003'].forEach(id => {
        // Randomly update progress
        if (Math.random() > 0.3) {
            let currentP = parseInt(document.querySelector(`[data-task="${id}"]`)?.dataset?.p || "0");
            if (currentP === 0) {
                 // Start new
                 currentP = Math.floor(Math.random() * 20);
            } else {
                 // Increment
                 currentP += Math.floor(Math.random() * 5);
                 if (currentP > 100) currentP = 100;
            }

            // Store state hackily for dummy demo
            let names = {'001': 'Quantum_Physics.pdf', '002': 'AI_Research.docx', '003': 'Data_Structures.pdf'};
            asostUpdateJobProgress(id, names[id], currentP);

            // Hack to store percentage on the element for next iteration
            const el = activeJobs.get(id);
            if (el) {
                el.dataset.p = currentP;
                el.dataset.task = id;
            }
        }
    });

    const nextTimeout = Math.random() * 2000 + 500;
    setTimeout(simulateBackend, nextTimeout);
}

setTimeout(simulateBackend, 3000);



// 4. Modals and Layout Toggles
let isAlertActive = false;
function triggerRedAlert() {
    if (isAlertActive) return;
    isAlertActive = true;
    document.body.classList.add('red-alert-mode');
    asostAddLog('CRITICAL: TPM LIMIT EXCEEDED - ENFORCING COOLDOWN', 'ERR');
    setTimeout(() => {
        document.body.classList.remove('red-alert-mode');
        asostAddLog('TPM returning to nominal limits...', 'SYS');
        isAlertActive = false;
    }, 3000);
}

const toggleLayoutBtn = document.getElementById('toggle-layout');
const mainLayout = document.querySelector('.tiling-layout');

toggleLayoutBtn.addEventListener('click', () => {
    document.body.classList.toggle('floating-mode');

    // If we turned ON floating mode, initialize interact.js
    if (document.body.classList.contains('floating-mode')) {
        // Simple random scatter for initial float positions
        document.querySelectorAll('.window').forEach(win => {
            const x = Math.random() * (window.innerWidth - 400);
            const y = Math.random() * (window.innerHeight - 300);
            win.style.transform = `translate(${x}px, ${y}px)`;
            win.style.width = '400px';
            win.style.height = '300px';
            win.setAttribute('data-x', x);
            win.setAttribute('data-y', y);
        });

        interact('.window')
            .draggable({
                allowFrom: '.window-bar',
                listeners: {
                    move(event) {
                        const target = event.target;
                        const x = (parseFloat(target.getAttribute('data-x')) || 0) + event.dx;
                        const y = (parseFloat(target.getAttribute('data-y')) || 0) + event.dy;
                        target.style.transform = `translate(${x}px, ${y}px)`;
                        target.setAttribute('data-x', x);
                        target.setAttribute('data-y', y);
                    }
                }
            })
            .resizable({
                edges: { left: false, right: true, bottom: true, top: false },
                listeners: {
                    move(event) {
                        const target = event.target;
                        let x = (parseFloat(target.getAttribute('data-x')) || 0);
                        let y = (parseFloat(target.getAttribute('data-y')) || 0);

                        Object.assign(target.style, {
                            width: `${event.rect.width}px`,
                            height: `${event.rect.height}px`,
                            transform: `translate(${x}px, ${y}px)`
                        });
                    }
                }
            });
    } else {
        // Turned off floating mode, clean up interact.js and styles
        interact('.window').unset();
        document.querySelectorAll('.window').forEach(win => {
            win.style.transform = '';
            win.style.width = '';
            win.style.height = '';
            win.style.position = '';
            win.removeAttribute('data-x');
            win.removeAttribute('data-y');
        });
    }
});

// Modals logic
const queueModal = document.getElementById('queue-modal');
const apiModal = document.getElementById('api-modal');

document.getElementById('btn-que').addEventListener('click', () => {
    queueModal.style.display = 'flex';
    populateQueueTable();
});

document.getElementById('btn-api').addEventListener('click', () => {
    apiModal.style.display = 'flex';
    populateApiTable();
});

document.querySelectorAll('.modal-close').forEach(btn => {
    btn.addEventListener('click', (e) => {
        e.target.closest('.modal-overlay').style.display = 'none';
    });
});

// Click outside to close
window.addEventListener('click', (e) => {
    if (e.target === queueModal) queueModal.style.display = 'none';
    if (e.target === apiModal) apiModal.style.display = 'none';
});

// Dummy Table Data Generators
function populateQueueTable() {
    const tbody = document.querySelector('#queue-table tbody');
    tbody.innerHTML = '';
    const mockFiles = [
        {id: 'J01', name: 'Neuro_Ch1.pdf', size: '2.4M', status: 'PROCESSING'},
        {id: 'J02', name: 'Quantum.docx', size: '8.1M', status: 'QUEUED'},
        {id: 'J03', name: 'Notes_2023.txt', size: '12K', status: 'PAUSED'}
    ];

    mockFiles.forEach(f => {
        const row = document.createElement('tr');
        const statClass = f.status === 'PROCESSING' ? 'log-info' : (f.status === 'PAUSED' ? 'number' : 'comment');
        row.innerHTML = `
            <td>${f.id}</td>
            <td class="string">${f.name}</td>
            <td>${f.size}</td>
            <td class="${statClass}">${f.status}</td>
            <td><button class="btn-term">${f.status === 'PAUSED' ? 'RESUME' : 'PAUSE'}</button></td>
        `;
        tbody.appendChild(row);
    });
}

function populateApiTable() {
    const tbody = document.querySelector('#api-table tbody');
    tbody.innerHTML = '';
    const mockKeys = [
        {alias: 'GEMINI_MAIN', limits: '2 / 30000', status: 'ACTIVE'},
        {alias: 'GEMINI_BACKUP', limits: '2 / 30000', status: 'COOLING'},
        {alias: 'GEMINI_FREE', limits: '2 / 30000', status: 'EXHAUSTED'}
    ];

    mockKeys.forEach(k => {
        const row = document.createElement('tr');
        let statColor = 'ok';
        if(k.status === 'COOLING') statColor = 'warn';
        if(k.status === 'EXHAUSTED') statColor = 'log-err';

        row.innerHTML = `
            <td class="keyword">${k.alias}</td>
            <td>${k.limits}</td>
            <td class="${statColor}">${k.status}</td>
            <td><button class="btn-term">TOGGLE</button></td>
        `;
        tbody.appendChild(row);
    });
}


// 5. ASCII Upload Zone Interactivity
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const borderBox = dropZone.querySelector('.border-box');

const normalHtml = `
    <p class="center-text comment">/* DROP PDF/DOCX FILES HERE */</p>
    <p class="center-text glow-text"><i class="fa-solid fa-file-import fa-2x"></i></p>
    <p class="center-text string">[ CLICK TO BROWSE ]</p>
`;

const hoverHtml = `
    <p class="center-text comment">/* !!! INCOMING !!! */</p>
    <p class="center-text glow-text" style="color: var(--term-orange)"><i class="fa-solid fa-parachute-box fa-2x"></i></p>
    <p class="center-text string" style="color: var(--term-orange)">[ RELEASE MOUSE ]</p>
`;

dropZone.addEventListener('click', () => fileInput.click());

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    borderBox.innerHTML = hoverHtml;
});

dropZone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    borderBox.innerHTML = normalHtml;
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    if (e.dataTransfer.files.length) {
        handleFileTermMock(e.dataTransfer.files[0].name);
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) {
        handleFileTermMock(e.target.files[0].name);
    }
});

function handleFileTermMock(fileName) {
    // Terminal visual
    borderBox.innerHTML = `
        <p class="center-text comment">/* FILE QUEUED */</p>
        <p class="center-text glow-text" style="color: var(--term-blue)"><i class="fa-solid fa-check-double fa-2x"></i></p>
        <p class="center-text string">"${fileName}"</p>
    `;

    // Log using new API
    asostAddLog(`<span class="keyword">received_upload</span> <span class="punct">:</span> <span class="string">"${fileName}"</span>`, 'sys');

    // Reset
    setTimeout(() => {
        borderBox.innerHTML = normalHtml;
        fileInput.value = '';
    }, 3000);
}

// Simple clock and resource gauge updates for Polybar
setInterval(() => {
    const clock = document.getElementById('clock');
    const now = new Date();
    clock.innerText = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;

    // Update RAM
    const memEl = document.getElementById('mem-usage');
    let currentMem = parseFloat(memEl.innerText);
    currentMem += (Math.random() * 0.4) - 0.2;
    if (currentMem < 2.0) currentMem = 2.0;
    if (currentMem > 15.0) currentMem = 15.0;
    memEl.innerText = currentMem.toFixed(1);

    // Update CPU
    const cpuEl = document.getElementById('cpu-usage');
    let currentCpu = parseInt(cpuEl.innerText);
    currentCpu += Math.floor((Math.random() * 10) - 5);
    if (currentCpu < 1) currentCpu = 1;
    if (currentCpu > 99) currentCpu = 99;
    cpuEl.innerText = currentCpu;

}, 1000);

// --- Matrix Rain Background Effect ---
const canvas = document.getElementById('matrix-bg');
const ctx = canvas.getContext('2d');

let width, height;
let columns;
const fontSize = 14;
let drops = [];

function initMatrix() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
    columns = Math.floor(width / fontSize);
    drops = [];
    for (let i = 0; i < columns; i++) {
        drops[i] = Math.random() * -100; // Start off screen randomly
    }
}

window.addEventListener('resize', initMatrix);
initMatrix();

// Binary and hex characters
const chars = "010101010101010101010101010101010101010101ABCDEF".split("");

function drawMatrix() {
    // Translucent black to create fade effect
    ctx.fillStyle = 'rgba(5, 5, 5, 0.05)';
    ctx.fillRect(0, 0, width, height);

    ctx.fillStyle = 'rgba(70, 102, 0, 0.3)'; // Dim green
    ctx.font = fontSize + 'px "JetBrains Mono"';

    for (let i = 0; i < drops.length; i++) {
        const text = chars[Math.floor(Math.random() * chars.length)];
        ctx.fillText(text, i * fontSize, drops[i] * fontSize);

        if (drops[i] * fontSize > height && Math.random() > 0.975) {
            drops[i] = 0;
        }
        drops[i]++;
    }

    requestAnimationFrame(drawMatrix);
}

drawMatrix();
