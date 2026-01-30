"""Tests for fipe_api_scraper.py - core scraper behaviors."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from datetime import datetime
import json


class TestParseMonthString:
    """Tests for _parse_month_string - Portuguese month parsing."""

    @pytest.fixture
    def scraper(self, mocker):
        """Create scraper with mocked dependencies."""
        mocker.patch.dict(
            "config.PROXY_CONFIG",
            {"enabled": False, "proxy_file": "proxies.txt", "max_consecutive_failures": 5},
        )
        mocker.patch("config.RESUME_CONFIG", {"enable_resume": False, "checkpoint_file": "test.json"})
        from fipe_api_scraper import FIPEAPIScraper
        return FIPEAPIScraper()

    def test_parses_dezembro_2024(self, scraper):
        """Should parse 'dezembro/2024' correctly."""
        result = scraper._parse_month_string("dezembro/2024")
        assert result.month == 12
        assert result.year == 2024

    def test_parses_janeiro_2020(self, scraper):
        """Should parse 'janeiro/2020' correctly."""
        result = scraper._parse_month_string("janeiro/2020")
        assert result.month == 1
        assert result.year == 2020

    def test_parses_marco_with_cedilla(self, scraper):
        """Should parse 'março/2023' (with ç) correctly."""
        result = scraper._parse_month_string("março/2023")
        assert result.month == 3
        assert result.year == 2023

    def test_handles_uppercase(self, scraper):
        """Should handle uppercase input."""
        result = scraper._parse_month_string("JUNHO/2022")
        assert result.month == 6
        assert result.year == 2022

    def test_handles_extra_whitespace(self, scraper):
        """Should handle extra whitespace."""
        result = scraper._parse_month_string("  abril / 2021  ")
        assert result.month == 4
        assert result.year == 2021

    def test_invalid_format_returns_now(self, scraper):
        """Invalid format should return current datetime."""
        result = scraper._parse_month_string("invalid")
        # Should be close to now (within same year at least)
        assert result.year == datetime.now().year


class TestCleanPrice:
    """Tests for _clean_price - Brazilian currency parsing."""

    @pytest.fixture
    def scraper(self, mocker):
        """Create scraper with mocked dependencies."""
        mocker.patch.dict(
            "config.PROXY_CONFIG",
            {"enabled": False, "proxy_file": "proxies.txt", "max_consecutive_failures": 5},
        )
        mocker.patch("config.RESUME_CONFIG", {"enable_resume": False, "checkpoint_file": "test.json"})
        from fipe_api_scraper import FIPEAPIScraper
        return FIPEAPIScraper()

    def test_parses_simple_price(self, scraper):
        """Should parse 'R$ 45.000,00' correctly."""
        result = scraper._clean_price("R$ 45.000,00")
        assert result == 45000.00

    def test_parses_price_without_cents(self, scraper):
        """Should parse 'R$ 100.000' correctly."""
        result = scraper._clean_price("R$ 100.000,00")
        assert result == 100000.00

    def test_parses_small_price(self, scraper):
        """Should parse 'R$ 5.500,50' correctly."""
        result = scraper._clean_price("R$ 5.500,50")
        assert result == 5500.50

    def test_handles_extra_whitespace(self, scraper):
        """Should handle extra whitespace."""
        result = scraper._clean_price("  R$  30.000,00  ")
        assert result == 30000.00


class TestFilterMonthsByDateRange:
    """Tests for _filter_months_by_date_range."""

    @pytest.fixture
    def scraper(self, mocker):
        """Create scraper with mocked dependencies."""
        mocker.patch.dict(
            "config.PROXY_CONFIG",
            {"enabled": False, "proxy_file": "proxies.txt", "max_consecutive_failures": 5},
        )
        mocker.patch("config.RESUME_CONFIG", {"enable_resume": False, "checkpoint_file": "test.json"})
        from fipe_api_scraper import FIPEAPIScraper
        return FIPEAPIScraper()

    def test_filters_within_range(self, scraper, mocker):
        """Should keep months within date range."""
        mocker.patch.dict(
            "config.DATE_RANGE",
            {"start_date": "2024-01", "end_date": "2024-03"},
        )

        months = [
            {"Mes": "dezembro/2023", "Codigo": 311},
            {"Mes": "janeiro/2024", "Codigo": 312},
            {"Mes": "fevereiro/2024", "Codigo": 313},
            {"Mes": "março/2024", "Codigo": 314},
            {"Mes": "abril/2024", "Codigo": 315},
        ]

        result = scraper._filter_months_by_date_range(months)

        assert len(result) == 3
        assert result[0]["Codigo"] == 312  # janeiro
        assert result[1]["Codigo"] == 313  # fevereiro
        assert result[2]["Codigo"] == 314  # março

    def test_returns_all_when_no_range_specified(self, scraper, mocker):
        """Should return all months when no date range."""
        mocker.patch.dict(
            "config.DATE_RANGE",
            {"start_date": None, "end_date": None},
        )

        months = [
            {"Mes": "janeiro/2024", "Codigo": 312},
            {"Mes": "fevereiro/2024", "Codigo": 313},
        ]

        result = scraper._filter_months_by_date_range(months)
        assert len(result) == 2

    def test_returns_all_on_invalid_date_format(self, scraper, mocker):
        """Should return all months on invalid date format."""
        mocker.patch.dict(
            "config.DATE_RANGE",
            {"start_date": "invalid", "end_date": "also-invalid"},
        )

        months = [
            {"Mes": "janeiro/2024", "Codigo": 312},
            {"Mes": "fevereiro/2024", "Codigo": 313},
        ]

        result = scraper._filter_months_by_date_range(months)
        assert len(result) == 2


class TestLoadCheckpoint:
    """Tests for _load_checkpoint."""

    def test_loads_existing_checkpoint(self, mocker, tmp_path):
        """Should load checkpoint data from file."""
        checkpoint_file = tmp_path / "checkpoint.json"
        checkpoint_data = {"312_59_123": True, "312_59_124": True}
        checkpoint_file.write_text(json.dumps(checkpoint_data))

        mocker.patch.dict(
            "config.PROXY_CONFIG",
            {"enabled": False, "proxy_file": "proxies.txt", "max_consecutive_failures": 5},
        )
        mocker.patch("config.RESUME_CONFIG", {
            "enable_resume": True,
            "checkpoint_file": str(checkpoint_file)
        })

        from fipe_api_scraper import FIPEAPIScraper
        scraper = FIPEAPIScraper()

        assert scraper.checkpoint == checkpoint_data

    def test_returns_empty_when_file_not_found(self, mocker):
        """Should return empty dict when checkpoint file doesn't exist."""
        mocker.patch.dict(
            "config.PROXY_CONFIG",
            {"enabled": False, "proxy_file": "proxies.txt", "max_consecutive_failures": 5},
        )
        mocker.patch("config.RESUME_CONFIG", {
            "enable_resume": True,
            "checkpoint_file": "/nonexistent/checkpoint.json"
        })

        from fipe_api_scraper import FIPEAPIScraper
        scraper = FIPEAPIScraper()

        assert scraper.checkpoint == {}

    def test_returns_empty_when_resume_disabled(self, mocker):
        """Should return empty dict when resume is disabled."""
        mocker.patch.dict(
            "config.PROXY_CONFIG",
            {"enabled": False, "proxy_file": "proxies.txt", "max_consecutive_failures": 5},
        )
        mocker.patch("config.RESUME_CONFIG", {
            "enable_resume": False,
            "checkpoint_file": "checkpoint.json"
        })

        from fipe_api_scraper import FIPEAPIScraper
        scraper = FIPEAPIScraper()

        assert scraper.checkpoint == {}


