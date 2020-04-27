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

"""Functions to work with Kodi JSON-RPC API"""

from __future__ import absolute_import, unicode_literals

import json
from pprint import pformat

from kodi_six import xbmc

from .kodi_utils import logger

try:
    from typing import Text, Optional, List
except ImportError:
    pass


class NoDataError(Exception):
    pass


def send_json_rpc(method, params=None):
    # type: (Text, Optional[dict]) -> dict
    """
    Send JSON-RPC to Kodi
    """
    request = {'jsonrpc': '2.0', 'method': method, 'id': '1'}
    if params is not None:
        request['params'] = params
    logger.debug('JSON-RPC request:\n{0}'.format(pformat(request)))
    json_reply = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
    logger.debug('JSON-RPC reply:\n{0}'.format(pformat(json_reply)))
    return json_reply['result']


def get_tvshows():
    # type: () -> List[dict]
    """
    Get te list of TV shows from the Kodi database
    :return: the list of TV show data as Python dicts.
    :raises NoDataError: if the Kodi library has no TV shows

    Example TV show data::

        {u'label': u'Westworld',
         u'tvshowid': 45,
         u'uniqueid': {u'imdb': u'tt0475784',
                       u'tmdb': u'63247',
                       u'tvdb': u'296762'}}
    """
    params = {
        'properties': ['uniqueid'],
        'sort': {'order': 'ascending', 'method': 'label'}
    }
    result = send_json_rpc('VideoLibrary.GetTVShows', params)
    if not result.get('tvshows'):
        raise NoDataError('Kodi medialibrary has no TV shows')
    return result['tvshows']


def get_episodes(tvshowid):
    # type: (int) -> List[dict]
    """
    Get the list of episodes from a specific TV show

    :param tvshowid: internal Kodi database ID for a TV show
    :return: the list of episode data as Python dicts.
    :raises NoDataError: if a TV show has no episodes.

    Example episode data::

        {u'episode': 1,
         u'episodeid': 1043,
         u'label': u'3x01. Parce Domine',
         u'playcount': 3,
         u'season': 3,
         u'tvshowid': 45}
    """
    params = {
        'tvshowid': tvshowid,
        'properties': ['season', 'episode', 'playcount', 'tvshowid']
    }
    result = send_json_rpc('VideoLibrary.GetEpisodes', params)
    if not result.get('episodes'):
        raise NoDataError('TV show {} has no episodes'.format(tvshowid))
    return result['episodes']


def get_recent_episodes():
    # type: () -> List[dict]
    """
    Get the list of recently added episodes

    :return: the list of recent episodes
    :raises NoDataError: if the Kodi library has no recent episodes
    """
    params = {'properties': ['playcount', 'tvshowid', 'season', 'episode']}
    result = send_json_rpc('VideoLibrary.GetRecentlyAddedEpisodes', params)
    if not result.get('episodes'):
        raise NoDataError
    return result['episodes']


def get_episode_details(episode_id):
    # type: (int) -> dict
    """
    Get episode details

    :param episode_id: movie or episode Kodi database ID
    :return: item details
    """
    method = 'VideoLibrary.GetEpisodeDetails'
    params = {
        'episodeid': episode_id,
        'properties': ['playcount', 'tvshowid', 'season', 'episode', 'uniqueid']
    }
    return send_json_rpc(method, params)['episodedetails']


def set_episode_playcount(episode_id, playcount=1):
    # type: (int, int) -> None
    """
    Set episode playcount

    :param episode_id:
    :param playcount: 1 or 0
    """
    original_playcount = get_episode_details(episode_id)['playcount']
    if playcount != int(bool(original_playcount)):
        method = 'VideoLibrary.SetEpisodeDetails'
        params = {'episodeid': episode_id, 'playcount': playcount}
        send_json_rpc(method, params)