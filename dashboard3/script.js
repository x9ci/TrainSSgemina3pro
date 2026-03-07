// ================================================================
//  ASOST Dashboard v3.1 — Main JS Engine
//  No-Alert | Full Topology | Pipeline Flow | TPM | Gantt
// ================================================================
'use strict';

// ── Chart.js defaults ───────────────────────────────────────────
if (typeof Chart !== 'undefined' && Chart.defaults) {
    if (!Chart.defaults.font) Chart.defaults.font = {};
    Chart.defaults.color       = '#7c6f64';
    Chart.defaults.font.family = "'JetBrains Mono', monospace";
    Chart.defaults.font.size   = 10;
}

const C = {
    green:   '#8ab800',
    greenDim:'rgba(138,184,0,0.12)',
    blue:    '#458588',
    orange:  '#d79921',
    red:     '#cc241d',
    purple:  '#b16286',
    aqua:    '#689d6a',
    bg:      'rgba(8,10,8,0.85)',
    border:  'rgba(70,102,0,0.22)',
};

// ================================================================
//  1. CLOCK
// ================================================================
const clockEl = document.getElementById('clock');
function updateClock() {
    const n = new Date();
    const pad = v => String(v).padStart(2,'0');
    if (clockEl) clockEl.innerHTML = `<i class="fa-regular fa-clock"></i> ${pad(n.getHours())}:${pad(n.getMinutes())}:${pad(n.getSeconds())}`;
}
setInterval(updateClock, 1000);
updateClock();

function getTs() {
    const n = new Date(), pad = v => String(v).padStart(2,'0');
    return `[${pad(n.getHours())}:${pad(n.getMinutes())}:${pad(n.getSeconds())}]`;
}

// ================================================================
//  2. SOUND (Web Audio API)
// ================================================================
let audioCtx = null, soundEnabled = false;
document.getElementById('sound-toggle').addEventListener('click', () => {
    soundEnabled = !soundEnabled;
    if (soundEnabled && !audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    document.getElementById('sound-icon').className = soundEnabled ? 'fa-solid fa-volume-low' : 'fa-solid fa-volume-xmark';
    document.getElementById('sound-toggle').classList.toggle('on', soundEnabled);
    if (soundEnabled) playClick();
});
function playClick() {
    if (!audioCtx || !soundEnabled) return;
    try {
        const buf = audioCtx.createBuffer(1, Math.floor(audioCtx.sampleRate * 0.022), audioCtx.sampleRate);
        const d   = buf.getChannelData(0);
        for (let i = 0; i < d.length; i++) d[i] = (Math.random()*2-1) * Math.pow(1 - i/d.length, 12);
        const s = audioCtx.createBufferSource(), g = audioCtx.createGain();
        s.buffer = buf; g.gain.value = 0.05;
        s.connect(g); g.connect(audioCtx.destination); s.start();
    } catch(e) {}
}

// ================================================================
//  3. WINDOW MAXIMIZE
// ================================================================
document.querySelectorAll('.ctrl-max').forEach(btn => {
    btn.addEventListener('click', e => {
        e.stopPropagation();
        const el = document.getElementById(btn.dataset.win);
        if (!el) return;
        el.classList.toggle('maximized');
        setTimeout(() => { if (typeof Chart !== 'undefined' && Chart.instances) Object.values(Chart.instances).forEach(c => c.resize()); }, 60);
    });
});
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.window.maximized').forEach(w => w.classList.remove('maximized'));
        document.querySelectorAll('.modal-overlay').forEach(m => m.classList.remove('open'));
    }
});

// ================================================================
//  4. LOG TERMINAL
// ================================================================
const termBody = document.getElementById('terminal-output');
let curFilter = 'ALL', curSearch = '';

function asostAddLog(msg, type = 'info') {
    if (!termBody) return;
    playClick();
    const div = document.createElement('div');
    div.dataset.type = type;
    div.dataset.raw  = msg.replace(/<[^>]+>/g,'').toLowerCase();
    let cls = 'log-info', pre = '';
    if (type==='sys')  cls = 'log-sys';
    if (type==='warn') { cls = 'log-warn'; pre = 'WARN: '; }
    if (type==='err')  { cls = 'log-err';  pre = 'ERR!: '; }
    div.innerHTML = `<span class="log-time">${getTs()}</span><span class="${cls}">${pre}${msg}</span>`;
    if (!matchFilter(div)) div.classList.add('hidden');
    termBody.appendChild(div);
    if (termBody.children.length > 280) termBody.removeChild(termBody.firstChild);
    termBody.scrollTop = termBody.scrollHeight;
}
function matchFilter(el) {
    const t = el.dataset.type || 'info';
    const r = el.dataset.raw  || '';
    return (curFilter === 'ALL' || t === curFilter) && (!curSearch || r.includes(curSearch));
}
function applyFilters() {
    termBody.querySelectorAll('div').forEach(el => el.classList.toggle('hidden', !matchFilter(el)));
    termBody.scrollTop = termBody.scrollHeight;
}
document.querySelectorAll('.log-filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.log-filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        curFilter = btn.dataset.filter;
        applyFilters();
    });
});
const logSearch = document.getElementById('log-search');
if (logSearch) logSearch.addEventListener('input', () => { curSearch = logSearch.value.trim().toLowerCase(); applyFilters(); });
document.getElementById('log-clear-btn').addEventListener('click', () => { termBody.innerHTML = ''; });

// ================================================================
//  5. TPM LIVE CHART (3 keys)
// ================================================================
const tpmLabels = [], tpmA = [], tpmB = [], tpmC = [];
for (let i = 19; i >= 0; i--) {
    const t = new Date(Date.now() - i * 3000);
    tpmLabels.push(`${String(t.getMinutes()).padStart(2,'0')}:${String(t.getSeconds()).padStart(2,'0')}`);
    tpmA.push(Math.floor(28000 + Math.random() * 22000));
    tpmB.push(Math.floor(38000 + Math.random() * 18000));
    tpmC.push(Math.floor(8000  + Math.random() * 42000));
}

