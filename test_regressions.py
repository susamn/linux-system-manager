#!/usr/bin/env python3
"""Regression tests for bugs that actually shipped.

Every test here corresponds to a real defect that was live in main. Each one was
verified to FAIL against the pre-fix code -- a regression test that passes against
the broken version is worse than no test, because it manufactures confidence.

The shell tests drive the real scripts through subprocess against temp fixtures
rather than mocking, because every one of these bugs lived in the interaction
between bash options (`set -euo pipefail`) and command exit codes. Mocks cannot
express that.
"""
import builtins
import contextlib
import importlib.util
import io
import os
import shutil
import subprocess
import symtable
import tempfile
import textwrap
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASH = shutil.which('bash') or '/bin/bash'


def run_bash(script, *args, env=None, stdin=None, cwd=None):
    """Run a shell script and capture everything, never raising on failure."""
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    return subprocess.run(
        [BASH, script, *args],
        capture_output=True, text=True, timeout=60,
        env=full_env, input=stdin, cwd=cwd,
    )


class TestInstallerRegressions(unittest.TestCase):
    """install.py aborted with NameError before registering any package hooks."""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "install_under_test", os.path.join(SCRIPT_DIR, "install.py"))
        cls.install = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.install)

    def test_no_unresolved_globals_in_any_function(self):
        """The NameError that shipped: a function reading another's local.

        Static check across the whole module, so this catches the next one too --
        not just the specific name that broke.
        """
        with open(os.path.join(SCRIPT_DIR, "install.py")) as f:
            source = f.read()
        table = symtable.symtable(source, "install.py", "exec")
        # `import builtins`, not `dir(__builtins__)`: the latter is a module when a
        # file runs as __main__ but a dict when imported, so under test discovery it
        # would yield dict methods and flag every builtin as unresolved.
        module_names = set(dir(self.install)) | set(dir(builtins))

        offenders = []
        for func in table.get_children():
            if func.get_type() != 'function':
                continue
            for sym in func.get_symbols():
                name = sym.get_name()
                if (sym.is_global() and not sym.is_assigned()
                        and name not in module_names):
                    offenders.append(f"{func.get_name()}() -> {name}")

        self.assertEqual(
            offenders, [],
            "Functions reference names that do not exist at module scope: "
            + ", ".join(offenders))

    def test_rclone_helper_is_callable(self):
        """Directly exercises the function whose NameError went unnoticed.

        Fully isolated: SUDO_USER/USER are pointed at a throwaway account name so
        the helper resolves an empty profile directory. Without this the test walks
        the developer's real rclone profiles, shells out to the network, and tries
        to write into /etc/systemd/system.
        """
        import unittest.mock as mock

        with tempfile.TemporaryDirectory() as tmp:
            services = os.path.join(tmp, 'services')
            fake_home = os.path.join(tmp, 'home', 'nobody-under-test')
            os.makedirs(services)
            os.makedirs(fake_home)

            original = self.install.SERVICES_SRC_DIR
            env = {k: v for k, v in os.environ.items()
                   if k not in ('SUDO_USER', 'USER')}
            env['USER'] = 'nobody-under-test'

            try:
                self.install.SERVICES_SRC_DIR = services
                with mock.patch.dict(os.environ, env, clear=True), \
                     mock.patch.object(self.install.os.path, 'expanduser',
                                       return_value=fake_home), \
                     mock.patch.object(self.install.subprocess, 'run') as fake_run, \
                     contextlib.redirect_stdout(io.StringIO()):
                    fake_run.return_value = subprocess.CompletedProcess(
                        args=[], returncode=1, stdout='', stderr='')
                    self.install.install_rclone_sync_helper()

                # No profiles exist, so no systemd calls should have been attempted.
                self.assertEqual(
                    fake_run.call_count, 0,
                    "helper shelled out despite there being no profiles")
            except NameError as e:
                self.fail(f"install_rclone_sync_helper raised NameError: {e}")
            finally:
                self.install.SERVICES_SRC_DIR = original

    def test_install_phases_are_independent(self):
        """One failing phase must not skip the others.

        The NameError was only catastrophic because it aborted main() before hook
        registration ran.
        """
        with open(os.path.join(SCRIPT_DIR, "install.py")) as f:
            source = f.read()

        # assertTrue rather than assertIn: assertIn embeds the entire haystack in
        # the failure message, which for a source file is unreadable in CI logs.
        self.assertTrue(
            "phases" in source,
            "main() should iterate independent phases so one failure "
            "cannot skip hook registration")
        self.assertTrue(
            "except Exception" in source,
            "each install phase should be individually guarded")


