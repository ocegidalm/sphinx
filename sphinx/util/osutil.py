# -*- coding: utf-8 -*-
"""
    sphinx.util.osutil
    ~~~~~~~~~~~~~~~~~~

    Operating system-related utility functions for Sphinx.

    :copyright: Copyright 2007-2018 by the Sphinx team, see AUTHORS.
    :license: BSD, see LICENSE for details.
"""
from __future__ import print_function

import contextlib
import errno
import filecmp
import os
import re
import shutil
import sys
import time
import warnings
from io import BytesIO, StringIO
from os import path

from six import text_type

from sphinx.deprecation import RemovedInSphinx30Warning, RemovedInSphinx40Warning

if False:
    # For type annotation
    from typing import Any, Iterator, List, Tuple, Union  # NOQA

# Errnos that we need.
EEXIST = getattr(errno, 'EEXIST', 0)
ENOENT = getattr(errno, 'ENOENT', 0)
EPIPE = getattr(errno, 'EPIPE', 0)
EINVAL = getattr(errno, 'EINVAL', 0)

# SEP separates path elements in the canonical file names
#
# Define SEP as a manifest constant, not so much because we expect it to change
# in the future as to avoid the suspicion that a stray "/" in the code is a
# hangover from more *nix-oriented origins.
SEP = "/"


def os_path(canonicalpath):
    # type: (unicode) -> unicode
    return canonicalpath.replace(SEP, path.sep)


def canon_path(nativepath):
    # type: (unicode) -> unicode
    """Return path in OS-independent form"""
    return nativepath.replace(path.sep, SEP)


def relative_uri(base, to):
    # type: (unicode, unicode) -> unicode
    """Return a relative URL from ``base`` to ``to``."""
    if to.startswith(SEP):
        return to
    b2 = base.split(SEP)
    t2 = to.split(SEP)
    # remove common segments (except the last segment)
    for x, y in zip(b2[:-1], t2[:-1]):
        if x != y:
            break
        b2.pop(0)
        t2.pop(0)
    if b2 == t2:
        # Special case: relative_uri('f/index.html','f/index.html')
        # returns '', not 'index.html'
        return ''
    if len(b2) == 1 and t2 == ['']:
        # Special case: relative_uri('f/index.html','f/') should
        # return './', not ''
        return '.' + SEP
    return ('..' + SEP) * (len(b2) - 1) + SEP.join(t2)


def ensuredir(path):
    # type: (unicode) -> None
    """Ensure that a path exists."""
    try:
        os.makedirs(path)
    except OSError:
        # If the path is already an existing directory (not a file!),
        # that is OK.
        if not os.path.isdir(path):
            raise


def walk(top, topdown=True, followlinks=False):
    # type: (unicode, bool, bool) -> Iterator[Tuple[unicode, List[unicode], List[unicode]]]
    warnings.warn('sphinx.util.osutil.walk() is deprecated for removal. '
                  'Please use os.walk() instead.',
                  RemovedInSphinx40Warning)
    return os.walk(top, topdown=topdown, followlinks=followlinks)


def mtimes_of_files(dirnames, suffix):
    # type: (List[unicode], unicode) -> Iterator[float]
    for dirname in dirnames:
        for root, dirs, files in os.walk(dirname):
            for sfile in files:
                if sfile.endswith(suffix):
                    try:
                        yield path.getmtime(path.join(root, sfile))
                    except EnvironmentError:
                        pass


def movefile(source, dest):
    # type: (unicode, unicode) -> None
    """Move a file, removing the destination if it exists."""
    if os.path.exists(dest):
        try:
            os.unlink(dest)
        except OSError:
            pass
    os.rename(source, dest)


def copytimes(source, dest):
    # type: (unicode, unicode) -> None
    """Copy a file's modification times."""
    st = os.stat(source)
    if hasattr(os, 'utime'):
        os.utime(dest, (st.st_atime, st.st_mtime))


def copyfile(source, dest):
    # type: (unicode, unicode) -> None
    """Copy a file and its modification times, if possible.

    Note: ``copyfile`` skips copying if the file has not been changed"""
    if not path.exists(dest) or not filecmp.cmp(source, dest):
        shutil.copyfile(source, dest)
        try:
            # don't do full copystat because the source may be read-only
            copytimes(source, dest)
        except OSError:
            pass


no_fn_re = re.compile(r'[^a-zA-Z0-9_-]')


