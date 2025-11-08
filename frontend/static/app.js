const API_BASE = 'http://localhost:8000/api';

function renderTopList(selector, items, keyName){
  const el = document.getElementById(selector);
  el.innerHTML = '';
  items.forEach(it => {
    const li = document.createElement('li');
    li.textContent = `${it[keyName]} (${it.count})`;
    el.appendChild(li);
  });
}

async function init(){
  // Metrics
  const metrics = await fetchJSON('/metrics');

  document.getElementById('avgLoanVal').textContent = metrics.average_loan_days ?? '-';
  document.getElementById('totalRecordsVal').textContent = metrics.total_records ?? '-';
  document.getElementById('uniqueBorrowersVal').textContent = metrics.unique_borrowers ?? '-';
  document.getElementById('currentlyLoanedVal').textContent = metrics.currently_loaned ?? '-';
  if(metrics.top_person && metrics.top_person.person){
    document.getElementById('topPersonVal').textContent = `${metrics.top_person.person} (${metrics.top_person.count})`;
  } else {
    document.getElementById('topPersonVal').textContent = '-';
  }

  // average delay: compute from delay_by_genre overall average if present
  let avgDelay = '-';
  if(metrics.delay_by_genre && metrics.delay_by_genre.length){
    const arr = metrics.delay_by_genre.map(d => d.avg_delay).filter(x => x!=null);
    if(arr.length) avgDelay = (arr.reduce((a,b)=>a+b,0)/arr.length).toFixed(2);
  }
  document.getElementById('avgDelayVal').textContent = avgDelay;

  // Top people list
  renderTopList('topPeopleList', metrics.top_people || [], 'person');
  // Delay tables (render as friendly tables with progress bars)
  function renderDelayTable(containerId, rows, type){
    const cont = document.getElementById(containerId);
    if(!rows || !rows.length){
      cont.innerHTML = `<h4>${type}</h4><p>-</p>`;
      return;
    }
    let html = `<h4>${type}</h4><table>`;
    html += '<thead><tr><th>Categoria</th><th>Total</th><th>Atrasos</th><th>% atrasos</th><th>Delay médio (dias)</th></tr></thead><tbody>';
    rows.forEach(r => {
      const label = r['Gênero'] ?? r['age_group'] ?? r['age_group'] ?? 'N/A';
      const total = r['total'] ?? 0;
      const delayed = r['delayed'] ?? 0;
      const pct = Math.round((r['pct_delayed'] ?? 0)*100);
      const avg = r['avg_delay'] != null ? Number(r['avg_delay']).toFixed(2) : '-';
      html += `<tr><td>${label}</td><td>${total}</td><td>${delayed}</td><td><div class="pct-bar"><div class="pct-fill" style="width:${pct}%"></div></div><small> ${pct}%</small></td><td>${avg}</td></tr>`;
    });
    html += '</tbody></table>';
    cont.innerHTML = html;
  }

  renderDelayTable('delayByGenre', metrics.delay_by_genre, 'Por Gênero');
  renderDelayTable('delayByAge', metrics.delay_by_age, 'Por faixa etária');

  // Time series
  const ts = await fetchJSON('/time_series');
  const months = ts.months || [];
  const livros = ts.livros || [];
  const notebook = ts.notebook || [];
  const traces = [
    { x: months, y: livros, name: 'Livros', type: 'scatter', mode: 'lines+markers', line:{color:'#006d33'} },
    { x: months, y: notebook, name: 'Notebook', type: 'scatter', mode: 'lines+markers', line:{color:'#00994d'} }
  ];
  Plotly.newPlot('tsChart', traces, {title: 'Empréstimos mensais por tipo', paper_bgcolor: '#fff', plot_bgcolor:'#fff'});

  // Heatmap (weekday x hour)
  const hm = await fetchJSON('/heatmap');
  const z = hm.values || [];
  const x = (hm.hours || []).map(h => (h<10? '0'+h : ''+h) + ':00');
  const y = hm.weekdays || [];
  const data = [{ z: z, x: x, y: y, type: 'heatmap', colorscale: [[0,'#e6f6ec'],[1,'#006d33']], reversescale:false }];
  const layout = {title: 'Heatmap de empréstimos (dia x hora)', xgap:1, ygap:1, paper_bgcolor:'#fff', plot_bgcolor:'#fff'};
  Plotly.newPlot('heatmapChart', data, layout, {responsive:true});
}

// small wrapper to account for different base path
async function fetchJSON(path){
  // Prefer explicit window.API_BASE (set in index.html). Fallback to localhost:8000 when developing,
  // otherwise use same-origin /api (when backend is proxied).
  const base = (typeof window.API_BASE !== 'undefined' && window.API_BASE) ? window.API_BASE : (window.location.origin.startsWith('http://localhost') ? 'http://localhost:8000' : '');
  const prefix = base ? base.replace(/\/$/, '') : '';
  const url = prefix + '/api' + path;
  const res = await fetch(url);
  return res.json();
}

init().catch(err => console.error(err));
