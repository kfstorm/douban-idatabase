// This script runs in the page context and accesses window.Radarr or window.Sonarr
try {
  let apiInfo = {
    apiRoot: '',
    apiKey: '',
    type: ''
  };

  // Try to access Radarr API data
  if (window.Radarr) {
    apiInfo = {
      apiRoot: window.Radarr?.apiRoot || '',
      apiKey: window.Radarr?.apiKey || '',
      type: 'radarr'
    };
  }
  // Try to access Sonarr API data
  else if (window.Sonarr) {
    apiInfo = {
      apiRoot: window.Sonarr?.apiRoot || '',
      apiKey: window.Sonarr?.apiKey || '',
      type: 'sonarr'
    };
  }

  // Post message to the content script
  window.postMessage({
    type: 'ARR_API_DATA',
    payload: apiInfo
  }, '*');
} catch(e) {
  window.postMessage({
    type: 'ARR_API_DATA',
    payload: { apiRoot: '', apiKey: '', type: '' }
  }, '*');
}
