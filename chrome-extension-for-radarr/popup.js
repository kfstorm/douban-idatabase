// Simple popup functionality
document.addEventListener('DOMContentLoaded', function() {
  // Get current status from storage
  chrome.storage.sync.get([
    'apiBaseUrl',
    'goodRatingThreshold',
    'mediumRatingThreshold',
    'goodRatingColor',
    'mediumRatingColor',
    'lowRatingColor',
    'noRatingColor'
  ], function(data) {
    const statusElement = document.createElement('p');
    statusElement.textContent = `API URL: ${data.apiBaseUrl || 'http://localhost:8000'}`;
    document.body.insertBefore(statusElement, document.querySelector('.button'));

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
