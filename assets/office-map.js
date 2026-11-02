// Presentation guide bands, not occupancy targets or a thermal-comfort standard.
// Classify the displayed value so a rounded boundary never contradicts its colour.
export function mapScore(row, lens) {
  const raw = row[lens];
  if (!row.allowed || !Number.isFinite(raw)
      || (lens === 'usage' && (raw < 0 || raw > 100))
      || (lens === 'rating' && (raw < 1 || raw > 5))) {
    return {tone:'unknown', label:'No qualifying data', value:'—'};
  }
  const n = lens === 'usage' ? Math.round(raw) : Number(raw.toFixed(lens === 'rating' ? 2 : 1));
  const value = lens === 'usage' ? n + '%' : lens === 'temperature' ? n.toFixed(1) + '°' : n.toFixed(2);
  if (lens === 'usage') return n < 20 ? {tone:'rag-red',label:'Low use',value}
    : n < 40 ? {tone:'rag-amber',label:'Moderate use',value} : {tone:'rag-green',label:'High use',value};
  if (lens === 'rating') return n < 3 ? {tone:'rag-red',label:'Low sample rating',value}
    : n < 4 ? {tone:'rag-amber',label:'Mixed sample rating',value} : {tone:'rag-green',label:'Positive sample rating',value};
  if (lens === 'temperature') return n < 18 || n > 26
    ? {tone:'rag-red',label:n < 18 ? 'Well below guide range' : 'Well above guide range',value}
    : n < 20 || n > 24 ? {tone:'rag-amber',label:n < 20 ? 'Below guide range' : 'Above guide range',value}
    : {tone:'rag-green',label:'Within guide range',value};
  return {tone:'unknown',label:'No qualifying data',value:'—'};
}

const mapScales = {
  usage: ['Low <20%', 'Moderate 20–39%', 'High ≥40%', 'Time in use · guide bands, not targets.'],
  temperature: ['<18° / >26°', '18–<20° / >24–26°', '20–24°C', 'Mean temperature · illustrative comfort bands.'],
  rating: ['<3/5', '3–3.99/5', '4–5/5', 'Invented space ratings · at least 5 responses.'],
};

