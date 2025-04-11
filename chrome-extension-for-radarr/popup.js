// Simple popup functionality
document.addEventListener('DOMContentLoaded', function() {
  // Check if current page is a Radarr or Sonarr page
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
    statusElement.textContent = `API 网址: ${data.doubanIdatabaseApiBaseUrl || 'http://localhost:8000'}`;

    const apiKeyStatus = document.createElement('p');
    apiKeyStatus.textContent = `豆瓣数据库 API 密钥: ${data.doubanIdatabaseApiKey ? '已配置' : '未配置'}`;

    document.body.insertBefore(statusElement, document.querySelector('.button'));
    document.body.insertBefore(apiKeyStatus, document.querySelector('.button'));

    // Add rating color legend
    const legendElement = document.createElement('div');
    legendElement.className = 'rating-legend';
    legendElement.innerHTML = `
      <p><strong>评分颜色说明:</strong></p>
      <div class="legend-item">
        <span class="color-dot" style="background-color: ${data.goodRatingColor}"></span>
        <span>好评 (≥ ${data.goodRatingThreshold})</span>
      </div>
      <div class="legend-item">
        <span class="color-dot" style="background-color: ${data.mediumRatingColor}"></span>
        <span>中评 (≥ ${data.mediumRatingThreshold})</span>
      </div>
      <div class="legend-item">
        <span class="color-dot" style="background-color: ${data.lowRatingColor}"></span>
        <span>低评 (< ${data.mediumRatingThreshold})</span>
      </div>
      <div class="legend-item">
        <span class="color-dot" style="background-color: ${data.noRatingColor}"></span>
        <span>暂无评分</span>
      </div>
    `;
    document.body.insertBefore(legendElement, document.querySelector('.button'));
  });
});

// Function to check if the current tab is a Radarr or Sonarr page
function checkCurrentTab() {
  chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
    if (tabs[0]) {
      chrome.tabs.sendMessage(
        tabs[0].id,
        {action: "getArrStatus"},
        function(response) {
          displayArrStatus(response);
        }
      );
    }
  });
}

// Function to display Radarr/Sonarr page status in the popup
function displayArrStatus(response) {
  const statusElement = document.createElement('div');
  statusElement.className = 'arr-status';

  if (response) {
    if (response.isRadarrPage || response.isSonarrPage) {
      const appType = response.isRadarrPage ? 'Radarr' : 'Sonarr';
      const contentType = response.isRadarrPage ? '电影' : '剧集';

      statusElement.innerHTML = `<p><strong>✅ 这是 ${appType} 页面</strong></p>`;
      if (response.hasApiAccess) {
        statusElement.innerHTML += '<p>✅ API 访问: 可用</p>';
        statusElement.innerHTML += `<p>豆瓣评分将显示在${contentType}旁边。</p>`;
      } else {
        statusElement.innerHTML += '<p>❌ API 访问: 不可用</p>';
      }
    } else {
      statusElement.innerHTML = '<p><strong>❌ 这不是 Radarr 或 Sonarr 页面</strong></p>';
      statusElement.innerHTML += '<p>豆瓣评分只会在 Radarr 和 Sonarr 页面上显示。</p>';
    }
  } else {
    statusElement.innerHTML = '<p><strong>❓ 无法确定这是否为 Radarr 或 Sonarr 页面</strong></p>';
    statusElement.innerHTML += '<p>扩展程序可能无法访问此页面。</p>';
  }

  // Insert the status at the top of the popup
  document.body.insertBefore(statusElement, document.body.firstChild);
}
