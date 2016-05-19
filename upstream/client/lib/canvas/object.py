#
# Copyright (C) 2013-2016   Ian Firns   <firnsy@kororaproject.org>
#                           Chris Smart <csmart@kororaproject.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import collections
import hashlib
import json

from pykickstart.base import KickstartCommand
from pykickstart.parser import Script
import pykickstart.constants


class ErrorInvalidObject(Exception):
    def __init__(self, reason, code=0):
        self.reason = reason.lower()
        self.code = code

        self._db = None

    def __str__(self):
        return 'error: {0}'.format(str(self.reason))

class Object(object):
    """ A Canvas object that represents a template Object. """

    # CONSTANTS
    MAP_OBJ_STRING_TO_SCRIPT_TYPE = {
        'ks-post':          pykickstart.constants.KS_SCRIPT_POST,
        'ks-pre':           pykickstart.constants.KS_SCRIPT_PRE,
        'ks-pre-install':   pykickstart.constants.KS_SCRIPT_PREINSTALL,
        'ks-traceback':     pykickstart.constants.KS_SCRIPT_TRACEBACK
    }

    MAP_SCRIPT_TYPE_TO_OBJ_STRING = {
        pykickstart.constants.KS_SCRIPT_PRE:        'ks-pre',
        pykickstart.constants.KS_SCRIPT_POST:       'ks-post',
        pykickstart.constants.KS_SCRIPT_TRACEBACK:  'ks-traceback',
        pykickstart.constants.KS_SCRIPT_PREINSTALL: 'ks-pre-install'
    }

    def __init__(self, name=None):
        self._name = None
        self._xsum = None
        self._data = None
        self._actions = []

        self._parse_object(name)

    def __eq__(self, other):
        if isinstance(other, Object):
            return (self._xsum == other._xsum)
        else:
            return False

    def __hash__(self):
        return self._xsum

    def __ne__(self, other):
        return (not self.__eq__(other))

    def __repr__(self):
        return 'Object: {0} (xsum: {1}, actions: {2})'.format(self._name, self._xsum[0:7], len(self._actions))

    def _from_ks_command(self, command):
        self._data = str(command)
        self._xsum = hashlib.sha256(self._data.encode('utf-8')).hexdigest()
        self._name = "ks-command-{0}".format(self._xsum[0:7])

        action = {
            'type':     'ks-command',
            'priority': command.writePriority,
            'command':  command.currentCmd,
        }

        self._actions = [action]

    def _from_ks_script(self, script):
        self._data = script.script
        self._xsum = hashlib.sha256(self._data.encode('utf-8')).hexdigest()
        self._name = "ks-script-{0}".format(self._xsum[0:7])

        type = self.MAP_SCRIPT_TYPE_TO_OBJ_STRING[script.type]

        action = {
            'type':          type,
            'interp':        script.interp,
            'in_chroot':     script.inChroot,
            'line_no':       script.lineno,
            'error_on_fail': script.errorOnFail,
        }

        self._actions = [action]

    def _parse_object(self, data):
        if (isinstance(data, Script)):
            self._from_ks_script(data)

        elif (isinstance(data, KickstartCommand)):
            self._from_ks_command(data)

        # parse the dict form, the most common form and directly
        # relates to the json structures returned by canvas server
        elif (isinstance(data, dict)):
            self._name = data.get('name', None)
            self._xsum = data.get('checksum', {}).get('sha256', None)
            self._actions = data.get('actions', [])
            self._data = data.get('data', None)

        # checksum is set confirm it equals the data
        if self._xsum is not None:
            if (self._data is None):
                raise ErrorInvalidObject('checksum defined without data')

            _xsum = hashlib.sha256(self._data.encode('utf-8')).hexdigest()

            if self._xsum != _xsum:
                raise ErrorInvalidObject("calculate checksum doesn't not match: {0} != {1}".format(_xsum, self._xsum))

    @property
    def actions(self):
        return self._actions

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, data):
        self._data = data
        self._xsum = hashlib.sha256(self._data.encode('utf-8')).hexdigest()

    @property
    def name(self):
        return self._name

    @property
    def xsum(self):
        return self._xsum

    #
    # PUBLIC METHODS
    def add_action(self, action):
        pass

    def is_ks_command():
        if len(self._actions) != 1:
            return None

        action = self._actions[0]
        type = action.get('type', '')

        # check we we're a ks-command
        return type == 'ks-command'

    def is_ks_script():
        if len(self._actions) != 1:
            return None

        action = self._actions[0]
        type = action.get('type', '')

        # check we we're a ks-script
        return type in self.MAP_OBJ_STRING_TO_SCRIPT_TYPES.keys()

    def to_ks_script():
        # kickstart scripts only have a single action
        if len(self._actions) != 1:
            return None

        action = self._actions[0]
        type = action.get('type', '')

        # check we contain ks-script
        if type not in self.MAP_OBJ_STRING_TO_SCRIPT_TYPES.keys():
            return None

        return pykickstart.parser.Script(self._data,
            errorOnFail = action.get('error_on_fail', None),
            interp      = action.get('interp', None),
            inChroot    = action.get('in_chroot', None),
            type        = self.MAP_OBJ_STRING_TO_SCRIPT_TYPES[type]
        )


    def to_object(self):
        return {
            'name': self._name,
            'data': self._data,
            'checksum': {
                'sha256': self._xsum
            },
            'action': self._actions
        }

    def to_json(self):
        return json.dumps(self.to_object(), separators=(',', ':'), sort_keys=True)


class ObjectSet(collections.MutableSet):
    def __init__(self, initvalue=()):
        self._set = []

        for x in initvalue:
            self.add(x)

    def __contains__(self, item):
        return item in self._set

    def __getitem__(self, index):
        return self._set[index]

    def __iter__(self):
        return iter(self._set)

    def __len__(self):
        return len(self._set)

    def __repr__(self):
        return "%s(%r)" % (type(self).__name__, self._set)

    def add(self, item):
        if not isinstance(item, Object):
            raise TypeError('Not an Object.')

        if item not in self._set:
            self._set.append(item)

    def discard(self, item):
        if not isinstance(item, Object):
            raise TypeError('Not an Object.')

        try:
            self._set.remove(item)

        except:
            pass

    def difference(self, other):
        if not isinstance(other, ObjectSet):
            raise TypeError('Not a ObjectSet.')

        uniq_self = ObjectSet()
        uniq_other = ObjectSet()

        # find unique items to self
        for x in self._set:
            if x not in other:
                uniq_self.add(x)

        # find unique items to other
        for x in other:
            if x not in self._set:
                uniq_other.add(x)

        return (uniq_self, uniq_other)

    def union(self, *args):
        if len(args) == 0:
            raise Exception('No ObjectSets defined for union.')

        u = RepoSet(self._set)

        for o in args:
            if not isinstance(o, ObjectSet):
                raise TypeError('Not a ObjectSet.')

            # add takes care of uniqueness so let's use it
            for x in o:
                u.add(x)

        return u

    def update(self, *args):
        for o in args:
            if not isinstance(o, ObjectSet):
                raise TypeError('Not a ObjectSet.')

            # add takes care of uniqueness so let's use it
            for x in o:
                self.add(x)
