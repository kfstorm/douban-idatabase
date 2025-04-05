// Simple popup functionality
document.addEventListener('DOMContentLoaded', function() {
  // Check if current page is a Radarr page
  checkCurrentTab();

  // Get current status from storage
  chrome.storage.sync.get([
    'doubanIdatabaseApiBaseUrl',
    'doubanIdatabaseApiKey',
    'goodRatingThreshold',
    'mediumRatingThreshold',
    'goodRatingColor',
    'mediumRatingColor',
    'lowRatingColor',
    'noRatingColor'
  ], function(data) {
    const statusElement = document.createElement('p');
    statusElement.textContent = `API URL: ${data.doubanIdatabaseApiBaseUrl || 'http://localhost:8000'}`;

    const apiKeyStatus = document.createElement('p');
    apiKeyStatus.textContent = `douban-idatabase API Key: ${data.doubanIdatabaseApiKey ? 'Configured' : 'Not configured'}`;

    document.body.insertBefore(statusElement, document.querySelector('.button'));
    document.body.insertBefore(apiKeyStatus, document.querySelector('.button'));

    // Add rating color legend
    const legendElement = document.createElement('div');
    legendElement.className = 'rating-legend';
    legendElement.innerHTML = `
      <p><strong>Rating Color Legend:</strong></p>
      <div class="legend-item">
        <span class="color-dot" style="background-color: ${data.goodRatingColor}"></span>
        <span>Good (≥ ${data.goodRatingThreshold})</span>
      </div>
      <div class="legend-item">
        <span class="color-dot" style="background-color: ${data.mediumRatingColor}"></span>
        <span>Medium (≥ ${data.mediumRatingThreshold})</span>
      </div>
      <div class="legend-item">
        <span class="color-dot" style="background-color: ${data.lowRatingColor}"></span>
        <span>Low (< ${data.mediumRatingThreshold})</span>
      </div>
      <div class="legend-item">
        <span class="color-dot" style="background-color: ${data.noRatingColor}"></span>
        <span>No Rating</span>
      </div>
    `;
    document.body.insertBefore(legendElement, document.querySelector('.button'));
  });
});

// Function to check if the current tab is a Radarr page
function checkCurrentTab() {
  chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
    if (tabs[0]) {
      chrome.tabs.sendMessage(
        tabs[0].id,
        {action: "getRadarrStatus"},
        function(response) {
          displayRadarrStatus(response);
        }
      );
    }
  });
}

// Function to display Radarr page status in the popup
function displayRadarrStatus(response) {
  const statusElement = document.createElement('div');
  statusElement.className = 'radarr-status';

  if (response) {
    if (response.isRadarrPage) {
      statusElement.innerHTML = '<p><strong>✅ This is a Radarr page</strong></p>';
      if (response.hasApiAccess) {
        statusElement.innerHTML += '<p>✅ API access: Available</p>';
      } else {
        statusElement.innerHTML += '<p>❌ API access: Not available</p>';
      }
    } else {
      statusElement.innerHTML = '<p><strong>❌ This is not a Radarr page</strong></p>';
      statusElement.innerHTML += '<p>Douban ratings will only be displayed on Radarr pages.</p>';
    }
  } else {
    statusElement.innerHTML = '<p><strong>❓ Unable to determine if this is a Radarr page</strong></p>';
    statusElement.innerHTML += '<p>Extension may not have access to this page.</p>';
  }

  // Insert the status at the top of the popup
  document.body.insertBefore(statusElement, document.body.firstChild);
}
