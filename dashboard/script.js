// Global Chart Settings to match the Cyberpunk / Glassmorphism theme
Chart.defaults.color = '#8abf8a';
Chart.defaults.font.family = "'JetBrains Mono', monospace";

// 1. Throughput Line Chart (Smooth Curve)
const ctxThroughput = document.getElementById('throughputChart').getContext('2d');

// Create Gradient for Line Fill
const gradientFill = ctxThroughput.createLinearGradient(0, 0, 0, 300);
gradientFill.addColorStop(0, 'rgba(0, 255, 65, 0.4)');
gradientFill.addColorStop(1, 'rgba(0, 255, 65, 0.0)');

const throughputData = {
    labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    datasets: [{
        label: 'Pages Translated',
        data: [1200, 1900, 1500, 2200, 1800, 2500, 3100],
        borderColor: '#00ff41',
        backgroundColor: gradientFill,
        borderWidth: 2,
        pointBackgroundColor: '#0a0e0a',
        pointBorderColor: '#00ff41',
        pointBorderWidth: 2,
        pointRadius: 4,
        pointHoverRadius: 6,
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
                backgroundColor: 'rgba(10, 20, 10, 0.8)',
                titleColor: '#00ff41',
                bodyColor: '#e6ffe6',
                borderColor: 'rgba(0, 255, 65, 0.2)',
                borderWidth: 1,
                padding: 10,
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
                    color: 'rgba(0, 255, 65, 0.05)',
                    drawBorder: false,
                },
                ticks: { padding: 10 }
            },
            x: {
                grid: { display: false, drawBorder: false },
                ticks: { padding: 10 }
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
            '#00ff41',
            'rgba(0, 255, 65, 0.1)'
        ],
        borderColor: '#0a0e0a', // Matches background
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
                backgroundColor: 'rgba(10, 20, 10, 0.8)',
                bodyColor: '#e6ffe6',
                borderColor: 'rgba(0, 255, 65, 0.2)',
                borderWidth: 1,
                padding: 10,
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
    dropZone.style.borderColor = '#00ff41';
    dropZone.style.boxShadow = '0 0 20px rgba(0, 255, 65, 0.2)';
});

dropZone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    dropZone.style.transform = 'scale(1)';
    dropZone.style.borderColor = 'rgba(0, 255, 65, 0.15)';
    dropZone.style.boxShadow = '0 10px 40px rgba(0, 0, 0, 0.4)';
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.style.transform = 'scale(1)';
    dropZone.style.borderColor = 'rgba(0, 255, 65, 0.15)';
    dropZone.style.boxShadow = '0 10px 40px rgba(0, 0, 0, 0.4)';

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
        <div class="upload-icon-large" style="color: #fff">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
        </div>
        <h3 style="color: #00ff41">File Accepted</h3>
        <p style="color: #fff; font-family: var(--font-tech); font-size: 0.8rem;">${fileName}</p>
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
