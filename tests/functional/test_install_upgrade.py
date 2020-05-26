import os
import sys
import textwrap

import pytest

from tests.lib import pyversion  # noqa: F401
from tests.lib import assert_all_changes
from tests.lib.local_repos import local_checkout


@pytest.mark.network
def test_no_upgrade_unless_requested(script):
    """
    No upgrade if not specifically requested.

    """
    script.pip('install', 'INITools==0.1')
    result = script.pip('install', 'INITools')
    assert not result.files_created, (
        'pip install INITools upgraded when it should not have'
    )


def test_invalid_upgrade_strategy_causes_error(script):
    """
    It errors out when the upgrade-strategy is an invalid/unrecognised one

    """
    result = script.pip_install_local(
        '--upgrade', '--upgrade-strategy=bazinga', 'simple',
        expect_error=True
    )

    assert result.returncode
    assert "invalid choice" in result.stderr


@pytest.mark.fails_on_new_resolver
def test_only_if_needed_does_not_upgrade_deps_when_satisfied(script):
    """
    It doesn't upgrade a dependency if it already satisfies the requirements.

    """
    script.pip_install_local('simple==2.0')
    result = script.pip_install_local(
        '--upgrade', '--upgrade-strategy=only-if-needed', 'require_simple'
    )

    assert (
        (script.site_packages / 'require_simple-1.0-py{pyversion}.egg-info'
            .format(**globals()))
        not in result.files_deleted
    ), "should have installed require_simple==1.0"
    assert (
        (script.site_packages / 'simple-2.0-py{pyversion}.egg-info'
            .format(**globals()))
        not in result.files_deleted
    ), "should not have uninstalled simple==2.0"
    assert (
        "Requirement already satisfied, skipping upgrade: simple"
        in result.stdout
    ), "did not print correct message for not-upgraded requirement"


def test_only_if_needed_does_upgrade_deps_when_no_longer_satisfied(script):
    """
    It does upgrade a dependency if it no longer satisfies the requirements.

    """
    script.pip_install_local('simple==1.0')
    result = script.pip_install_local(
        '--upgrade', '--upgrade-strategy=only-if-needed', 'require_simple'
    )

    assert (
        (script.site_packages / 'require_simple-1.0-py{pyversion}.egg-info'
            .format(**globals()))
        not in result.files_deleted
    ), "should have installed require_simple==1.0"
    expected = (
        script.site_packages /
        'simple-3.0-py{pyversion}.egg-info'.format(**globals())
    )
    result.did_create(expected, "should have installed simple==3.0")
    expected = (
        script.site_packages /
        'simple-1.0-py{pyversion}.egg-info'.format(**globals())
    )
    assert (
        expected in result.files_deleted
    ), "should have uninstalled simple==1.0"


def test_eager_does_upgrade_dependecies_when_currently_satisfied(script):
    """
    It does upgrade a dependency even if it already satisfies the requirements.

    """
    script.pip_install_local('simple==2.0')
    result = script.pip_install_local(
        '--upgrade', '--upgrade-strategy=eager', 'require_simple'
    )

    assert (
        (script.site_packages /
            'require_simple-1.0-py{pyversion}.egg-info'.format(**globals()))
        not in result.files_deleted
    ), "should have installed require_simple==1.0"
    assert (
        (script.site_packages /
            'simple-2.0-py{pyversion}.egg-info'.format(**globals()))
        in result.files_deleted
    ), "should have uninstalled simple==2.0"


def test_eager_does_upgrade_dependecies_when_no_longer_satisfied(script):
    """
    It does upgrade a dependency if it no longer satisfies the requirements.

    """
    script.pip_install_local('simple==1.0')
    result = script.pip_install_local(
        '--upgrade', '--upgrade-strategy=eager', 'require_simple'
    )

    assert (
        (script.site_packages /
            'require_simple-1.0-py{pyversion}.egg-info'.format(**globals()))
        not in result.files_deleted
    ), "should have installed require_simple==1.0"
    result.did_create(
        script.site_packages /
        'simple-3.0-py{pyversion}.egg-info'.format(**globals()),
        "should have installed simple==3.0"
    )
    assert (
        script.site_packages /
        'simple-1.0-py{pyversion}.egg-info'.format(**globals())
        in result.files_deleted
    ), "should have uninstalled simple==1.0"


@pytest.mark.network
def test_upgrade_to_specific_version(script):
    """
    It does upgrade to specific version requested.

    """
    script.pip('install', 'INITools==0.1')
    result = script.pip('install', 'INITools==0.2')
    assert result.files_created, (
        'pip install with specific version did not upgrade'
    )
    assert (
        script.site_packages / 'INITools-0.1-py{pyversion}.egg-info'
        .format(**globals())
        in result.files_deleted
    )
    result.did_create(
        script.site_packages / 'INITools-0.2-py{pyversion}.egg-info'
        .format(**globals())
    )


