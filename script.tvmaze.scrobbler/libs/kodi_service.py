# coding: utf-8
# (c) Roman Miroshnychenko <roman1972@gmail.com> 2020
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Classes and functions to interact with Kodi API"""

from __future__ import absolute_import, unicode_literals

import hashlib
import inspect
import os
import re
import sys
from contextlib import contextmanager
from platform import uname
from pprint import pformat

import six
from six.moves import cPickle as pickle
from kodi_six import xbmc
from kodi_six.xbmcaddon import Addon

try:
    from typing import Text, Dict, Callable, Generator  # pylint: disable=unused-import
except ImportError:
    pass


ADDON = Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_VERSION = ADDON.getAddonInfo('version')
ADDON_PROFILE_DIR = xbmc.translatePath(ADDON.getAddonInfo('profile'))
ADDON_DIR = xbmc.translatePath(ADDON.getAddonInfo('path'))
ADDON_ICON = xbmc.translatePath(ADDON.getAddonInfo('icon'))

if not os.path.exists(ADDON_PROFILE_DIR):
    os.mkdir(ADDON_PROFILE_DIR)


class logger(object):  # pylint: disable=invalid-name
    # pylint: disable=missing-docstring
    FORMAT = '{id} [v.{version}] - {filename}:{lineno} - {message}'

    @classmethod
    def _write_message(cls, message, level=xbmc.LOGDEBUG):
        # type: (Text, int) -> None
        curr_frame = inspect.currentframe()
        xbmc.log(
            cls.FORMAT.format(
                id=ADDON_ID,
                version=ADDON_VERSION,
                filename=os.path.basename(curr_frame.f_back.f_back.f_code.co_filename),
                lineno=curr_frame.f_back.f_back.f_lineno,
                message=message
            ),
            level
        )

    @classmethod
    def info(cls, message):
        # type: (Text) -> None
        cls._write_message(message, xbmc.LOGINFO)

    @classmethod
    def warning(cls, message):
        # type: (Text) -> None
        cls._write_message(message, xbmc.LOGWARNING)

    @classmethod
    def error(cls, message):
        # type: (Text) -> None
        cls._write_message(message, xbmc.LOGERROR)

    @classmethod
    def debug(cls, message):
        # type: (Text) -> None
        cls._write_message(message, xbmc.LOGDEBUG)


class LocalizationService(object):
    """Emulate GNU Gettext by mapping English UI strings to their numeric string IDs"""

    class LocalizationError(Exception):  # pylint: disable=missing-docstring
        pass

    def __init__(self):
        # type: () -> None
        self._en_gb_string_po_path = os.path.join(
            ADDON_DIR, 'resources', 'language', 'resource.language.en_gb', 'strings.po'
        )
        if not os.path.exists(self._en_gb_string_po_path):
            raise self.LocalizationError('Missing English strings.po localization file')
        self._string_mapping_path = os.path.join(ADDON_PROFILE_DIR, 'strings-map.pickle')
        self._mapping = self._load_strings_mapping()  # type: Dict[Text, int]

    def _load_strings_po(self):  # pylint: disable=missing-docstring
        # type: () -> bytes
        with open(self._en_gb_string_po_path, 'rb') as fo:
            return fo.read()

    def _load_strings_mapping(self):
        # type: () -> Dict[Text, int]
        """
        Load mapping of English UI strings to their IDs

        If a mapping file is missing or English strins.po file has been updated,
        a new mapping file is created.

        :return: UI strings mapping
        """
        strings_po = self._load_strings_po()
        strings_po_md5 = hashlib.md5(strings_po).hexdigest()
        try:
            with open(self._string_mapping_path, 'rb') as fo:
                mapping = pickle.load(fo)
            if mapping['md5'] != strings_po_md5:
                raise IOError('English strings.po has been updated')
        except IOError:
            strings_mapping = self._parse_strings_po(strings_po.decode('utf-8'))
            mapping = {
                'strings': strings_mapping,
                'md5': strings_po_md5,
            }
            with open(self._string_mapping_path, 'wb') as fo:
                pickle.dump(mapping, fo, protocol=2)
        return mapping['strings']

    @staticmethod
    def _parse_strings_po(strings_po):
        # type: (Text) -> Dict[Text, int]
        """
        Parse English strings.po file contents into a mapping of UI strings
        to their numeric IDs.

        :param strings_po: the content of strings.po file as a text string
        :return: UI strings mapping
        """
        id_string_pairs = re.findall(r'^msgctxt "#(\d+?)"\r?\nmsgid "(.*)"\r?$', strings_po, re.M)
        return {string: int(string_id) for string_id, string in id_string_pairs if string}

    def gettext(self, en_string):
        # type: (Text) -> Text
        """
        Return a localized UI string by an English source string

        :param en_string: English UI string
        :return: localized UI string
        """
        try:
            string_id = self._mapping[en_string]
        except KeyError:
            raise self.LocalizationError(
                'Unable to find English string "{}" in strings.po'.format(en_string))
        return ADDON.getLocalizedString(string_id)


GETTEXT = LocalizationService().gettext


def _format_vars(variables):
    # type: (dict) -> Text
    """
    Format variables dictionary

    :param variables: variables dict
    :return: formatted string with sorted ``var = val`` pairs
    """
    var_list = [(var, val) for var, val in six.iteritems(variables)
                if not (var.startswith('__') or var.endswith('__'))]
    var_list.sort(key=lambda i: i[0])
    lines = []
    for var, val in var_list:
        lines.append('{} = {}'.format(var, pformat(val)))
    return '\n'.join(lines)


def _format_code_context(frame_info):
    # type: (tuple) -> Text
    context = ''
    if frame_info[4] is not None:
        for i, line in enumerate(frame_info[4], frame_info[2] - frame_info[5]):
            if i == frame_info[2]:
                context += '{}:>{}'.format(six.text_type(i).rjust(5), line)
            else:
                context += '{}: {}'.format(six.text_type(i).rjust(5), line)
    return context


EXCEPTION_TEMPLATE = """
*********************************** Unhandled exception detected ***********************************
====================================================================================================
                                           Diagnostic info