class TestScraperInitialization:
    """Tests for FIPEAPIScraper initialization."""

    def test_initializes_stats(self, mocker):
        """Should initialize statistics dict."""
        mocker.patch.dict(
            "config.PROXY_CONFIG",
            {"enabled": False, "proxy_file": "proxies.txt", "max_consecutive_failures": 5},
        )
        mocker.patch("config.RESUME_CONFIG", {"enable_resume": False, "checkpoint_file": "test.json"})

        from fipe_api_scraper import FIPEAPIScraper
        scraper = FIPEAPIScraper()

        assert scraper.stats["total_requests"] == 0
        assert scraper.stats["successful_requests"] == 0
        assert scraper.stats["failed_requests"] == 0
        assert scraper.stats["rate_limit_hits"] == 0
        assert scraper.stats["retries"] == 0
        assert scraper.stats["prices_saved"] == 0

    def test_initializes_adaptive_rate_limiting(self, mocker):
        """Should initialize adaptive rate limiting values."""
        mocker.patch.dict(
            "config.PROXY_CONFIG",
            {"enabled": False, "proxy_file": "proxies.txt", "max_consecutive_failures": 5},
        )
        mocker.patch("config.RESUME_CONFIG", {"enable_resume": False, "checkpoint_file": "test.json"})

        from fipe_api_scraper import FIPEAPIScraper
        scraper = FIPEAPIScraper()

        assert scraper.adaptive_delay == 0.5
        assert scraper.min_delay == 0.4
        assert scraper.max_delay == 2.0
        assert scraper.consecutive_successes == 0
        assert scraper.recent_520_errors == 0
        assert scraper.recent_429_errors == 0

    def test_initializes_batch_buffer(self, mocker):
        """Should initialize empty batch buffer."""
        mocker.patch.dict(
            "config.PROXY_CONFIG",
            {"enabled": False, "proxy_file": "proxies.txt", "max_consecutive_failures": 5},
        )
        mocker.patch("config.RESUME_CONFIG", {"enable_resume": False, "checkpoint_file": "test.json"})

        from fipe_api_scraper import FIPEAPIScraper
        scraper = FIPEAPIScraper()

        assert scraper.db_batch == []
        assert scraper.batch_size == 100

    def test_respects_max_concurrent_requests(self, mocker):
        """Should set semaphore based on max_concurrent_requests."""
        mocker.patch.dict(
            "config.PROXY_CONFIG",
            {"enabled": False, "proxy_file": "proxies.txt", "max_consecutive_failures": 5},
        )
        mocker.patch("config.RESUME_CONFIG", {"enable_resume": False, "checkpoint_file": "test.json"})

        from fipe_api_scraper import FIPEAPIScraper
        scraper = FIPEAPIScraper(max_concurrent_requests=5)

        assert scraper.max_concurrent_requests == 5