@pytest.mark.network
def test_upgrade_if_requested(script):
    """
    And it does upgrade if requested.

    """
    script.pip('install', 'INITools==0.1')
    result = script.pip('install', '--upgrade', 'INITools')
    assert result.files_created, 'pip install --upgrade did not upgrade'
    result.did_not_create(
        script.site_packages /
        'INITools-0.1-py{pyversion}.egg-info'.format(**globals())
    )


@pytest.mark.fails_on_new_resolver
def test_upgrade_with_newest_already_installed(script, data):
    """
    If the newest version of a package is already installed, the package should
    not be reinstalled and the user should be informed.
    """
    script.pip('install', '-f', data.find_links, '--no-index', 'simple')
    result = script.pip(
        'install', '--upgrade', '-f', data.find_links, '--no-index', 'simple'
    )
    assert not result.files_created, 'simple upgraded when it should not have'
    assert 'already up-to-date' in result.stdout, result.stdout


@pytest.mark.network
def test_upgrade_force_reinstall_newest(script):
    """
    Force reinstallation of a package even if it is already at its newest
    version if --force-reinstall is supplied.
    """
    result = script.pip('install', 'INITools')
    result.did_create(
        script.site_packages / 'initools',
        sorted(result.files_created.keys())
    )
    result2 = script.pip(
        'install', '--upgrade', '--force-reinstall', 'INITools'
    )
    assert result2.files_updated, 'upgrade to INITools 0.3 failed'
    result3 = script.pip('uninstall', 'initools', '-y')
    assert_all_changes(result, result3, [script.venv / 'build', 'cache'])


@pytest.mark.network
def test_uninstall_before_upgrade(script):
    """
    Automatic uninstall-before-upgrade.

    """
    result = script.pip('install', 'INITools==0.2')
    result.did_create(
        script.site_packages / 'initools',
        sorted(result.files_created.keys())
    )
    result2 = script.pip('install', 'INITools==0.3')
    assert result2.files_created, 'upgrade to INITools 0.3 failed'
    result3 = script.pip('uninstall', 'initools', '-y')
    assert_all_changes(result, result3, [script.venv / 'build', 'cache'])


@pytest.mark.network
def test_uninstall_before_upgrade_from_url(script):
    """
    Automatic uninstall-before-upgrade from URL.

    """
    result = script.pip('install', 'INITools==0.2')
    result.did_create(
        script.site_packages / 'initools',
        sorted(result.files_created.keys())
    )
    result2 = script.pip(
        'install',
        'https://files.pythonhosted.org/packages/source/I/INITools/INITools-'
        '0.3.tar.gz',
    )
    assert result2.files_created, 'upgrade to INITools 0.3 failed'
    result3 = script.pip('uninstall', 'initools', '-y')
    assert_all_changes(result, result3, [script.venv / 'build', 'cache'])


@pytest.mark.network
@pytest.mark.fails_on_new_resolver
def test_upgrade_to_same_version_from_url(script):
    """
    When installing from a URL the same version that is already installed, no
    need to uninstall and reinstall if --upgrade is not specified.

    """
    result = script.pip('install', 'INITools==0.3')
    result.did_create(
        script.site_packages / 'initools',
        sorted(result.files_created.keys())
    )
    result2 = script.pip(
        'install',
        'https://files.pythonhosted.org/packages/source/I/INITools/INITools-'
        '0.3.tar.gz',
    )
    assert script.site_packages / 'initools' not in result2.files_updated, (
        'INITools 0.3 reinstalled same version'
    )
    result3 = script.pip('uninstall', 'initools', '-y')
    assert_all_changes(result, result3, [script.venv / 'build', 'cache'])


@pytest.mark.network
def test_upgrade_from_reqs_file(script):
    """
    Upgrade from a requirements file.

    """
    script.scratch_path.joinpath("test-req.txt").write_text(textwrap.dedent("""\
        PyLogo<0.4
        # and something else to test out:
        INITools==0.3
        """))
    install_result = script.pip(
        'install', '-r', script.scratch_path / 'test-req.txt'
    )
    script.scratch_path.joinpath("test-req.txt").write_text(textwrap.dedent("""\
        PyLogo
        # and something else to test out:
        INITools
        """))
    script.pip(
        'install', '--upgrade', '-r', script.scratch_path / 'test-req.txt'
    )
    uninstall_result = script.pip(
        'uninstall', '-r', script.scratch_path / 'test-req.txt', '-y'
    )
    assert_all_changes(
        install_result,
        uninstall_result,
        [script.venv / 'build', 'cache', script.scratch / 'test-req.txt'],
    )


