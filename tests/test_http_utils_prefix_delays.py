import pytest
from unittest.mock import patch
from app.http_utils import Throttler


@pytest.fixture
def throttler():
    """Create a fresh throttler instance for testing."""
    return Throttler()


@pytest.fixture
def sample_delay_config():
    """Sample configuration for testing prefix-based delays."""
    return {
        "https://movie.douban.com/subject/": {"min": 2.0, "max": 5.0},
        "https://movie.douban.com/j/": {"min": 0.5, "max": 1.0},
        "https://movie.douban.com/": {"min": 1.0, "max": 2.0},
        "https://api.themoviedb.org/3/": {"min": 0.1, "max": 0.3},
        "https://api.themoviedb.org/": {"min": 0.2, "max": 0.4},
        "https://": {"min": 0.5, "max": 1.5},  # Catch-all
    }


class TestPrefixMatching:
    """Test core prefix matching logic."""

    def test_exact_prefix_match(self, throttler, sample_delay_config):
        """Test URL matches exact configured prefix."""
        with patch("app.http_utils.settings.REQUEST_DELAY_CONFIG", sample_delay_config):
            url = "https://movie.douban.com/subject/123456"
            min_delay, max_delay = throttler._get_delay_for_url(url)
            assert min_delay == 2.0
            assert max_delay == 5.0

    def test_longest_prefix_wins(self, throttler, sample_delay_config):
        """Test longest matching prefix takes precedence."""
        with patch("app.http_utils.settings.REQUEST_DELAY_CONFIG", sample_delay_config):
            url = "https://api.themoviedb.org/3/movie/123"
            min_delay, max_delay = throttler._get_delay_for_url(url)
            assert (
                min_delay == 0.1
            )  # Should match "/3/" not just "/api.themoviedb.org/"
            assert max_delay == 0.3

    def test_shorter_prefix_when_longer_doesnt_match(
        self, throttler, sample_delay_config
    ):
        """Test falls back to shorter prefix when longer doesn't match."""
        with patch("app.http_utils.settings.REQUEST_DELAY_CONFIG", sample_delay_config):
            url = "https://api.themoviedb.org/v4/movie/123"  # No /3/ prefix
            min_delay, max_delay = throttler._get_delay_for_url(url)
            assert min_delay == 0.2  # Should match "/api.themoviedb.org/"
            assert max_delay == 0.4

    def test_catch_all_prefix_match(self, throttler, sample_delay_config):
        """Test catch-all prefix works for unmatched URLs."""
        with patch("app.http_utils.settings.REQUEST_DELAY_CONFIG", sample_delay_config):
            url = "https://unknown-site.com/path"
            min_delay, max_delay = throttler._get_delay_for_url(url)
            assert min_delay == 0.5  # Should match "https://" catch-all
            assert max_delay == 1.5


class TestDelayApplication:
    """Test delay range application."""

    @patch("app.http_utils.time.sleep")
    @patch("app.http_utils.random.uniform")
    def test_correct_delay_applied_for_prefix(
        self, mock_uniform, mock_sleep, throttler, sample_delay_config
    ):
        """Test correct delay range is used for matched prefix."""
        with patch("app.http_utils.settings.REQUEST_DELAY_CONFIG", sample_delay_config):
            mock_uniform.return_value = 3.5
            url = "https://movie.douban.com/subject/123"

            throttler._check_rate_limit(url)

            mock_uniform.assert_called_once_with(2.0, 5.0)  # subject prefix range
            mock_sleep.assert_called_once_with(3.5)

    @patch("app.http_utils.time.sleep")
    @patch("app.http_utils.random.uniform")
    def test_different_delays_for_different_prefixes(
        self, mock_uniform, mock_sleep, throttler, sample_delay_config
    ):
        """Test different prefixes get different delay ranges."""
        with patch("app.http_utils.settings.REQUEST_DELAY_CONFIG", sample_delay_config):
            mock_uniform.return_value = 0.8

            # First call - JSON API prefix
            url1 = "https://movie.douban.com/j/search"
            throttler._check_rate_limit(url1)
            mock_uniform.assert_called_with(0.5, 1.0)

            mock_uniform.reset_mock()
            mock_uniform.return_value = 2.5

            # Second call - subject prefix
            url2 = "https://movie.douban.com/subject/123"
            throttler._check_rate_limit(url2)
            mock_uniform.assert_called_with(2.0, 5.0)


