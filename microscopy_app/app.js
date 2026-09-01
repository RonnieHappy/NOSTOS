const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];

const fileInput = $('#file');
const drop = $('#drop');
const analyze = $('#analyze');
const imageElements = {
  source: $('#source'),
  overlay: $('#overlay'),
  orientation: $('#orientationMap'),
  coherence: $('#coherenceMap'),
  support: $('#supportMap'),
  spectrum: $('#spectrumMap'),
};

let selectedFiles = [];
let imageData = null;
let lastResult = null;
let currentView = 'source';

fetch('/api/health')
  .then(response => response.json())
  .then(data => {
    $('#health').textContent = 'Ready';
    $('#health').classList.add('ready');
    $('#device').textContent = `${String(data.device).toUpperCase()} local analysis`;
  })
  .catch(() => {
    $('#health').textContent = 'Offline';
    $('#health').classList.add('error');
  });

function mode() {
  return $('#mode').value;
}

function resetResult() {
  lastResult = null;
  $('#export').disabled = true;
  $('#measurementState').textContent = 'Not run';
  $('#measurementState').dataset.state = '';
  $('#evidenceState').textContent = 'Not evaluated';
  $('#runtimeState').textContent = '-';
  $('#warnings').textContent = 'No result available.';
  ['metric1', 'metric2', 'metric3', 'metric4'].forEach(id => { $(`#${id}`).textContent = '--'; });
  Object.values(imageElements).forEach(element => { element.hidden = true; element.removeAttribute('src'); });
  $('#viewerTools').hidden = true;
  $('#viewerMeta').hidden = true;
  $('#emptyState').hidden = false;
}

function syncMode() {
  selectedFiles = [];
  imageData = null;
  fileInput.value = '';
  resetResult();
  const isPshg = mode() === 'label_free_pshg';
  const isCartilage = mode() === 'cartilage';
  $('#stainField').hidden = !isCartilage;
  $('#pshgProtocol').hidden = !isPshg;
  if (isPshg) {
    fileInput.multiple = true;
    fileInput.setAttribute('webkitdirectory', '');
    fileInput.setAttribute('directory', '');
    fileInput.accept = 'image/tiff,.tif,.tiff';
    $('#dropTitle').textContent = 'Load PSHG acquisition folder';
    $('#dropHelp').textContent = '10 FSHG frames plus R2.tif and SNR.tif';
    $('#scale').value = '1.00';
    setMetricLabels([
      ['Mean axial angle', 'degrees'],
      ['Axial resultant', '0 to 1'],
      ['Median coherence', '0 to 1'],
      ['Accepted support', 'field fraction'],
    ]);
  } else {
    fileInput.multiple = false;
    fileInput.removeAttribute('webkitdirectory');
    fileInput.removeAttribute('directory');
    fileInput.accept = 'image/png,image/jpeg,image/tiff,.tif,.tiff';
    $('#dropTitle').textContent = 'Load calibrated microscopy image';
    $('#dropHelp').textContent = 'PNG, JPEG or browser-readable TIFF';
    $('#scale').value = isCartilage ? '5.16' : '1.00';
    setMetricLabels([
      ['Orientation', 'degrees, axial'],
      ['Anisotropy', 'FFT order'],
      ['Angular entropy', 'spectral disorder'],
      ['Characteristic frequency', 'cycles per mm'],
    ]);
  }
  $('#loadStatus').textContent = 'No acquisition loaded.';
  analyze.disabled = true;
}

function setMetricLabels(labels) {
  labels.forEach((item, index) => {
    $(`#metricLabel${index + 1}`).textContent = item[0];
    $(`#metricUnit${index + 1}`).textContent = item[1];
  });
}

function validatePshg(files) {
  const names = files.map(item => item.name.toLowerCase());
  const angles = names
    .map(name => name.match(/_fshg_p(\d+)\.tiff?$/))
    .filter(Boolean)
    .map(match => Number(match[1]))
    .sort((a, b) => a - b);
  const expected = Array.from({ length: 10 }, (_, index) => index * 20);
  const correctAngles = angles.length === expected.length && angles.every((value, index) => value === expected[index]);
  const hasR2 = names.includes('r2.tif') || names.includes('r2.tiff');
  const hasSnr = names.includes('snr.tif') || names.includes('snr.tiff');
  const hasFi = names.includes('fi.tif') || names.includes('fi.tiff');
  if (!correctAngles || !hasR2 || !hasSnr) {
    return { ok: false, message: `${files.length} TIFF files loaded. Required: angles 0:20:180, R2.tif and SNR.tif.` };
  }
  return { ok: true, message: `Complete ${files.length}-file acquisition${hasFi ? ' with evaluation-only FI map' : ''}.` };
}

function loadSelection(fileList) {
  resetResult();
  if (mode() === 'label_free_pshg') {
    selectedFiles = [...fileList].filter(item => /\.tiff?$/i.test(item.name));
    const validation = validatePshg(selectedFiles);
    $('#loadStatus').textContent = validation.message;
    $('#loadStatus').classList.toggle('invalid', !validation.ok);
    analyze.disabled = !validation.ok;
    return;
  }
  const first = fileList[0];
  if (!first) return;
  selectedFiles = [first];
  const reader = new FileReader();
  reader.onload = () => {
    imageData = reader.result;
    imageElements.source.src = imageData;
    imageElements.source.hidden = false;
    $('#emptyState').hidden = true;
    $('#loadStatus').classList.remove('invalid');
    $('#loadStatus').textContent = `${first.name} loaded.`;
    analyze.disabled = false;
  };
  reader.readAsDataURL(first);
}

function fileData(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve({ name: file.name, data: reader.result });
    reader.onerror = () => reject(new Error(`Could not read ${file.name}`));
    reader.readAsDataURL(file);
  });
}

