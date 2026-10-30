export default function(component) {
  const { data, parentElement, setTriggerValue } = component;
  const isFit = data.view === 'fit';
  // Streamlit can render new data into the same host before unmounting it.
  parentElement.querySelectorAll('.office-map-widget').forEach(previous => previous.remove());
  const root = document.createElement('section');
  root.className = 'office-map-widget' + (isFit ? ' office-map-fit' : '');
  root.setAttribute('aria-label', 'London office map and product labels');
  parentElement.appendChild(root);
  root.innerHTML = `<div class="map-toolbar" aria-label="Map measure"><button type="button" data-lens="usage" aria-pressed="true">Usage</button><button type="button" data-lens="temperature" aria-pressed="false">Temperature</button><button type="button" data-lens="rating" aria-pressed="false">Sentiment · sample</button></div><div class="map-grid"><div class="map-picture"><img alt="London office illustration with room positions confirmed by Ryan"><div class="map-pins"></div></div><div class="map-labels" aria-label="Spaces and Neat products"></div></div><div class="map-legend" aria-live="polite"></div>`;
  root.querySelector('img').src = data.image;
  root.querySelector('.map-toolbar').hidden = isFit;
  const pins = root.querySelector('.map-pins');
  const labels = root.querySelector('.map-labels');
  // Streamlit supplies a ShadowRoot when style isolation is enabled. Store
  // view state on its host element; a ShadowRoot itself has no dataset.
  const stateHost = parentElement.host || parentElement;
  let lens = isFit ? 'usage' : stateHost.dataset.officeLens || 'usage';
  let selected = data.selected;
  const products = row => row.products.map(p => p.name.replace(/^Neat /, '') + (p.count > 1 ? ' ×' + p.count : '')).join(' · ') || 'Products not reported';
  function value(row) {
    if (!row.allowed) return '—';
    const v = row[lens];
    if (v === null || v === undefined) return '—';
    return lens === 'usage' ? Math.round(v) + '%' : lens === 'temperature' ? v.toFixed(1) + '°' : v.toFixed(1);
  }
  function tone(row) {
    if (!row.allowed || row[lens] === null || row[lens] === undefined) return 'unknown';
    if (lens === 'temperature') return 'temperature';
    if (lens === 'rating') return 'rating';
    return 'usage';
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
      pin.querySelector('strong').textContent = value(row);
      pin.setAttribute('aria-label', row.name + ', ' + products(row) + ', ' + lens + ' ' + value(row));
      pin.title = row.name + ' · ' + products(row);
    });
    root.querySelector('.map-legend').textContent = isFit ? 'Map percentages show time in use. Purple outlines mark the selected room; — means insufficient usage evidence.' : lens === 'usage' ? 'Time in use · — means no qualifying room-use evidence' : lens === 'temperature' ? 'Mean °C · recorded conditions, not a comfort pass/fail · — means no single reading' : 'Invented space ratings / 5 · at least 5 responses · — means no qualifying sample';
  }
  root.querySelectorAll('[data-lens]').forEach(b => b.onclick = () => {
    lens = b.dataset.lens; stateHost.dataset.officeLens = lens; draw();
  });
  draw();
  return () => root.remove();
}
