// Background Animation - Subtle Matrix/Pixel clouds effect
const canvas = document.getElementById('bg-canvas');
const ctx = canvas.getContext('2d');

let width, height;
let particles = [];

function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
}
window.addEventListener('resize', resize);
resize();

// Subtle characters for the background texture
const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%&*()";
const charArray = chars.split("");

class Particle {
    constructor() {
        this.reset();
    }

    reset() {
        this.x = Math.random() * width;
        this.y = Math.random() * height;
        this.size = Math.random() * 8 + 4; // Font size roughly
        this.speedX = (Math.random() - 0.5) * 0.2;
        this.speedY = Math.random() * -0.5 - 0.1; // Float slowly upwards
        this.opacity = Math.random() * 0.15; // Very subtle
        this.char = charArray[Math.floor(Math.random() * charArray.length)];
        this.life = Math.random() * 100 + 50;
    }

    update() {
        this.x += this.speedX;
        this.y += this.speedY;
        this.life -= 0.5;

        if (this.y < 0 || this.life <= 0) {
            this.reset();
            this.y = height + Math.random() * 50;
        }
    }

    draw() {
        ctx.fillStyle = `rgba(0, 255, 65, ${this.opacity})`;
        ctx.font = `${this.size}px monospace`;
        ctx.fillText(this.char, this.x, this.y);
    }
}

// Create particles
const numParticles = 150; // Keep it light
for (let i = 0; i < numParticles; i++) {
    particles.push(new Particle());
}

function animate() {
    ctx.clearRect(0, 0, width, height);

    for (let particle of particles) {
        particle.update();
        particle.draw();
    }

    requestAnimationFrame(animate);
}

// Start background animation
animate();

// --- Dummy Terminal Logic ---
const terminalBody = document.getElementById('terminal-output');

const logs = [
    { type: 'info', msg: 'System initialized. All modules loaded.' },
    { type: 'info', msg: 'Connecting to main database... OK' },
    { type: 'info', msg: 'API Gateway ready. Rate limiters online.' },
    { type: 'info', msg: 'Started job processing queue listener.' },
    { type: 'warn', msg: 'High load detected on worker node 03.' },
    { type: 'info', msg: 'Re-routing translation request ASOST-9021.' },
    { type: 'info', msg: 'PDF text extraction completed for [The_Quantum_Enigma.pdf]' },
    { type: 'info', msg: 'Translating chapter 4: Entanglement...' },
];

let logIndex = 0;

function getTimestamp() {
    const now = new Date();
    return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
}

function appendLog() {
    if (logIndex >= logs.length) {
        // Reset or add random logs just to keep it looking active
        logs.push({
            type: Math.random() > 0.8 ? 'warn' : 'info',
            msg: `Processing background task hash: ${Math.random().toString(36).substring(7).toUpperCase()}...`
        });
    }

    const log = logs[logIndex];
    const logEl = document.createElement('div');

    let colorClass = 'log-info';
    let prefix = '[INFO]';

    if (log.type === 'warn') { colorClass = 'log-warn'; prefix = '[WARN]'; }
    if (log.type === 'error') { colorClass = 'log-error'; prefix = '[ERR] ';}

    logEl.innerHTML = `<span class="log-time">${getTimestamp()}</span> <span class="${colorClass}">${prefix} ${log.msg}</span>`;

    terminalBody.appendChild(logEl);

    // Scroll to bottom
    terminalBody.scrollTop = terminalBody.scrollHeight;

    logIndex++;

    // Trigger next log randomly between 1 to 4 seconds
    const nextTimeout = Math.random() * 3000 + 1000;
    setTimeout(appendLog, nextTimeout);
}

// Start terminal logs
setTimeout(appendLog, 1000);

// --- Simple File Upload UI logic (Mock) ---
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');

dropZone.addEventListener('click', () => {
    fileInput.click();
});

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.style.backgroundColor = 'rgba(0, 255, 65, 0.1)';
});

dropZone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    dropZone.style.backgroundColor = '';
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.style.backgroundColor = '';

    if (e.dataTransfer.files.length) {
        handleFile(e.dataTransfer.files[0]);
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) {
        handleFile(e.target.files[0]);
    }
});

function handleFile(file) {
    const fileName = file.name;
    const terminalOutput = document.getElementById('terminal-output');

    // Add to terminal visually
    logs.push({ type: 'info', msg: `Received upload: ${fileName}` });
    logs.push({ type: 'info', msg: `Adding ${fileName} to queue...` });

    // Visual feedback in dropzone
    dropZone.innerHTML = `
        <div class="upload-icon" style="color: white">[+]</div>
        <p style="color: white">File Queued</p>
        <span class="sub-text" style="color: var(--neon-green)">${fileName}</span>
    `;

    setTimeout(() => {
        // Reset dropzone after a bit
        dropZone.innerHTML = `
            <div class="upload-icon">[_]</div>
            <p>Drag & Drop PDF/DOCX here</p>
            <span class="sub-text">or click to browse</span>
            <input type="file" id="file-input" hidden>
        `;
    }, 4000);
}

// Mock active navigation state changes
const navItems = document.querySelectorAll('.nav-item');
navItems.forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        navItems.forEach(nav => nav.classList.remove('active'));
        item.classList.add('active');

        // Push click log to terminal
        const pageName = item.textContent.trim().replace(/\[.*?\]\s*/, '');
        logs.push({ type: 'info', msg: `User navigated to: ${pageName}` });
    });
});
