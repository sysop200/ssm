#!/usr/bin/env python
#
# (C)2011 Red Hat, Inc., Lukas Czerner <lczerner@redhat.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Miscellaneous functions for use by System Storage Manager

import os
import re
import sys
import threading
import subprocess


def get_unit_size(string):
    """
    Check the last character of the string for the unit and return the unit
    value, otherwise return zero. It check only the last character of the
    string.

    >>> get_unit_size("B")
    1
    >>> get_unit_size("k")
    1024
    >>> get_unit_size("M")
    1048576
    >>> get_unit_size("g")
    1073741824
    >>> get_unit_size("T")
    1099511627776
    >>> get_unit_size("p")
    1125899906842624
    >>> get_unit_size("")
    0
    >>> get_unit_size("H")
    0
    """
    mult = 0
    units = {'B': 1, 'K': 2 ** 10, 'M': 2 ** 20, 'G': 2 ** 30, 'T': 2 ** 40,
             'P': 2 ** 50}
    if len(string) > 0 and string[-1].upper() in units:
        mult = units[string[-1].upper()]
    return mult


def is_number(string):
    """
    Check is the string is number and return True or False.

    >>> is_number("3.14")
    True
    >>> is_number("+3.14")
    True
    >>> is_number("-3.14")
    True
    >>> is_number("314")
    True
    >>> is_number("3a14")
    False
    """
    try:
        float(string)
        return True
    except ValueError:
        return False


def get_real_size(size):
    '''
    Get the real number from the size argument. It converts the size with units
    into the size in kilobytes. Is no unit is specified it defaults to
    kilobytes.

    >>> get_real_size("3141")
    '3141'
    >>> get_real_size("3141K")
    '3141.00'
    >>> get_real_size("3141k")
    '3141.00'
    >>> get_real_size("3141M")
    '3216384.00'
    >>> get_real_size("3141G")
    '3293577216.00'
    >>> get_real_size("3141T")
    '3372623069184.00'
    >>> get_real_size("3141P")
    '3453566022844416.00'
    >>> get_real_size("3.14")
    '3.14'
    >>> get_real_size("+3.14")
    '+3.14'
    >>> get_real_size("-3.14")
    '-3.14'
    >>> get_real_size("3.14k")
    '3.14'
    >>> get_real_size("+3.14K")
    '+3.14'
    >>> get_real_size("-3.14k")
    '-3.14'
    >>> get_real_size("3.14G")
    '3292528.64'
    >>> get_real_size("+3.14g")
    '+3292528.64'
    >>> get_real_size("-3.14G")
    '-3292528.64'
    >>> get_real_size("G")
    Traceback (most recent call last):
    ...
    Exception: Not supported unit in the size 'G' argument.
    >>> get_real_size("3141H")
    Traceback (most recent call last):
    ...
    Exception: Not supported unit in the size '3141H' argument.
    '''
    if is_number(size):
        return size
    elif is_number(size[:-1]):
        # Always use kilobytes in ssm
        mult = get_unit_size(size) / 1024
        sign = '+' if size[0] == '+' else ''
        if mult:
            return '{0}{1:.2f}'.format(sign, float(size[:-1]) * mult)
    raise Exception("Not supported unit in the " + \
            "size \'{}\' argument.".format(size))


def check_binary(name):
    command = ['which', name]
    if run(command, can_fail=True)[0]:
        return False
    else:
        return True


def do_mount(device, directory, options=None):
    command = ['mount']
    if options:
        command.extend(['-o', ",".join(options)])
    command.extend([device, directory])
    run(command)


def get_fs_type(dev):
    command = ["blkid", "-c", "/dev/null", "-s", "TYPE", dev]
    output = run(command, can_fail=True)[1]

    m = re.search(r"TYPE=\"(?P<fstyp>\w+)\"", output)
    if m:
        fstype = m.group('fstyp')
        return fstype
    else:
        return ""


def get_real_device(device):
    if os.path.islink(device):
        return os.path.abspath(os.path.join(os.path.dirname(device),
            os.readlink(device)))
    else:
        return device


def get_swaps():
    swap = []
    with open('/proc/swaps', 'r') as f:
        for line in f.readlines()[1:]:
            swap.append(line.split())
    return swap


