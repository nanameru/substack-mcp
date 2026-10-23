"""No browser, credentials, or network is used by these regression tests."""
from unittest.mock import patch

import pytest

from substack_mcp import chrome_setup, setup_cli


@pytest.mark.parametrize("flags", [["--chrome"], ["--from-browser", "chrome"]])
def test_legacy_cookie_import_stops_before_credentials_or_browser(flags):
    with patch("sys.argv", ["setup", *flags]), \
         patch.object(setup_cli, "_show_existing") as show, \
         patch.object(setup_cli, "_confirm_overwrite") as confirm, \
         patch.object(setup_cli, "_browser_flow") as browser:
        with pytest.raises(SystemExit) as exc:
            setup_cli.main()
        assert exc.value.code == 2
        show.assert_not_called()
        confirm.assert_not_called()
        browser.assert_not_called()


@pytest.mark.parametrize("flags,selected", [([], "_browser_flow"), (["--manual"], "_manual_flow")])
def test_supported_modes_do_not_import_existing_browser(flags, selected):
    with patch("sys.argv", ["setup", "--yes", *flags]), \
         patch.object(setup_cli, "_show_existing"), \
         patch.object(setup_cli, selected, return_value=0) as flow, \
         patch.object(setup_cli, "_chrome_flow") as legacy:
        with pytest.raises(SystemExit) as exc:
            setup_cli.main()
        assert exc.value.code == 0
        flow.assert_called_once_with()
        legacy.assert_not_called()


def test_compatibility_stub_never_returns_credentials():
    assert chrome_setup.run_chrome_setup("chrome") is None


def test_existing_token_is_fully_hidden(capsys):
    creds = setup_cli.Credentials(publication_url="https://example.substack.com", session_token="DO-NOT-PRINT-THIS-TOKEN")
    with patch.object(setup_cli, "load_credentials", return_value=creds):
        setup_cli._show_existing()
    output = capsys.readouterr().out
    assert "DO-NOT" not in output
    assert "TOKEN" not in output
    assert "stored (hidden)" in output
