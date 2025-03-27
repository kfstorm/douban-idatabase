// Save options to Chrome storage
function saveOptions() {
  const apiBaseUrl = document.getElementById('apiBaseUrl').value.trim();
  const radarrApiRoot = document.getElementById('radarrApiRoot').value.trim();
  const radarrApiKey = document.getElementById('radarrApiKey').value.trim();
  const goodRatingThreshold = parseFloat(document.getElementById('goodRatingThreshold').value) || 8.0;
  const mediumRatingThreshold = parseFloat(document.getElementById('mediumRatingThreshold').value) || 7.0;
  const goodRatingColor = document.getElementById('goodRatingColor').value;
  const mediumRatingColor = document.getElementById('mediumRatingColor').value;
  const lowRatingColor = document.getElementById('lowRatingColor').value;
  const noRatingColor = document.getElementById('noRatingColor').value;

  chrome.storage.sync.set({
    apiBaseUrl: apiBaseUrl || 'http://localhost:8000',
    radarrApiRoot: radarrApiRoot,
    radarrApiKey: radarrApiKey,
    goodRatingThreshold: goodRatingThreshold,
    mediumRatingThreshold: mediumRatingThreshold,
    goodRatingColor: goodRatingColor,
    mediumRatingColor: mediumRatingColor,
    lowRatingColor: lowRatingColor,
    noRatingColor: noRatingColor
  }, function() {
    // Update status to let user know options were saved
    const status = document.getElementById('status');
    status.textContent = 'Options saved!';
    status.className = 'status success';
    status.style.display = 'block';

    setTimeout(function() {
      status.style.display = 'none';
    }, 3000);
  });
}

// Restore saved options when opening the options page
function restoreOptions() {
  chrome.storage.sync.get({
    apiBaseUrl: 'http://localhost:8000',
    radarrApiRoot: '',
    radarrApiKey: '',
    goodRatingThreshold: 8.0,
    mediumRatingThreshold: 7.0,
    goodRatingColor: '#2e963d', // green
    mediumRatingColor: '#e09b24', // yellow
    lowRatingColor: '#e05924',  // red
    noRatingColor: '#888888'    // gray
  }, function(items) {
    document.getElementById('apiBaseUrl').value = items.apiBaseUrl;
    document.getElementById('radarrApiRoot').value = items.radarrApiRoot;
    document.getElementById('radarrApiKey').value = items.radarrApiKey;
    document.getElementById('goodRatingThreshold').value = items.goodRatingThreshold;
    document.getElementById('mediumRatingThreshold').value = items.mediumRatingThreshold;
    document.getElementById('goodRatingColor').value = items.goodRatingColor;
    document.getElementById('mediumRatingColor').value = items.mediumRatingColor;
    document.getElementById('lowRatingColor').value = items.lowRatingColor;
    document.getElementById('noRatingColor').value = items.noRatingColor;

    // Update color previews
    updateColorPreviews(items);
  });
}

// Update color preview elements
function updateColorPreviews(items) {
  const goodColorPreview = document.getElementById('goodColorPreview');
  const mediumColorPreview = document.getElementById('mediumColorPreview');
  const lowColorPreview = document.getElementById('lowColorPreview');
  const noColorPreview = document.getElementById('noColorPreview');

  goodColorPreview.style.backgroundColor = items.goodRatingColor;
  mediumColorPreview.style.backgroundColor = items.mediumRatingColor;
  lowColorPreview.style.backgroundColor = items.lowRatingColor;
  noColorPreview.style.backgroundColor = items.noRatingColor;
}

// Add event listeners to update preview when colors change
function setupColorPreviewUpdates() {
  document.getElementById('goodRatingColor').addEventListener('input', function(e) {
    document.getElementById('goodColorPreview').style.backgroundColor = e.target.value;
  });

  document.getElementById('mediumRatingColor').addEventListener('input', function(e) {
    document.getElementById('mediumColorPreview').style.backgroundColor = e.target.value;
  });

  document.getElementById('lowRatingColor').addEventListener('input', function(e) {
    document.getElementById('lowColorPreview').style.backgroundColor = e.target.value;
  });

  document.getElementById('noRatingColor').addEventListener('input', function(e) {
    document.getElementById('noColorPreview').style.backgroundColor = e.target.value;
  });
}

// Initialize the page
document.addEventListener('DOMContentLoaded', function() {
  restoreOptions();
  setupColorPreviewUpdates();
});
document.getElementById('save').addEventListener('click', saveOptions);
