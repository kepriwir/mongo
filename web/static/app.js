window.initDashboard = function () {
  const tbody = document.getElementById('status-body');
  const qform = document.getElementById('query-form');
  const qtype = document.getElementById('query-type');
  const qout = document.getElementById('query-output');
  const sform = document.getElementById('ssh-form');
  const snode = document.getElementById('ssh-node');
  const scmd = document.getElementById('ssh-cmd');
  const sout = document.getElementById('ssh-output');
  const cfgArea = document.getElementById('config-json');
  const btnLoad = document.getElementById('btn-load-config');
  const btnSave = document.getElementById('btn-save-config');

  const ctx = document.getElementById('lagChart').getContext('2d');
  const lagChart = new Chart(ctx, {
    type: 'line',
    data: { labels: [], datasets: [] },
    options: { responsive: true, animation: false, scales: { y: { beginAtZero: true } } }
  });

  function updateTable(members) {
    tbody.innerHTML = '';
    members.forEach(m => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${m.name}</td><td>${m.state}</td><td>${m.optime}</td>`+
        `<td class="${(m.lag_seconds||0) > 1 ? 'lag-bad':''}">${m.lag_seconds != null ? m.lag_seconds.toFixed(3) : '-'}</td>`;
      tbody.appendChild(tr);
    });
  }

  function updateChart(members, timeLabel) {
    if (lagChart.data.labels.length > 120) {
      lagChart.data.labels.shift();
      lagChart.data.datasets.forEach(ds => ds.data.shift());
    }
    lagChart.data.labels.push(timeLabel);
    members.forEach((m, idx) => {
      let ds = lagChart.data.datasets[idx];
      if (!ds) {
        ds = { label: m.name, data: [], borderColor: `hsl(${(idx*90)%360},70%,50%)`, fill: false };
        lagChart.data.datasets.push(ds);
      }
      ds.data.push(m.lag_seconds || 0);
    });
    lagChart.update();
  }

  // Streaming status via SSE
  const es = new EventSource('/api/stream/status');
  es.onmessage = (ev) => {
    try {
      const payload = JSON.parse(ev.data);
      if (payload.ok) {
        updateTable(payload.members);
        updateChart(payload.members, new Date(payload.time).toLocaleTimeString());
      }
    } catch (e) { console.error(e); }
  }

  qform.addEventListener('submit', async (e) => {
    e.preventDefault();
    qout.textContent = 'Running...';
    const res = await fetch('/api/query/test', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type: qtype.value })});
    const data = await res.json();
    qout.textContent = JSON.stringify(data, null, 2);
  });

  sform.addEventListener('submit', async (e) => {
    e.preventDefault();
    sout.textContent = 'Executing...';
    const res = await fetch('/api/ssh', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ node: snode.value.trim(), cmd: scmd.value })});
    const data = await res.json();
    sout.textContent = (data.stdout||'') + (data.stderr||'');
  });

  btnLoad.addEventListener('click', async () => {
    const res = await fetch('/api/config');
    const data = await res.json();
    cfgArea.value = JSON.stringify(data.config, null, 2);
  });
  btnSave.addEventListener('click', async () => {
    try {
      const cfg = JSON.parse(cfgArea.value);
      const res = await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cfg)});
      const data = await res.json();
      alert(data.ok ? 'Saved' : `Error: ${data.error}`);
    } catch (e) {
      alert('Invalid JSON');
    }
  });
}

