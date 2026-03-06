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


// 2. Terminal Log Animation
const terminalBody = document.getElementById('terminal-output');

const initLogs = [
    { type: 'sys', msg: 'archlinux x86_64 loaded.' },
    { type: 'sys', msg: 'asost-daemon v2.4.1 starting...' },
    { type: 'info', msg: 'connecting to main sqlite db [OK]' },
    { type: 'info', msg: 'worker pool initialized (4 threads)' },
    { type: 'warn', msg: 'tpm limit near for key: AIzaSyCq9' },
    { type: 'info', msg: 'listening on port 8080' },
];

let logIndex = 0;

function getTimestamp() {
    const now = new Date();
    return `[${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}]`;
}

function renderLog(log) {
    const logEl = document.createElement('div');

    let colorClass = 'log-info';
    let prefix = '';

    if (log.type === 'sys')  { colorClass = 'log-sys'; }
    if (log.type === 'warn') { colorClass = 'log-warn'; prefix = 'WARN: '; }
    if (log.type === 'err')  { colorClass = 'log-err'; prefix = 'ERR: '; }

    logEl.innerHTML = `<span class="log-time">${getTimestamp()}</span> <span class="${colorClass}">${prefix}${log.msg}</span>`;
    terminalBody.appendChild(logEl);

    terminalBody.scrollTop = terminalBody.scrollHeight;
}

// Initial burst of logs
initLogs.forEach(log => {
    setTimeout(() => renderLog(log), Math.random() * 1000);
});

// Continuous dummy logs with "Syntax Highlighting"
function appendContinuousLog() {
    const operations = ['extract_pdf', 'chunk_text', 'gemini_req', 'save_db'];
    const files = ['Neuro_Ch1.pdf', 'Quantum.docx', 'BladeRunner.pdf'];
    const op = operations[Math.floor(Math.random() * operations.length)];
    const file = files[Math.floor(Math.random() * files.length)];

    const isWarn = Math.random() > 0.9;
    const statusText = isWarn ? 'DELAY' : 'OK';
    const statusClass = isWarn ? 'number' : 'log-sys'; // Using orange for warn, green for ok

    const formattedMsg = `<span class="keyword">${op}</span> <span class="punct">-></span> <span class="string">"${file}"</span> <span class="punct">[</span><span class="${statusClass}">${statusText}</span><span class="punct">]</span>`;

    renderLog({
        type: isWarn ? 'warn' : 'info',
        msg: formattedMsg
    });

    const nextTimeout = Math.random() * 4000 + 1000;
    setTimeout(appendContinuousLog, nextTimeout);
}

setTimeout(appendContinuousLog, 2500);


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

    // Log
    renderLog({ type: 'sys', msg: `<span class="keyword">received_upload</span> <span class="punct">:</span> <span class="string">"${fileName}"</span>` });

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
