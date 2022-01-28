"""
Copyright 2022 epiccakeking

This file is part of epiccakeking_journal.

epiccakeking_journal is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your option) any later
version.

epiccakeking_journal is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
epiccakeking_journal. If not, see <https://www.gnu.org/licenses/>.
"""
import string

from gi.repository import Gtk
from pkg_resources import resource_string

letters = set(string.ascii_letters)


def strip_non_letters(s):
    for start, c in enumerate(s):
        if c in letters:
            break
    for end in range(len(s) - 1, start - 1, -1):
        if s[end] in letters:
            end += 1
            break
    return s[start:end]


def templated(c):
    return Gtk.Template(string=resource_string(__name__, f"ui/{c.__name__}.ui"))(c)
