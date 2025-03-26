// Save options to Chrome storage
function saveOptions() {
  const apiBaseUrl = document.getElementById('apiBaseUrl').value.trim();
  const radarrApiRoot = document.getElementById('radarrApiRoot').value.trim();
  const radarrApiKey = document.getElementById('radarrApiKey').value.trim();

  chrome.storage.sync.set({
    apiBaseUrl: apiBaseUrl || 'http://localhost:8000',
    radarrApiRoot: radarrApiRoot,
    radarrApiKey: radarrApiKey
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
    radarrApiKey: ''
  }, function(items) {
    document.getElementById('apiBaseUrl').value = items.apiBaseUrl;
    document.getElementById('radarrApiRoot').value = items.radarrApiRoot;
    document.getElementById('radarrApiKey').value = items.radarrApiKey;
  });
}

// Initialize the page
document.addEventListener('DOMContentLoaded', restoreOptions);
document.getElementById('save').addEventListener('click', saveOptions);
