#!/usr/bin/env python3
import os
import sys
import unittest
import json
import importlib.util
from unittest.mock import patch, mock_open, MagicMock

# Import the orchestrator and installer modules dynamically since their filenames contain hyphens or clash
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

import types

# Import linux-system-manager.sh (manually compile since importlib doesn't auto-load .sh files as python)
sys_manager = types.ModuleType("sys_manager")
sys_manager.__file__ = os.path.join(SCRIPT_DIR, "linux-system-manager.sh")
with open(sys_manager.__file__, 'r') as f:
    source_code = f.read()
code_obj = compile(source_code, sys_manager.__file__, 'exec')
exec(code_obj, sys_manager.__dict__)
sys.modules["sys_manager"] = sys_manager

# Import install.py
install_spec = importlib.util.spec_from_file_location("install", os.path.join(SCRIPT_DIR, "install.py"))
install = importlib.util.module_from_spec(install_spec)
install_spec.loader.exec_module(install)

class TestSysManager(unittest.TestCase):

    @patch('os.path.exists')
    @patch('os.path.isdir')
    def test_detect_distro_exact_match(self, mock_isdir, mock_exists):
        # Setup mocks
        mock_exists.return_value = True
        mock_isdir.side_effect = lambda path: 'arch' in path
        
        os_release_content = 'ID=arch\nNAME="Arch Linux"\nID_LIKE="usr-defined"'
        
        with patch('builtins.open', mock_open(read_data=os_release_content)):
            distro_id, distro_name = sys_manager.detect_distro()
            self.assertEqual(distro_id, 'arch')
            self.assertEqual(distro_name, 'Arch Linux')

    @patch('os.path.exists')
    @patch('os.path.isdir')
    def test_detect_distro_fallback_match(self, mock_isdir, mock_exists):
        # Setup mocks
        mock_exists.return_value = True
        # ID is fedora, but we only have 'rhel' folder in our mock
        mock_isdir.side_effect = lambda path: 'rhel' in path
        
        os_release_content = 'ID=fedora\nNAME="Fedora Linux"\nID_LIKE="rhel centos"'
        
        with patch('builtins.open', mock_open(read_data=os_release_content)):
            distro_id, distro_name = sys_manager.detect_distro()
            self.assertEqual(distro_id, 'rhel')
            self.assertEqual(distro_name, 'Fedora Linux')

    @patch('os.path.exists')
    @patch('os.path.isdir')
    def test_detect_distro_unsupported(self, mock_isdir, mock_exists):
        mock_exists.return_value = True
        mock_isdir.return_value = False # No folders exist
        
        os_release_content = 'ID=ubuntu\nNAME="Ubuntu"'
        
        with patch('builtins.open', mock_open(read_data=os_release_content)):
            distro_id, distro_name = sys_manager.detect_distro()
            self.assertIsNone(distro_id)
            self.assertEqual(distro_name, 'Ubuntu')

    @patch('os.path.exists')
    def test_load_menu_success(self, mock_exists):
        mock_exists.return_value = True
        menu_json_content = '{"distro_id": "arch", "sections": []}'
        
        with patch('builtins.open', mock_open(read_data=menu_json_content)):
            data = sys_manager.load_menu('arch')
            self.assertEqual(data['distro_id'], 'arch')
            self.assertEqual(data['sections'], [])

    def test_render_menu_mapping(self):
        menu_data = {
            "sections": [
                {
                    "id": "1",
                    "title": "Test Section",
                    "items": [
                        {"key": "a", "label": "Test A", "exec": "a.sh"},
                        {"key": "b", "label": "Test B", "exec": "b.sh"}
                    ]
                }
            ]
        }
        
        # Patch print to suppress output during test
        with patch('builtins.print'):
            action_map = sys_manager.render_menu(menu_data, "Test Distro")
            
        self.assertIn("1a", action_map)
        self.assertIn("1b", action_map)
        self.assertEqual(action_map["1a"]["label"], "Test A")
        self.assertEqual(action_map["1b"]["exec"], "b.sh")

    @patch('os.path.exists')
    @patch('os.access')
    @patch('subprocess.run')
    @patch('builtins.input', return_value='')
    def test_run_action_success(self, mock_input, mock_run, mock_access, mock_exists):
        mock_exists.return_value = True
        mock_access.return_value = True
        mock_run.return_value = MagicMock(returncode=0)
        
        item = {"key": "a", "label": "Test A", "exec": "test.sh", "args": ["--arg"]}
        
        with patch('builtins.print'):
            sys_manager.run_action('arch', item)
            
        # Verify subprocess was called correctly
        self.assertTrue(mock_run.called)
        args, kwargs = mock_run.call_args
        self.assertTrue(args[0][0].endswith('test.sh'))
        self.assertIn('--arg', args[0])


class TestInstaller(unittest.TestCase):

    @patch('os.geteuid', return_value=0) # Simulated root user
    @patch('os.path.isdir')
    @patch('os.listdir')
    @patch('shutil.copy2')
    @patch('os.chmod')
    @patch('subprocess.run')
    def test_install_systemd_services(self, mock_run, mock_chmod, mock_copy, mock_listdir, mock_isdir, mock_geteuid):
        mock_isdir.return_value = True
        mock_listdir.return_value = ['test.service']
        
        # Suppress printing during tests
        with patch('builtins.print'):
            install.install_systemd_services()
        
        # Verify copy was attempted
        self.assertTrue(mock_copy.called)
        args, kwargs = mock_copy.call_args
        self.assertEqual(args[1], '/etc/systemd/system/test.service')
        
        # Verify systemd daemon-reload was triggered
        self.assertTrue(mock_run.called)
        self.assertEqual(mock_run.call_args[0][0], ['systemctl', 'daemon-reload'])

    @patch('os.path.exists', return_value=True)
    @patch('os.access', return_value=True)
    @patch('subprocess.run')
    def test_run_distro_installer(self, mock_run, mock_access, mock_exists):
        mock_run.return_value = MagicMock(returncode=0)
        
        with patch('builtins.print'):
            install.run_distro_installer('arch')
        
        self.assertTrue(mock_run.called)
        args, kwargs = mock_run.call_args
        self.assertTrue(args[0][0].endswith('install_hooks.sh'))


if __name__ == '__main__':
    unittest.main()