class TestHandleResponseBehavior:
    """Tests for _handle_response adaptive behavior."""

    @pytest.fixture
    def scraper(self, mocker):
        """Create scraper with mocked dependencies."""
        mocker.patch.dict(
            "config.PROXY_CONFIG",
            {"enabled": False, "proxy_file": "proxies.txt", "max_consecutive_failures": 5},
        )
        mocker.patch("config.RESUME_CONFIG", {"enable_resume": False, "checkpoint_file": "test.json"})
        from fipe_api_scraper import FIPEAPIScraper
        return FIPEAPIScraper()

    @pytest.mark.asyncio
    async def test_200_increments_successful_requests(self, scraper):
        """200 response should increment successful_requests."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": "test"})

        initial_count = scraper.stats["successful_requests"]
        await scraper._handle_response(mock_response, None, "test")

        assert scraper.stats["successful_requests"] == initial_count + 1

    @pytest.mark.asyncio
    async def test_200_increments_consecutive_successes(self, scraper):
        """200 response should increment consecutive_successes."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": "test"})

        initial_count = scraper.consecutive_successes
        await scraper._handle_response(mock_response, None, "test")

        assert scraper.consecutive_successes == initial_count + 1

    @pytest.mark.asyncio
    async def test_429_increments_rate_limit_hits(self, scraper):
        """429 response should increment rate_limit_hits."""
        mock_response = AsyncMock()
        mock_response.status = 429

        initial_count = scraper.stats["rate_limit_hits"]
        await scraper._handle_response(mock_response, None, "test")

        assert scraper.stats["rate_limit_hits"] == initial_count + 1

    @pytest.mark.asyncio
    async def test_429_resets_consecutive_successes(self, scraper):
        """429 response should reset consecutive_successes to 0."""
        mock_response = AsyncMock()
        mock_response.status = 429

        scraper.consecutive_successes = 10
        await scraper._handle_response(mock_response, None, "test")

        assert scraper.consecutive_successes == 0

    @pytest.mark.asyncio
    async def test_520_increments_520_error_count(self, scraper):
        """520 response should increment recent_520_errors."""
        mock_response = AsyncMock()
        mock_response.status = 520

        initial_count = scraper.recent_520_errors
        await scraper._handle_response(mock_response, None, "test")

        assert scraper.recent_520_errors == initial_count + 1

    @pytest.mark.asyncio
    async def test_520_resets_consecutive_successes(self, scraper):
        """520 response should reset consecutive_successes to 0."""
        mock_response = AsyncMock()
        mock_response.status = 520

        scraper.consecutive_successes = 10
        await scraper._handle_response(mock_response, None, "test")

        assert scraper.consecutive_successes == 0

    @pytest.mark.asyncio
    async def test_other_status_increments_failed_requests(self, scraper):
        """Non-200/429/520 status should increment failed_requests."""
        mock_response = AsyncMock()
        mock_response.status = 500

        initial_count = scraper.stats["failed_requests"]
        await scraper._handle_response(mock_response, None, "test")

        assert scraper.stats["failed_requests"] == initial_count + 1

    @pytest.mark.asyncio
    async def test_200_returns_json_data(self, scraper):
        """200 response should return parsed JSON."""
        mock_response = AsyncMock()
        mock_response.status = 200
        expected_data = {"Modelos": [{"Label": "Gol", "Value": 123}]}
        mock_response.json = AsyncMock(return_value=expected_data)

        result = await scraper._handle_response(mock_response, None, "test")

        assert result == expected_data

    @pytest.mark.asyncio
    async def test_429_returns_none(self, scraper):
        """429 response should return None."""
        mock_response = AsyncMock()
        mock_response.status = 429

        result = await scraper._handle_response(mock_response, None, "test")

        assert result is None

    @pytest.mark.asyncio
    async def test_520_returns_none(self, scraper):
        """520 response should return None."""
        mock_response = AsyncMock()
        mock_response.status = 520

        result = await scraper._handle_response(mock_response, None, "test")

        assert result is None