def get_partitions():
    partitions = []
    with open('/proc/partitions', 'r') as f:
        for line in f.readlines()[2:]:
            partitions.append(line.split())
    return partitions


def get_mounts(regex):
    mounts = {}
    reg = re.compile(regex)
    with open('/proc/mounts', 'r') as f:
        for line in f:
            m = reg.search(line)
            if m:
                l = line.split()[:2]
                dev = get_real_device(l[0])
                mounts[dev] = l[1]
    return mounts


def get_dmnumber(name):
    reg = re.compile(name)
    with open('/proc/devices', 'r') as f:
        for line in f:
            m = reg.search(line)
            if m:
                dmnumber = line.split()[0]
                break
    return dmnumber


def wipefs(device, typ):
    command = ['wipefs', '-p', device]
    output = run(command)[1]
    for line in output[1:].split('\n'):
        if not line:
            continue
        array = line.split(",")
        if array[-1] == typ:
            print "Wiping {0} signature from ".format(typ) + \
                  "the device {0}".format(device)
            command = ['wipefs', '--offset', array[0], device]
            run(command)


def humanize_size(arg):
    """
    Returns the number with power of two units "KiB, MiB, ...etc. Parameter arg
    should be string of non-zero length, or integer. IMPORTANT: The arg
    argument is expected to be in KiB.

    >>> humanize_size(314)
    '314.00 KB'
    >>> humanize_size("314")
    '314.00 KB'
    >>> humanize_size(314159)
    '306.80 MB'
    >>> humanize_size(314159265)
    '299.61 GB'
    >>> humanize_size(314159265358)
    '292.58 TB'
    >>> humanize_size(314159265358979)
    '285.73 PB'
    >>> humanize_size(314159265358979323)
    '279.03 EB'
    >>> humanize_size(314159265358979323846)
    '272.49 ZB'
    >>> humanize_size(314159265358979323846264)
    '266.10 YB'
    >>> humanize_size(314159265358979323846264338)
    '266103.25 YB'
    >>> humanize_size(-314159265)
    '-299.61 GB'
    >>> humanize_size("")
    ''
    >>> humanize_size("hello world")
    Traceback (most recent call last):
        ...
    ValueError: could not convert string to float: hello world
    """
    count = 0
    if type(arg) is str and len(arg) == 0:
        return ""
    size = float(arg)
    while abs(size) >= 1024 and count < 7:
        size /= 1024
        count += 1
    units = ["KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
    try:
        unit = units[count]
    except IndexError:
        unit = "???"
    return ("{0:.2f} {1}").format(size, unit)


def run(cmd, show_cmd=False, stdout=False, stderr=True, can_fail=False,
        stdin_data=None, return_stdout=True):
    command = "{delim}\nCOMMAND: \"{command}\"\n{delim}\n".format(
              command=" ".join(cmd), delim=("-" * (len(cmd) + 9)))
    if stdout:
        print command,

    stdin = None
    if stdin_data is not None:
        stdin = subprocess.PIPE

    if stderr:
        stderr = subprocess.STDOUT
    else:
        stderr = subprocess.PIPE

    if stdout:
        stdout = None
    else:
        stdout = subprocess.PIPE

    try:
        proc = subprocess.Popen(cmd, stdout=stdout,
                            stderr=stderr, stdin=stdin)
    except OSError, ex:
        print >> sys.stderr, \
            "Failure while executing \"{0}\"".format(" ".join(cmd))
        print >> sys.stderr, ex
        raise ex

    if stdin_data is not None:

        class StdinThread(threading.Thread):

            def run(self):
                proc.stdin.write(stdin_data)
                proc.stdin.close()
        stdin_thread = StdinThread()
        stdin_thread.daemon = True
        stdin_thread.start()

    output, error = proc.communicate()

    if stdin_data is not None:
        stdin_thread.join()

    err_msg = "ERROR running command: \"{0}\"".format(" ".join(cmd))
    if proc.returncode != 0 and show_cmd:
        if output:
            print output, error
        print >> sys.stderr, err_msg

    if proc.returncode != 0 and not can_fail:
        if output:
            print output, error
        raise RuntimeError(err_msg)

    if not return_stdout:
        output = None

    return (proc.returncode, output)
