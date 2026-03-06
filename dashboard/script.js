// Global Chart Settings to match the Cyberpunk / Glassmorphism theme
Chart.defaults.color = '#9ddb9d';
Chart.defaults.font.family = "'Rajdhani', sans-serif";
Chart.defaults.font.size = 14;

// 1. Throughput Line Chart (Smooth Curve)
const ctxThroughput = document.getElementById('throughputChart').getContext('2d');

// Create Gradient for Line Fill
const gradientFill = ctxThroughput.createLinearGradient(0, 0, 0, 300);
gradientFill.addColorStop(0, 'rgba(57, 255, 20, 0.4)');
gradientFill.addColorStop(1, 'rgba(57, 255, 20, 0.0)');

const throughputData = {
    labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    datasets: [{
        label: 'Pages Translated',
        data: [1200, 1900, 1500, 2200, 1800, 2500, 3100],
        borderColor: '#39ff14',
        backgroundColor: gradientFill,
        borderWidth: 3,
        pointBackgroundColor: '#060806',
        pointBorderColor: '#39ff14',
        pointBorderWidth: 2,
        pointRadius: 5,
        pointHoverRadius: 8,
        fill: true,
        tension: 0.4 // Smooth curve (Apple-like)
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
                backgroundColor: 'rgba(6, 15, 6, 0.9)',
                titleColor: '#39ff14',
                bodyColor: '#e0ffe0',
                borderColor: 'rgba(57, 255, 20, 0.3)',
                borderWidth: 1,
                padding: 12,
                titleFont: { family: "'Rajdhani', sans-serif", size: 16 },
                bodyFont: { family: "'Rajdhani', sans-serif", size: 14 },
                displayColors: false,
                callbacks: {
                    label: function(context) {
                        return context.parsed.y + ' Pages';
                    }
                }
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                grid: {
                    color: 'rgba(57, 255, 20, 0.05)',
                    drawBorder: false,
                },
                ticks: { padding: 10, font: { family: "'JetBrains Mono', monospace", size: 11 } }
            },
            x: {
                grid: { display: false, drawBorder: false },
                ticks: { padding: 10, font: { family: "'JetBrains Mono', monospace", size: 11 } }
            }
        },
        interaction: { intersect: false, mode: 'index' },
    }
};

new Chart(ctxThroughput, throughputConfig);


// 2. API Health Doughnut Chart
const ctxApiHealth = document.getElementById('apiHealthChart').getContext('2d');

const apiHealthData = {
    labels: ['Active', 'Cooldown'],
    datasets: [{
        data: [8, 2], // 8 active keys, 2 on cooldown
        backgroundColor: [
            '#39ff14',
            'rgba(57, 255, 20, 0.15)'
        ],
        borderColor: '#060806', // Matches background
        borderWidth: 2,
        hoverOffset: 4
    }]
};

const apiHealthConfig = {
    type: 'doughnut',
    data: apiHealthData,
    options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '80%', // Thin elegant ring
        plugins: {
            legend: { display: false },
            tooltip: {
                backgroundColor: 'rgba(6, 15, 6, 0.9)',
                bodyColor: '#e0ffe0',
                borderColor: 'rgba(57, 255, 20, 0.3)',
                borderWidth: 1,
                padding: 12,
                bodyFont: { family: "'Rajdhani', sans-serif", size: 16 },
                displayColors: true
            }
        }
    }
};

new Chart(ctxApiHealth, apiHealthConfig);


// --- Interactive Terminal Simulation ---
const terminalBody = document.getElementById('terminal-output');

const logs = [
    { type: 'info', msg: 'System initialized. All core modules active.' },
    { type: 'info', msg: 'DB connection established. Latency: 4ms' },
    { type: 'warn', msg: 'Key [AIzaSyCq9...] approaching TPM limit.' },
    { type: 'info', msg: 'Started dynamic chunking for [Neuro_Ch1.pdf]' },
    { type: 'info', msg: 'Translation engine: Gemini-2.5-Pro loaded.' },
];

let logIndex = 0;

function getTimestamp() {
    const now = new Date();
    return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
}

