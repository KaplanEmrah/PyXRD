# coding=UTF-8
# ex:ts=4:sw=4:et=on
#  -------------------------------------------------------------------------
#  Copyright (C) 2014 by Mathijs Dumon <mathijs dot dumon at gmail dot com>
#  Copyright (c) 2007 by Guillaume Libersat <glibersat AT linux62.org>
#  Copyright (C) 2005 by Roberto Cavada <roboogle@gmail.com>
#
#  mvc is a framework derived from the original pygtkmvc framework
#  hosted at: <http://sourceforge.net/projects/pygtkmvc/>
#
#  mvc is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 2 of the License, or (at your option) any later version.
#
#  mvc is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor,
#  Boston, MA 02110, USA.
#  -------------------------------------------------------------------------

# TODO remove gladeXML: deprecated!

from .support.exceptions import ViewError

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
Builder = Gtk.Builder

# ----------------------------------------------------------------------

class View (object):
    top = None
    builder = None

    def __init__(self, top=None,
                 parent=None,
                 builder=None, *args, **kwargs):
        """
        Only the first three may be given as positional arguments. If an
        argument is empty a class attribute of the same name is used. This
        does not work for *parent*.

        *builder* is a path to a Glade XML file.

        *top* is a string containing the name of our top level widget.

        *parent* is used to call :meth:`set_parent_view`.

        The last two only work if *builder* is used, not if you
        intend to create widgets later from code.
        """
        super(View, self).__init__(*args, **kwargs)

        self.manualWidgets = {}
        self.autoWidgets = {}
        self.__autoWidgets_calculated = False

        if top: self._top = top
        else: self._top = self.top

        # retrieves objects from builder if available
        if builder: _builder = builder
        else: _builder = self.builder
        if _builder is not None:
            # if the user passed a Builder, use it as it is, otherwise
            # build one
            if isinstance(_builder, Builder):
                self._builder = _builder
            else:
                self._builder = Gtk.Builder()
                self._builder.add_from_file(_builder)
                pass
            pass
        else: self._builder = None # no gtk builder

        if parent is not None: self.set_parent_view(parent)

        return

    def __getitem__(self, key):
        """
        Return the widget named *key*, or ``None``.
        
        .. note::
        
           In future versions this will likely change to raise ``KeyError``.
        """
        wid = None

        # first try with manually-added widgets:
        if key in self.manualWidgets:
            wid = self.manualWidgets[key]
            pass

        if wid is None:
            # then try with glade and builder, starting from memoized
            if key in self.autoWidgets: wid = self.autoWidgets[key]
            else:
                # try with Gtk.builder
                if wid is None and self._builder is not None:
                    wid = self._builder.get_object(key)
                    if wid is not None:
                        self.autoWidgets[key] = wid
                        pass
                    pass
                pass
            pass

        return wid

    def __setitem__(self, key, wid):
        """
        Add a widget. This overrides widgets of the same name that were loaded
        from XML. It does not affect GTK container/child relations.
        
        If no top widget is known, this sets it.
        """
        self.manualWidgets[key] = wid
        return

    def show(self):
        """
        Call `show()` on each top widget or `show_all()` if only one is known. 
        Otherwise does nothing.
        """
        top = self.get_top_widget()
        if type(top) in (list, tuple):
            for t in top:
                if t is not None: t.show()
                pass
        elif (top is not None): top.show_all()
        return


    def hide(self):
        """
        Call `hide()` on all known top widgets.
        """
        top = self.get_top_widget()
        if type(top) in (list, tuple):
            for t in top:
                if t is not None: t.hide()
                pass
        elif top is not None: top.hide()
        return

    def get_top_widget(self):
        return self[self._top]

    def set_parent_view(self, parent_view):
        """
        Set ``self.``:meth:`get_top_widget` transient for 
        ``parent_view.get_top_widget()``.
        """
        top = self.get_top_widget()
        if type(top) in (list, tuple):
            for t in top:
                if t is not None and hasattr(t, "set_transient_for"):
                    t.set_transient_for(parent_view.get_top_widget())
                    pass
                pass
        elif (top is not None) and hasattr(top, "set_transient_for"):
            top.set_transient_for(parent_view.get_top_widget())
            pass

        return

    def set_transient(self, transient_view):
        """
        Set ``transient_view.get_top_widget()`` transient for
        ``self.``:meth:`get_top_widget`.
        """
        top = self.get_top_widget()
        if type(top) in (list, tuple):
            for t in top:
                if t is not None:
                    transient_view.get_top_widget().set_transient_for(t)
                    pass
                pass
        elif (top is not None):
            transient_view.get_top_widget().set_transient_for(top)
            pass
        return

    # Finds the right callback for custom widget creation and calls it
    # Returns None if an undefined or invalid  handler is found
    def _custom_widget_create(self, glade, function_name, widget_name,
                              str1, str2, int1, int2):
        # This code was kindly provided by Allan Douglas <zalguod at
        # users.sourceforge.net>
        if function_name is not None:
            handler = getattr(self, function_name, None)
            if handler is not None: return handler(str1, str2, int1, int2)
            pass
        return None

    def __iter__(self):
        """
        Return an iterator over widgets added with :meth:`__setitem__` and
        those loaded from XML.
        
        .. note::
           In case of name conflicts this yields widgets that are not 
           accessible via :meth:`__getitem__`.
        """
        # precalculates if needed
        self.__extract_autoWidgets()

        import itertools
        for i in itertools.chain(self.manualWidgets, self.autoWidgets): yield i
        return

    def __extract_autoWidgets(self):
        """Extract autoWidgets map if needed, out of the glade
        specifications and gtk builder"""
        if self.__autoWidgets_calculated: return

        if self._builder is not None:
            for wid in self._builder.get_objects():
                # General workaround for issue
                # https://bugzilla.gnome.org/show_bug.cgi?id=607492
                try: name = Gtk.Buildable.get_name(wid)
                except TypeError: continue

                if name in self.autoWidgets and self.autoWidgets[name] != wid:
                    raise ViewError("Widget '%s' in builder also found in glade specification" % name)

                self.autoWidgets[name] = wid
                pass
            pass

        self.__autowidgets_calculated = True
        return

    pass # end of class View