class TestConfigurationValidation:
    """Test configuration validation and parsing."""

    def test_valid_config_structure(self, throttler):
        """Test valid configuration is parsed correctly."""
        config = {
            "https://example.com/api/": {"min": 1.0, "max": 2.0},
            "https://example.com/": {"min": 0.5, "max": 1.0},
        }

        with patch("app.http_utils.settings.REQUEST_DELAY_CONFIG", config):
            min_delay, max_delay = throttler._get_delay_for_url(
                "https://example.com/api/v1"
            )
            assert min_delay == 1.0
            assert max_delay == 2.0

    def test_zero_min_delay_valid(self, throttler):
        """Test zero minimum delay is valid."""
        config = {"https://fast-api.com/": {"min": 0.0, "max": 0.5}}

        with patch("app.http_utils.settings.REQUEST_DELAY_CONFIG", config):
            min_delay, max_delay = throttler._get_delay_for_url(
                "https://fast-api.com/endpoint"
            )
            assert min_delay == 0.0
            assert max_delay == 0.5

    def test_equal_min_max_delay(self, throttler):
        """Test min and max delay can be equal (fixed delay)."""
        config = {"https://fixed-delay.com/": {"min": 1.0, "max": 1.0}}

        with patch("app.http_utils.settings.REQUEST_DELAY_CONFIG", config):
            min_delay, max_delay = throttler._get_delay_for_url(
                "https://fixed-delay.com/test"
            )
            assert min_delay == 1.0
            assert max_delay == 1.0


class TestFallbackBehavior:
    """Test fallback to global settings."""

    @patch("app.http_utils.settings.REQUEST_DELAY_CONFIG", None)
    @patch("app.http_utils.settings.REQUEST_DELAY_MAX_SECONDS", 3.0)
    def test_no_config_uses_global_default(self, throttler):
        """Test fallback to global setting when no config provided."""
        min_delay, max_delay = throttler._get_delay_for_url("https://any-url.com")
        assert min_delay == 0
        assert max_delay == 3.0

    @patch("app.http_utils.settings.REQUEST_DELAY_CONFIG", {})
    @patch("app.http_utils.settings.REQUEST_DELAY_MAX_SECONDS", 2.5)
    def test_empty_config_uses_global_default(self, throttler):
        """Test fallback to global setting when config is empty."""
        min_delay, max_delay = throttler._get_delay_for_url("https://any-url.com")
        assert min_delay == 0
        assert max_delay == 2.5

    def test_no_matching_prefix_uses_global_default(
        self, throttler, sample_delay_config
    ):
        """Test fallback when URL doesn't match any configured prefix."""
        with (
            patch("app.http_utils.settings.REQUEST_DELAY_CONFIG", sample_delay_config),
            patch("app.http_utils.settings.REQUEST_DELAY_MAX_SECONDS", 4.0),
        ):
            # URL doesn't start with any configured prefix
            min_delay, max_delay = throttler._get_delay_for_url(
                "ftp://file-server.com/file"
            )
            assert min_delay == 0
            assert max_delay == 4.0