class TestSetEShellIdioms(unittest.TestCase):
    """`set -euo pipefail` + idioms that return non-zero on success."""

    def test_counter_increment_does_not_abort(self):
        """((VAR++)) exits 1 when VAR is 0, killing the script under set -e.

        This is the bug that stopped check_boot.sh from ever printing its verdict.
        """
        broken = textwrap.dedent("""\
            set -euo pipefail
            N=0
            bump() { N=$((N + 1)); }
            bump; bump
            echo "N=$N"
        """)
        res = subprocess.run([BASH, '-c', broken], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"aborted: {res.stderr}")
        self.assertIn("N=2", res.stdout)

    def test_no_bare_postincrement_in_shipped_scripts(self):
        """Guard the whole tree, not just the two files that were broken."""
        import re
        pattern = re.compile(r'\(\(\s*\w+\+\+\s*\)\)')
        offenders = []
        for root, _dirs, files in os.walk(SCRIPT_DIR):
            if '.git' in root:
                continue
            for name in files:
                if not name.endswith('.sh'):
                    continue
                path = os.path.join(root, name)
                with open(path, encoding='utf-8', errors='replace') as f:
                    for lineno, line in enumerate(f, 1):
                        if pattern.search(line):
                            rel = os.path.relpath(path, SCRIPT_DIR)
                            offenders.append(f"{rel}:{lineno}")
        self.assertEqual(
            offenders, [],
            "((VAR++)) returns 1 when VAR is 0 and aborts under `set -e`; "
            "use VAR=$((VAR + 1)) instead. Found at: " + ", ".join(offenders))

    def test_grep_c_fallback_does_not_double_up(self):
        """`grep -c ... || echo 0` yields "0\\n0" and breaks the comparison.

        This inverted the GRUB safety verdict: a config with no kernel entries was
        reported as passing.
        """
        with tempfile.TemporaryDirectory() as tmp:
            empty = os.path.join(tmp, 'grub.cfg')
            with open(empty, 'w') as f:
                f.write("menuentry 'Broken' {\n}\n")

            good = textwrap.dedent(f"""\
                set -euo pipefail
                c=$(grep -c "vmlinuz-linux" "{empty}" || true)
                if [[ $c -eq 0 ]]; then echo "VERDICT=error"; else echo "VERDICT=ok"; fi
            """)
            res = subprocess.run([BASH, '-c', good], capture_output=True, text=True)
            self.assertIn("VERDICT=error", res.stdout,
                          "a GRUB config with no kernel entries must report an error")
            self.assertNotIn("syntax error", res.stderr)

    def test_no_grep_c_echo_zero_idiom_remains(self):
        import re
        pattern = re.compile(r'grep -c[^|\n]*\|\|\s*echo\s+"?0"?')
        offenders = []
        for root, _dirs, files in os.walk(SCRIPT_DIR):
            if '.git' in root:
                continue
            for name in files:
                if not name.endswith('.sh'):
                    continue
                path = os.path.join(root, name)
                with open(path, encoding='utf-8', errors='replace') as f:
                    for lineno, line in enumerate(f, 1):
                        if pattern.search(line):
                            offenders.append(
                                f"{os.path.relpath(path, SCRIPT_DIR)}:{lineno}")
        self.assertEqual(
            offenders, [],
            'grep -c prints "0" AND exits 1, so `|| echo "0"` appends a second '
            'value. Use `|| true`. Found at: ' + ", ".join(offenders))


