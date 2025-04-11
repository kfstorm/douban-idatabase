// Content script that runs on Radarr and Sonarr pages

// Default API URL - this can be overridden in options
let doubanIdatabaseApiBaseUrl = 'http://localhost:8000';
let doubanIdatabaseApiKey = '';
let arrApiRoot = '';
let arrApiKey = '';
let arrType = ''; // 'radarr' or 'sonarr'
// Rating threshold settings
let goodRatingThreshold = 8.0;
let mediumRatingThreshold = 7.0;
let goodRatingColor = '#2e963d'; // green
let mediumRatingColor = '#e09b24'; // yellow
let lowRatingColor = '#e05924';  // red
let noRatingColor = '#888888';   // gray
// Add a variable to track the last time checkForMediaItems was called
let lastCheckTime = 0;
let isScrolling = false;
let scrollTimeout = null;
// Add a rating cache to avoid redundant API requests
let ratingCache = {}; // Maps IDs to {rating, url} objects
// Add media cache to avoid redundant API requests
let mediaCache = null;
let lastMediaCacheTime = 0;
const MEDIA_CACHE_TTL = 5 * 60 * 1000; // 5 minutes cache validity

// Add flag to track if we're on a Radarr or Sonarr page
let isRadarrPage = false;
let isSonarrPage = false;

// Function to check if we're on a Radarr or Sonarr page
function checkIfArrPage() {
  // Check for meta tag in head
  const metaTags = document.querySelectorAll('meta[name="description"]');
  for (const tag of metaTags) {
    if (tag.content === "Radarr") {
      isRadarrPage = true;
      return true;
    }
    if (tag.content === "Sonarr") {
      isSonarrPage = true;
      return true;
    }
  }

  return false;
}

// Function to inject a script into the page context to access window.Radarr or window.Sonarr
function injectApiScript() {
  // Only proceed if we think this is a Radarr or Sonarr page
  if (!isRadarrPage && !isSonarrPage) {
    return;
  }

  // Use the extension's own script file instead of inline script
  const script = document.createElement('script');
  script.src = chrome.runtime.getURL('api-access.js');
  (document.head || document.documentElement).appendChild(script);

  // Clean up after the script has loaded
  script.onload = function() {
    script.remove();
  };
}

// Listen for messages from the injected script
window.addEventListener('message', function(event) {
  // Make sure the message is from our page
  if (event.source !== window) return;

  if (event.data.type === 'ARR_API_DATA') {
    const apiInfo = event.data.payload;
    if (apiInfo.apiRoot && apiInfo.apiKey) {
      arrApiRoot = apiInfo.apiRoot;
      arrApiKey = apiInfo.apiKey;
      arrType = apiInfo.type;
      console.log(`Successfully retrieved ${arrType} API details`);

      // Immediately check for items once we have the API details
      checkForMediaItems(true);
    } else if (isRadarrPage || isSonarrPage) {
      // Only log the warning if we believe this is a relevant page
      console.warn('API details not found in page context');
    }
  }
});

// Add message listener to respond with page status
chrome.runtime.onMessage.addListener(
  function(request, sender, sendResponse) {
    if (request.action === "getArrStatus") {
      sendResponse({
        isRadarrPage: isRadarrPage,
        isSonarrPage: isSonarrPage,
        hasApiAccess: !!(arrApiRoot && arrApiKey),
        type: arrType || (isRadarrPage ? 'radarr' : (isSonarrPage ? 'sonarr' : ''))
      });
    }
    return true; // Keep the message channel open for async response
  }
);

// First, get the API settings from storage
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
  if (data.doubanIdatabaseApiBaseUrl) {
    doubanIdatabaseApiBaseUrl = data.doubanIdatabaseApiBaseUrl;
  }

  if (data.doubanIdatabaseApiKey) {
    doubanIdatabaseApiKey = data.doubanIdatabaseApiKey;
  }

  // Set rating thresholds and colors if available
  if (data.goodRatingThreshold) {
    goodRatingThreshold = data.goodRatingThreshold;
  }

  if (data.mediumRatingThreshold) {
    mediumRatingThreshold = data.mediumRatingThreshold;
  }

  if (data.goodRatingColor) {
    goodRatingColor = data.goodRatingColor;
  }

  if (data.mediumRatingColor) {
    mediumRatingColor = data.mediumRatingColor;
  }

  if (data.lowRatingColor) {
    lowRatingColor = data.lowRatingColor;
  }

  if (data.noRatingColor) {
    noRatingColor = data.noRatingColor;
  }

  // Start processing once the DOM is fully loaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', processArrPage);
  } else {
    processArrPage();
  }
});

