# coding=UTF-8
# ex:ts=4:sw=4:et=on

# Copyright (c) 2013, Mathijs Dumon
# All rights reserved.
# Complete license can be found in the LICENSE file.

from traceback import print_exc

from base_models import BaseObjectListStore
from pyxrd.generic.models.observers import ListObserver, ListItemObserver
from weakref import WeakKeyDictionary
from pyxrd.generic.utils import not_none

try:
    import gobject, gtk
except ImportError:
    from pyxrd.generic.gtk_tools import dummy_gobject as gobject, dummy_gtk as gtk

class ObjectListStore(BaseObjectListStore):
    """
        GenericTreeModel implementation that wraps a python list of 
        ObjectListStoreChildMixin objects. In addition, it expects all objects 
        to be of a certain type, which needs to be passed to the __init__ as 
        the first argument. 
    """

    # PROPERTIES:
    @property
    def _data(self):
        return getattr(self._model, self._prop_name, None)

    def is_wrapping(self, model, prop_name):
        return self._model == model and self._prop_name == prop_name

    # ------------------------------------------------------------
    #      Initialization and other internals
    # ------------------------------------------------------------
    def __init__(self, class_type, model, prop_name):
        BaseObjectListStore.__init__(self, class_type)
        self._model = model
        self._prop_name = prop_name

        self._observer = ListObserver(
            self.on_item_inserted, self.on_item_deleted,
            on_deleted_before=self.on_item_deleted_before,
            prop_name=self._prop_name, model=self._model
        )

        self._list_item_observers = WeakKeyDictionary()
        for item in self._data:
            self._observe_item(item)

    def _observe_item(self, item):
        obs = ListItemObserver(self.on_item_changed, model=item)
        self._list_item_observers[item] = obs

    def _unobserve_item(self, item):
        observer = self._list_item_observers.get(item, None)
        if observer is not None: observer.clear()

    def on_item_changed(self, item):
        itr = self.create_tree_iter(item)
        path = self.get_path(itr)
        try:
            self.row_changed(path, itr)
        except TypeError:
            print "TypeError when emitting row_changed using:", path, itr
            raise

    def on_item_inserted(self, item):
        try:
            itr = self.create_tree_iter(item)
            path = self.get_path(itr)
            self._observe_item(item)
            self.row_inserted(path, itr)
        except ValueError:
            pass # invalid rowref

    _deleted_paths = []
    def on_item_deleted_before(self, item):
        self._unobserve_item(item)
        self._deleted_paths.append((self._data.index(item),))

    def on_item_deleted(self, item):
        for path in self._deleted_paths:
            self.row_deleted(path)
        self._deleted_paths = []

    # ------------------------------------------------------------
    #      Methods & Functions
    # ------------------------------------------------------------
    def on_get_iter(self, path):
        try:
            return self._data[path[0]]
        except IndexError:
            return None

    def on_get_path(self, rowref):
        try:
            return (self._data.index(rowref),)
        except ValueError:
            print "ValueError in on_get_path of %s caused by %s" % (self, rowref)
            print_exc()
            pass

    def set_value(self, itr, column, value):
        user_data = self.get_user_data(itr)
        setattr(user_data, self._columns[column][0], value)
        self.row_changed(self.get_path(itr), itr)

    def on_get_value(self, rowref, column):
        value = getattr(rowref, self._columns[column][0])
        try:
            default = self._columns[column][1]()
        except TypeError:
            default = ""
        return not_none(value, default)

    def on_iter_next(self, rowref):
        n, = self.on_get_path(rowref)
        try:
            return self._data[n + 1]
        except IndexError:
            pass

    def on_iter_children(self, rowref):
        if rowref:
            return None
        if self._data:
            return self.on_get_iter((0,))
        return None

    def on_iter_has_child(self, rowref):
        if rowref:
            return False
        if len(self._data) > 0:
            return True
        return False

    def on_iter_n_children(self, rowref):
        if rowref:
            return 0
        return len(self._data)

    def on_iter_nth_child(self, parent, n):
        if parent:
            return None
        if n < 0 or n >= len(self._data):
            return None
        return self._data[n]

    def on_iter_parent(self, rowref):
        return None

    pass # end of class

gobject.type_register(ObjectListStore)