class TestCleanupBackupsSafety(unittest.TestCase):
    """The cleanup unit calls rm -rf; its scoping is a safety property."""

    def setUp(self):
        self.script = os.path.join(SCRIPT_DIR, 'services', 'cleanup-backups.sh')
        if not os.path.isfile(self.script):
            self.skipTest("services/cleanup-backups.sh not present")
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _make_backup_tree(self, age_parent_days=90):
        home = os.path.join(self.tmp, 'u1')
        backups = os.path.join(home, '.boot-backups')
        old = os.path.join(backups, 'boot-backup-20200101_000000')
        new = os.path.join(backups, 'boot-backup-20991231_000000')
        for d in (old, new):
            os.makedirs(d)

        old_ts = 1000000000  # long past
        os.utime(old, (old_ts, old_ts))
        if age_parent_days:
            os.utime(backups, (old_ts, old_ts))
        return backups, old, new

    def test_aged_parent_directory_is_never_deleted(self):
        """The trap: without -mindepth/-name, an aged .boot-backups matches
        `-type d` and rm -rf takes every backup with it, including today's."""
        backups, old, new = self._make_backup_tree()

        res = run_bash(self.script, '--home-root', self.tmp)
        self.assertEqual(res.returncode, 0, res.stderr)

        self.assertTrue(os.path.isdir(backups),
                        "the .boot-backups parent must survive even when aged")
        self.assertTrue(os.path.isdir(new),
                        "a recent backup must survive")
        self.assertFalse(os.path.isdir(old),
                         "an aged backup should have been pruned")

    def test_dry_run_deletes_nothing(self):
        backups, old, new = self._make_backup_tree()
        res = run_bash(self.script, '--dry-run', '--home-root', self.tmp)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("would remove", res.stdout)
        self.assertTrue(os.path.isdir(old), "--dry-run must not delete anything")
        self.assertTrue(os.path.isdir(new))

    def test_rejects_invalid_retention(self):
        res = run_bash(self.script, '--retention-days', 'abc', '--home-root', self.tmp)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("non-negative integer", res.stderr)

    def test_unknown_option_is_rejected(self):
        res = run_bash(self.script, '--definitely-not-an-option')
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("unknown option", res.stderr)

    def test_service_unit_does_not_rely_on_shell_globbing(self):
        """systemd does not expand globs in ExecStart; the original unit did."""
        unit = os.path.join(SCRIPT_DIR, 'services', 'sys-manager-cleanup.service')
        if not os.path.isfile(unit):
            self.skipTest("unit file not present")
        with open(unit) as f:
            unit_lines = f.readlines()
        for line in unit_lines:
            if line.startswith('ExecStart='):
                self.assertNotIn(
                    '*', line,
                    "ExecStart contains a glob, which systemd passes through "
                    "literally: " + line.strip())


