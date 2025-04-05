// This script runs in the page context and accesses window.Radarr
try {
  const apiInfo = {
    apiRoot: window.Radarr?.apiRoot || '',
    apiKey: window.Radarr?.apiKey || ''
  };

  // Post message to the content script
  window.postMessage({
    type: 'RADARR_API_DATA',
    payload: apiInfo
  }, '*');
} catch(e) {
  window.postMessage({
    type: 'RADARR_API_DATA',
    payload: { apiRoot: '', apiKey: '' }
  }, '*');
}