export default function(component) {
  const { data, parentElement, setTriggerValue } = component;
  const isFit = data.view === 'fit';
  const isExperience = data.view === 'experience';
  const isImprove = data.view === 'improve';
  const isCompact = isFit || isExperience || isImprove;
  // Streamlit can render new data into the same host before unmounting it.
  parentElement.querySelectorAll('.office-map-widget').forEach(previous => previous.remove());
  const root = document.createElement('section');
  root.className = 'office-map-widget' + (isCompact ? ' office-map-compact' : '') + (isFit ? ' office-map-fit' : '') + (isExperience ? ' office-map-experience' : '') + (isImprove ? ' office-map-improve' : '');
  root.setAttribute('aria-label', 'London office map and product labels');
  parentElement.appendChild(root);
  root.innerHTML = `<div class="map-toolbar" aria-label="Map measure"><button type="button" data-lens="usage" aria-pressed="true">Usage</button><button type="button" data-lens="temperature" aria-pressed="false">Temperature</button><button type="button" data-lens="rating" aria-pressed="false">Sentiment · sample</button></div><div class="map-grid"><div class="map-picture"><img alt="London office illustration with room positions confirmed by Ryan"><div class="map-pins"></div></div><div class="map-labels" aria-label="Spaces and Neat products"></div></div><div class="map-legend" aria-live="polite"></div>`;
  root.querySelector('img').src = data.image;
  root.querySelector('.map-toolbar').hidden = isCompact;
  // Keep score ranges visible beside the view choice, even when product labels
  // make the map tall. The action map retains its existing explanatory footer.
  if (!isImprove) root.querySelector('.map-grid').before(root.querySelector('.map-legend'));
  const pins = root.querySelector('.map-pins');
  const labels = root.querySelector('.map-labels');
  // Streamlit supplies a ShadowRoot when style isolation is enabled. Store
  // view state on its host element; a ShadowRoot itself has no dataset.
  const stateHost = parentElement.host || parentElement;
  let lens = isImprove ? 'action' : isExperience ? 'rating' : isFit ? 'usage' : stateHost.dataset.officeLens || 'usage';
  let selected = data.selected;
  const products = row => row.products.map(p => p.name.replace(/^Neat /, '') + (p.count > 1 ? ' ×' + p.count : '')).join(' · ') || 'Products not reported';
  function value(row) {
    if (!row.allowed) return '—';
    if (isImprove) return {controls:'Controls',layout:'Layout',evidence:'Check'}[row.action] || '—';
    return mapScore(row, lens).value;
  }
  function tone(row) {
    if (isImprove) return row.allowed && row.action ? row.action : 'unknown';
    return mapScore(row, lens).tone;
  }
  function select(row) {
    if (!row.allowed) return;
    selected = row.id;
    draw();
    setTriggerValue('picked', row.id);
  }
  data.rows.forEach(row => {
    const pin = document.createElement('button');
    pin.type = 'button'; pin.className = 'map-pin'; pin.dataset.id = row.id;
    pin.style.left = row.x + '%'; pin.style.top = row.y + '%';
    pin.disabled = !row.allowed;
    pin.innerHTML = '<span></span><strong></strong>';
    pin.querySelector('span').textContent = row.id;
    pin.onclick = () => select(row);
    pins.appendChild(pin);
    const label = document.createElement('button');
    label.type = 'button'; label.className = 'map-label'; label.dataset.id = row.id;
    label.disabled = !row.allowed;
    label.innerHTML = '<span class="map-letter"></span><span class="map-label-copy"><b></b><small></small></span>';
    label.querySelector('.map-letter').textContent = row.id;
    label.querySelector('b').textContent = row.name;
    label.querySelector('small').textContent = isFit
      ? (row.capacity === null ? 'No room data in scope' : row.capacity + ' seats')
      : isExperience ? (row.rating === null ? '— · ' : row.rating.toFixed(2) + '/5 · ') + row.responses + ' samples'
      : isImprove ? row.action_label
      : products(row);
    label.title = row.name + ' · ' + products(row);
    label.onclick = () => select(row);
    labels.appendChild(label);
  });
  function draw() {
    root.querySelectorAll('[data-lens]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.lens === lens)));
    data.rows.forEach(row => {
      const pin = pins.querySelector('[data-id="' + row.id + '"]');
      const label = labels.querySelector('[data-id="' + row.id + '"]');
      pin.setAttribute('aria-pressed', String(row.id === selected));
      label.setAttribute('aria-pressed', String(row.id === selected));
      pin.dataset.tone = tone(row);
      label.dataset.tone = tone(row);
      pin.querySelector('strong').textContent = value(row);
      const status = isImprove ? row.action_label : mapScore(row, lens).label;
      const description = row.name + ', ' + products(row) + ', ' + lens + ' ' + value(row) + ', ' + status;
      pin.setAttribute('aria-label', description);
      label.setAttribute('aria-label', description);
      pin.title = label.title = description;
    });
    const legend = root.querySelector('.map-legend');
    if (isImprove) {
      legend.textContent = 'Green: controls · Purple: layout · Gold: evidence first. Select a room to see its next step.';
    } else {
      const scale = mapScales[lens];
      legend.innerHTML = '<div class="map-scale">' + ['red','amber','green'].map((colour, index) =>
        '<span><i class="rag-' + colour + '"></i>' + scale[index] + '</span>').join('')
        + '<span><i class="unknown"></i>— No data</span></div>'
        + '<div class="map-scale-note">' + scale[3] + ' Purple outline: ' + (isExperience ? 'companion room.' : 'selected room.') + '</div>';
    }
  }
  root.querySelectorAll('[data-lens]').forEach(b => b.onclick = () => {
    lens = b.dataset.lens; stateHost.dataset.officeLens = lens; draw();
  });
  draw();
  return () => root.remove();
}