fileInput.onchange = event => loadSelection(event.target.files);
$('#mode').onchange = syncMode;
['dragenter', 'dragover'].forEach(name => drop.addEventListener(name, event => {
  event.preventDefault();
  drop.classList.add('drag');
}));
['dragleave', 'drop'].forEach(name => drop.addEventListener(name, event => {
  event.preventDefault();
  drop.classList.remove('drag');
}));
drop.addEventListener('drop', event => loadSelection(event.dataTransfer.files));

analyze.onclick = async () => {
  analyze.disabled = true;
  $('#progress').hidden = false;
  $('#measurementState').textContent = 'Running';
  $('#progressText').textContent = mode() === 'label_free_pshg'
    ? 'Resolving orientation and acquisition support'
    : 'Segmenting tissue and resolving spectra';
  try {
    const payload = {
      mode: mode(),
      stain: $('#stain').value,
      pixel_size_um: Number($('#scale').value),
    };
    if (mode() === 'label_free_pshg') {
      payload.files = await Promise.all(selectedFiles.map(fileData));
    } else {
      payload.image_data = imageData;
    }
    const response = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Analysis failed');
    lastResult = data;
    render(data);
  } catch (error) {
    $('#measurementState').textContent = 'Error';
    $('#measurementState').dataset.state = 'error';
    $('#warnings').innerHTML = `<div class="alert">${escapeHtml(error.message)}</div>`;
  } finally {
    $('#progress').hidden = true;
    analyze.disabled = false;
  }
};

function number(value, digits = 3) {
  return value === null || value === undefined ? '--' : Number(value).toFixed(digits);
}

function render(data) {
  if (data.analysis_mode === 'label_free_pshg') renderPshg(data);
  else renderLegacy(data);
  $('#imageSize').textContent = `${data.image.width} × ${data.image.height} px`;
  $('#viewerMeta').hidden = false;
  $('#viewerTools').hidden = false;
  $('#emptyState').hidden = true;
  $('#warnings').innerHTML = data.warnings.map(message => `<div>${escapeHtml(message)}</div>`).join('');
  $('#export').disabled = false;
}

function renderPshg(data) {
  imageElements.source.src = data.source_png;
  imageElements.orientation.src = data.orientation_png;
  imageElements.coherence.src = data.coherence_png;
  imageElements.support.src = data.support_png;
  $$('.pshg-view').forEach(button => { button.hidden = false; });
  $$('.legacy-view').forEach(button => { button.hidden = true; });
  $('#metric1').textContent = `${number(data.metrics.mean_axial_orientation_degrees, 1)}°`;
  $('#metric2').textContent = number(data.metrics.axial_resultant);
  $('#metric3').textContent = number(data.metrics.median_coherence);
  $('#metric4').textContent = `${number(100 * data.metrics.eligible_fraction, 1)}%`;
  $('#measurementState').textContent = titleCase(data.measurement_status);
  $('#measurementState').dataset.state = data.measurement_status;
  $('#evidenceState').textContent = titleCase(data.evidence_status);
  $('#runtimeState').textContent = `${data.elapsed_seconds.toFixed(3)} s CPU`;
  $('#caseState').textContent = data.profile.provenance.verified
    ? `Verified public bundle: ${data.profile.provenance.matched_group}`
    : 'New acquisition: instrument bridge required';
  setView('orientation');
}

function renderLegacy(data) {
  imageElements.overlay.src = data.overlay_png;
  imageElements.spectrum.src = data.spectrum_png;
  $$('.pshg-view').forEach(button => { button.hidden = true; });
  $$('.legacy-view').forEach(button => { button.hidden = false; });
  $('#metric1').textContent = `${number(data.metrics.orientation_degrees, 1)}°`;
  $('#metric2').textContent = number(data.metrics.anisotropy);
  $('#metric3').textContent = number(data.metrics.angular_entropy);
  $('#metric4').textContent = number(data.metrics.characteristic_frequency_cycles_per_mm, 1);
  $('#measurementState').textContent = titleCase(data.qc.status);
  $('#measurementState').dataset.state = data.qc.status;
  $('#evidenceState').textContent = 'Exploratory adapter';
  $('#runtimeState').textContent = `${data.elapsed_seconds.toFixed(3)} s ${String(data.device).toUpperCase()}`;
  $('#caseState').textContent = `${data.metrics.analyzed_tiles} analyzed tiles`;
  setView(data.analysis_mode === 'cartilage' ? 'overlay' : 'source');
}

function setView(view) {
  currentView = view;
  Object.entries(imageElements).forEach(([name, element]) => { element.hidden = name !== view; });
  $$('#viewerTools button').forEach(button => button.classList.toggle('active', button.dataset.view === view));
}

$$('#viewerTools button').forEach(button => {
  button.onclick = () => setView(button.dataset.view);
});

$('#export').onclick = () => {
  if (!lastResult) return;
  const clean = JSON.parse(JSON.stringify(lastResult));
  Object.keys(clean).filter(key => key.endsWith('_png')).forEach(key => { delete clean[key]; });
  const blob = new Blob([JSON.stringify(clean, null, 2)], { type: 'application/json' });
  const anchor = document.createElement('a');
  anchor.href = URL.createObjectURL(blob);
  anchor.download = `nostos_${Date.now()}.json`;
  anchor.click();
  URL.revokeObjectURL(anchor.href);
};

function titleCase(value) {
  return String(value || '').replaceAll('_', ' ').replace(/\b\w/g, character => character.toUpperCase());
}

function escapeHtml(value) {
  const element = document.createElement('div');
  element.textContent = value;
  return element.innerHTML;
}

syncMode();
