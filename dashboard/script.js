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

const throughputData = {
    labels: ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'],
    datasets: [{
        label: 'PG_PROC',
        data: [1200, 1900, 1500, 2200, 1800, 2500, 3100],
        borderColor: termGreenBright,
        backgroundColor: 'transparent',
        borderWidth: 1, // Thin terminal lines
        pointBackgroundColor: bgWindow,
        pointBorderColor: termGreenBright,
        pointBorderWidth: 1,
        pointRadius: 3,
        pointHoverRadius: 5,
        fill: false,
        tension: 0.0 // Sharp angles, no curves
    }]
};

const throughputConfig = {
    type: 'line',
    data: throughputData,
    options: {
        responsive: true,
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
                grid: {
                    color: borderMuted,
                    drawBorder: false,
                },
                ticks: { padding: 8, color: termGreen }
            },
            x: {
                grid: {
                    color: borderMuted,
                    drawBorder: false,
                    tickLength: 4
                },
                ticks: { padding: 8, color: termGreen }
            }
        },
        interaction: { intersect: false, mode: 'index' },
    }
};

new Chart(ctxThroughput, throughputConfig);


// 1b. API Key Doughnut Chart
const ctxApi = document.getElementById('apiChart');
let apiChartInstance = null;
if (ctxApi) {
    const apiData = {
        labels: ['ACTIVE', 'COOLING', 'EXHAUSTED'],
        datasets: [{
            data: [60, 30, 10],
            backgroundColor: [
                termGreenBright, // Active
                '#d3869b',       // Cooling (purple/pinkish)
                '#fb4934'        // Exhausted (red/orange)
            ],
            borderColor: bgWindow,
            borderWidth: 2,
            hoverOffset: 4
        }]
    };

    apiChartInstance = new Chart(ctxApi.getContext('2d'), {
        type: 'doughnut',
        data: apiData,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '75%', // Make it thin
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: bgWindow,
                    titleColor: termGreenBright,
                    bodyColor: '#a0a0a0',
                    borderColor: termGreen,
                    borderWidth: 1,
                    cornerRadius: 0,
                    bodyFont: { family: "'JetBrains Mono', monospace", size: 12 },
                }
            }
        }
    });
}

// ==========================================
// CORE ASOST FRONTEND API (FOR REAL DATA)
// ==========================================

// 2. Terminal Log Output
const terminalBody = document.getElementById('terminal-output');

function getTimestamp() {
    const now = new Date();
    return `[${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}]`;
}

/**
 * Adds a log to the terminal window.
 * @param {string} msg - The log message (can include HTML for syntax highlighting).
 * @param {string} type - 'info', 'sys', 'warn', 'err'
 */
function asostAddLog(msg, type = 'info') {
    if (!terminalBody) return;
    const logEl = document.createElement('div');

    let colorClass = 'log-info';
    let prefix = '';

    if (type === 'sys')  { colorClass = 'log-sys'; }
    if (type === 'warn') { colorClass = 'log-warn'; prefix = 'WARN: '; }
    if (type === 'err')  { colorClass = 'log-err'; prefix = 'ERR: '; }

    logEl.innerHTML = `<span class="log-time">${getTimestamp()}</span> <span class="${colorClass}">${prefix}${msg}</span>`;
    terminalBody.appendChild(logEl);

    // Auto-scroll to bottom
    terminalBody.scrollTop = terminalBody.scrollHeight;
}

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

        const isWarn = Math.random() > 0.9;
        const statusText = isWarn ? 'DELAY' : 'OK';
        const statusClass = isWarn ? 'number' : 'log-sys';
        const formattedMsg = `<span class="keyword">${op}</span> <span class="punct">-></span> <span class="string">"${file}"</span> <span class="punct">[</span><span class="${statusClass}">${statusText}</span><span class="punct">]</span>`;

        asostAddLog(formattedMsg, isWarn ? 'warn' : 'info');
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



// 3. ASCII Upload Zone Interactivity
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

// Simple clock update for Polybar
setInterval(() => {
    const clock = document.getElementById('clock');
    const now = new Date();
    clock.innerText = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
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