function appendLog() {
    if (logIndex >= logs.length) {
        // Generate continuous random dummy logs to keep the UI feeling alive
        const operations = ['Extracting', 'Translating', 'Formatting', 'Verifying'];
        const files = ['Ch3_Matrix.pdf', 'Ghost_Shell_Doc.docx', 'Blade_Runner.pdf'];
        const op = operations[Math.floor(Math.random() * operations.length)];
        const file = files[Math.floor(Math.random() * files.length)];

        logs.push({
            type: Math.random() > 0.85 ? 'warn' : 'info',
            msg: `${op} ${file}... OK`
        });
    }

    const log = logs[logIndex];
    const logEl = document.createElement('div');

    let colorClass = 'log-info';
    let prefix = '[SYS]';

    if (log.type === 'warn') { colorClass = 'log-warn'; prefix = '[WRN]'; }
    if (log.type === 'error') { colorClass = 'log-error'; prefix = '[ERR]'; }

    logEl.innerHTML = `<span class="log-time">${getTimestamp()}</span> <span class="${colorClass}">${prefix} ${log.msg}</span>`;

    terminalBody.appendChild(logEl);

    // Auto scroll to bottom smoothly
    terminalBody.scrollTo({
        top: terminalBody.scrollHeight,
        behavior: 'smooth'
    });

    logIndex++;

    // Trigger next log randomly between 2s and 5s
    const nextTimeout = Math.random() * 3000 + 2000;
    setTimeout(appendLog, nextTimeout);
}

// Start terminal logs after a slight delay
setTimeout(appendLog, 1500);

// --- Sleek Upload Zone Interactivity ---
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.style.transform = 'scale(1.02)';
    dropZone.style.borderColor = '#39ff14';
    dropZone.style.boxShadow = 'inset 0 1px 1px rgba(255, 255, 255, 0.1), 0 20px 40px rgba(0, 0, 0, 0.8), 0 0 25px rgba(57, 255, 20, 0.4)';
});

dropZone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    dropZone.style.transform = 'scale(1)';
    dropZone.style.borderColor = 'rgba(57, 255, 20, 0.25)';
    dropZone.style.boxShadow = 'inset 0 1px 1px rgba(255, 255, 255, 0.1), inset 0 -2px 10px rgba(57, 255, 20, 0.05), 0 15px 35px rgba(0, 0, 0, 0.7), 0 5px 15px rgba(0, 0, 0, 0.5)';
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.style.transform = 'scale(1)';
    dropZone.style.borderColor = 'rgba(57, 255, 20, 0.25)';
    dropZone.style.boxShadow = 'inset 0 1px 1px rgba(255, 255, 255, 0.1), inset 0 -2px 10px rgba(57, 255, 20, 0.05), 0 15px 35px rgba(0, 0, 0, 0.7), 0 5px 15px rgba(0, 0, 0, 0.5)';

    if (e.dataTransfer.files.length) {
        handleFileMock(e.dataTransfer.files[0]);
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) {
        handleFileMock(e.target.files[0]);
    }
});

function handleFileMock(file) {
    const fileName = file.name;
    const content = dropZone.querySelector('.upload-content');

    // Add upload event to terminal
    logs.push({ type: 'info', msg: `Upload initiated: ${fileName}` });

    // Visual feedback
    content.innerHTML = `
        <div class="upload-icon-large" style="color: #fff; text-shadow: 0 0 10px #fff;">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
        </div>
        <h3 style="color: #39ff14; text-shadow: 0 0 10px rgba(57,255,20,0.5);">File Accepted</h3>
        <p style="color: #e0ffe0; font-family: var(--font-tech); font-size: 0.9rem;">${fileName}</p>
    `;

    // Reset after 3 seconds
    setTimeout(() => {
        content.innerHTML = `
            <div class="upload-icon-large">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
            </div>
            <h3>Upload Document</h3>
            <p>Drag PDF or DOCX here</p>
            <button class="btn-primary" onclick="document.getElementById('file-input').click()">Browse Files</button>
            <input type="file" id="file-input" hidden>
        `;
    }, 3000);
}