// Main function to process the page
function processArrPage() {
  // Only check if we're on a Radarr/Sonarr page once
  const isArrPage = checkIfArrPage();

  // Only continue if we think this is a relevant page
  if (!isArrPage) {
    return;
  }

  // Try to get API details from page context
  injectApiScript();

  // Use MutationObserver to detect when new items are added to the page
  const observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(mutation) {
      if (mutation.addedNodes && mutation.addedNodes.length > 0) {
        checkForMediaItems();
      }
    });
  });

  // Start observing the document
  observer.observe(document.body, { childList: true, subtree: true });

  // Initial check for items
  checkForMediaItems();

  // Set up intersection observer to detect when elements come into view
  setupIntersectionObserver();

  // Set up periodic checks for missed elements
  setInterval(checkForMediaItems, 3000);

  // Add scroll event listener
  window.addEventListener('scroll', handleScroll);
}

// Function to handle scroll events
function handleScroll() {
  isScrolling = true;

  // Clear previous timeout
  if (scrollTimeout) {
    clearTimeout(scrollTimeout);
  }

  // Set a timeout to run after scrolling stops
  scrollTimeout = setTimeout(function() {
    isScrolling = false;
    processUnprocessedElements();
  }, 300);
}

// Function to get all media elements based on the current page type
function getMediaElements() {
  if (isRadarrPage) {
    return [...document.querySelectorAll('div[class^="MovieIndexPoster-content"]')];
  } else if (isSonarrPage) {
    return [...document.querySelectorAll('div[class^="SeriesIndexPoster-content"]')];
  }
  return [];
}

// Function to set up intersection observer
function setupIntersectionObserver() {
  const options = {
    root: null, // viewport
    rootMargin: '0px',
    threshold: 0.1 // trigger when at least 10% of the element is visible
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const element = entry.target;
        // Process this element when it comes into view
        processMediaElement(element);
        // Unobserve after processing
        observer.unobserve(element);
      }
    });
  }, options);

  // Observe all media elements
  function observeMediaElements() {
    const mediaElements = getMediaElements();
    mediaElements.forEach(element => {
      observer.observe(element);
    });
  }

  // Initial observation
  observeMediaElements();

  // Set up periodic checks for new elements to observe
  setInterval(observeMediaElements, 2000);
}

// Function to process elements that weren't processed during scrolling
function processUnprocessedElements() {
  const mediaElements = getMediaElements();

  if (mediaElements.length > 0) {
    checkForMediaItems(true); // Force processing
  }
}

// Function to check for media items (movies or TV shows)
function checkForMediaItems(force = false) {
  // Skip if not on a relevant page
  if (!isRadarrPage && !isSonarrPage) {
    return;
  }

  // Check if enough time has passed since the last call or if forcing
  const currentTime = Date.now();
  if (!force && currentTime - lastCheckTime < 500) {
    // Not enough time has passed, exit early
    return;
  }

  // Update the last check time
  lastCheckTime = currentTime;

  // If we don't have API settings yet, try to get them
  if (!arrApiRoot || !arrApiKey) {
    injectApiScript();
    return;
  }

  // Otherwise fetch items from API
  fetchMediaFromAPI();
}

// Function to fetch media from Radarr/Sonarr API
function fetchMediaFromAPI() {
  const currentTime = Date.now();

  // Check if we have a valid cache
  if (mediaCache && (currentTime - lastMediaCacheTime < MEDIA_CACHE_TTL)) {
    processMediaFromAPI(mediaCache);
    return;
  }

  const endpoint = isRadarrPage ? 'movie' : 'series';

  fetch(`${arrApiRoot}/${endpoint}?apikey=${arrApiKey}`)
    .then(response => {
      if (!response.ok) {
        throw new Error(`API request failed for ${isRadarrPage ? 'Radarr' : 'Sonarr'}`);
      }
      return response.json();
    })
    .then(media => {
      // Update the cache
      mediaCache = media;
      lastMediaCacheTime = currentTime;

      processMediaFromAPI(media);
    });
}

// Process media from API and match with DOM elements
function processMediaFromAPI(media) {
  const mediaElements = getMediaElements();

  mediaElements.forEach(element => {
    processMediaElement(element);
  });
}

