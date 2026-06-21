"""Phase 1: doctor secret-permission posture check.

`_secret_permission_check` is pure over its path list, so it's tested
hermetically here. Missing paths are skipped (optional+unconfigured), present
files broader than 0600/0700 WARN (configured+broken posture).
"""

from rebalance import doctor


def test_all_secure_paths_ok(tmp_path):
    d = tmp_path / "secrets"
    d.mkdir()
    d.chmod(0o700)
    f = d / "github_token"
    f.write_text("x")
    f.chmod(0o600)

    check = doctor._secret_permission_check([d, f])
    assert check.status == doctor.OK
    assert "2 secret" in check.detail


def test_broad_file_mode_warns(tmp_path):
    f = tmp_path / "rbos.config"
    f.write_text("{}")
    f.chmod(0o644)  # the audit's observed posture

    check = doctor._secret_permission_check([f])
    assert check.status == doctor.WARN
    assert "0644" in check.detail
    assert "broader than 0600/0700" in check.detail


def test_broad_dir_mode_warns(tmp_path):
    d = tmp_path / "rebalance-os"
    d.mkdir()
    d.chmod(0o755)

    check = doctor._secret_permission_check([d])
    assert check.status == doctor.WARN
    assert "0755" in check.detail


def test_missing_paths_skipped(tmp_path):
    # Unconfigured (absent) secret → clean skip, not a warning.
    check = doctor._secret_permission_check([tmp_path / "nope"])
    assert check.status == doctor.OK
    assert "0 secret" in check.detail