----------------------------------------------------------------------------------------------------
Exception type  : {exc_type}
Exception value : {exc}
System info     : {system_info}
Python version  : {python_version}
OS info         : {os_info}
Kodi version    : {kodi_version}
File            : {file_path}:{lineno}
sys.argv        : {sys_argv}
----------------------------------------------------------------------------------------------------
sys.path:
{sys_path}
----------------------------------------------------------------------------------------------------
Code context:
{code_context}
----------------------------------------------------------------------------------------------------
Global variables:
{global_vars}
----------------------------------------------------------------------------------------------------
Local variables:
{local_vars}
====================================================================================================
**************************************** End diagnostic info ***************************************
"""


@contextmanager
def debug_exception(logger_func=logger.error):
    # type: (Callable[[Text], None]) -> Generator[None, None, None]
    """
    Diagnostic helper context manager

    It controls execution within its context and writes extended
    diagnostic info to the Kodi log if an unhandled exception
    happens within the context. The info includes the following items:

    - System info
    - Python version
    - Kodi version
    - Module path.
    - Code fragment where the exception has happened.
    - Global variables.
    - Local variables.

    After logging the diagnostic info the exception is re-raised.

    Example::

        with debug_exception():
            # Some risky code
            raise RuntimeError('Fatal error!')

    :param logger_func: logger function that accepts a single argument
        that is a log message.
    """
    try:
        yield
    except Exception as exc:
        frame_info = inspect.trace(5)[-1]
        message = EXCEPTION_TEMPLATE.format(
            exc_type=type(exc),
            exc=exc,
            system_info=uname(),
            python_version=sys.version.replace('\n', ' '),
            os_info=xbmc.getInfoLabel('System.OSVersionInfo'),
            kodi_version=xbmc.getInfoLabel('System.BuildVersion'),
            file_path=frame_info[1],
            lineno=frame_info[2],
            sys_argv=pformat(sys.argv),
            sys_path=pformat(sys.path),
            code_context=_format_code_context(frame_info),
            global_vars=_format_vars(frame_info[0].f_globals),
            local_vars=_format_vars(frame_info[0].f_locals)
        )
        logger_func(message)
        raise exc
