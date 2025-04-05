// Content script that runs on Radarr pages

// Default API URL - this can be overridden in options
let doubanIdatabaseApiBaseUrl = 'http://localhost:8000';
let doubanIdatabaseApiKey = '';
let radarrApiRoot = '';
let radarrApiKey = '';
// Rating threshold settings
let goodRatingThreshold = 8.0;
let mediumRatingThreshold = 7.0;
let goodRatingColor = '#2e963d'; // green
let mediumRatingColor = '#e09b24'; // yellow
let lowRatingColor = '#e05924';  // red
let noRatingColor = '#888888';   // gray
// Add a variable to track the last time checkForMovieItems was called
let lastCheckTime = 0;
let isScrolling = false;
let scrollTimeout = null;
// Add a rating cache to avoid redundant API requests
let ratingCache = {}; // Maps TMDB IDs to {rating, url} objects
// Add movie cache to avoid redundant Radarr API requests
let movieCache = null;
let lastMovieCacheTime = 0;
const MOVIE_CACHE_TTL = 5 * 60 * 1000; // 5 minutes cache validity

// Add flag to track if we're on a Radarr page
let isRadarrPage = false;

// Function to check if we're on a Radarr page
function checkIfRadarrPage() {
  // Check for Radarr meta tag in head
  const metaTags = document.querySelectorAll('meta[name="description"]');
  for (const tag of metaTags) {
    if (tag.content === "Radarr") {
      return true;
    }
  }

  return false;
}

// Function to inject a script into the page context to access window.Radarr
function injectRadarrApiScript() {
  // Only proceed if we think this is a Radarr page
  if (!isRadarrPage) {
    return;
  }

  // Use the extension's own script file instead of inline script
  const script = document.createElement('script');
  script.src = chrome.runtime.getURL('radarr-api-access.js');
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

  if (event.data.type === 'RADARR_API_DATA') {
    const apiInfo = event.data.payload;
    if (apiInfo.apiRoot && apiInfo.apiKey) {
      radarrApiRoot = apiInfo.apiRoot;
      radarrApiKey = apiInfo.apiKey;
      console.log('Successfully retrieved Radarr API details');

      // Immediately check for movie items once we have the API details
      checkForMovieItems(true);
    } else if (isRadarrPage) {
      // Only log the warning if we believe this is a Radarr page
      console.warn('Radarr API details not found in page context');
    }
  }
});

// Add message listener to respond with Radarr page status
chrome.runtime.onMessage.addListener(
  function(request, sender, sendResponse) {
    if (request.action === "getRadarrStatus") {
      sendResponse({
        isRadarrPage: isRadarrPage,
        hasApiAccess: !!(radarrApiRoot && radarrApiKey)
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
    document.addEventListener('DOMContentLoaded', processRadarrPage);
  } else {
    processRadarrPage();
  }
});

// Main function to process the Radarr page
function processRadarrPage() {
  // Only check if we're on a Radarr page once
  isRadarrPage = checkIfRadarrPage();

  // Only continue if we think this is a Radarr page
  if (!isRadarrPage) {
    return;
  }

  // Try to get Radarr API details from page context
  injectRadarrApiScript();

  // Use MutationObserver to detect when new movie items are added to the page
  const observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(mutation) {
      if (mutation.addedNodes && mutation.addedNodes.length > 0) {
        checkForMovieItems();
      }
    });
  });

  // Start observing the document
  observer.observe(document.body, { childList: true, subtree: true });

  // Initial check for movie items
  checkForMovieItems();

  // Set up intersection observer to detect when movie elements come into view
  setupIntersectionObserver();

  // Set up periodic checks for missed elements
  setInterval(checkForMovieItems, 3000);

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
        processMovieElement(element);
        // Unobserve after processing
        observer.unobserve(element);
      }
    });
  }, options);

  // Observe all movie elements
  function observeMovieElements() {
    const movieElements = document.querySelectorAll('div[class^="MovieIndexPoster-content"]');
    movieElements.forEach(element => {
      observer.observe(element);
    });
  }

  // Initial observation
  observeMovieElements();

  // Set up periodic checks for new elements to observe
  setInterval(observeMovieElements, 2000);
}