class TestURLVariations:
    """Test various URL formats and edge cases."""

    @pytest.mark.parametrize(
        "url,expected_min,expected_max",
        [
            ("https://movie.douban.com/subject/123456", 2.0, 5.0),
            ("https://movie.douban.com/subject/123456?param=value", 2.0, 5.0),
            ("https://movie.douban.com/subject/123456#fragment", 2.0, 5.0),
            ("https://movie.douban.com/j/search_subjects", 0.5, 1.0),
            ("https://movie.douban.com/j/search?q=test", 0.5, 1.0),
            (
                "https://movie.douban.com/people/user123",
                1.0,
                2.0,
            ),  # Falls back to broader prefix
            ("https://api.themoviedb.org/3/movie/123", 0.1, 0.3),
            (
                "https://api.themoviedb.org/4/list/456",
                0.2,
                0.4,
            ),  # Falls back to broader prefix
        ],
    )
    def test_url_variations_match_correct_prefix(
        self, throttler, sample_delay_config, url, expected_min, expected_max
    ):
        """Test various URL formats match expected prefixes."""
        with patch("app.http_utils.settings.REQUEST_DELAY_CONFIG", sample_delay_config):
            min_delay, max_delay = throttler._get_delay_for_url(url)
            assert min_delay == expected_min
            assert max_delay == expected_max

    def test_case_sensitive_prefix_matching(self, throttler):
        """Test prefix matching is case-sensitive."""
        config = {"https://Api.Example.com/": {"min": 1.0, "max": 2.0}}

        with (
            patch("app.http_utils.settings.REQUEST_DELAY_CONFIG", config),
            patch("app.http_utils.settings.REQUEST_DELAY_MAX_SECONDS", 3.0),
        ):
            # Should not match due to case difference
            min_delay, max_delay = throttler._get_delay_for_url(
                "https://api.example.com/test"
            )
            assert min_delay == 0  # Falls back to global
            assert max_delay == 3.0


class TestMultiplePrefixPriority:
    """Test prefix priority and specificity."""

    def test_most_specific_prefix_wins(self, throttler):
        """Test more specific prefix takes precedence over general ones."""
        config = {
            "https://api.site.com/v1/users/": {"min": 3.0, "max": 6.0},
            "https://api.site.com/v1/": {"min": 2.0, "max": 4.0},
            "https://api.site.com/": {"min": 1.0, "max": 2.0},
            "https://": {"min": 0.5, "max": 1.0},
        }

        with patch("app.http_utils.settings.REQUEST_DELAY_CONFIG", config):
            url = "https://api.site.com/v1/users/123"
            min_delay, max_delay = throttler._get_delay_for_url(url)
            assert min_delay == 3.0  # Most specific prefix wins
            assert max_delay == 6.0

    def test_prefix_priority_order(self, throttler):
        """Test different URLs match their most specific prefixes."""
        config = {
            "https://api.site.com/v1/users/": {"min": 3.0, "max": 6.0},
            "https://api.site.com/v1/": {"min": 2.0, "max": 4.0},
            "https://api.site.com/": {"min": 1.0, "max": 2.0},
        }

        test_cases = [
            ("https://api.site.com/v1/users/123", 3.0, 6.0),
            ("https://api.site.com/v1/posts/456", 2.0, 4.0),
            ("https://api.site.com/health", 1.0, 2.0),
        ]

        with patch("app.http_utils.settings.REQUEST_DELAY_CONFIG", config):
            for url, expected_min, expected_max in test_cases:
                min_delay, max_delay = throttler._get_delay_for_url(url)
                assert min_delay == expected_min, f"URL {url} min_delay mismatch"
                assert max_delay == expected_max, f"URL {url} max_delay mismatch"


class TestExcludedHosts:
    """Test that excluded hosts still work with new URL-based logic."""

    @patch("app.http_utils.CHECK_RATE_LIMIT_EXCLUDED_HOSTS", ["api.themoviedb.org"])
    @patch("app.http_utils.time.sleep")
    def test_excluded_hosts_skip_delay(
        self, mock_sleep, throttler, sample_delay_config
    ):
        """Test that excluded hosts skip delay regardless of URL prefix config."""
        with patch("app.http_utils.settings.REQUEST_DELAY_CONFIG", sample_delay_config):
            url = "https://api.themoviedb.org/3/movie/123"  # Would normally get 0.1-0.3 delay

            throttler._check_rate_limit(url)

            mock_sleep.assert_not_called()  # Should not sleep for excluded hosts
