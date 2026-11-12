"""Startup failures must not depend on Tk or a writable log directory."""
from unittest import TestCase
from unittest.mock import Mock, patch

import app_launcher


class LauncherTests(TestCase):
    def test_missing_dependency_reports_failure_without_importing_tk(self):
        with patch.object(app_launcher.importlib, "import_module", side_effect=ImportError("missing Tk")), \
                patch.object(app_launcher, "show_startup_error") as show, \
                patch.object(app_launcher.logging, "getLogger"):
            self.assertEqual(app_launcher.run_application(), 1)
        show.assert_called_once_with()

    def test_denied_cache_reports_failure_and_does_not_start_again(self):
        application = Mock()
        application.main.side_effect = PermissionError("cache access denied")
        with patch.object(app_launcher.importlib, "import_module", return_value=application), \
                patch.object(app_launcher, "show_startup_error") as show, \
                patch.object(app_launcher.logging, "getLogger"):
            self.assertEqual(app_launcher.run_application(), 1)
        application.main.assert_called_once_with()
        show.assert_called_once_with()

    def test_logging_failure_does_not_hide_the_startup_message(self):
        with patch.object(app_launcher.importlib, "import_module", side_effect=ImportError()), \
                patch.object(app_launcher.logging, "getLogger", side_effect=OSError("log unavailable")), \
                patch.object(app_launcher, "show_startup_error") as show:
            self.assertEqual(app_launcher.run_application(), 1)
        show.assert_called_once_with()

    def test_success_does_not_display_an_error(self):
        application = Mock()
        with patch.object(app_launcher.importlib, "import_module", return_value=application), \
                patch.object(app_launcher, "show_startup_error") as show:
            self.assertEqual(app_launcher.run_application(), 0)
        application.main.assert_called_once_with()
        show.assert_not_called()
