import os
import subprocess
from pathlib import Path

import pytest

# Resolved from this file's own location, not the caller's CWD (GH-255): a bare
# relative path made the whole module pass from the repo root and fail anywhere else.
REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = str(REPO_ROOT / "utils" / "gh250" / "fence-writers.sh")

@pytest.fixture
def run_env(tmp_path):
    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()
    
    launchctl_stub = stub_bin / "launchctl"
    launchctl_stub.write_text(f"""#!/usr/bin/env bash
echo "$@" >> {tmp_path}/launchctl.log
if [ -f {tmp_path}/state.txt ]; then
    echo "WITH_STATE: launchctl $*" >> {tmp_path}/events.log
else
    echo "NO_STATE: launchctl $*" >> {tmp_path}/events.log
fi

if [ "$1" = "list" ]; then
    cat {tmp_path}/launchctl_list.txt
elif [ "$1" = "bootstrap" ]; then
    if [ -f {tmp_path}/fail_bootstrap ]; then exit 1; fi
    echo "129 0 $(basename $3 .plist)" >> {tmp_path}/launchctl_list.txt
elif [ "$1" = "bootout" ]; then
    if [ -f {tmp_path}/fail_bootout ]; then exit 1; fi
    grep -v "$(basename $3 .plist)" {tmp_path}/launchctl_list.txt > {tmp_path}/launchctl_list.tmp
    mv {tmp_path}/launchctl_list.tmp {tmp_path}/launchctl_list.txt
fi
""")
    launchctl_stub.chmod(0o755)
    
    python_stub = stub_bin / "python"
    python_stub.write_text(f"""#!/usr/bin/env bash
echo "$@" >> {tmp_path}/python.log

if [[ "$*" == *"-m three_eyes list"* ]] || [[ "$*" == *"-m three_eyes why"* ]]; then
    : # Don't log read actions to events
else
    if [ -f {tmp_path}/state.txt ]; then
        echo "WITH_STATE: python $*" >> {tmp_path}/events.log
    else
        echo "NO_STATE: python $*" >> {tmp_path}/events.log
    fi
fi

if [[ "$*" == *"-m three_eyes list"* ]]; then
    cat {tmp_path}/3eyes_list.txt
elif [[ "$*" == *"-m three_eyes why"* ]]; then
    if grep -q "$4 paused" {tmp_path}/3eyes_paused.txt 2>/dev/null; then
        echo "OPEN/quarantined"
        echo "reason: paused via CLI"
    else
        echo "closed"
    fi
elif [[ "$*" == *"-m three_eyes pause"* ]]; then
    if [ -f {tmp_path}/fail_pause_$4 ]; then
        exit 1
    fi
    echo "$4 paused" >> {tmp_path}/3eyes_paused.txt
elif [[ "$*" == *"-m three_eyes resume"* ]]; then
    if [ -f {tmp_path}/fail_resume_$4 ]; then
        exit 1
    fi
    grep -v "$4 paused" {tmp_path}/3eyes_paused.txt > {tmp_path}/3eyes_paused.tmp 2>/dev/null || true
    mv {tmp_path}/3eyes_paused.tmp {tmp_path}/3eyes_paused.txt 2>/dev/null || true
fi
""")
    python_stub.chmod(0o755)

    lsof_stub = stub_bin / "lsof"
    lsof_stub.write_text(f"""#!/usr/bin/env bash
echo "$@" >> {tmp_path}/lsof.log
if [ -f {tmp_path}/lsof_fail ]; then exit 0; else exit 1; fi
""")
    lsof_stub.chmod(0o755)
    
    sqlite_stub = stub_bin / "sqlite3"
    sqlite_stub.write_text(f"""#!/usr/bin/env bash
echo "$@" >> {tmp_path}/sqlite.log
if [ -f {tmp_path}/sqlite_fail ]; then exit 1; else exit 0; fi
""")
    sqlite_stub.chmod(0o755)

    env = os.environ.copy()
    env["LAUNCHCTL_CMD"] = str(launchctl_stub)
    env["PYTHON_CMD"] = str(python_stub)
    env["LSOF_CMD"] = str(lsof_stub)
    env["SQLITE_CMD"] = str(sqlite_stub)
    env["STATE_FILE"] = str(tmp_path / "state.txt")
    env["REBALANCE_DB"] = str(tmp_path / "mock_rebalance.db")
    
    # Initialize basic stub states
    (tmp_path / "launchctl_list.txt").write_text(
        "123 0 com.rebalance-os.github-sync\n"
        "124 0 com.rebalance-os.pulse-sync\n"
        "125 0 com.rebalance-os.daily-sync\n"
        "126 0 com.rebalance-os.3eyes.collector-health\n"
        "127 0 com.rebalance-os.vault-sync\n"
    )
    # Notice daily-sync is missing here to force bootout/bootstrap logic
    (tmp_path / "3eyes_list.txt").write_text(
        "github-sync launchd ...\n"
        "pulse-sync launchd ...\n"
        "collector-health launchd ...\n"
        "vault-sync launchd ...\n"
    )
    (tmp_path / "3eyes_paused.txt").touch()
    (tmp_path / "events.log").touch()
    
    return env, tmp_path

