// Arch Terminal Tiling UI - JS Logic

// 1. Chart.js Config for Terminal Aesthetic
Chart.defaults.color = '#555555';
Chart.defaults.font.family = "'JetBrains Mono', monospace";
Chart.defaults.font.size = 12;

const termGreen = '#466600';
const termGreenBright = '#699900';
const bgWindow = '#0a0a0a';
const borderMuted = '#222222';

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

// Continuous dummy logs
function appendContinuousLog() {
    const operations = ['extract_pdf', 'chunk_text', 'gemini_req', 'save_db'];
    const files = ['Neuro_Ch1.pdf', 'Quantum.docx', 'BladeRunner.pdf'];
    const op = operations[Math.floor(Math.random() * operations.length)];
    const file = files[Math.floor(Math.random() * files.length)];

    const isWarn = Math.random() > 0.9;

    renderLog({
        type: isWarn ? 'warn' : 'info',
        msg: `${op} -> ${file} [${isWarn ? 'DELAY' : 'OK'}]`
    });

    const nextTimeout = Math.random() * 4000 + 1000;
    setTimeout(appendContinuousLog, nextTimeout);
}

setTimeout(appendContinuousLog, 2500);


// 3. ASCII Upload Zone Interactivity
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const borderBox = dropZone.querySelector('.border-box');

const normalText = `===========================
 DROP PDF/DOCX FILES HERE
     [  _ _ _ _ _ _  ]
       CLICK TO BROWSE
===========================`;

const hoverText = `===========================
      !!! INCOMING !!!
     [  > > > < < <  ]
       RELEASE MOUSE
===========================`;

const droppedText = `===========================
        FILE QUEUED
     [  # # # # # #  ]
      PROCESSING...
===========================`;

dropZone.addEventListener('click', () => fileInput.click());

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    borderBox.innerHTML = hoverText.split('\n').map(l => `<p class="center-text">${l}</p>`).join('');
    borderBox.style.borderColor = termGreenBright;
    borderBox.style.color = termGreenBright;
});

dropZone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    borderBox.innerHTML = normalText.split('\n').map(l => `<p class="center-text">${l}</p>`).join('');
    borderBox.style.borderColor = '';
    borderBox.style.color = '';
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
    borderBox.innerHTML = droppedText.split('\n').map(l => `<p class="center-text">${l}</p>`).join('');
    borderBox.innerHTML += `<p class="center-text" style="color: #a0a0a0">${fileName}</p>`;
    borderBox.style.borderColor = termGreen;
    borderBox.style.color = termGreen;

    // Log
    renderLog({ type: 'sys', msg: `received upload: ${fileName}` });

    // Reset
    setTimeout(() => {
        borderBox.innerHTML = normalText.split('\n').map(l => `<p class="center-text">${l}</p>`).join('');
        borderBox.style.borderColor = '';
        borderBox.style.color = '';
        fileInput.value = '';
    }, 3000);
}

// Simple clock update for Polybar
setInterval(() => {
    const clock = document.getElementById('clock');
    const now = new Date();
    clock.innerText = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
}, 1000);