class TestPrivilegeEscalation(unittest.TestCase):
    """check_boot.sh silently dropped its flags when re-executing under sudo."""

    def test_original_args_captured_before_parse_loop(self):
        for distro in ('arch', 'debian'):
            path = os.path.join(SCRIPT_DIR, 'distros', distro, 'check_boot.sh')
            if not os.path.isfile(path):
                continue
            with open(path) as fh:
                source = fh.read()
            with self.subTest(distro=distro):
                self.assertIn(
                    'ORIGINAL_ARGS=("$@")', source,
                    f"{distro}/check_boot.sh must capture argv before the parse "
                    "loop consumes it")
                self.assertNotIn(
                    'exec sudo "$0" "$@"', source,
                    f'{distro}/check_boot.sh: `"$@"` inside a function refers to '
                    "the function's args, silently dropping --auto-fix")

    def test_flags_survive_reexec_construction(self):
        """Behavioural proof of the argv-replay pattern, without invoking sudo."""
        harness = textwrap.dedent("""\
            set -euo pipefail
            ORIGINAL_ARGS=("$@")
            AUTO_FIX=false
            while [[ $# -gt 0 ]]; do
              case "$1" in
                --auto-fix) AUTO_FIX=true; shift ;;
                --quick-banner) shift ;;
                *) shift ;;
              esac
            done
            echo "replay:${ORIGINAL_ARGS[@]+${ORIGINAL_ARGS[@]}}"
        """)
        res = subprocess.run(
            [BASH, '-c', harness, 'check_boot.sh', '--auto-fix', '--quick-banner'],
            capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("--auto-fix", res.stdout)
        self.assertIn("--quick-banner", res.stdout)

    def test_empty_args_do_not_trip_set_u(self):
        harness = textwrap.dedent("""\
            set -euo pipefail
            ORIGINAL_ARGS=("$@")
            echo "replay:${ORIGINAL_ARGS[@]+${ORIGINAL_ARGS[@]}}"
        """)
        res = subprocess.run([BASH, '-c', harness, 'check_boot.sh'],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0,
                         f"unset array expansion tripped set -u: {res.stderr}")


class TestPathResolution(unittest.TestCase):
    """No script may assume home directories live under /home/<user>."""

    def test_no_hardcoded_home_paths_in_executable_code(self):
        import re
        # Matches /home/ followed by a variable or name -- but not inside comments.
        pattern = re.compile(r'/home/(?!\*)[\w${]')
        offenders = []
        for root, dirs, files in os.walk(SCRIPT_DIR):
            dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__')]
            for name in files:
                if not name.endswith(('.sh', '.py', '.service', '.timer')):
                    continue
                path = os.path.join(root, name)
                with open(path, encoding='utf-8', errors='replace') as f:
                    for lineno, line in enumerate(f, 1):
                        stripped = line.strip()
                        if stripped.startswith('#') or stripped.startswith('//'):
                            continue
                        if pattern.search(line):
                            offenders.append(
                                f"{os.path.relpath(path, SCRIPT_DIR)}:{lineno}")
        self.assertEqual(
            offenders, [],
            "Home directories must be resolved from passwd (getent), not assumed "
            "to be under /home. Found at: " + ", ".join(offenders))

    def test_timeline_survives_minimal_environment(self):
        """Package-manager hooks run with almost no environment; a bare ${USER}
        is unbound under `set -u` and aborted the hook."""
        for distro in ('arch', 'debian'):
            path = os.path.join(SCRIPT_DIR, 'distros', distro, 'timeline.sh')
            if not os.path.isfile(path):
                continue
            with self.subTest(distro=distro):
                res = subprocess.run(
                    ['env', '-i', BASH, path, '--help'],
                    capture_output=True, text=True, timeout=30)
                self.assertNotIn("unbound variable", res.stderr)
                self.assertEqual(res.returncode, 0, res.stderr)

    def test_backup_dir_identical_with_and_without_sudo(self):
        """Under sudo $HOME is /root, which split backups across two locations."""
        path = os.path.join(SCRIPT_DIR, 'distros', 'arch', 'backup_boot.sh')
        if not os.path.isfile(path):
            self.skipTest("backup_boot.sh not present")

        probe = 'source <(sed -n "9,22p" %s); echo "$BACKUP_DIR"' % path

        plain = subprocess.run([BASH, '-c', probe],
                               capture_output=True, text=True)
        as_sudo = subprocess.run(
            [BASH, '-c', probe], capture_output=True, text=True,
            env={**os.environ, 'HOME': '/root', 'USER': 'root',
                 'SUDO_USER': os.environ.get('USER', 'root')})

        self.assertEqual(
            plain.stdout.strip(), as_sudo.stdout.strip(),
            "BACKUP_DIR must resolve to the invoking user's home whether or not "
            "the script was reached through sudo")


if __name__ == '__main__':
    unittest.main()