const tpmChart = typeof Chart !== 'undefined' ? new Chart(document.getElementById('tpmChart'), {
    type: 'line',
    data: {
        labels: tpmLabels,
        datasets: [
            { label:'KEY-A', data:tpmA, borderColor:C.green,  backgroundColor:'transparent', borderWidth:1.5, pointRadius:0, tension:0.3 },
            { label:'KEY-B', data:tpmB, borderColor:C.blue,   backgroundColor:'transparent', borderWidth:1.5, pointRadius:0, tension:0.3 },
            { label:'KEY-C', data:tpmC, borderColor:C.orange, backgroundColor:'transparent', borderWidth:1.5, pointRadius:0, tension:0.3 },
        ],
    },
    options: {
        responsive:true, maintainAspectRatio:false, animation:{duration:200},
        plugins: {
            legend:{display:false},
            tooltip:{
                backgroundColor:C.bg, titleColor:C.green, bodyColor:'#a0a0a0',
                borderColor:C.border, borderWidth:1, cornerRadius:0, padding:7,
                callbacks:{ label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y.toLocaleString()} tpm` },
            },
        },
        scales:{
            y:{ min:0, max:65000, grid:{color:C.border}, ticks:{color:C.green, callback:v=>v>=1000?(v/1000)+'K':v} },
            x:{ grid:{color:C.border}, ticks:{color:C.green, maxTicksLimit:7} },
        },
        interaction:{intersect:false, mode:'index'},
    },
}) : null;

if (typeof Chart !== 'undefined') {
Chart.register({
    id:'dangerLine',
    afterDraw(chart) {
        const {ctx, chartArea, scales} = chart;
        if (!chartArea) return;
        const y = scales.y.getPixelForValue(60000);
        ctx.save();
        ctx.strokeStyle='rgba(204,36,29,0.45)'; ctx.lineWidth=1; ctx.setLineDash([4,4]);
        ctx.beginPath(); ctx.moveTo(chartArea.left,y); ctx.lineTo(chartArea.right,y); ctx.stroke();
        ctx.restore();
    }
});
}

setInterval(() => {
    const t = new Date();
    tpmLabels.push(`${String(t.getMinutes()).padStart(2,'0')}:${String(t.getSeconds()).padStart(2,'0')}`);
    const next = (arr, spread) => Math.max(4000, Math.min(63000, (arr.at(-1)||30000) + (Math.random()-0.48)*spread));
    tpmA.push(next(tpmA,7000)); tpmB.push(next(tpmB,6000)); tpmC.push(next(tpmC,9000));
    if (tpmLabels.length > 30) { tpmLabels.shift(); tpmA.shift(); tpmB.shift(); tpmC.shift(); }

    // check limits and update API keys
    [tpmA, tpmB, tpmC].forEach((arr, i) => {
        const nm = ['KEY-A','KEY-B','KEY-C'][i];
        apiKeys[i].tpm = Math.round(arr.at(-1));
        if (arr.at(-1) > 58000) asostAddLog(`<span class="keyword">${nm}</span> nearing TPM limit: <span class="number">${arr.at(-1).toLocaleString()}</span>/60K`, 'warn');
    });

    if (tpmChart) tpmChart.update('none');
    updateApiStats();
    // Also update topo edge weights
    topoEdgeLoad[0] = tpmA.at(-1) / 60000;
    topoEdgeLoad[1] = tpmB.at(-1) / 60000;
    topoEdgeLoad[2] = tpmC.at(-1) / 60000;
}, 3500);

// ================================================================
//  6. RADAR CHART
// ================================================================
const radarChart = typeof Chart !== 'undefined' ? new Chart(document.getElementById('radarChart'), {
    type:'radar',
    data:{
        labels:['PDF','DOCX','TXT','SUCCESS','SPEED','ERRORS'],
        datasets:[{
            label:'stats', data:[85,60,30,98,75,12],
            borderColor:C.green, backgroundColor:'rgba(138,184,0,0.08)',
            borderWidth:1.5, pointBackgroundColor:C.green, pointRadius:3,
        }],
    },
    options:{
        responsive:true, maintainAspectRatio:false,
        plugins:{legend:{display:false}},
        scales:{r:{
            min:0, max:100,
            grid:{color:'rgba(70,102,0,0.18)'},
            angleLines:{color:'rgba(70,102,0,0.18)'},
            pointLabels:{color:C.green, font:{size:8, family:"'JetBrains Mono'"}},
            ticks:{display:false},
        }},
    },
}) : null;

setInterval(() => {
    if (!radarChart) return;
    const data = radarChart.data.datasets[0].data;
    data[0] = Math.max(70, Math.min(95, data[0] + (Math.random() - 0.5) * 5)); // PDF
    data[1] = Math.max(40, Math.min(80, data[1] + (Math.random() - 0.5) * 5)); // DOCX
    data[2] = Math.max(10, Math.min(40, data[2] + (Math.random() - 0.5) * 5)); // TXT
    data[3] = Math.max(90, Math.min(100, data[3] + (Math.random() - 0.5) * 2)); // SUCCESS
    data[4] = Math.max(60, Math.min(90, data[4] + (Math.random() - 0.5) * 4)); // SPEED
    data[5] = Math.max(5, Math.min(25, data[5] + (Math.random() - 0.5) * 3));  // ERRORS
    radarChart.update('none');
}, 2000);

// ================================================================
//  7. API DOUGHNUT (hidden — data only for modal counts)
// ================================================================
const apiDoughnut = typeof Chart !== 'undefined' ? new Chart(document.getElementById('apiChart'), {
    type:'doughnut',
    data:{
        labels:['ACTIVE','COOLING','EXHAUSTED'],
        datasets:[{ data:[3,1,1], backgroundColor:[C.green,C.purple,C.red], borderWidth:0 }],
    },
    options:{ responsive:false, plugins:{legend:{display:false}} },
}) : null;

// ================================================================
//  8. API KEYS DATA
// ================================================================
const apiKeys = [
    {alias:'KEY-A', masked:'AIzaSyCq9...xR3f', status:'ACTIVE',    tpm:45000, limit:60000, disabled:false},
    {alias:'KEY-B', masked:'AIzaSyRx3...pK7m', status:'COOLING',   tpm:58000, limit:60000, disabled:false},
    {alias:'KEY-C', masked:'AIzaSyMn7...qL2n', status:'EXHAUSTED', tpm:60000, limit:60000, disabled:false},
    {alias:'KEY-D', masked:'AIzaSyBp2...wN9p', status:'ACTIVE',    tpm:12000, limit:60000, disabled:false},
    {alias:'KEY-E', masked:'AIzaSyKz5...mT4r', status:'ACTIVE',    tpm:28000, limit:60000, disabled:false},
];

function updateApiStats() {
    const active    = apiKeys.filter(k => k.status==='ACTIVE' && !k.disabled).length;
    const cooling   = apiKeys.filter(k => k.status==='COOLING').length;
    const exhausted = apiKeys.filter(k => k.status==='EXHAUSTED').length;
    if (apiDoughnut) {
        apiDoughnut.data.datasets[0].data = [active, cooling, exhausted];
        apiDoughnut.update('none');
    }
    if (document.getElementById('api-modal').classList.contains('open')) renderApiTable();
}

function renderApiTable() {
    const tbody = document.getElementById('api-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';
    apiKeys.forEach((k, i) => {
        const pct = Math.min(100, Math.round((k.tpm / k.limit) * 100));
        const barCls = pct >= 95 ? 'danger' : pct >= 82 ? 'warn' : '';
        const stCls  = `status-${k.status.toLowerCase()}`;
        const tr = document.createElement('tr');
        if (k.disabled) tr.style.opacity = '0.4';
        tr.innerHTML = `
            <td class="keyword">${k.alias}</td>
            <td class="string">${k.masked}</td>
            <td><span class="status-badge ${stCls}">${k.status}</span></td>
            <td class="number">${k.tpm.toLocaleString()}</td>
            <td class="comment">${k.limit.toLocaleString()}</td>
            <td><div class="tpm-bar-wrap"><div class="tpm-bar-fill ${barCls}" style="width:${pct}%"></div></div></td>
            <td>
                <button class="action-btn ${k.disabled?'enable':'disable'}" onclick="toggleApiKey(${i})">
                    <i class="fa-solid fa-toggle-${k.disabled?'off':'on'}"></i></button>
                <button class="action-btn remove" onclick="removeApiKey(${i})"><i class="fa-solid fa-trash-can"></i></button>
            </td>`;
        tbody.appendChild(tr);
    });
}

window.toggleApiKey = i => {
    apiKeys[i].disabled = !apiKeys[i].disabled;
    apiKeys[i].status = apiKeys[i].disabled ? 'COOLING' : 'ACTIVE';
    asostAddLog(`<span class="keyword">${apiKeys[i].alias}</span> ${apiKeys[i].disabled?'disabled':'enabled'}`, 'sys');
    updateApiStats();
};
window.removeApiKey = i => {
    const r = apiKeys.splice(i,1)[0];
    asostAddLog(`<span class="keyword">removed_key</span>: ${r.alias}`, 'warn');
    updateApiStats();
};
document.getElementById('add-key-btn').addEventListener('click', () => {
    const inp = document.getElementById('new-key-input');
    const raw = inp.value.trim();
    if (!raw || raw.length < 10) return;
    const masked = raw.slice(0,8)+'...'+raw.slice(-4);
    const id = 'KEY-'+String.fromCharCode(65 + apiKeys.length);
    apiKeys.push({alias:id, masked, status:'ACTIVE', tpm:0, limit:60000, disabled:false});
    asostAddLog(`<span class="keyword">add_key</span>: <span class="string">${masked}</span> <span class="log-sys">[OK]</span>`, 'sys');
    inp.value = '';
    updateApiStats();
});
document.getElementById('rotate-keys-btn').addEventListener('click', () => {
    apiKeys.forEach(k => { if (!k.disabled) { k.tpm=0; k.status='ACTIVE'; } });
    asostAddLog('<span class="keyword">rotate_keys</span>: TPM counters reset', 'sys');
    updateApiStats();
});

// ================================================================
//  9. FILE QUEUE
// ================================================================
const fileQueue = [
    {id:'001', name:'Quantum_Physics.pdf',  type:'PDF',  progress:45, status:'RUNNING', priority:1},
    {id:'002', name:'AI_Research.docx',      type:'DOCX', progress:72, status:'RUNNING', priority:2},
    {id:'003', name:'Data_Structures.pdf',   type:'PDF',  progress:30, status:'PAUSED',  priority:3},
    {id:'004', name:'Blade_Runner.pdf',       type:'PDF',  progress:0,  status:'QUEUED',  priority:4},
    {id:'005', name:'Neuroscience_Ch1.pdf',   type:'PDF',  progress:100,status:'DONE',    priority:5},
];
let queueIdCtr = 6, allPaused = false;

function renderQueueTable() {
    const tbody = document.getElementById('queue-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';
    fileQueue.forEach((f, i) => {
        const pct = f.progress;
        const barCls = pct >= 90 ? 'danger' : pct >= 70 ? 'warn' : '';
        const stCls  = `status-${f.status.toLowerCase()}`;
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="keyword">#${f.id}</td>
            <td class="string">${f.name}</td>
            <td><span class="comment">${f.type}</span></td>
            <td><div class="progress-cell"><div class="progress-bar-wrap"><div class="progress-bar-fill ${barCls}" style="width:${pct}%"></div></div><span class="progress-pct">${pct}%</span></div></td>
            <td><span class="status-badge ${stCls}">${f.status}</span></td>
            <td>
                ${f.status!=='DONE'?`
                <button class="action-btn pause" onclick="togglePauseFile(${i})" title="${f.status==='PAUSED'?'Resume':'Pause'}">
                    <i class="fa-solid fa-${f.status==='PAUSED'?'play':'pause'}"></i></button>
                <button class="action-btn priority" onclick="prioritizeFile(${i})" title="Move top">
                    <i class="fa-solid fa-arrow-up"></i></button>`:''}
                <button class="action-btn remove" onclick="removeFile(${i})"><i class="fa-solid fa-xmark"></i></button>
            </td>`;
        tbody.appendChild(tr);
    });
    const running = fileQueue.filter(f=>f.status==='RUNNING').length;
    const queued  = fileQueue.filter(f=>f.status==='QUEUED').length;
    const done    = fileQueue.filter(f=>f.status==='DONE').length;
    const info = document.getElementById('queue-stats-info');
    if (info) info.textContent = `/* ${running} running · ${queued} queued · ${done} done */`;
    renderQueueMini();
}

window.togglePauseFile = i => {
    const f = fileQueue[i];
    if (!f || f.status==='DONE') return;
    f.status = f.status==='PAUSED' ? 'RUNNING' : 'PAUSED';
    asostAddLog(`<span class="keyword">${f.status==='PAUSED'?'pause':'resume'}</span>: <span class="string">"${f.name}"</span>`, 'sys');
    renderQueueTable();
};
window.prioritizeFile = i => {
    if (i===0) return;
    const [item] = fileQueue.splice(i,1);
    fileQueue.unshift(item);
    asostAddLog(`<span class="keyword">priority_up</span>: <span class="string">"${item.name}"</span>`, 'sys');
    renderQueueTable();
};
window.removeFile = i => {
    const [r] = fileQueue.splice(i,1);
    asostAddLog(`<span class="keyword">dequeue</span>: <span class="string">"${r.name}"</span>`, 'warn');
    renderQueueTable();
};

document.getElementById('clear-done-btn').addEventListener('click', () => {
    const before = fileQueue.length;
    fileQueue.splice(0, fileQueue.length, ...fileQueue.filter(f => f.status !== 'DONE'));
    if (fileQueue.length < before) asostAddLog(`<span class="keyword">clear_done</span>: removed ${before - fileQueue.length} tasks`, 'sys');
    renderQueueTable();
});
document.getElementById('pause-all-btn').addEventListener('click', () => {
    allPaused = !allPaused;
    fileQueue.forEach(f => { if (f.status==='RUNNING') f.status = allPaused ? 'PAUSED' : 'RUNNING'; });
    document.getElementById('pause-all-btn').innerHTML = allPaused
        ? '<i class="fa-solid fa-play"></i> RESUME ALL'
        : '<i class="fa-solid fa-pause"></i> PAUSE ALL';
    renderQueueTable();
});
document.getElementById('add-file-queue-btn').addEventListener('click', () => document.getElementById('modal-file-input').click());
document.getElementById('modal-file-input').addEventListener('change', e => {
    const file = e.target.files[0];
    if (!file) return;
    fileQueue.push({id:String(queueIdCtr++).padStart(3,'0'), name:file.name, type:file.name.split('.').pop().toUpperCase(), progress:0, status:'QUEUED', priority:fileQueue.length+1});
    asostAddLog(`<span class="keyword">enqueue</span>: <span class="string">"${file.name}"</span>`, 'sys');
    renderQueueTable(); e.target.value='';
});

function renderQueueMini() {
    const list = document.getElementById('queue-mini-list');
    if (!list) return;
    list.innerHTML = '';
    fileQueue.filter(f=>f.status!=='DONE').slice(0,4).forEach(f => {
        const col = f.status==='PAUSED' ? 'var(--term-orange)' : 'var(--term-green-bright)';
        const div = document.createElement('div');
        div.className = 'queue-mini-item';
        div.innerHTML = `<span class="comment" style="width:26px;flex-shrink:0">#${f.id}</span>
            <span class="string" style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:0.74em">${f.name}</span>
            <div class="queue-mini-bar-wrap" style="width:44px;flex-shrink:0"><div class="queue-mini-bar" style="width:${f.progress}%;background:${col}"></div></div>
            <span class="number" style="width:26px;flex-shrink:0;text-align:right;font-size:0.74em">${f.progress}%</span>`;
        list.appendChild(div);
    });
}

setInterval(() => {
    fileQueue.forEach(f => {
        if (f.status==='RUNNING' && f.progress < 100) {
            f.progress = Math.min(100, f.progress + Math.floor(Math.random()*3+1));
            if (f.progress >= 100) {
                f.status = 'DONE';
                asostAddLog(`<span class="keyword">finished</span> → <span class="string">"${f.name}"</span>`, 'sys');
                const next = fileQueue.find(q => q.status==='QUEUED');
                if (next) { next.status='RUNNING'; asostAddLog(`<span class="keyword">start</span>: <span class="string">"${next.name}"</span>`, 'sys'); }
            }
        }
    });
    renderQueueMini();
    if (document.getElementById('queue-modal').classList.contains('open')) renderQueueTable();
}, 1600);

// ================================================================
//  10. GANTT CHART (Canvas)
// ================================================================
const ganttCanvas = document.getElementById('ganttCanvas');
const ganttCtx    = ganttCanvas.getContext('2d');
const WORKERS     = 6;
const GANTT_W     = 22000;
const FILES_G     = ['Quantum.pdf','AI_Res.docx','DataSt.pdf','Neuro.pdf','Blade.pdf','Physics.docx'];
const WCOLS       = [C.green,C.blue,C.orange,C.purple,C.aqua,'#d65d0e'];
const workerJobs  = Array.from({length:WORKERS}, ()=>[]);

function addGanttJob(w, file, dur) {
    const now = Date.now();
    workerJobs[w].push({start:now, end:now+dur, file, color:WCOLS[Math.floor(Math.random()*WCOLS.length)]});
}
for (let w=0; w<WORKERS; w++) addGanttJob(w, FILES_G[w%FILES_G.length], 4000+Math.random()*9000);

function drawGantt() {
    const cw = ganttCanvas.parentElement.clientWidth;
    const ch = ganttCanvas.parentElement.clientHeight;
    ganttCanvas.width = cw; ganttCanvas.height = ch;
    const now = Date.now(), rowH = Math.floor(ch/WORKERS);
    const lW = 38, bW = cw - lW - 2;
    ganttCtx.clearRect(0,0,cw,ch);
    ganttCtx.strokeStyle='rgba(70,102,0,0.1)'; ganttCtx.lineWidth=1;
    for (let i=0;i<=WORKERS;i++) { ganttCtx.beginPath(); ganttCtx.moveTo(lW,i*rowH); ganttCtx.lineTo(cw,i*rowH); ganttCtx.stroke(); }
    const nowX = lW + bW;
    ganttCtx.strokeStyle='rgba(138,184,0,0.5)'; ganttCtx.lineWidth=1; ganttCtx.setLineDash([3,3]);
    ganttCtx.beginPath(); ganttCtx.moveTo(nowX,0); ganttCtx.lineTo(nowX,ch-10); ganttCtx.stroke();
    ganttCtx.setLineDash([]);
    for (let w=0;w<WORKERS;w++) {
        const y = w*rowH, cy = y+rowH/2;
        ganttCtx.fillStyle=C.green; ganttCtx.font='bold 8px "JetBrains Mono"';
        ganttCtx.fillText(`W-${String(w+1).padStart(2,'0')}`, 1, cy+3);
        workerJobs[w].forEach(job => {
            if (job.end < now - GANTT_W) return;
            const sOff = now - job.start, eOff = now - job.end;
            const x1 = Math.max(lW, lW + bW - (sOff/GANTT_W)*bW);
            const x2 = Math.min(cw, lW + bW - Math.min(0,(eOff/GANTT_W)*bW));
            const bw = Math.max(2, x2-x1), bh = rowH-5;
            ganttCtx.fillStyle = job.color+'44';
            ganttCtx.fillRect(x1, y+3, bw, bh);
            ganttCtx.strokeStyle = job.color; ganttCtx.lineWidth=1;
            ganttCtx.strokeRect(x1, y+3, bw, bh);
            if (job.end > now) {
                const prog = (now-job.start)/(job.end-job.start);
                ganttCtx.fillStyle = job.color+'88';
                ganttCtx.fillRect(x1, y+3, bw*prog, bh);
            }
            if (bw > 44) {
                ganttCtx.fillStyle=job.color; ganttCtx.font='7px "JetBrains Mono"';
                ganttCtx.fillText(job.file.substring(0,Math.floor(bw/6)), x1+3, cy+3);
            }
        });
    }
    requestAnimationFrame(drawGantt);
}
drawGantt();

function spawnGanttJob() {
    const w = Math.floor(Math.random()*WORKERS);
    addGanttJob(w, FILES_G[Math.floor(Math.random()*FILES_G.length)], 3000+Math.random()*11000);
    workerJobs.forEach((jobs,i) => { workerJobs[i]=jobs.filter(j=>j.end>Date.now()-GANTT_W*1.5); });
    setTimeout(spawnGanttJob, 400+Math.random()*1000); // more dense
}
setTimeout(spawnGanttJob, 800);

// ================================================================
//  11. NODE TOPOLOGY — CENTER BOTTOM (Full Canvas)
// ================================================================
const topoCanvas = document.getElementById('topoCanvas');
const topoCtx    = topoCanvas.getContext('2d');

// Topology state
let topoParticles = [];
let topoEdgeLoad  = [0.7, 0.95, 0.2]; // KEY-A/B/C load ratios (updated by TPM)
let topoTime      = 0;

// Node definitions (layout computed dynamically)
const NODES = {
    workers: Array.from({length:6}, (_,i) => ({
        id:`W-${String(i+1).padStart(2,'0')}`,
        status: ['ACTIVE','ACTIVE','ACTIVE','BUSY','ACTIVE','ACTIVE'][i],
    })),
    engine: { id:'ASOST ENGINE', sub:'Core v2.4', status:'ACTIVE' },
    db:     { id:'SQLite DB',    sub:'main.db',    status:'ACTIVE' },
    queue:  { id:'QUEUE',        sub:'4 pending',  status:'ACTIVE' },
    api:    { id:'GEMINI API',   sub:'2.5-Pro',    status:'BUSY'   },
    output: { id:'PDF OUTPUT',   sub:'exported',   status:'ACTIVE' },
};

// Assign colors per status
const nodeColor = (s) => s==='ACTIVE' ? C.green : s==='BUSY' ? C.orange : s==='DOWN' ? C.red : '#7c6f64';

// Particle: flows along a bezier or straight edge
function spawnParticle(x1,y1,x2,y2,cp1x,cp1y,cp2x,cp2y, color) {
    topoParticles.push({ x1,y1,x2,y2,cp1x,cp1y,cp2x,cp2y, t:0, speed:0.006+Math.random()*0.01, color });
}

function lerpBezier(x1,y1,cp1x,cp1y,cp2x,cp2y,x2,y2, t) {
    const u = 1-t;
    return {
        x: u*u*u*x1 + 3*u*u*t*cp1x + 3*u*t*t*cp2x + t*t*t*x2,
        y: u*u*u*y1 + 3*u*u*t*cp1y + 3*u*t*t*cp2y + t*t*t*y2,
    };
}

function drawTopoEdge(ctx, x1,y1,cp1x,cp1y,cp2x,cp2y, x2,y2, color, dashed=false, width=1) {
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth   = width;
    if (dashed) ctx.setLineDash([4,5]);
    else ctx.setLineDash([]);
    ctx.beginPath();
    ctx.moveTo(x1,y1);
    ctx.bezierCurveTo(cp1x,cp1y,cp2x,cp2y,x2,y2);
    ctx.stroke();
    ctx.restore();
}

function drawHex(ctx, cx,cy,r, color) {
    ctx.beginPath();
    for (let i=0;i<6;i++) {
        const a = (Math.PI/3)*i - Math.PI/6;
        const x = cx + r*Math.cos(a), y = cy + r*Math.sin(a);
        i===0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y);
    }
    ctx.closePath();
    ctx.fillStyle   = 'rgba(6,8,6,0.92)';
    ctx.strokeStyle = color;
    ctx.lineWidth   = 1.5;
    ctx.fill(); ctx.stroke();
    // outer glow ring
    ctx.beginPath();
    for (let i=0;i<6;i++) {
        const a = (Math.PI/3)*i - Math.PI/6;
        ctx.lineTo(cx+(r+4)*Math.cos(a), cy+(r+4)*Math.sin(a));
    }
    ctx.closePath();
    ctx.strokeStyle = color+'33';
    ctx.lineWidth=1; ctx.stroke();
}

function drawRect(ctx, cx,cy,w,h, color) {
    ctx.fillStyle   = 'rgba(6,8,6,0.92)';
    ctx.strokeStyle = color;
    ctx.lineWidth   = 1.5;
    ctx.fillRect(cx-w/2, cy-h/2, w, h);
    ctx.strokeRect(cx-w/2, cy-h/2, w, h);
    // outer glow
    ctx.strokeStyle = color+'2a';
    ctx.lineWidth=1;
    ctx.strokeRect(cx-w/2-3, cy-h/2-3, w+6, h+6);
}

function drawDiamond(ctx, cx,cy,r, color) {
    ctx.beginPath();
    ctx.moveTo(cx,cy-r); ctx.lineTo(cx+r*0.7,cy);
    ctx.lineTo(cx,cy+r); ctx.lineTo(cx-r*0.7,cy);
    ctx.closePath();
    ctx.fillStyle   = 'rgba(6,8,6,0.92)';
    ctx.strokeStyle = color;
    ctx.lineWidth   = 1.5;
    ctx.fill(); ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(cx,cy-r-4); ctx.lineTo(cx+r*0.7+3,cy);
    ctx.lineTo(cx,cy+r+4); ctx.lineTo(cx-r*0.7-3,cy);
    ctx.closePath();
    ctx.strokeStyle = color+'2a'; ctx.lineWidth=1; ctx.stroke();
}

function nodeLabel(ctx, x,y, id, sub, color, below=true) {
    ctx.font = `bold 8px "JetBrains Mono"`;
    ctx.textAlign = 'center';
    ctx.fillStyle = color;
    ctx.fillText(id, x, y + (below ? 22 : -14));
    if (sub) {
        ctx.font = `8px "JetBrains Mono"`;
        ctx.fillStyle = '#7c6f64';
        ctx.fillText(sub, x, y + (below ? 31 : -5));
    }
    ctx.textAlign = 'left';
}

function drawTopo() {
    const el = topoCanvas.parentElement;
    const cw = el.clientWidth || 400;
    const ch = el.clientHeight || 200;
    topoCanvas.width = cw;
    topoCanvas.height = ch;
    topoTime += 0.02;

    topoCtx.clearRect(0,0,cw,ch);

    // Grid overlay (very faint — BG image provides atmosphere)
    topoCtx.strokeStyle = 'rgba(0,200,180,0.04)';
    topoCtx.lineWidth = 1;
    for (let x=0; x<cw; x+=40) { topoCtx.beginPath(); topoCtx.moveTo(x,0); topoCtx.lineTo(x,ch); topoCtx.stroke(); }
    for (let y=0; y<ch; y+=40) { topoCtx.beginPath(); topoCtx.moveTo(0,y); topoCtx.lineTo(cw,y); topoCtx.stroke(); }

    // Layout positions
    const pad  = 24;
    const worX = pad + 18;
    const engX = cw * 0.28;
    const dbX  = cw * 0.48;
    const queX = cw * 0.48;
    const apiX = cw * 0.72;
    const outX = cw - pad - 18;
    const midY = ch / 2;
    const worYs = NODES.workers.map((_,i) => pad + (i+0.5)*((ch-pad*2)/NODES.workers.length));
    const engY  = midY;
    const dbY   = midY * 0.6;
    const queY  = midY * 1.4;
    const apiY  = midY;
    const outY  = midY;

    // ── Draw edges ──
    // Workers → Engine (bezier)
    NODES.workers.forEach((w,i) => {
        const col = nodeColor(w.status);
        const load = topoEdgeLoad[i % 3];
        const edgeCol = `rgba(${load>0.9?'204,36,29':load>0.7?'215,153,33':'70,102,0'},${0.15+load*0.25})`;
        drawTopoEdge(topoCtx,
            worX, worYs[i], engX-16, engY,
            worX+(engX-worX)*0.5, worYs[i],
            worX+(engX-worX)*0.5, engY,
            engX, engY,
            edgeCol, false, 1
        );
    });

    // Engine → DB
    drawTopoEdge(topoCtx, engX+18, engY, dbX-12, dbY, engX+60, engY, dbX-60, dbY, C.green+'55', false, 1.2);
    // Engine → Queue
    drawTopoEdge(topoCtx, engX+18, engY, queX-12, queY, engX+60, engY, queX-60, queY, C.blue+'55', false, 1.2);
    // DB → API
    drawTopoEdge(topoCtx, dbX+14, dbY, apiX-20, apiY, dbX+60, dbY, apiX-60, apiY, C.orange+'55', false, 1.2);
    // Queue → API
    drawTopoEdge(topoCtx, queX+14, queY, apiX-20, apiY, queX+60, queY, apiX-60, apiY, C.blue+'44', false, 1.0);
    // API → Output
    drawTopoEdge(topoCtx, apiX+20, apiY, outX-16, outY, apiX+60, apiY, outX-60, outY, C.green+'66', false, 1.3);

    // ── Draw particles ──
    topoParticles = topoParticles.filter(p => p.t < 1);
    topoParticles.forEach(p => {
        p.t += p.speed;
        const pos = lerpBezier(p.x1,p.y1,p.cp1x,p.cp1y,p.cp2x,p.cp2y,p.x2,p.y2,Math.min(p.t,1));
        const alpha = Math.sin(p.t * Math.PI);
        topoCtx.beginPath();
        topoCtx.arc(pos.x, pos.y, 2.5, 0, Math.PI*2);
        topoCtx.fillStyle = p.color + Math.round(alpha*255).toString(16).padStart(2,'0');
        topoCtx.shadowColor = p.color; topoCtx.shadowBlur = 8;
        topoCtx.fill();
        topoCtx.shadowBlur = 0;
    });

    // ── Draw Nodes ──
    // Workers (circles)
    NODES.workers.forEach((w,i) => {
        const col = nodeColor(w.status);
        const pulse = Math.sin(topoTime*2 + i*0.8)*0.5+0.5;
        topoCtx.beginPath();
        topoCtx.arc(worX, worYs[i], 9, 0, Math.PI*2);
        topoCtx.fillStyle = 'rgba(6,8,6,0.9)';
        topoCtx.strokeStyle = col; topoCtx.lineWidth = 1.5;
        topoCtx.fill(); topoCtx.stroke();
        // Inner dot
        topoCtx.beginPath();
        topoCtx.arc(worX, worYs[i], 3, 0, Math.PI*2);
        topoCtx.fillStyle = col + Math.round(100+pulse*155).toString(16).padStart(2,'0');
        topoCtx.fill();
        // Label
        topoCtx.font='7px "JetBrains Mono"'; topoCtx.textAlign='center';
        topoCtx.fillStyle=col; topoCtx.fillText(w.id, worX, worYs[i]-12);
        topoCtx.textAlign='left';
    });

    // Engine (large hexagon)
    const engCol = nodeColor(NODES.engine.status);
    const engPulse = Math.sin(topoTime*1.5)*0.3+0.7;
    topoCtx.shadowColor=engCol; topoCtx.shadowBlur=10*engPulse;
    drawHex(topoCtx, engX, engY, 20, engCol);
    topoCtx.shadowBlur=0;
    topoCtx.font='bold 7px "JetBrains Mono"'; topoCtx.textAlign='center';
    topoCtx.fillStyle=engCol; topoCtx.fillText('ASOST', engX, engY-3);
    topoCtx.fillText('ENGINE', engX, engY+6);
    nodeLabel(topoCtx, engX, engY+20, '', NODES.engine.sub, '#7c6f64', true);
    topoCtx.textAlign='left';

    // DB (rectangle)
    drawRect(topoCtx, dbX, dbY, 28, 22, nodeColor(NODES.db.status));
    topoCtx.font='bold 7px "JetBrains Mono"'; topoCtx.textAlign='center';
    topoCtx.fillStyle=nodeColor(NODES.db.status);
    topoCtx.fillText('SQLite', dbX, dbY-2); topoCtx.fillText('DB', dbX, dbY+7);
    nodeLabel(topoCtx, dbX, dbY+11, '', NODES.db.sub, '#7c6f64', true);
    topoCtx.textAlign='left';

    // Queue (rounded-rect via circle)
    drawRect(topoCtx, queX, queY, 28, 22, nodeColor(NODES.queue.status));
    topoCtx.font='bold 7px "JetBrains Mono"'; topoCtx.textAlign='center';
    topoCtx.fillStyle=nodeColor(NODES.queue.status);
    topoCtx.fillText('QUEUE', queX, queY+4);
    nodeLabel(topoCtx, queX, queY+11, '', NODES.queue.sub, '#7c6f64', true);
    topoCtx.textAlign='left';

    // API (diamond — most important, pulsing)
    const apiCol   = nodeColor(NODES.api.status);
    const apiPulse = Math.sin(topoTime*2.5)*0.4+0.6;
    topoCtx.shadowColor=apiCol; topoCtx.shadowBlur=14*apiPulse;
    drawDiamond(topoCtx, apiX, apiY, 20, apiCol);
    topoCtx.shadowBlur=0;
    topoCtx.font='bold 7px "JetBrains Mono"'; topoCtx.textAlign='center';
    topoCtx.fillStyle=apiCol; topoCtx.fillText('GEMINI', apiX, apiY-2);
    topoCtx.fillText('API', apiX, apiY+7);
    nodeLabel(topoCtx, apiX, apiY+20, '', NODES.api.sub, '#7c6f64', true);
    topoCtx.textAlign='left';

    // Output (hexagon)
    drawHex(topoCtx, outX, outY, 16, nodeColor(NODES.output.status));
    topoCtx.font='bold 7px "JetBrains Mono"'; topoCtx.textAlign='center';
    topoCtx.fillStyle=nodeColor(NODES.output.status);
    topoCtx.fillText('PDF', outX, outY-2); topoCtx.fillText('OUT', outX, outY+7);
    nodeLabel(topoCtx, outX, outY+16, '', NODES.output.sub, '#7c6f64', true);
    topoCtx.textAlign='left';

    requestAnimationFrame(drawTopo);
}
drawTopo();

// Spawn particles along each edge route
function spawnTopoParticles() {
    const el = topoCanvas.parentElement;
    const cw = el.clientWidth||400, ch=el.clientHeight||200;
    const pad=24, worX=pad+18, engX=cw*0.28;
    const dbX=cw*0.48, queX=cw*0.48, apiX=cw*0.72, outX=cw-pad-18;
    const midY=ch/2;
    const worYs = NODES.workers.map((_,i) => pad+(i+0.5)*((ch-pad*2)/NODES.workers.length));
    const engY=midY, dbY=midY*0.6, queY=midY*1.4, apiY=midY, outY=midY;

    // Random worker → engine
    const wi = Math.floor(Math.random()*NODES.workers.length);
    const load = topoEdgeLoad[wi%3];
    const pcol = load > 0.88 ? C.orange : C.green;
    spawnParticle(worX,worYs[wi], engX,engY,
        worX+(engX-worX)*0.5, worYs[wi],
        worX+(engX-worX)*0.5, engY, pcol);

    // Engine → DB or Queue
    if (Math.random() > 0.15) spawnParticle(engX+18,engY, dbX-12,dbY, engX+60,engY, dbX-60,dbY, C.green);
    if (Math.random() > 0.25) spawnParticle(engX+18,engY, queX-12,queY, engX+60,engY, queX-60,queY, C.blue);

    // DB → API
    if (Math.random() > 0.15) spawnParticle(dbX+14,dbY, apiX-20,apiY, dbX+60,dbY, apiX-60,apiY, C.orange);
    // Queue → API
    if (Math.random() > 0.2) spawnParticle(queX+14,queY, apiX-20,apiY, queX+60,queY, apiX-60,apiY, C.blue);
    // API → Output
    if (Math.random() > 0.1) spawnParticle(apiX+20,apiY, outX-16,outY, apiX+60,apiY, outX-60,outY, C.green);

    setTimeout(spawnTopoParticles, 80+Math.random()*200); // significantly faster topology animation
}
setTimeout(spawnTopoParticles, 600);

// Simulate API going DOWN occasionally
setInterval(() => {
    if (Math.random() > 0.92) {
        NODES.api.status = 'DOWN';
        asostAddLog(`<span class="keyword">topology</span>: <span class="log-err">Gemini API node DOWN — retrying...</span>`, 'warn');
        setTimeout(() => { NODES.api.status = 'BUSY'; asostAddLog(`<span class="keyword">topology</span>: Gemini API node <span class="log-sys">RESTORED</span>`, 'sys'); }, 4000);
    }
    if (Math.random() > 0.88) {
        const wi = Math.floor(Math.random()*NODES.workers.length);
        NODES.workers[wi].status = 'BUSY';
        setTimeout(()=>{ NODES.workers[wi].status='ACTIVE'; }, 3000+Math.random()*4000);
    }
    // Update queue sub-label
    const queued = fileQueue.filter(f=>f.status==='QUEUED').length;
    NODES.queue.sub = `${queued} pending`;
}, 8000);

// ================================================================
//  12. PIPELINE PROGRESS FLOW
// ================================================================
const STAGE_NAMES   = ['EXTRACT TEXT','SMART CHUNK','TRANSLATE','ASSEMBLE','CREATE PDF'];
const STAGE_STATUS  = ['waiting','waiting','waiting','waiting','waiting'];
const STAGE_PCT     = [0,0,0,0,0];
const STAGE_SPEEDS  = [3.5, 2.5, 1.2, 2.8, 4.0]; // relative processing speed %/tick

let pipelineActive  = false;
let pipelineStage   = -1; // current active stage index
let pipelineFile    = '';
let pipelineTimer   = null;

function setPipelineStage(idx, pct, statusTxt) {
    for (let i=0;i<5;i++) {
        const el   = document.getElementById(`stage-${i}`);
        const bar  = document.getElementById(`bar-${i}`);
        const pctEl= document.getElementById(`pct-${i}`);
        const stxt = document.getElementById(`stxt-${i}`);
        const conn = document.getElementById(`conn-${i}`);
        if (!el) continue;

        el.classList.remove('active','done');
        if (i < idx) {
            el.classList.add('done');
            if (bar)  bar.style.width = '100%';
            if (pctEl) pctEl.textContent = '100%';
            if (stxt) { stxt.textContent = 'done'; }
            if (conn) conn.classList.remove('flowing');
        } else if (i === idx) {
            el.classList.add('active');
            if (bar)  bar.style.width = pct + '%';
            if (pctEl) pctEl.textContent = pct + '%';
            if (stxt) stxt.textContent = statusTxt || 'processing...';
            if (conn) conn.classList.add('flowing');
        } else {
            if (bar)  bar.style.width = '0%';
            if (pctEl) pctEl.textContent = '—';
            if (stxt) stxt.textContent = 'waiting';
            if (conn) conn.classList.remove('flowing');
        }
    }
}

function resetPipeline() {
    pipelineActive = false;
    pipelineStage  = -1;
    for (let i=0;i<5;i++) {
        const el   = document.getElementById(`stage-${i}`);
        const bar  = document.getElementById(`bar-${i}`);
        const pctEl= document.getElementById(`pct-${i}`);
        const stxt = document.getElementById(`stxt-${i}`);
        const conn = document.getElementById(`conn-${i}`);
        if (el)   el.classList.remove('active','done');
        if (bar)  bar.style.width = '0%';
        if (pctEl) pctEl.textContent = '—';
        if (stxt) stxt.textContent = 'waiting';
        if (conn) conn.classList.remove('flowing');
    }
    const fnEl = document.getElementById('pipeline-filename');
    if (fnEl) fnEl.textContent = '/* idle */';
    fnEl.className = 'pipeline-file-name comment';
}

function startPipeline(filename) {
    if (pipelineTimer) clearInterval(pipelineTimer);
    pipelineFile   = filename;
    pipelineActive = true;
    pipelineStage  = 0;
    STAGE_PCT.fill(0);

    const fnEl = document.getElementById('pipeline-filename');
    if (fnEl) { fnEl.textContent = `"${filename}"`; fnEl.className = 'pipeline-file-name string'; }

    const statusTexts = [
        ['reading bytes...','parsing structure...','extracting text...','cleaning output...'],
        ['tokenizing...','detecting paragraphs...','chunking by context...','optimizing splits...'],
        ['sending to Gemini...','streaming response...','translating chunks...','validating output...'],
        ['merging chunks...','applying formatting...','fixing alignment...','post-processing...'],
        ['generating PDF...','embedding fonts...','writing file...','finalizing...'],
    ];

    let stageStepIdx = 0;
    asostAddLog(`<span class="keyword">pipeline_start</span>: <span class="string">"${filename}"</span>`, 'sys');

    pipelineTimer = setInterval(() => {
        if (!pipelineActive || pipelineStage > 4) { clearInterval(pipelineTimer); return; }

        const speed = STAGE_SPEEDS[pipelineStage];
        STAGE_PCT[pipelineStage] = Math.min(100, STAGE_PCT[pipelineStage] + speed * (0.8+Math.random()*0.4));
        const pct = Math.round(STAGE_PCT[pipelineStage]);
        stageStepIdx = Math.floor(pct / 25) % statusTexts[pipelineStage].length;
        const stxt = statusTexts[pipelineStage][stageStepIdx];

        setPipelineStage(pipelineStage, pct, stxt);

        if (pct >= 100) {
            asostAddLog(`<span class="keyword">stage_${String(pipelineStage+1).padStart(2,'0')}</span>: ${STAGE_NAMES[pipelineStage]} <span class="log-sys">[DONE]</span>`, 'sys');
            pipelineStage++;
            if (pipelineStage > 4) {
                clearInterval(pipelineTimer);
                setPipelineStage(5, 0, '');
                asostAddLog(`<span class="keyword">pipeline_done</span>: <span class="string">"${pipelineFile}"</span> — all stages complete`, 'sys');
                setTimeout(resetPipeline, 800); // Much faster reset
            }
        }
    }, 90); // 2x faster pipeline updates
}

// Auto-start pipeline with the first running file
setTimeout(() => {
    const first = fileQueue.find(f => f.status === 'RUNNING');
    if (first) startPipeline(first.name);
}, 500);

// Auto-refill queue when empty to keep dashboard busy
const DEMO_FILES = [
    {name:'Arabic_Philosophy.pdf', type:'PDF'},
    {name:'Modern_Physics.docx',   type:'DOCX'},
    {name:'Machine_Learning.pdf',  type:'PDF'},
    {name:'World_History_V2.pdf',  type:'PDF'},
    {name:'Chemistry_Lab.docx',    type:'DOCX'},
    {name:'Sociology_Theory.pdf',  type:'PDF'},
];
function autoRefillQueue() {
    const active = fileQueue.filter(f => f.status !== 'DONE').length;
    if (active < 2) {
        const pick = DEMO_FILES[Math.floor(Math.random()*DEMO_FILES.length)];
        const id   = String(queueIdCtr++).padStart(3,'0');
        fileQueue.push({id, name:pick.name, type:pick.type, progress:0, status:'QUEUED', priority:fileQueue.length+1});
        asostAddLog(`<span class="keyword">auto_queue</span>: <span class="string">"${pick.name}"</span> <span class="log-sys">[ENQUEUED]</span>`, 'info');
        renderQueueMini();
    }
}
setInterval(autoRefillQueue, 8000);

// Auto-restart pipeline
function checkPipelineNeeded() {
    if (!pipelineActive) {
        const running = fileQueue.find(f => f.status === 'RUNNING');
        if (running) setTimeout(() => startPipeline(running.name), 300);
    }
}
setInterval(checkPipelineNeeded, 1200);

// ================================================================
//  13. UPLOAD ZONE
// ================================================================
const dropZone   = document.getElementById('drop-zone');
const fileInput  = document.getElementById('file-input');
const dzInner    = document.getElementById('dropzone-inner');
const normalHtml = `<p class="center-text comment">/* DROP PDF/DOCX FILES HERE */</p><p class="center-text glow-text"><i class="fa-solid fa-file-import fa-2x"></i></p><p class="center-text string">[ CLICK TO BROWSE ]</p><input type="file" id="file-input" hidden accept=".pdf,.docx">`;
const hoverHtml  = `<p class="center-text comment">/* !!! INCOMING !!! */</p><p class="center-text glow-text" style="color:var(--term-orange)"><i class="fa-solid fa-parachute-box fa-2x"></i></p><p class="center-text string" style="color:var(--term-orange)">[ RELEASE TO QUEUE ]</p>`;

dropZone.addEventListener('click', e => { if (!e.target.closest('button')&&!e.target.closest('.queue-preview')) fileInput.click(); });
dropZone.addEventListener('dragover', e => { e.preventDefault(); dzInner.innerHTML = hoverHtml; });
dropZone.addEventListener('dragleave', e => { e.preventDefault(); dzInner.innerHTML = normalHtml; });
dropZone.addEventListener('drop', e => { e.preventDefault(); if (e.dataTransfer.files.length) handleDrop(e.dataTransfer.files[0]); });
fileInput.addEventListener('change', e => { if (e.target.files.length) handleDrop(e.target.files[0]); });

function handleDrop(file) {
    dzInner.innerHTML = `<p class="center-text comment">/* FILE QUEUED */</p><p class="center-text glow-text" style="color:var(--term-blue)"><i class="fa-solid fa-check-double fa-2x"></i></p><p class="center-text string">"${file.name}"</p>`;
    fileQueue.push({id:String(queueIdCtr++).padStart(3,'0'), name:file.name, type:file.name.split('.').pop().toUpperCase(), progress:0, status:'QUEUED', priority:fileQueue.length+1});
    asostAddLog(`<span class="keyword">received_upload</span>: <span class="string">"${file.name}"</span> <span class="log-sys">[QUEUED]</span>`, 'sys');
    renderQueueMini();
    setTimeout(() => { dzInner.innerHTML = normalHtml; fileInput.value=''; }, 3000);
}

// ================================================================
//  14. MODALS
// ================================================================
document.getElementById('open-queue-ws').addEventListener('click',  () => openModal('queue-modal'));
document.getElementById('open-queue-btn').addEventListener('click', () => openModal('queue-modal'));
document.getElementById('open-api-ws').addEventListener('click',    () => openModal('api-modal'));

function openModal(id) {
    document.getElementById(id).classList.add('open');
    if (id==='queue-modal') renderQueueTable();
    if (id==='api-modal')   renderApiTable();
}
document.querySelectorAll('.modal-close').forEach(btn => {
    btn.addEventListener('click', () => document.getElementById(btn.dataset.modal).classList.remove('open'));
});
document.querySelectorAll('.modal-overlay').forEach(ov => {
    ov.addEventListener('click', e => { if (e.target===ov) ov.classList.remove('open'); });
});

// ================================================================
//  15. GAUGES
// ================================================================
let cpuVal=12, ramVal=26, diskVal=61;
function animateGauges() {
    cpuVal  = Math.max(2,  Math.min(96, cpuVal  + (Math.random()-0.5)*9));
    ramVal  = Math.max(15, Math.min(90, ramVal  + (Math.random()-0.5)*2));
    diskVal = Math.max(55, Math.min(80, diskVal + (Math.random()-0.5)*0.4));
    const set = (id, val) => { const el=document.getElementById(id); if(el) el.style.width=val.toFixed(0)+'%'; };
    const txt = (id, val, sfx) => { const el=document.getElementById(id); if(el) el.textContent=val.toFixed(0)+sfx; };
    set('cpu-bar', cpuVal); txt('cpu-pct', cpuVal,'%');
    set('ram-bar', ramVal); txt('ram-pct', ramVal,'%');
    set('disk-bar',diskVal);txt('disk-pct',diskVal,'%');
    document.getElementById('cpu-bar').classList.toggle('danger', cpuVal > 80);
    const cpuD=document.getElementById('cpu-display'); if(cpuD) cpuD.textContent=cpuVal.toFixed(0)+'%';
    const ramD=document.getElementById('ram-display'); if(ramD) ramD.textContent=((ramVal/100)*16).toFixed(1)+'G/16G';
}
setInterval(animateGauges, 2200);
animateGauges();

// ================================================================
//  16. BACKGROUND LOG SIMULATION + LIVE STATS
// ================================================================
const OPS  = ['extract_pdf','chunk_text','gemini_req','save_db','vectorize','index_doc','cleanup_tmp','requeue','flush_cache','rotate_key'];
const FLOG = ['Neuro_Ch1.pdf','Quantum.docx','BladeRunner.pdf','AI_Ethics.pdf','DataSci.docx','Mech_Eng.pdf','Sociology.docx','Calculus_V2.pdf','Philosophy.pdf','LingTheory.docx'];
const CHUNKS_MSG = ['chunk 12/48','chunk 31/48','chunk 48/48 ✓','chunks merged','delta applied'];

// PRE-FILL LOGS
function preFillLogs() {
    for (let i = 0; i < 40; i++) {
        const op = OPS[Math.floor(Math.random()*OPS.length)];
        const f  = FLOG[Math.floor(Math.random()*FLOG.length)];
        const r = Math.random();
        let status = '<span class="log-sys">OK</span>';
        if (r > 0.9) status = '<span class="log-warn">DELAY</span>';
        const msg = `<span class="keyword">${op}</span> <span class="punct">→</span> <span class="string">"${f}"</span> <span class="punct">[</span>${status}<span class="punct">]</span>`;
        asostAddLog(msg, r > 0.9 ? 'warn' : 'info');
    }
}
preFillLogs();

// Live counters
let liveBooks = 1204, livePages = 452000, liveThreads = 12;
let uptimeStart = Date.now() - (14*24*3600 + 2*3600 + 31*60) * 1000;

// Update polybar stats
function updatePolybarStats() {
    const bEl = document.getElementById('stat-books');
    const pEl = document.getElementById('stat-pages');
    if (bEl) bEl.textContent = liveBooks.toLocaleString();
    if (pEl) pEl.textContent = livePages >= 1000000
        ? (livePages/1000000).toFixed(1)+'M'
        : Math.round(livePages/1000)+'K';
}

// Update uptime display
function updateUptime() {
    const elapsed = Date.now() - uptimeStart;
    const d = Math.floor(elapsed/86400000);
    const h = Math.floor((elapsed%86400000)/3600000);
    const m = Math.floor((elapsed%3600000)/60000);
    const el = document.querySelector('.stats-grid-term .stat-line:nth-child(4) .number');
    if (el) el.textContent = `${d}d ${h}h ${m}m`;
}
setInterval(updateUptime, 60000);

function simulateBackend() {
    const r  = Math.random();
    const op = OPS[Math.floor(Math.random()*OPS.length)];
    const f  = FLOG[Math.floor(Math.random()*FLOG.length)];

    let type = 'info', status = '<span class="log-sys">OK</span>';
    if (r > 0.86) { type='warn'; status='<span class="log-warn">DELAY</span>'; }
    if (r > 0.96) { type='err';  status='<span class="log-err">FAIL</span>'; }

    // Vary log messages for realism
    let msg;
    if (r < 0.3) {
        const chk = CHUNKS_MSG[Math.floor(Math.random()*CHUNKS_MSG.length)];
        msg = `<span class="keyword">${op}</span> <span class="punct">→</span> <span class="string">"${f}"</span> <span class="comment">[${chk}]</span> <span class="punct">[</span>${status}<span class="punct">]</span>`;
    } else if (r < 0.55) {
        const ms  = Math.floor(120 + Math.random()*880);
        msg = `<span class="keyword">${op}</span> <span class="punct">→</span> <span class="string">"${f}"</span> <span class="comment">${ms}ms</span> <span class="punct">[</span>${status}<span class="punct">]</span>`;
    } else {
        msg = `<span class="keyword">${op}</span> <span class="punct">→</span> <span class="string">"${f}"</span> <span class="punct">[</span>${status}<span class="punct">]</span>`;
    }
    asostAddLog(msg, type);

    // Occasionally increment live counters
    if (Math.random() > 0.7) {
        const pgDelta = Math.floor(Math.random() * 24 + 4);
        livePages += pgDelta;
        if (Math.random() > 0.94) liveBooks++;
        updatePolybarStats();
    }

    // Randomly vary thread count
    if (Math.random() > 0.93) {
        liveThreads = Math.max(8, Math.min(16, liveThreads + (Math.random()>0.5?1:-1)));
        const tEl = document.querySelector('#win-stats .number'); // threads display not in stats window
    }

    setTimeout(simulateBackend, 700 + Math.random()*1900);
}

// ================================================================
//  17. BOOT SEQUENCE
// ================================================================
[
    {m:'asost-daemon v3.2.0 booting...',                                                    t:'sys',  d:200},
    {m:'loading kernel modules [<span class="log-sys">OK</span>]',                         t:'sys',  d:650},
    {m:'sqlite3 db connected — <span class="number">1204</span> records [<span class="log-sys">OK</span>]', t:'info', d:1050},
    {m:'worker pool initialized: <span class="number">12</span> threads [<span class="log-sys">OK</span>]', t:'info', d:1400},
    {m:'tpm monitor started: 5 keys registered [<span class="log-sys">OK</span>]',          t:'sys',  d:1750},
    {m:'gemini-2.5-pro endpoint verified [<span class="log-sys">OK</span>]',                t:'sys',  d:2100},
    {m:'<span class="log-warn">WARN:</span> KEY-B nearing limit — 58,412/60,000 tpm',      t:'warn', d:2500},
    {m:'node topology graph: all <span class="number">5</span> nodes UP [<span class="log-sys">OK</span>]', t:'sys', d:3000},
    {m:'pipeline engine ready — <span class="number">4</span> files in queue [<span class="log-sys">STANDBY</span>]', t:'sys', d:3500},
    {m:'background workers spawned [<span class="log-sys">OK</span>]',                      t:'info', d:3900},
    {m:'listening on <span class="number">:8080</span> [<span class="log-sys">READY</span>]', t:'sys', d:4200},
    {m:'<span class="string">system nominal. all services operational.</span>',              t:'sys',  d:4700},
].forEach(({m,t,d}) => setTimeout(()=>asostAddLog(m,t), d));

setTimeout(simulateBackend, 5200);
setTimeout(()=>{renderQueueMini(); updateApiStats(); updatePolybarStats();}, 400);

// ================================================================
//  18. MATRIX RAIN
// ================================================================
const matCanvas = document.getElementById('matrix-bg');
const matCtx    = matCanvas.getContext('2d');
let matDrops    = [];
const FS        = 13;
const MCHARS    = '010101ABCDEF█░▒▓01'.split('');
function initMatrix() {
    matCanvas.width  = window.innerWidth;
    matCanvas.height = window.innerHeight;
    const cols = Math.floor(matCanvas.width/FS);
    matDrops = Array.from({length:cols}, ()=>Math.random()*-100);
}
window.addEventListener('resize', () => {
    initMatrix();
    if (typeof Chart !== 'undefined' && Chart.instances) Object.values(Chart.instances).forEach(c=>c.resize());
});
initMatrix();
function drawMatrix() {
    // Much more transparent fade — bg image does the heavy lifting
    matCtx.fillStyle='rgba(2,6,12,0.18)';
    matCtx.fillRect(0,0,matCanvas.width,matCanvas.height);
    // Teal-green color matching city neon lights
    matCtx.fillStyle='rgba(0,210,180,0.18)';
    matCtx.font=FS+'px "JetBrains Mono"';
    matDrops.forEach((y,i) => {
        matCtx.fillText(MCHARS[Math.floor(Math.random()*MCHARS.length)], i*FS, y*FS);
        if (y*FS>matCanvas.height && Math.random()>0.975) matDrops[i]=0;
        matDrops[i]++;
    });
    requestAnimationFrame(drawMatrix);
}
drawMatrix();
