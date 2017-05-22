import collections
import os
import sys
import pdb
#import apt_pkg

import ansible.modules.packaging.os.apt as apt_module
import pytest
apt = pytest.importorskip("apt")
apt_pkg = pytest.importorskip("apt_pkg")

from ansible.compat.tests import mock
from ansible.compat.tests import unittest

try:
    from ansible.modules.packaging.os.apt import (
        expand_pkgspec_from_fnmatches,
    )
except:
    # Need some more module_utils work (porting urls.py) before we can test
    # modules.  So don't error out in this case.
    if sys.version_info[0] >= 3:
        pass


class AptExpandPkgspecTestCase(unittest.TestCase):

    def setUp(self):
        FakePackage = collections.namedtuple("Package", ("name",))
        self.fake_cache = [ FakePackage("apt"),
                            FakePackage("apt-utils"),
                            FakePackage("not-selected"),
        ]

    def test_trivial(self):
        foo = ["apt"]
        self.assertEqual(
            expand_pkgspec_from_fnmatches(None, foo, self.fake_cache), foo)

    def test_version_wildcard(self):
        foo = ["apt=1.0*"]
        self.assertEqual(
            expand_pkgspec_from_fnmatches(None, foo, self.fake_cache), foo)

    def test_pkgname_wildcard_version_wildcard(self):
        foo = ["apt*=1.0*"]
        m_mock = mock.Mock()
        self.assertEqual(
            expand_pkgspec_from_fnmatches(m_mock, foo, self.fake_cache),
            ['apt', 'apt-utils'])

    def test_pkgname_expands(self):
        foo = ["apt*"]
        m_mock = mock.Mock()
        self.assertEqual(
            expand_pkgspec_from_fnmatches(m_mock, foo, self.fake_cache),
            ["apt", "apt-utils"])

class AptInstallationTestCase(unittest.TestCase):

    def setUp(self):
        FakePackage = collections.namedtuple("Package", ("name",))
        self.fake_cache = [ FakePackage("apt"),
                            FakePackage("apt-utils"),
                            FakePackage("apt-utils:x86_64"),
                            FakePackage("not-selected"),
        ]

    def test_install_right_package(self):
        """this is a simple test for installation of a couple of packages
        
        The test demonstrates that if two packages are given as
        arguments, dpkg will be called to install them.
        """

        m_mock = mock.Mock()
        debs = "apt, apt-utils" 
        force = False
        install_recommends = False
        allow_unauthenticated = False
        dpkg_options="fake-option"
        m_mock.run_command.side_effect = [ [ "0", "fake out", "fake error" ] ]
        apt_module.install_deb(m_mock, debs, self.fake_cache, force, install_recommends, 
                        allow_unauthenticated, dpkg_options)
        assert len(m_mock.run_command.call_args_list) > 0, "run command not called!"
        # it might be reasonable to call multiple commands during
        # package installation, however this test isn't ready to deal
        # with that.
        assert len(m_mock.run_command.call_args_list) == 1, "run command called multiple times - this test may be outdated" 
        command_args=m_mock.run_command.call_args_list[0][0][0]
        assert "dpkg" in command_args, "dpkg wasn't in run_command args"
        assert "apt" in command_args, "apt wasn't in run_command args"
        assert "apt-utils" in command_args, "apt-utils wasn't in run_command args"


    def test_install_right_package_with_architecture(self):

        """verify that we will install packages for alternate architectures
        
        This test simulates a request to install two packages which
        match the versions of packages on the system, but where one
        package (apt) comes from a different architecture from the one
        currently installed and so should be installed even so.
        """

        # Given that I am asked to install two packages
        m_mock = mock.Mock()
        debs = "apt.deb, apt-utils.deb" 
        DebPackage_double = mock.Mock()
        force = False
        install_recommends = False
        allow_unauthenticated = False
        dpkg_options = "fake-option"
        m_mock.get_bin_path.return_value = "/usr/fakebin/dpkg" 

        # and that I have more than one architecture on my system
        get_architectures_double = mock.Mock(return_value=[ "i386", "x86_64" ])
        # and that the versions of the modules match those installed
        # but one package (apt) has a different architecture from the installed version
        #   N.B. we hardwire a call dpkg once for each package to get the architecture
        #        then once to install the missing packages
        m_mock.run_command.side_effect = [ 
            # 'apt'
            [ 0, "apt", "fake err" ],[ 0, "10101", "fake err" ],[ 0, "i386", "fake err" ],  
            # 'apt-utils'
            [ 0, "apt-utils", "fake err" ],[ 0, "1901", "fake err" ], [ 0, "x86_64", "fake err" ],  
            # result from actual install 
            [ 0, "fake out", "fake error" ] 
        ]
        apt_cache_double=mock.MagicMock(spec=apt.Cache)
        package_double = apt_cache_double()["nokey"]
        installed_package_double = package_double.installed
        version_property=mock.PropertyMock(side_effect=[
            None,  "1901"
        ])
        type(installed_package_double).version = version_property
        # When I ask the apt module to install those packages

        with mock.patch.object(apt_pkg, 'get_architectures', get_architectures_double):
            with mock.patch.object(apt.debfile, 'DebPackage', DebPackage_double):
                with mock.patch.object(apt, 'Cache', apt_cache_double):
                    apt_module.install_deb(m_mock, debs, self.fake_cache, force, install_recommends, 
                                           allow_unauthenticated, dpkg_options)

        # Then the installation function should check our architectures
        assert len(get_architectures_double.call_args_list) > 0, "didn't check for system architectures"

        # and should check the architecture of each package to be installed
        assert len(m_mock.run_command.call_args_list) > 0, "run command not called - dpkg needed!"
        assert len(m_mock.run_command.call_args_list) > 6, "run command not called for each package!"

        package_lookup_mock=apt_cache_double().__getitem__
        package_lookup_mock.assert_has_calls([mock.call("apt:i386"),mock.call("apt-utils:x86_64")])

        # and the final command should install only the alternate architecture package.
        assert len(m_mock.run_command.call_args_list) == 7, "didn't get expected call sequence"
        command_args=m_mock.run_command.call_args_list[6][0][0]
        assert "dpkg" in command_args, "dpkg wasn't in run_command args"
        assert "-i" in command_args, "-i missing argument to dpgk when install mode when expected"
        assert "apt" in command_args, "apt wasn't in run_command args when install expected"
        assert "apt-utils" not in command_args, "apt-utils was installed when should be skipped"
