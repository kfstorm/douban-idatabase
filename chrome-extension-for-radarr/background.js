// Background script for the Douban Ratings extension

// Initialize default settings when extension is installed
chrome.runtime.onInstalled.addListener(function() {
  chrome.storage.sync.set({
    doubanIdatabaseApiBaseUrl: 'http://localhost:8000',
    doubanIdatabaseApiKey: '',
    goodRatingThreshold: 8.0,
    mediumRatingThreshold: 7.0,
    goodRatingColor: '#2e963d', // green
    mediumRatingColor: '#e09b24', // yellow
    lowRatingColor: '#e05924',  // red
    noRatingColor: '#888888'   // gray
  }, function() {
    console.log('Default settings initialized');
  });
});

// Listen for messages from content script
chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
  if (request.action === 'fetchDoubanRating') {
    const doubanIdatabaseApiBaseUrl = request.doubanIdatabaseApiBaseUrl || 'http://localhost:8000';
    const doubanIdatabaseApiKey = request.doubanIdatabaseApiKey || '';
    const imdbId = request.imdbId;

    let url = `${doubanIdatabaseApiBaseUrl}/api/item?imdb_id=${imdbId}`;
    if (doubanIdatabaseApiKey) {
      url += `&api_key=${doubanIdatabaseApiKey}`;
    }

    fetch(url)
      .then(response => response.json())
      .then(data => {
        sendResponse({ success: true, data: data });
      })
      .catch(error => {
        sendResponse({ success: false, error: error.message });
      });

    // Return true to indicate that the response will be sent asynchronously
    return true;
  }
});
