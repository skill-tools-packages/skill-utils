import json
import logging

import pytest

from skill_utils import load_config, retry, setup_logging
from skill_utils import utils


class TestLoadConfig:
    @pytest.fixture(autouse=True)
    def isolate(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("SKILL_CONFIG", raising=False)

    def write(self, path, data):
        path.write_text(json.dumps(data))
        return path

    def test_explicit_path(self, tmp_path):
        assert load_config(self.write(tmp_path / "c.json", {"a": 1})) == {"a": 1}

    def test_env_var(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SKILL_CONFIG", str(self.write(tmp_path / "env.json", {"src": "env"})))

        assert load_config() == {"src": "env"}

    def test_cwd_skill_json(self, tmp_path):
        self.write(tmp_path / "skill.json", {"src": "cwd"})

        assert load_config() == {"src": "cwd"}

    def test_precedence(self, tmp_path, monkeypatch):
        explicit = self.write(tmp_path / "x.json", {"src": "explicit"})
        monkeypatch.setenv("SKILL_CONFIG", str(self.write(tmp_path / "env.json", {"src": "env"})))
        self.write(tmp_path / "skill.json", {"src": "cwd"})

        assert load_config(explicit) == {"src": "explicit"}
        assert load_config() == {"src": "env"}

    def test_missing_path_falls_through(self, tmp_path):
        self.write(tmp_path / "skill.json", {"src": "cwd"})

        assert load_config(tmp_path / "missing.json") == {"src": "cwd"}

    def test_directory_falls_through(self, tmp_path):
        assert load_config(tmp_path) == {}

    def test_nothing_found(self):
        assert load_config() == {}

    def test_invalid_json_raises(self, tmp_path):
        (tmp_path / "bad.json").write_text("{")

        with pytest.raises(json.JSONDecodeError):
            load_config(tmp_path / "bad.json")


class TestSetupLogging:
    def test_configures_logger_once(self):
        logger = setup_logging("skill_utils_test_once", logging.DEBUG)
        again = setup_logging("skill_utils_test_once", logging.WARNING)

        assert logger is again
        assert len(logger.handlers) == 1
        assert logger.level == logging.WARNING


class TestRetry:
    @pytest.fixture(autouse=True)
    def no_sleep(self, monkeypatch):
        self.sleeps = []
        self.jitter = []
        monkeypatch.setattr(utils.time, "sleep", self.sleeps.append)

        def uniform(a, b):
            self.jitter.append((a, b))
            return b

        monkeypatch.setattr(utils.random, "uniform", uniform)

    def flaky(self, failures, exc=RuntimeError):
        calls = []

        def fn(x):
            calls.append(x)
            if len(calls) <= failures:
                raise exc("boom")
            return x * 2

        return fn, calls

    def test_returns_immediately_on_success(self):
        fn, calls = self.flaky(0)

        assert retry()(fn)(5) == 10
        assert calls == [5]
        assert self.sleeps == []

    def test_retries_with_exponential_backoff(self):
        fn, calls = self.flaky(2)

        assert retry(max_attempts=3, backoff_factor=0.5)(fn)(1) == 2
        assert len(calls) == 3
        assert self.sleeps == [0.5, 1.0]

    def test_raises_last_exception_without_final_sleep(self):
        fn, calls = self.flaky(10)

        with pytest.raises(RuntimeError, match="boom"):
            retry(max_attempts=3)(fn)(1)
        assert len(calls) == 3
        assert self.sleeps == [1.0, 2.0]

    def test_other_exceptions_not_retried(self):
        fn, calls = self.flaky(1, exc=KeyError)

        with pytest.raises(KeyError):
            retry(exceptions=(ValueError,))(fn)(1)
        assert len(calls) == 1

    def test_logs_each_failure(self, caplog):
        fn, _ = self.flaky(1)
        logger = logging.getLogger("skill_utils_test_retry")

        with caplog.at_level(logging.WARNING, logger="skill_utils_test_retry"):
            retry(logger=logger)(fn)(1)

        assert "Attempt 1/3 failed (RuntimeError)" in caplog.text

    def test_preserves_function_metadata(self):
        @retry()
        def documented():
            """Docs."""

        assert documented.__name__ == "documented"
        assert documented.__doc__ == "Docs."

    def test_delay_capped(self):
        fn, _ = self.flaky(10)

        with pytest.raises(RuntimeError):
            retry(max_attempts=5, backoff_factor=10, max_delay=25)(fn)(1)
        assert self.sleeps == [10, 20, 25, 25]

    def test_jitter_shortens_delay_by_up_to_half(self):
        fn, _ = self.flaky(1)
        retry()(fn)(1)

        assert self.jitter == [(0.5, 1.0)]

    @pytest.mark.parametrize("attempts", [0, -1])
    def test_rejects_fewer_than_one_attempt(self, attempts):
        with pytest.raises(ValueError, match="at least 1"):
            retry(max_attempts=attempts)
