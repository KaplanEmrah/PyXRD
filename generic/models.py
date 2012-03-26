# coding=UTF-8
# ex:ts=4:sw=4:et=on

# Author: Mathijs Dumon
# This work is licensed under the Creative Commons Attribution-ShareAlike 3.0 Unported License. 
# To view a copy of this license, visit http://creativecommons.org/licenses/by-sa/3.0/ or send
# a letter to Creative Commons, 444 Castro Street, Suite 900, Mountain View, California, 94041, USA.

import matplotlib
import matplotlib.transforms as transforms

import numpy as np

from gtkmvc import Observable
from gtkmvc.model import Model, Signal, ListStoreModel
from gtkmvc.support.metaclasses import ObservablePropertyMeta

from generic.treemodels import XYListStore
from generic.io import Storable, PyXRDDecoder

class CSVMixin():
    
    __csv_storables__ = [] #list of tuples "label", "property_name"

    @classmethod
    def save_as_csv(type, filename, items):
        import csv
        atl_writer = csv.writer(open(filename, 'wb'), delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)      
        labels, props = zip(*type.__csv_storables__)
        atl_writer.writerow(labels)
        for item in items:
            prop_row = []
            for prop in props:
                prop_row.append(getattr(item, prop))
            atl_writer.writerow(prop_row)
           
    @classmethod 
    def get_from_csv(type, filename, callback = None):
        import csv
        atl_reader = csv.reader(open(filename, 'rb'), delimiter=',', quotechar='"')
        labels, props = zip(*type.__csv_storables__)
        header = True
        items = []
        for row in atl_reader:
            if not header:
                kwargs = dict()
                for i, prop in enumerate(props):
                    kwargs[prop] = row[i]
                new_item = type(**kwargs)
                if callback is not None and callable(callback):
                    callback(new_item)
                items.append(new_item)
            header = False
        return items

class ObjectListStoreChildMixin():
    
    __list_store__ = None
        
    def liststore_item_changed(self):
        if self.__list_store__ != None:
            self.__list_store__.on_item_changed(self)

class ChildModel(Model):



    #SIGNALS:
    removed = Signal()
    added = Signal()

    #PROPERTIES:
    _parent = None
    @Model.getter("parent")
    def get_parent(self, prop_name):
        return self._parent
    @Model.setter("parent")
    def set_parent(self, prop_name, value):
        self._unattach_parent()
        self._parent = value
        self._attach_parent()

    __observables__ = ["parent",]

    #CONSTRUCTOR
    def __init__(self, parent=None):
        Model.__init__(self)
        self.parent = parent

    #METHODS & FUNCTIONS:        
    def _unattach_parent(self):
        if self.parent != None:
            self.removed.emit()
    
    def _attach_parent(self):
        if self.parent != None:
            self.added.emit()