def make_filename(string):
    # type: (str) -> unicode
    return no_fn_re.sub('', string) or 'sphinx'


def ustrftime(format, *args):
    # type: (unicode, Any) -> unicode
    """[DEPRECATED] strftime for unicode strings."""
    warnings.warn('sphinx.util.osutil.ustrtime is deprecated for removal',
                  RemovedInSphinx30Warning, stacklevel=2)

    if not args:
        # If time is not specified, try to use $SOURCE_DATE_EPOCH variable
        # See https://wiki.debian.org/ReproducibleBuilds/TimestampsProposal
        source_date_epoch = os.getenv('SOURCE_DATE_EPOCH')
        if source_date_epoch is not None:
            time_struct = time.gmtime(float(source_date_epoch))
            args = [time_struct]  # type: ignore
    # On Windows, time.strftime() and Unicode characters will raise UnicodeEncodeError.
    # https://bugs.python.org/issue8304
    try:
        return time.strftime(format, *args)  # type: ignore
    except UnicodeEncodeError:
        r = time.strftime(format.encode('unicode-escape').decode(), *args)  # type: ignore
        return r.encode().decode('unicode-escape')


def relpath(path, start=os.curdir):
    # type: (unicode, unicode) -> unicode
    """Return a relative filepath to *path* either from the current directory or
    from an optional *start* directory.

    This is an alternative of ``os.path.relpath()``.  This returns original path
    if *path* and *start* are on different drives (for Windows platform).
    """
    try:
        return os.path.relpath(path, start)
    except ValueError:
        return path


safe_relpath = relpath  # for compatibility
fs_encoding = sys.getfilesystemencoding() or sys.getdefaultencoding()  # type: unicode


def abspath(pathdir):
    # type: (unicode) -> unicode
    pathdir = path.abspath(pathdir)
    if isinstance(pathdir, bytes):
        try:
            pathdir = pathdir.decode(fs_encoding)
        except UnicodeDecodeError:
            raise UnicodeDecodeError('multibyte filename not supported on '  # type: ignore
                                     'this filesystem encoding '
                                     '(%r)' % fs_encoding)
    return pathdir


def getcwd():
    # type: () -> unicode
    warnings.warn('sphinx.util.osutil.getcwd() is deprecated. '
                  'Please use os.getcwd() instead.',
                  RemovedInSphinx40Warning)
    return os.getcwd()


@contextlib.contextmanager
def cd(target_dir):
    # type: (unicode) -> Iterator[None]
    cwd = os.getcwd()
    try:
        os.chdir(target_dir)
        yield
    finally:
        os.chdir(cwd)


class FileAvoidWrite:
    """File-like object that buffers output and only writes if content changed.

    Use this class like when writing to a file to avoid touching the original
    file if the content hasn't changed. This is useful in scenarios where file
    mtime is used to invalidate caches or trigger new behavior.

    When writing to this file handle, all writes are buffered until the object
    is closed.

    Objects can be used as context managers.
    """
    def __init__(self, path):
        # type: (unicode) -> None
        self._path = path
        self._io = None  # type: Union[StringIO, BytesIO]

    def write(self, data):
        # type: (Union[str, unicode]) -> None
        if not self._io:
            if isinstance(data, text_type):
                self._io = StringIO()
            else:
                self._io = BytesIO()

        self._io.write(data)  # type: ignore

    def close(self):
        # type: () -> None
        """Stop accepting writes and write file, if needed."""
        if not self._io:
            raise Exception('FileAvoidWrite does not support empty files.')

        buf = self.getvalue()
        self._io.close()

        r_mode = 'r'
        w_mode = 'w'
        if isinstance(self._io, BytesIO):
            r_mode = 'rb'
            w_mode = 'wb'

        old_content = None

        try:
            with open(self._path, r_mode) as old_f:
                old_content = old_f.read()
                if old_content == buf:
                    return
        except IOError:
            pass

        with open(self._path, w_mode) as f:
            f.write(buf)

    def __enter__(self):
        # type: () -> FileAvoidWrite
        return self

    def __exit__(self, type, value, traceback):
        # type: (unicode, unicode, unicode) -> None
        self.close()

    def __getattr__(self, name):
        # type: (str) -> Any
        # Proxy to _io instance.
        if not self._io:
            raise Exception('Must write to FileAvoidWrite before other '
                            'methods can be used')

        return getattr(self._io, name)


def rmtree(path):
    # type: (unicode) -> None
    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.remove(path)
