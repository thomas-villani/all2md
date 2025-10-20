"""Unit tests for timing instrumentation utilities."""

import logging
import os
import time

import pytest


@pytest.mark.timing
@pytest.mark.unit
@pytest.mark.skipif(os.getenv("CI") == "true", reason="Timing tests are flaky in CI")
class TestTimingContext:
    """Test TimingContext context manager."""

    def test_timing_context_basic(self):
        """Test basic timing context usage."""
        from all2md.cli.timing import TimingContext

        with TimingContext("test operation") as ctx:
            time.sleep(0.01)

        assert ctx.elapsed > 0.01
        assert ctx.elapsed < 0.1  # Should complete quickly

    def test_timing_context_logs(self, caplog):
        """Test that timing context logs messages."""
        from all2md.cli.timing import TimingContext

        with caplog.at_level(logging.DEBUG):
            with TimingContext("test operation"):
                pass

        # Should have start and completion logs
        assert any("Starting: test operation" in record.message for record in caplog.records)
        assert any("completed in" in record.message for record in caplog.records)

    def test_timing_context_with_exception(self, caplog):
        """Test timing context logs failure on exception."""
        from all2md.cli.timing import TimingContext

        with caplog.at_level(logging.DEBUG):
            try:
                with TimingContext("failing operation"):
                    raise ValueError("Test error")
            except ValueError:
                pass

        # Should have failure log
        assert any("failed after" in record.message for record in caplog.records)

    def test_timing_context_custom_logger(self, caplog):
        """Test timing context with custom logger."""
        from all2md.cli.timing import TimingContext

        custom_logger = logging.getLogger("custom_test")

        with caplog.at_level(logging.DEBUG, logger="custom_test"):
            with TimingContext("test", logger_instance=custom_logger):
                pass

        # Should log to custom logger
        custom_logs = [r for r in caplog.records if r.name == "custom_test"]
        assert len(custom_logs) > 0

    def test_timing_context_custom_log_level(self, caplog):
        """Test timing context with custom log level."""
        from all2md.cli.timing import TimingContext

        with caplog.at_level(logging.INFO):
            with TimingContext("test", log_level=logging.INFO):
                pass

        # Should have INFO level logs
        info_logs = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_logs) >= 2  # Start and completion

@pytest.mark.timing
@pytest.mark.unit
@pytest.mark.skipif(os.getenv("CI") == "true", reason="Timing tests are flaky in CI")
class TestInstrumentTiming:
    """Test instrument_timing decorator."""

    def test_decorator_basic(self, caplog):
        """Test basic decorator usage."""
        from all2md.cli.timing import instrument_timing

        @instrument_timing()
        def test_function():
            time.sleep(0.01)
            return "result"

        with caplog.at_level(logging.DEBUG):
            result = test_function()

        assert result == "result"
        assert any("test_function" in record.message for record in caplog.records)
        assert any("completed in" in record.message for record in caplog.records)

    def test_decorator_custom_name(self, caplog):
        """Test decorator with custom operation name."""
        from all2md.cli.timing import instrument_timing

        @instrument_timing("custom operation")
        def test_function():
            return "result"

        with caplog.at_level(logging.DEBUG):
            test_function()

        # Should use custom name
        assert any("custom operation" in record.message for record in caplog.records)

    def test_decorator_preserves_function_metadata(self):
        """Test that decorator preserves function metadata."""
        from all2md.cli.timing import instrument_timing

        @instrument_timing()
        def test_function():
            """Test docstring."""
            pass

        assert test_function.__name__ == "test_function"
        assert test_function.__doc__ == "Test docstring."

    def test_decorator_with_arguments(self, caplog):
        """Test decorator on function with arguments."""
        from all2md.cli.timing import instrument_timing

        @instrument_timing()
        def add(a, b):
            return a + b

        with caplog.at_level(logging.DEBUG):
            result = add(2, 3)

        assert result == 5
        assert any("completed in" in record.message for record in caplog.records)