def test_uninstall_rollback(script, data):
    """
    Test uninstall-rollback (using test package with a setup.py
    crafted to fail on install).

    """
    result = script.pip(
        'install', '-f', data.find_links, '--no-index', 'broken==0.1'
    )
    result.did_create(
        script.site_packages / 'broken.py',
        list(result.files_created.keys())
    )
    result2 = script.pip(
        'install', '-f', data.find_links, '--no-index', 'broken===0.2broken',
        expect_error=True,
    )
    assert result2.returncode == 1, str(result2)
    assert script.run(
        'python', '-c', "import broken; print(broken.VERSION)"
    ).stdout == '0.1\n'
    assert_all_changes(
        result.files_after,
        result2,
        [script.venv / 'build'],
    )


@pytest.mark.network
def test_should_not_install_always_from_cache(script):
    """
    If there is an old cached package, pip should download the newer version
    Related to issue #175
    """
    script.pip('install', 'INITools==0.2')
    script.pip('uninstall', '-y', 'INITools')
    result = script.pip('install', 'INITools==0.1')
    result.did_not_create(
        script.site_packages /
        'INITools-0.2-py{pyversion}.egg-info'.format(**globals())
    )
    result.did_create(
        script.site_packages /
        'INITools-0.1-py{pyversion}.egg-info'.format(**globals())
    )


@pytest.mark.network
def test_install_with_ignoreinstalled_requested(script):
    """
    Test old conflicting package is completely ignored
    """
    script.pip('install', 'INITools==0.1')
    result = script.pip('install', '-I', 'INITools==0.3')
    assert result.files_created, 'pip install -I did not install'
    # both the old and new metadata should be present.
    assert os.path.exists(
        script.site_packages_path /
        'INITools-0.1-py{pyversion}.egg-info'.format(**globals())
    )
    assert os.path.exists(
        script.site_packages_path /
        'INITools-0.3-py{pyversion}.egg-info'.format(**globals())
    )


@pytest.mark.network
def test_upgrade_vcs_req_with_no_dists_found(script, tmpdir):
    """It can upgrade a VCS requirement that has no distributions otherwise."""
    req = "{checkout}#egg=pip-test-package".format(
        checkout=local_checkout(
            "git+https://github.com/pypa/pip-test-package.git", tmpdir,
        )
    )
    script.pip("install", req)
    result = script.pip("install", "-U", req)
    assert not result.returncode


@pytest.mark.network
def test_upgrade_vcs_req_with_dist_found(script):
    """It can upgrade a VCS requirement that has distributions on the index."""
    # TODO(pnasrat) Using local_checkout fails on windows - oddness with the
    # test path urls/git.
    req = (
        "{url}#egg=pretend".format(
            url=(
                "git+git://github.com/alex/pretend@e7f26ad7dbcb4a02a4995aade4"
                "743aad47656b27"
            ),
        )
    )
    script.pip("install", req, expect_stderr=True)
    result = script.pip("install", "-U", req, expect_stderr=True)
    assert "pypi.org" not in result.stdout, result.stdout


class TestUpgradeDistributeToSetuptools(object):
    """
    From pip1.4 to pip6, pip supported a set of "hacks" (see Issue #1122) to
    allow distribute to conflict with setuptools, so that the following would
    work to upgrade distribute:

     ``pip install -U  setuptools``

    In pip7, the hacks were removed.  This test remains to at least confirm pip
    can upgrade distribute to setuptools using:

      ``pip install -U distribute``

    The reason this works is that a final version of distribute (v0.7.3) was
    released that is simple wrapper with:

      install_requires=['setuptools>=0.7']

    The test use a fixed set of packages from our test packages dir. Note that
    virtualenv-1.9.1 contains distribute-0.6.34 and virtualenv-1.10 contains
    setuptools-0.9.7
    """

    def prep_ve(self, script, version, pip_src, distribute=False):
        self.script = script
        self.script.pip_install_local(
            'virtualenv=={version}'.format(**locals()))
        args = ['virtualenv', self.script.scratch_path / 'VE']
        if distribute:
            args.insert(1, '--distribute')
        if version == "1.9.1" and not distribute:
            # setuptools 0.6 didn't support PYTHONDONTWRITEBYTECODE
            del self.script.environ["PYTHONDONTWRITEBYTECODE"]
        self.script.run(*args)
        if sys.platform == 'win32':
            bindir = "Scripts"
        else:
            bindir = "bin"
        self.ve_bin = self.script.scratch_path / 'VE' / bindir
        self.script.run(self.ve_bin / 'pip', 'uninstall', '-y', 'pip')
        self.script.run(
            self.ve_bin / 'python', 'setup.py', 'install',
            cwd=pip_src,
            expect_stderr=True,
        )
