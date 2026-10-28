import subprocess
import sys

import pytest

from toonrooter.hardware.openocd import OpenOCD, OpenOCDError, Query, require_safe_jtag


def client_for(script):
    calls = []
    def spawn(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.Popen([sys.executable, "-c", script], **kwargs)
    return OpenOCD("/fake/openocd", spawn=spawn), calls


def test_fixed_host_sequences():
    client, calls = client_for("print('bcm2835gpio linuxgpiod')")
    assert b"linuxgpiod" in client.query(Query.ADAPTERS)
    assert calls[0][0] == ["/fake/openocd", "-c", "noinit; adapter list; shutdown"]
    assert calls[0][1]["start_new_session"]
    assert calls[0][1]["cwd"] == "/"


@pytest.mark.parametrize("script", [
    "raise SystemExit(1)",
    "import time; time.sleep(10)",
    "print('x'*1000)",
])
def test_failure_timeout_and_output_limit(script):
    client, _ = client_for(script)
    with pytest.raises(OpenOCDError):
        client.query(Query.VERSION, timeout=0.2, limit=100)


def test_no_arbitrary_scripts_or_jtag():
    client, calls = client_for("print('unused')")
    with pytest.raises(OpenOCDError):
        client.query("reset halt")
    with pytest.raises(OpenOCDError, match="disabled"):
        require_safe_jtag()
    assert not calls


def test_interruption_reaps_process(monkeypatch):
    import os
    import selectors
    import signal
    processes = []
    def spawn(args, **kwargs):
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"],
                                   **kwargs)
        processes.append(process)
        return process
    def interrupted(*args):
        raise KeyboardInterrupt
    monkeypatch.setattr(selectors.EpollSelector, "select", interrupted)
    with pytest.raises(KeyboardInterrupt):
        OpenOCD("/fake/openocd", spawn=spawn).query(Query.VERSION)
    assert processes[0].returncode == -signal.SIGKILL
    with pytest.raises(ProcessLookupError):
        os.kill(processes[0].pid, 0)