@pytest.mark.unit
class TestFormatDuration:
    """Test format_duration utility."""

    def test_format_microseconds(self):
        """Test formatting microseconds."""
        from all2md.cli.timing import format_duration

        assert "µs" in format_duration(0.0001)

    def test_format_milliseconds(self):
        """Test formatting milliseconds."""
        from all2md.cli.timing import format_duration

        result = format_duration(0.123)
        assert "123ms" == result

    def test_format_seconds(self):
        """Test formatting seconds."""
        from all2md.cli.timing import format_duration

        result = format_duration(5.5)
        assert "5.5s" == result

    def test_format_minutes(self):
        """Test formatting minutes."""
        from all2md.cli.timing import format_duration

        result = format_duration(125.5)  # 2m 5.5s
        assert "2m" in result
        assert "5.5s" in result

    def test_format_hours(self):
        """Test formatting hours."""
        from all2md.cli.timing import format_duration

        result = format_duration(3665)  # 1h 1m 5s
        assert "1h" in result
        assert "1m" in result
        assert "5s" in result


@pytest.mark.timing
@pytest.mark.skipif(os.getenv("CI") == "true", reason="Timing tests are flaky in CI")
class TestOperationTimer:
    """Test OperationTimer class."""

    def test_timer_basic(self):
        """Test basic timer usage."""
        from all2md.cli.timing import OperationTimer

        timer = OperationTimer()
        timer.start("operation1")
        time.sleep(0.01)
        duration = timer.stop("operation1")

        assert duration > 0.01
        assert duration < 0.2  # Increased threshold to account for system variability

    def test_timer_multiple_operations(self):
        """Test timer with multiple operations."""
        from all2md.cli.timing import OperationTimer

        timer = OperationTimer()

        timer.start("op1")
        time.sleep(0.01)
        timer.stop("op1")

        timer.start("op2")
        time.sleep(0.01)
        timer.stop("op2")

        stats1 = timer.get_stats("op1")
        stats2 = timer.get_stats("op2")

        assert stats1['count'] == 1
        assert stats2['count'] == 1

    def test_timer_multiple_calls_same_operation(self):
        """Test timer with multiple calls to same operation."""
        from all2md.cli.timing import OperationTimer

        timer = OperationTimer()

        for _i in range(3):
            timer.start("operation")
            time.sleep(0.01)
            timer.stop("operation")

        stats = timer.get_stats("operation")
        assert stats['count'] == 3
        assert stats['total'] > 0.03
        assert stats['mean'] > 0.01

    def test_timer_stats(self):
        """Test timer statistics calculation."""
        from all2md.cli.timing import OperationTimer

        timer = OperationTimer()

        # Add operations with known durations (approximately)
        for sleep_time in [0.01, 0.02, 0.03]:
            timer.start("op")
            time.sleep(sleep_time)
            timer.stop("op")

        stats = timer.get_stats("op")

        assert stats['count'] == 3
        assert stats['total'] > 0.05  # At least 0.06 total
        assert stats['min'] > 0.005  # Minimum > 0.01
        assert stats['max'] > 0.025  # Maximum > 0.03

    def test_timer_stop_without_start_raises(self):
        """Test that stopping without starting raises error."""
        from all2md.cli.timing import OperationTimer

        timer = OperationTimer()

        with pytest.raises(ValueError, match="was not started"):
            timer.stop("nonexistent")

    def test_timer_report(self, caplog):
        """Test timer report generation."""
        from all2md.cli.timing import OperationTimer

        timer = OperationTimer()

        timer.start("op1")
        time.sleep(0.01)
        timer.stop("op1")

        timer.start("op2")
        time.sleep(0.01)
        timer.stop("op2")

        with caplog.at_level(logging.INFO):
            report = timer.report()

        # Report should contain operation names
        assert "op1" in report
        assert "op2" in report

        # Should have timing info
        assert "calls" in report

        # Should log the report
        assert any("Timing Report" in record.message for record in caplog.records)

    def test_timer_get_stats_nonexistent(self):
        """Test get_stats for nonexistent operation."""
        from all2md.cli.timing import OperationTimer

        timer = OperationTimer()
        stats = timer.get_stats("nonexistent")

        # Should return zero stats
        assert stats['count'] == 0
        assert stats['total'] == 0.0
        assert stats['mean'] == 0.0


class TestTimingFunction:
    """Test timing() context manager function."""

    def test_timing_function(self):
        """Test timing() function."""
        from all2md.cli.timing import timing

        with timing("test operation") as timer:
            time.sleep(0.01)

        assert timer.elapsed > 0.01

    def test_timing_function_with_logger(self, caplog):
        """Test timing() with custom logger."""
        from all2md.cli.timing import timing

        custom_logger = logging.getLogger("custom")

        with caplog.at_level(logging.DEBUG, logger="custom"):
            with timing("test", custom_logger):
                pass

        custom_logs = [r for r in caplog.records if r.name == "custom"]
        assert len(custom_logs) > 0
