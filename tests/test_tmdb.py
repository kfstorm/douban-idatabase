import pytest
from app.info_provider.tmdb import get_imdb_id_from_tmdb_id, get_imdb_id_from_tvdb_id
from app.config import settings


@pytest.mark.skipif(
    not settings.TMDB_API_KEY, reason="TMDB_API_KEY not configured in environment"
)
class TestTMDB:
    """Tests for the TMDB API wrapper functions.

    These tests make real API calls to TMDB, so they require a valid API key.
    Skip these tests if TMDB_API_KEY is not configured.
    """

    def test_get_imdb_id_from_tmdb_id_movie(self):
        """Test getting IMDB ID from a TMDB movie ID."""
        # The Shawshank Redemption TMDB ID
        tmdb_id = "278"
        media_type = "movie"

        imdb_id = get_imdb_id_from_tmdb_id(tmdb_id, media_type)

        assert imdb_id == "tt0111161"  # The Shawshank Redemption IMDb ID

    def test_get_imdb_id_from_tmdb_id_tv(self):
        """Test getting IMDB ID from a TMDB TV series ID."""
        # Breaking Bad TMDB ID
        tmdb_id = "1396"
        media_type = "tv"

        imdb_id = get_imdb_id_from_tmdb_id(tmdb_id, media_type)

        assert imdb_id == "tt0903747"  # Breaking Bad IMDb ID

    def test_get_imdb_id_from_tmdb_id_invalid_media_type(self):
        """Test getting IMDB ID with an invalid media type."""
        tmdb_id = "278"
        media_type = "invalid"

        with pytest.raises(ValueError, match="media_type must be 'movie' or 'tv'"):
            get_imdb_id_from_tmdb_id(tmdb_id, media_type)

    def test_get_imdb_id_from_tmdb_id_nonexistent(self):
        """Test getting IMDB ID from a nonexistent TMDB ID."""
        tmdb_id = "99999999999"  # Assuming this ID doesn't exist
        media_type = "movie"

        imdb_id = get_imdb_id_from_tmdb_id(tmdb_id, media_type)

        assert imdb_id is None

    def test_get_imdb_id_from_tvdb_id(self):
        """Test getting IMDB ID from a TVDB ID."""
        # Breaking Bad TVDB ID
        tvdb_id = "81189"

        imdb_id = get_imdb_id_from_tvdb_id(tvdb_id)

        assert imdb_id == "tt0903747"  # Breaking Bad IMDb ID

    def test_get_imdb_id_from_tvdb_id_nonexistent(self):
        """Test getting IMDB ID from a nonexistent TVDB ID."""
        tvdb_id = "99999999999"  # Assuming this ID doesn't exist

        imdb_id = get_imdb_id_from_tvdb_id(tvdb_id)

        assert imdb_id is None

    def test_edge_cases(self):
        """Test various edge cases and error handling."""
        # Test with empty TMDB ID
        with pytest.raises(ValueError):
            get_imdb_id_from_tmdb_id("", "movie")

        # Test with None TMDB ID
        with pytest.raises(ValueError):
            get_imdb_id_from_tmdb_id(None, "movie")

        # Test with empty media type
        with pytest.raises(ValueError):
            get_imdb_id_from_tmdb_id("278", "")

        # Test with None media type
        with pytest.raises(ValueError):
            get_imdb_id_from_tmdb_id("278", None)

        # Test with empty TVDB ID
        with pytest.raises(ValueError):
            get_imdb_id_from_tvdb_id("")

        # Test with None TVDB ID
        with pytest.raises(ValueError):
            get_imdb_id_from_tvdb_id(None)
