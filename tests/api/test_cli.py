import pytest
from typer.testing import CliRunner
from unittest.mock import MagicMock, patch

from app.cli import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "STT Platform management CLI" in result.output


def test_list_users_empty():
    mock_db = MagicMock()
    mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []

    with patch("app.cli.get_db", return_value=mock_db):
        result = runner.invoke(app, ["list-users"])
    assert result.exit_code == 0


def test_create_admin_user_not_found():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with patch("app.cli.get_db", return_value=mock_db):
        result = runner.invoke(app, ["create-admin", "notfound@example.com"])
    assert result.exit_code == 1


def test_stats_runs():
    mock_db = MagicMock()
    mock_result = MagicMock()
    mock_result.mappings.return_value.one.return_value = {
        "total_users": 5, "total_jobs": 10, "completed": 8,
        "failed": 1, "pending": 1, "total_hours": 2.5, "total_cost": 0.05,
    }
    mock_db.execute.return_value = mock_result

    with patch("app.cli.get_db", return_value=mock_db):
        result = runner.invoke(app, ["stats"])
    assert result.exit_code == 0