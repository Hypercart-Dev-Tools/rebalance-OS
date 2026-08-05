import os
import subprocess
import pytest

SCRIPT_PATH = "utils/gh250/fence-writers.sh"

@pytest.fixture
def run_env(tmp_path):
    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()
    
    launchctl_stub = stub_bin / "launchctl"
    launchctl_stub.write_text(f"""#!/usr/bin/env bash
echo "$@" >> {tmp_path}/launchctl.log
if [ "$1" = "list" ]; then
    cat {tmp_path}/launchctl_list.txt
fi
""")
    launchctl_stub.chmod(0o755)
    
    python_stub = stub_bin / "python"
    python_stub.write_text(f"""#!/usr/bin/env bash
echo "$@" >> {tmp_path}/python.log
if [[ "$*" == *"-m three_eyes list"* ]]; then
    cat {tmp_path}/3eyes_list.txt
elif [[ "$*" == *"-m three_eyes why"* ]]; then
    if grep -q "$4 paused" {tmp_path}/3eyes_paused.txt 2>/dev/null; then
        echo "OPEN/quarantined paused by operator"
    else
        echo "closed"
    fi
elif [[ "$*" == *"-m three_eyes pause"* ]]; then
    if [ -f {tmp_path}/fail_pause_$4 ]; then
        exit 1
    fi
    echo "$4 paused" >> {tmp_path}/3eyes_paused.txt
elif [[ "$*" == *"-m three_eyes resume"* ]]; then
    sed -i.bak "/$4 paused/d" {tmp_path}/3eyes_paused.txt 2>/dev/null || true
fi
""")
    python_stub.chmod(0o755)

    lsof_stub = stub_bin / "lsof"
    lsof_stub.write_text(f"""#!/usr/bin/env bash
if [ -f {tmp_path}/lsof_fail ]; then exit 0; else exit 1; fi
""")
    lsof_stub.chmod(0o755)
    
    sqlite_stub = stub_bin / "sqlite3"
    sqlite_stub.write_text(f"""#!/usr/bin/env bash
if [ -f {tmp_path}/sqlite_fail ]; then exit 1; else exit 0; fi
""")
    sqlite_stub.chmod(0o755)

    env = os.environ.copy()
    env["LAUNCHCTL_CMD"] = str(launchctl_stub)
    env["PYTHON_CMD"] = str(python_stub)
    env["LSOF_CMD"] = str(lsof_stub)
    env["SQLITE_CMD"] = str(sqlite_stub)
    env["STATE_FILE"] = str(tmp_path / "state.txt")
    
    # Initialize basic stub states
    (tmp_path / "launchctl_list.txt").write_text(
        "123 0 com.rebalance-os.github-sync\n"
        "124 0 com.rebalance-os.pulse-sync\n"
        "125 0 com.rebalance-os.daily-sync\n"
        "126 0 com.rebalance-os.3eyes.collector-health\n"
    )
    (tmp_path / "3eyes_list.txt").write_text(
        "github-sync launchd ...\n"
        "pulse-sync launchd ...\n"
        "daily-sync launchd ...\n"
        "collector-health launchd ...\n"
    )
    (tmp_path / "3eyes_paused.txt").touch()
    
    return env, tmp_path

def run_script(cmd, env, check=True):
    return subprocess.run([SCRIPT_PATH, cmd], env=env, text=True, capture_output=True, check=check)

def test_fence_records_pre_state(run_env):
    env, tmp = run_env
    run_script("fence", env)
    
    state = (tmp / "state.txt").read_text()
    assert "com.rebalance-os.github-sync:3eyes:github-sync" in state
    assert "com.rebalance-os.pulse-sync:3eyes:pulse-sync" in state
    
    py_log = (tmp / "python.log").read_text()
    assert "-m three_eyes pause github-sync" in py_log

def test_fence_twice_no_clobber(run_env):
    env, tmp = run_env
    (tmp / "launchctl_list.txt").write_text("123 0 com.rebalance-os.github-sync\n")
    run_script("fence", env)
    state1 = (tmp / "state.txt").read_text()
    
    (tmp / "launchctl_list.txt").write_text(
        "123 0 com.rebalance-os.github-sync\n"
        "124 0 com.rebalance-os.pulse-sync\n"
    )
    run_script("fence", env)
    state2 = (tmp / "state.txt").read_text()
    assert state1 == state2 

def test_unfence_restores_recorded(run_env):
    env, tmp = run_env
    state_content = "com.rebalance-os.github-sync:3eyes:github-sync\ncom.rebalance-os.daily-sync:launchctl:none\n"
    (tmp / "state.txt").write_text(state_content)
    
    run_script("unfence", env)
    
    py_log = (tmp / "python.log").read_text()
    assert "-m three_eyes resume github-sync" in py_log
    launch_log = (tmp / "launchctl.log").read_text()
    assert "bootstrap" in launch_log
    assert "com.rebalance-os.daily-sync.plist" in launch_log

def test_unfence_no_state_file_fails(run_env):
    env, tmp = run_env
    if (tmp / "state.txt").exists():
        (tmp / "state.txt").unlink()
    
    res = run_script("unfence", env, check=False)
    assert res.returncode != 0
    assert "Error: No state file found" in res.stdout

def test_verify_fails_when_writer_loaded(run_env):
    env, tmp = run_env
    res = run_script("verify", env, check=False)
    assert res.returncode != 0
    assert "FAIL:" in res.stdout
    
    (tmp / "3eyes_paused.txt").write_text(
        "github-sync paused\npulse-sync paused\ndaily-sync paused\ncollector-health paused\n"
    )
    res = run_script("verify", env, check=True)
    assert res.returncode == 0

def test_fence_interrupt_restores(run_env):
    env, tmp = run_env
    (tmp / "fail_pause_pulse-sync").touch()
    
    res = run_script("fence", env, check=False)
    assert res.returncode != 0
    assert "Interrupt received, restoring..." in res.stdout
    assert "Restoring fenced writers..." in res.stdout
    
    py_log = (tmp / "python.log").read_text()
    # It paused github-sync first
    assert "-m three_eyes pause github-sync" in py_log
    # Then it should have resumed it in the trap
    assert "-m three_eyes resume github-sync" in py_log