class TestAdaptiveDelayAdjustment:
    """Tests for adaptive delay behavior."""

    @pytest.fixture
    def scraper(self, mocker):
        """Create scraper with mocked dependencies."""
        mocker.patch.dict(
            "config.PROXY_CONFIG",
            {"enabled": False, "proxy_file": "proxies.txt", "max_consecutive_failures": 5},
        )
        mocker.patch("config.RESUME_CONFIG", {"enable_resume": False, "checkpoint_file": "test.json"})
        from fipe_api_scraper import FIPEAPIScraper
        return FIPEAPIScraper()

    @pytest.mark.asyncio
    async def test_delay_increases_after_multiple_429s(self, scraper):
        """Delay should increase after rate_limit_threshold 429 errors."""
        mock_response = AsyncMock()
        mock_response.status = 429

        initial_delay = scraper.adaptive_delay
        scraper.rate_limit_threshold = 3

        # Trigger threshold number of 429s
        for _ in range(3):
            await scraper._handle_response(mock_response, None, "test")

        assert scraper.adaptive_delay > initial_delay

    @pytest.mark.asyncio
    async def test_delay_increases_after_multiple_520s(self, scraper):
        """Delay should increase after error_threshold 520 errors."""
        mock_response = AsyncMock()
        mock_response.status = 520

        initial_delay = scraper.adaptive_delay
        scraper.error_threshold = 3

        # Trigger threshold number of 520s
        for _ in range(3):
            await scraper._handle_response(mock_response, None, "test")

        assert scraper.adaptive_delay > initial_delay

    @pytest.mark.asyncio
    async def test_delay_capped_at_max(self, scraper):
        """Delay should not exceed max_delay."""
        mock_response = AsyncMock()
        mock_response.status = 429

        scraper.rate_limit_threshold = 1
        scraper.adaptive_delay = 1.9  # Close to max

        # Keep triggering rate limits
        for _ in range(10):
            await scraper._handle_response(mock_response, None, "test")

        assert scraper.adaptive_delay <= scraper.max_delay

    @pytest.mark.asyncio
    async def test_delay_decreases_after_many_successes(self, scraper):
        """Delay should decrease after speedup_threshold successes."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": "test"})

        # Set delay above minimum so it can decrease
        scraper.adaptive_delay = 0.6
        initial_delay = scraper.adaptive_delay
        scraper.speedup_threshold = 3

        # Trigger enough successes to speed up
        for _ in range(4):
            await scraper._handle_response(mock_response, None, "test")

        assert scraper.adaptive_delay < initial_delay

    @pytest.mark.asyncio
    async def test_delay_not_below_minimum(self, scraper):
        """Delay should not go below min_delay."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": "test"})

        scraper.speedup_threshold = 1
        scraper.adaptive_delay = scraper.min_delay + 0.01

        # Keep succeeding
        for _ in range(100):
            await scraper._handle_response(mock_response, None, "test")

        assert scraper.adaptive_delay >= scraper.min_delay
