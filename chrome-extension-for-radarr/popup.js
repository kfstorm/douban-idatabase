// Simple popup functionality
document.addEventListener('DOMContentLoaded', function() {
  // Get current status from storage
  chrome.storage.sync.get('apiBaseUrl', function(data) {
    const statusElement = document.createElement('p');
    statusElement.textContent = `API URL: ${data.apiBaseUrl || 'http://localhost:8000'}`;
    document.body.insertBefore(statusElement, document.querySelector('.button'));
  });
});
