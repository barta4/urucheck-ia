import sys
from unittest.mock import MagicMock

# If databases or sqlalchemy are not installed in host test runner, mock them
if "databases" not in sys.modules:
    try:
        import databases
    except ImportError:
        mock_db_module = MagicMock()
        mock_db_instance = MagicMock()
        mock_db_module.Database.return_value = mock_db_instance
        sys.modules["databases"] = mock_db_module

if "sqlalchemy" not in sys.modules:
    try:
        import sqlalchemy
    except ImportError:
        mock_sa = MagicMock()
        sys.modules["sqlalchemy"] = mock_sa
