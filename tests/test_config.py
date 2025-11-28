"""Tests for the config module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import tomli_w

from rwreader.config import DEFAULT_CONFIG, Configuration, get_conf_value

# Test constants
CACHE_SIZE_SMALL = 5000
CACHE_SIZE_LARGE = 10000
READING_WIDTH_SMALL = 80
READING_WIDTH_LARGE = 100


class TestGetConfValue:
    """Test cases for get_conf_value function."""

    def test_get_conf_value_plain_string(self) -> None:
        """Test getting a plain configuration value."""
        value = get_conf_value("plain_token_123")
        assert value == "plain_token_123"

    @patch("subprocess.run")
    def test_get_conf_value_1password_success(self, mock_run: MagicMock) -> None:
        """Test getting value from 1Password CLI successfully."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["op", "read", "op://vault/item/field"],
            returncode=0,
            stdout="secret_token_456\n",
            stderr="",
        )

        value = get_conf_value("op read op://vault/item/field")
        assert value == "secret_token_456"
        mock_run.assert_called_once_with(
            args=["op", "read", "op://vault/item/field"],
            capture_output=True,
            text=True,
            check=True,
        )

    @patch("subprocess.run")
    def test_get_conf_value_1password_command_error(self, mock_run: MagicMock) -> None:
        """Test 1Password CLI command failure."""
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["op", "read", "op://vault/item/field"]
        )

        with pytest.raises(SystemExit) as excinfo:
            get_conf_value("op read op://vault/item/field")

        assert excinfo.value.code == 1

    @patch("subprocess.run")
    def test_get_conf_value_1password_not_found(self, mock_run: MagicMock) -> None:
        """Test 1Password CLI not installed."""
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(SystemExit) as excinfo:
            get_conf_value("op read op://vault/item/field")

        assert excinfo.value.code == 1