class XYData(Model, Storable, Observable):
    xy_empty_data = ([0,0],[0,0])
    line = None
    
    xy_data = None

    _data_name = "XYData"    
    @Model.getter("data_name")
    def get_data_name(self, prop_name):
        return self._data_name
    @Model.setter("data_name")
    def set_data_name(self, prop_name, value):
        self._data_name = value
        self.line.set_label(self.data_label)

    _data_label = "%(name)s"
    @Model.getter("data_label")
    def get_data_label(self, prop_name):
        return self._data_label % { 'name': self._data_name }
    @Model.setter("data_label")
    def set_data_label(self, prop_name, value):
        self._data_label = value
        self.line.set_label(self.data_label)
    
    _display_offset = 0
    @Model.getter("display_offset")
    def get_display_offset(self, prop_name):
        return self._display_offset
    @Model.setter("display_offset")
    def set_display_offset(self, prop_name, value):
        if value != self._display_offset:
            self._display_offset = value
            self.update_data()
    
    
    _bg_position = 0
    bg_line = None
    @Model.getter("bg_position")
    def get_bg_position(self, prop_name):
        return self._bg_position
    @Model.setter("bg_position")
    def set_bg_position(self, prop_name, value):
        value = float(value)
        if value != self._bg_position:
            self._bg_position = value
            self.plot_update.emit()

    _bg_type = 0
    _bg_types = { 0: "Linear" } #TODO add more types
    @Model.getter("bg_type")
    def get_bg_type(self, prop_name):
        return self._bg_type
    @Model.setter("bg_type")
    def set_bg_type(self, prop_name, value):
        value = int(value)
        if value in self._bg_types: 
            self._bg_type = value      
        else:
            raise ValueError, "'%s' is not a valid value for a background type!" % value
    
    plot_update = None
    data_update = None
    
    __observables__ = ["data_name", "data_label", "xy_data", "plot_update", "data_update", "display_offset", "bg_position", "bg_type"]
    __storables__ = [val for val in __observables__ if not val in ("plot_update", "data_update", "display_offset", "bg_position", "bg_type") ] + ["color",]
       
    @property
    def color(self):
        return self.line.get_color()
    @color.setter
    def color(self, color):
        if self.color != color:
            self.line.set_color(color)
            if self.line.get_visible() and self.line.get_axes() != None:
                self.plot_update.emit()
       
    def __init__(self, data_name=None, data_label=None, xy_data=None, color="#0000FF", **kwargs):
        Model.__init__(self)
        Storable.__init__(self)
        Observable.__init__(self)
        self.plot_update = Signal()
        self.data_update = Signal()
        self._data_name = data_name or self._data_name
        self._data_label = data_label or self._data_label
        self.line = matplotlib.lines.Line2D(*self.xy_empty_data, label=self.data_label, color=color, aa=True)
        self.xy_data = xy_data or XYListStore()
        self.update_data()
    
    @staticmethod
    def from_json(data_name=None, data_label=None, xy_data=None, color=None, **kwargs):
        xy_data = PyXRDDecoder.__pyxrd_decode__(xy_data)
        return XYData(data_name=data_name, data_label=data_label, xy_data=xy_data, color=color)
            
    def update_data(self, silent=False):
        if len(self.xy_data._model_data_x) > 1:
            data = np.array(zip(self.xy_data._model_data_x, self.xy_data._model_data_y))
            if self._display_offset != 0:
                trans = transforms.Affine2D().translate(0, self._display_offset)
                data = trans.transform(data)
            self.line.set_data(np.transpose(data))
            self.line.set_visible(True)
        else:
            self.line.set_data(self.xy_empty_data)
            self.line.set_visible(False)
        if not silent: self.data_update.emit()
    
    def clear(self, update=True):
        self.xy_data.clear()
        if update: self.update_data()
    
    def on_update_plot(self, figure, axes, pctrl):
        self.update_data()
        
        #Add pattern
        lines = axes.get_lines()
        if not self.line in lines:
            axes.add_line(self.line)
            
        #Add bg line (if present)
        try:
            self.bg_line.remove()
        except:
            pass
        if self._bg_position != 0.0:
            self.bg_line = axes.axhline(y=self.bg_position, c="#660099")
        else:
            self.bg_line = None
    
    def remove_background(self):
        y_data = self.xy_data._model_data_y
        print y_data
        if self.bg_type == 0:
            y_data = np.maximum((y_data - self.bg_position) / (1.0 - self.bg_position), 0.0)
        print y_data
        self.xy_data._model_data_y = y_data
        self.bg_position = 0
        self.update_data()
        
    def find_bg(self):
        y_min = np.min(self.xy_data._model_data_y)
        self.bg_position = y_min
            
    def load_data(self, data, format="DAT", has_header=True, clear=True, silent=False):
        xydata = []
        max_y = 0.0
    
        if clear:
            self.clear(update=False)    

        if format=="DAT":
            if has_header:
                header, data = data.split("\n", 1)
            for i, line in enumerate(data.split("\n")):
                if line != "": #i is not 0 and 
                    x, y = map(float, line.split())
                    max_y = max(y, max_y)
                    xydata.append((x,y))
        if format=="BIN":
            import struct
            #open file
            f = None
            close = False
            if type(data) is file:
                f = data
            elif type(data) is str:
                f = open(data, 'rb')
                close = True
            else:
                raise TypeError, "Wrong data type supplied for binary format, must be either file or string, but %s was given" % type(data)
            if f != None:
                #seek data limits
                f.seek(214)
                stepx, minx, maxx = struct.unpack("ddd", f.read(24))
                nx = int((maxx-minx)/stepx)
                #read values                          
                f.seek(250)
                n = 0
                xydata = []
                while n < nx:
                    y, = struct.unpack("H", f.read(2))
                    max_y = max(y, max_y)
                    xydata.append((minx + stepx*n, float(y)))
                    n += 1
                #close file
                if close: f.close()
            
        #import data            
        if xydata != []:
            for x, y in xydata:
                self.xy_data.append(x, y / max_y )
            
        self.update_data(silent=silent)