// Function to process a single media element (movie or TV show)
function processMediaElement(mediaElement) {
  if (!mediaCache) {
    return;
  }

  // Extract ID from the element
  let link;

  if (isRadarrPage) {
    link = mediaElement.querySelector('a[class^="MovieIndexPoster-link"]');
  } else if (isSonarrPage) {
    link = mediaElement.querySelector('a[class^="SeriesIndexPoster-link"]');
  } else {
    return;
  }

  if (!link || !link.href) return;

  const parts = link.href.split("/");
  const mediaId = parts[parts.length - 1];

  if (!mediaId) return;

  // Check if this element has already been processed for this specific media
  const currentMediaId = mediaElement.getAttribute('data-douban-media-id');

  // If the element has been processed for this specific media, no need to process again
  if (currentMediaId === mediaId) {
    return;
  }

  // If the element has a rating display but for a different media, remove it
  if (currentMediaId && currentMediaId !== mediaId) {
    const existingRating = mediaElement.querySelector('.douban-rating');
    if (existingRating) {
      existingRating.remove();
    }
  }

  // Find matching media in our cache
  const mediaItem = mediaCache.find(m => {
    if (isRadarrPage) {
      return m.tmdbId == mediaId;
    } else if (isSonarrPage) {
      // For Sonarr, match by titleSlug
      return m.titleSlug === mediaId;
    }
    return false;
  });

  // Only proceed if we have an IMDb ID
  if (mediaItem) {
    // Store the current media ID to detect changes
    mediaElement.setAttribute('data-douban-media-id', mediaId);

    // Check if rating is already in cache
    if (ratingCache[mediaId] !== undefined) {
      // Use cached rating and url
      const { rating, url } = ratingCache[mediaId];
      displayDoubanRating(rating, url, mediaElement);
    } else {
      if (mediaItem.imdbId) {
        // Fetch rating and then display it
        fetchDoubanRating(mediaItem.imdbId, mediaId)
          .then(({ rating, url }) => {
            displayDoubanRating(rating, url, mediaElement);
          });
      } else {
        // If no IMDb ID, display a placeholder
        displayDoubanRating(null, null, mediaElement);
      }
    }
  }
}

// Function to fetch Douban rating using the API
function fetchDoubanRating(imdbId, mediaId) {
  let url = `${doubanIdatabaseApiBaseUrl}/api/item?imdb_id=${imdbId}`;
  if (doubanIdatabaseApiKey) {
    url += `&api_key=${doubanIdatabaseApiKey}`;
  }

  return fetch(url)
    .then(response => {
      if (response.ok) {
        return response.json();
      }
      return null;
    })
    .catch(() => {
      return null;
    })
    .then(data => {
      let rating = null;
      let url = null;
      let doubanId = null;

      if (data && data.length > 0) {
        const item = data[0];
        if (item) {
          rating = item.rating || null;
          doubanId = item.douban_id || null;

          // Construct the Douban URL using the douban_id
          if (doubanId) {
            url = `https://movie.douban.com/subject/${doubanId}/`;
          }
        }
      }

      // Store in cache as an object with both rating and url
      ratingCache[mediaId] = { rating, url };

      return { rating, url };
    });
}

// Function to display the Douban rating in the UI
function displayDoubanRating(ratingValue, url, mediaElement) {
  // Remove any existing rating element first
  const existingRating = mediaElement.querySelector('.douban-rating');
  if (existingRating) {
    existingRating.remove();
  }

  // Create base element - use an anchor if we have a URL, otherwise a div
  const ratingElement = document.createElement(url ? 'a' : 'div');
  ratingElement.className = 'douban-rating';

  // If we have a URL, set anchor-specific properties
  if (url) {
    ratingElement.href = url;
    ratingElement.target = '_blank'; // Open in new tab
    ratingElement.title = '点击查看豆瓣详情';
  }

  // Ensure parent element has position relative for absolute positioning to work
  if (getComputedStyle(mediaElement).position === 'static') {
    mediaElement.classList.add('media-container');
  }

  // Determine color based on rating value and thresholds
  let ratingClass = 'low';
  let ratingColor = lowRatingColor;
  // Create a separate string for display
  let ratingStr;

  // Handle no rating case
  if (ratingValue == null) {
    ratingClass = 'none';
    ratingColor = noRatingColor;
    if (url) {
      ratingStr = 'N/A';
    } else {
      ratingStr = '?';
    }
  } else {
    // Format the rating to always display with one decimal place
    ratingStr = ratingValue.toFixed(1);

    if (ratingValue >= goodRatingThreshold) {
      ratingClass = 'good';
      ratingColor = goodRatingColor;
    } else if (ratingValue >= mediumRatingThreshold) {
      ratingClass = 'medium';
      ratingColor = mediumRatingColor;
    }
  }

  // Create rating content
  let ratingHtml = `
    <div class="douban-score">
      <span class="douban-logo douban-logo-${ratingClass}" style="background-color: ${ratingColor}">豆</span>
      <span class="douban-value douban-value-${ratingClass}" style="color: ${ratingColor}">${ratingStr}</span>
    </div>
  `;

  ratingElement.innerHTML = ratingHtml;
  mediaElement.appendChild(ratingElement);
}