class TestConfiguration:
    """Test cases for Configuration class."""

    @pytest.fixture
    def mock_config_file(self, tmp_path: Path) -> Path:
        """Create a temporary config file for testing."""
        config_path = tmp_path / "test_config.toml"
        config_data = {
            "general": {"cache_size": CACHE_SIZE_SMALL, "default_theme": "light"},
            "readwise": {"token": "test_token_123"},
            "display": {"font_size": "large", "reading_width": READING_WIDTH_LARGE},
        }
        config_path.write_text(tomli_w.dumps(config_data))
        return config_path

    @patch("rwreader.config.metadata.version")
    def test_configuration_load_success(
        self, mock_version: MagicMock, mock_config_file: Path
    ) -> None:
        """Test successful configuration loading."""
        mock_version.return_value = "0.1.1"

        config = Configuration(exec_args=["--config", str(mock_config_file)])

        assert config.token == "test_token_123"
        assert config.cache_size == CACHE_SIZE_SMALL
        assert config.default_theme == "light"
        assert config.font_size == "large"
        assert config.reading_width == READING_WIDTH_LARGE
        assert config.version == "0.1.1"

    @patch("rwreader.config.metadata.version")
    @patch("subprocess.run")
    def test_configuration_with_1password(
        self,
        mock_run: MagicMock,
        mock_version: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test configuration with 1Password token."""
        mock_version.return_value = "0.1.1"
        mock_run.return_value = subprocess.CompletedProcess(
            args=["op", "read", "op://vault/item/token"],
            returncode=0,
            stdout="1password_secret_token\n",
            stderr="",
        )

        config_path = tmp_path / "test_config_1p.toml"
        config_data = {
            "general": {"cache_size": CACHE_SIZE_LARGE, "default_theme": "dark"},
            "readwise": {"token": "op read op://vault/item/token"},
            "display": {"font_size": "medium", "reading_width": READING_WIDTH_SMALL},
        }
        config_path.write_text(tomli_w.dumps(config_data))

        config = Configuration(exec_args=["--config", str(config_path)])

        assert config.token == "1password_secret_token"
        assert config.cache_size == CACHE_SIZE_LARGE

    @patch("rwreader.config.metadata.version")
    def test_configuration_defaults(
        self, mock_version: MagicMock, tmp_path: Path
    ) -> None:
        """Test configuration with missing optional fields uses defaults."""
        mock_version.return_value = "0.1.1"

        config_path = tmp_path / "test_config_minimal.toml"
        config_data = {
            "readwise": {"token": "minimal_token"},
        }
        config_path.write_text(tomli_w.dumps(config_data))

        config = Configuration(exec_args=["--config", str(config_path)])

        assert config.token == "minimal_token"
        assert config.cache_size == CACHE_SIZE_LARGE  # Default
        assert config.default_theme == "dark"  # Default
        assert config.font_size == "medium"  # Default
        assert config.reading_width == READING_WIDTH_SMALL  # Default

    @patch("rwreader.config.metadata.version")
    def test_configuration_version_flag(self, mock_version: MagicMock, capsys) -> None:
        """Test --version flag."""
        mock_version.return_value = "0.1.1"

        with pytest.raises(SystemExit) as excinfo:
            Configuration(exec_args=["--version"])

        assert excinfo.value.code == 0
        captured = capsys.readouterr()
        assert "0.1.1" in captured.out

    @patch("rwreader.config.metadata.version")
    @patch("builtins.print")
    def test_configuration_create_config(
        self, mock_print: MagicMock, mock_version: MagicMock, tmp_path: Path
    ) -> None:
        """Test --create-config flag."""
        mock_version.return_value = "0.1.1"
        new_config_path = tmp_path / "new_config.toml"

        with pytest.raises(SystemExit) as excinfo:
            Configuration(exec_args=["--create-config", str(new_config_path)])

        assert excinfo.value.code == 0
        assert new_config_path.exists()
        assert DEFAULT_CONFIG in new_config_path.read_text()

    @patch("rwreader.config.metadata.version")
    @patch("builtins.print")
    def test_configuration_missing_config_creates_default(
        self, mock_print: MagicMock, mock_version: MagicMock, tmp_path: Path
    ) -> None:
        """Test that missing config file creates default and exits."""
        mock_version.return_value = "0.1.1"
        missing_config = tmp_path / "missing.toml"

        with pytest.raises(SystemExit) as excinfo:
            Configuration(exec_args=["--config", str(missing_config)])

        assert excinfo.value.code == 1
        assert missing_config.exists()  # Should be created
        mock_print.assert_called()

    @patch("rwreader.config.metadata.version")
    def test_configuration_invalid_toml(
        self, mock_version: MagicMock, tmp_path: Path
    ) -> None:
        """Test handling of invalid TOML file."""
        mock_version.return_value = "0.1.1"
        invalid_config = tmp_path / "invalid.toml"
        invalid_config.write_text("this is not valid [ TOML")

        with pytest.raises(SystemExit) as excinfo:
            Configuration(exec_args=["--config", str(invalid_config)])

        assert excinfo.value.code == 1

    @patch("rwreader.config.metadata.version")
    def test_configuration_missing_required_field(
        self, mock_version: MagicMock, tmp_path: Path
    ) -> None:
        """Test handling of missing required token field."""
        mock_version.return_value = "0.1.1"
        config_path = tmp_path / "no_token.toml"
        config_data = {
            "general": {"cache_size": 5000},
            # Missing readwise section with token
        }
        config_path.write_text(tomli_w.dumps(config_data))

        with pytest.raises(SystemExit) as excinfo:
            Configuration(exec_args=["--config", str(config_path)])

        assert excinfo.value.code == 1

    @patch("rwreader.config.metadata.version")
    def test_configuration_version_fallback(
        self, mock_version: MagicMock, mock_config_file: Path
    ) -> None:
        """Test version fallback when metadata.version fails."""
        mock_version.side_effect = Exception("Package not found")

        config = Configuration(exec_args=["--config", str(mock_config_file)])

        assert config.version == "0.1.0"  # Fallback version

    def test_create_default_config(self, tmp_path: Path) -> None:
        """Test create_default_config method."""
        config_path = tmp_path / "subdir" / "config.toml"

        # Create a temporary config instance just to call the method
        with patch("rwreader.config.metadata.version", return_value="0.1.1"):
            # Create instance with a valid config first
            temp_config_path = tmp_path / "temp.toml"
            temp_data = {"readwise": {"token": "temp"}}
            temp_config_path.write_text(tomli_w.dumps(temp_data))

            config = Configuration(exec_args=["--config", str(temp_config_path)])
            config.create_default_config(str(config_path))

        assert config_path.exists()
        assert DEFAULT_CONFIG in config_path.read_text()

    def test_create_default_config_parent_dir_error(self, tmp_path: Path) -> None:
        """Test create_default_config with directory creation error."""
        # Mock both exists and mkdir to test directory creation error handling
        with patch("rwreader.config.metadata.version", return_value="0.1.1"):
            temp_config_path = tmp_path / "temp.toml"
            temp_data = {"readwise": {"token": "temp"}}
            temp_config_path.write_text(tomli_w.dumps(temp_data))

            config = Configuration(exec_args=["--config", str(temp_config_path)])

            # Mock exists to return False and mkdir to raise PermissionError
            with patch("pathlib.Path.exists", return_value=False):
                with patch("pathlib.Path.mkdir", side_effect=PermissionError("No access")):
                    with pytest.raises(SystemExit) as excinfo:
                        config.create_default_config(str(tmp_path / "newdir" / "config.toml"))

                    assert excinfo.value.code == 1