// Function to process elements that weren't processed during scrolling
function processUnprocessedElements() {
  const movieElements = document.querySelectorAll('div[class^="MovieIndexPoster-content"]');
  if (movieElements.length > 0) {
    checkForMovieItems(true); // Force processing
  }
}

// Function to check for movie items and extract IMDb IDs
function checkForMovieItems(force = false) {
  // Skip if not on a Radarr page
  if (!isRadarrPage) {
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
  if (!radarrApiRoot || !radarrApiKey) {
    injectRadarrApiScript();
    return;
  }

  // Otherwise fetch movies from Radarr API
  fetchMoviesFromRadarrAPI();
}

// Function to fetch movies from Radarr API
function fetchMoviesFromRadarrAPI() {
  const currentTime = Date.now();

  // Check if we have a valid cache
  if (movieCache && (currentTime - lastMovieCacheTime < MOVIE_CACHE_TTL)) {
    processMoviesFromAPI(movieCache);
    return;
  }

  fetch(`${radarrApiRoot}/movie?apikey=${radarrApiKey}`)
    .then(response => {
      if (!response.ok) {
        throw new Error('Radarr API request failed');
      }
      return response.json();
    })
    .then(movies => {
      // Update the cache
      movieCache = movies;
      lastMovieCacheTime = currentTime;

      processMoviesFromAPI(movies);
    });
}

// Process movies from Radarr API and match with DOM elements
function processMoviesFromAPI(movies) {
  // This selector needs to be adjusted based on Radarr's actual DOM structure
  const movieElements = document.querySelectorAll('div[class^="MovieIndexPoster-content"]');

  movieElements.forEach(element => {
    processMovieElement(element);
  });
}

// Function to process a single movie element
function processMovieElement(movieElement) {
  if (!movieCache) {
    return;
  }

  // Extract TMDB ID from the element
  const link = movieElement.querySelector('a[class^="MovieIndexPoster-link"]');
  if (!link || !link.href) return;

  const parts = link.href.split("/");
  const tmdbId = parts[parts.length - 1];

  if (!tmdbId) return;

  // Check if this element has already been processed for this specific movie
  const currentMovieId = movieElement.getAttribute('data-douban-tmdb-id');

  // If the element has been processed for this specific movie, no need to process again
  if (currentMovieId === tmdbId) {
    return;
  }

  // If the element has a rating display but for a different movie, remove it
  if (currentMovieId && currentMovieId !== tmdbId) {
    const existingRating = movieElement.querySelector('.douban-rating');
    if (existingRating) {
      existingRating.remove();
    }
  }

  // Find matching movie in our cache
  const movie = movieCache.find(m => m.tmdbId == tmdbId);

  if (movie && movie.imdbId) {
    // Store the current movie ID to detect changes
    movieElement.setAttribute('data-douban-tmdb-id', tmdbId);

    // Check if rating is already in cache
    if (ratingCache[tmdbId] !== undefined) {
      // Use cached rating and url
      const { rating, url } = ratingCache[tmdbId];
      displayDoubanRating(rating, url, movieElement);
    } else {
      // Fetch rating and then display it
      fetchDoubanRating(movie.imdbId, tmdbId)
        .then(({ rating, url }) => {
          displayDoubanRating(rating, url, movieElement);
        });
    }
  }
}

// Function to fetch Douban rating using the API
function fetchDoubanRating(imdbId, tmdbId) {
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
      ratingCache[tmdbId] = { rating, url };

      return { rating, url };
    });
}

// Function to display the Douban rating in the UI
function displayDoubanRating(ratingValue, url, movieElement) {
  // Remove any existing rating element first
  const existingRating = movieElement.querySelector('.douban-rating');
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
  if (getComputedStyle(movieElement).position === 'static') {
    movieElement.classList.add('movie-container');
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
  movieElement.appendChild(ratingElement);
}