def run_script(cmd, env, check=True):
    return subprocess.run([SCRIPT_PATH, cmd], env=env, text=True, capture_output=True, check=check)

def test_fence_records_pre_state(run_env):
    env, tmp = run_env
    run_script("fence", env)
    
    state = (tmp / "state.txt").read_text()
    assert "com.rebalance-os.github-sync:3eyes:github-sync" in state
    assert "com.rebalance-os.daily-sync:launchctl:none" in state
    assert "com.rebalance-os.vault-sync:3eyes:vault-sync" in state
    
    events_log = (tmp / "events.log").read_text()
    assert "NO_STATE: python" not in events_log
    assert "NO_STATE: launchctl bootout" not in events_log
    assert "WITH_STATE: python" in events_log
    assert "WITH_STATE: launchctl bootout" in events_log

def test_fence_twice_no_clobber(run_env):
    env, tmp = run_env
    (tmp / "launchctl_list.txt").write_text("123 0 com.rebalance-os.github-sync\n")
    run_script("fence", env)
    state1 = (tmp / "state.txt").read_text()
    
    (tmp / "launchctl_list.txt").write_text(
        "123 0 com.rebalance-os.github-sync\n"
        "124 0 com.rebalance-os.pulse-sync\n"
    )
    res = run_script("fence", env)
    assert "A fence is already active. Doing nothing." in res.stdout
    state2 = (tmp / "state.txt").read_text()
    assert state1 == state2 
    
    py_log = (tmp / "python.log").read_text()
    assert "pause pulse-sync" not in py_log

def test_unfence_restores_recorded(run_env):
    env, tmp = run_env
    state_content = "com.rebalance-os.github-sync:3eyes:github-sync\ncom.rebalance-os.daily-sync:launchctl:none\n"
    (tmp / "state.txt").write_text(state_content)
    (tmp / "3eyes_paused.txt").write_text("github-sync paused\n")
    (tmp / "launchctl_list.txt").write_text("123 0 com.rebalance-os.github-sync\n")
    
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
        "github-sync paused\npulse-sync paused\ncollector-health paused\nvault-sync paused\n"
    )
    # also remove unmanaged daily-sync from launchctl to pass
    (tmp / "launchctl_list.txt").write_text(
        "123 0 com.rebalance-os.github-sync\n"
        "124 0 com.rebalance-os.pulse-sync\n"
        "126 0 com.rebalance-os.3eyes.collector-health\n"
        "127 0 com.rebalance-os.vault-sync\n"
    )
    res = run_script("verify", env, check=True)
    assert res.returncode == 0

