// Content script that runs on Radarr pages

// Default API URL - this can be overridden in options
let apiBaseUrl = 'http://localhost:8000';
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
// Add a rating cache to avoid redundant API requests
let ratingCache = {}; // Maps TMDB IDs to {rating, url} objects
// Add movie cache to avoid redundant Radarr API requests
let movieCache = null;
let lastMovieCacheTime = 0;
const MOVIE_CACHE_TTL = 5 * 60 * 1000; // 5 minutes cache validity

// First, get the API settings from storage
chrome.storage.sync.get([
  'apiBaseUrl',
  'radarrApiRoot',
  'radarrApiKey',
  'goodRatingThreshold',
  'mediumRatingThreshold',
  'goodRatingColor',
  'mediumRatingColor',
  'lowRatingColor',
  'noRatingColor'
], function(data) {
  if (data.apiBaseUrl) {
    apiBaseUrl = data.apiBaseUrl;
  }

  if (data.radarrApiRoot) {
    radarrApiRoot = data.radarrApiRoot;
  }

  if (data.radarrApiKey) {
    radarrApiKey = data.radarrApiKey;
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
}

// Function to check for movie items and extract IMDb IDs
function checkForMovieItems() {
  // Check if 0.5 seconds have passed since the last call
  const currentTime = Date.now();
  if (currentTime - lastCheckTime < 500) {
    // Not enough time has passed, exit early
    return;
  }

  // Update the last check time
  lastCheckTime = currentTime;

  // Check if we have the necessary Radarr API settings
  if (radarrApiRoot && radarrApiKey) {
    fetchMoviesFromRadarrAPI();
  }
}

// Function to fetch movies from Radarr API
function fetchMoviesFromRadarrAPI() {
  const currentTime = Date.now();

  // Check if we have a valid cache
  if (movieCache && (currentTime - lastMovieCacheTime < MOVIE_CACHE_TTL)) {
    console.log('Using cached movie data from Radarr API');
    processMoviesFromAPI(movieCache);
    return;
  }

  console.log('Fetching fresh movie data from Radarr API');
  fetch(`${radarrApiRoot}/api/v3/movie?apikey=${radarrApiKey}`)
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

  movies.forEach(movie => {
    // Look for IMDb ID in movie data
    if (movie.imdbId) {
      const imdbId = movie.imdbId;
      const tmdbId = movie.tmdbId;

      // Find the corresponding DOM element for this movie
      const movieElement = findMovieElementById(movieElements, tmdbId);

      if (movieElement && movieElement.getAttribute('douban-processed') !== 'true') {
        // Mark as processed
        movieElement.setAttribute('douban-processed', 'true');

        // Check if rating is already in cache
        if (ratingCache[tmdbId] !== undefined) {
          // Use cached rating and url
          const { rating, url } = ratingCache[tmdbId];
          displayDoubanRating(rating, url, movieElement);
        } else {
          // Fetch rating and then display it
          fetchDoubanRating(imdbId, tmdbId)
            .then(({ rating, url }) => {
              displayDoubanRating(rating, url, movieElement);
            });
        }
      }
    }
  });
}

// Helper function to find movie element by ID
function findMovieElementById(movieElements, tmdbId) {
  for (const element of movieElements) {
    url = element.querySelector('a[class^="MovieIndexPoster-link"]')["href"];
    parts = url.split("/");
    elementMovieId = parts[parts.length - 1];
    if (elementMovieId && elementMovieId == tmdbId) {
      return element;
    }
  }
  return null;
}

// Function to fetch Douban rating using the API
function fetchDoubanRating(imdbId, tmdbId) {
  return fetch(`${apiBaseUrl}/api/item?imdb_id=${imdbId}`)
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
  // Create base element - use an anchor if we have a URL, otherwise a div
  const ratingElement = document.createElement(url ? 'a' : 'div');
  ratingElement.className = 'douban-rating';

  // If we have a URL, set anchor-specific properties
  if (url) {
    ratingElement.href = url;
    ratingElement.target = '_blank'; // Open in new tab
    ratingElement.title = 'Click to view on Douban';
  }

  // Ensure parent element has position relative for absolute positioning to work
  if (getComputedStyle(movieElement).position === 'static') {
    movieElement.classList.add('movie-container');
  }

  // Determine color based on rating value and thresholds
  let ratingClass = 'low';
  let ratingColor = lowRatingColor;

  // Handle no rating case
  if (!ratingValue || ratingValue === '?') {
    ratingClass = 'none';
    ratingColor = noRatingColor;
    ratingValue = '?';
  } else {
    // Convert ratingValue to a number for comparison
    const numericRating = parseFloat(ratingValue);

    if (numericRating >= goodRatingThreshold) {
      ratingClass = 'good';
      ratingColor = goodRatingColor;
    } else if (numericRating >= mediumRatingThreshold) {
      ratingClass = 'medium';
      ratingColor = mediumRatingColor;
    }
  }

  // Create rating content
  let ratingHtml = `
    <div class="douban-score">
      <span class="douban-logo douban-logo-${ratingClass}" style="background-color: ${ratingColor}">豆</span>
      <span class="douban-value douban-value-${ratingClass}" style="color: ${ratingColor}">${ratingValue}</span>
    </div>
  `;

  ratingElement.innerHTML = ratingHtml;
  movieElement.appendChild(ratingElement);
}