def test_verify_fails_on_unknown_rebalance_job(run_env):
    env, tmp = run_env
    # Add an unknown job that matches com.rebalance-os.* but isn't a known writer
    with open(tmp / "launchctl_list.txt", "a") as f:
        f.write("199 0 com.rebalance-os.mysterious-writer\n")
    
    res = run_script("verify", env, check=False)
    assert res.returncode != 0
    assert "Unknown writer loaded: com.rebalance-os.mysterious-writer" in res.stdout

def test_fence_interrupt_restores_and_idempotent(run_env):
    env, tmp = run_env
    (tmp / "fail_bootout").touch() # daily-sync will fail on bootout
    
    res = run_script("fence", env, check=False)
    assert res.returncode != 0
    assert "restoring..." in res.stdout
    assert "Restoring fenced writers..." in res.stdout
    
    py_log = (tmp / "python.log").read_text()
    # All 3-Eyes managed writers should be paused before launchctl bootout fails
    assert "-m three_eyes pause github-sync" in py_log
    assert "-m three_eyes pause pulse-sync" in py_log
    assert "-m three_eyes pause collector-health" in py_log
    assert "-m three_eyes pause vault-sync" in py_log
    
    # And the trap should resume all of them
    assert "-m three_eyes resume github-sync" in py_log
    assert "-m three_eyes resume pulse-sync" in py_log
    assert "-m three_eyes resume collector-health" in py_log
    assert "-m three_eyes resume vault-sync" in py_log
    
    # Since bootout failed, daily-sync is STILL loaded.
    # The restore logic should see it's loaded and skip bootstrap (idempotent unfence)
    events_log = (tmp / "events.log").read_text()
    # We shouldn't see bootstrap in the trap execution
    launchctl_log = (tmp / "launchctl.log").read_text()
    assert "bootstrap" not in launchctl_log

def test_unfence_failures_continue_and_retain_state(run_env):
    env, tmp = run_env
    state_content = "com.rebalance-os.github-sync:3eyes:github-sync\ncom.rebalance-os.daily-sync:launchctl:none\ncom.rebalance-os.pulse-sync:3eyes:pulse-sync\n"
    (tmp / "state.txt").write_text(state_content)
    (tmp / "3eyes_paused.txt").write_text("github-sync paused\npulse-sync paused\n")
    (tmp / "launchctl_list.txt").write_text("123 0 com.rebalance-os.github-sync\n124 0 com.rebalance-os.pulse-sync\n")
    (tmp / "fail_resume_github-sync").touch()
    
    res = run_script("unfence", env, check=False)
    assert res.returncode != 0
    assert "Unfence encountered errors. State file retained." in res.stdout
    
    py_log = (tmp / "python.log").read_text()
    assert "-m three_eyes resume github-sync" in py_log
    assert "-m three_eyes resume pulse-sync" in py_log
    
    launch_log = (tmp / "launchctl.log").read_text()
    assert "bootstrap" in launch_log
    assert "com.rebalance-os.daily-sync.plist" in launch_log
    
    assert (tmp / "state.txt").exists()

def test_already_paused_writer_gets_neither_pause_nor_resume(run_env):
    env, tmp = run_env
    # Pre-pause github-sync before fence
    (tmp / "3eyes_paused.txt").write_text("github-sync paused\n")
    
    res = run_script("fence", env)
    assert res.returncode == 0
    assert "is 3-Eyes managed and already paused" in res.stdout
    
    # State file shouldn't record github-sync
    state_content = (tmp / "state.txt").read_text()
    assert "com.rebalance-os.github-sync" not in state_content
    
    py_log = (tmp / "python.log").read_text()
    # It shouldn't pause github-sync because it was already paused
    assert "-m three_eyes pause github-sync" not in py_log
    
    # Now unfence
    res2 = run_script("unfence", env)
    assert res2.returncode == 0
    
    py_log_after = (tmp / "python.log").read_text()
    # It shouldn't resume github-sync because it wasn't in state
    assert "-m three_eyes resume github-sync" not in py_log_after

