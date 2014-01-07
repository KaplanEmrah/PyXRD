#  Author: Roberto Cavada <roboogle@gmail.com>
#
#  Copyright (c) 2005 by Roberto Cavada
#
#  pygtkmvc is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 2 of the License, or (at your option) any later version.
#
#  pygtkmvc is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor,
#  Boston, MA 02110, USA.
#
#  For more information on pygtkmvc see <http://pygtkmvc.sourceforge.net>
#  or email to the author Roberto Cavada <roboogle@gmail.com>.
#  Please report bugs to <roboogle@gmail.com>.

import types

from collections import OrderedDict

from pyxrd.gtkmvc.support.object_pool import ThreadedObjectPool
from pyxrd.gtkmvc.support.propintel import PropIntel, OptionPropIntel
from pyxrd.gtkmvc.support import wrappers
from pyxrd.gtkmvc.support.log import logger

from pyxrd.generic.utils import get_unique_list, get_new_uuid


# ----------------------------------------------------------------------

OBS_TUPLE_NAME = "properties"

# This keeps the names of all observable properties (old and new)
ALL_OBS_SET = "all_properties"

# these are the names of the internal maps associating logical
# properties names to their getters/setters
LOGICAL_GETTERS_MAP_NAME = "_getdict"
LOGICAL_SETTERS_MAP_NAME = "_setdict"


class PropertyMeta (type):
    """This is a meta-class that provides auto-property support.
    The idea is to allow programmers to define some properties which
    will be automatically connected to auto-generated code which handles
    access to those properties.
    How can you use this meta-class?
    First, '__metaclass__ = PropertyMeta' must be class member of the class
    you want to make the automatic properties handling.
    Second, '__properties__' must be a map containing the properties names
    as keys, values will be initial values for properties.
    That's all: after the instantiation, your class will contain all properties
    you named inside '__properties__'. Each of them will be also associated
    to a couple of automatically-generated functions which get and set the
    property value inside a generated member variable.
    About names: suppose the property is called 'x'.  The generated variable
    (which keeps the real value of the property x) is called _x.
    The getter is called get_prop_x(self), and the setter is called
    'set_prop_x(self, value)'.

    Customization:
    The base implementation of getter is to return the value stored in the
    variable associated to the property. The setter simply sets its value.
    Programmers can override basic behavior for getters or setters simply by
    defining their getters and setters (see at the names convention above).
    The customized function can lie everywhere in the user classes hierarchy.
    Every overridden function will not be generated by the metaclass.

    To supply your own methods is good for few methods, but can result in a
    very uncomfortable way for many methods. In this case you can extend
    the meta-class, and override methods get_[gs]etter_source with your
    implementation (this can be probably made better).
    An example is provided in meta-class PropertyMetaVerbose below.
    """

    # ------------------------------------------------------------
    #      Type creation:
    # ------------------------------------------------------------
    def __init__(cls, name, bases, _dict):
        """class constructor"""
        res = type.__init__(cls, name, bases, _dict)
        cls.process_properties(name, bases, _dict)
        return res

    def _expand_properties(cls, properties, _dict):  # @NoSelf
        for prop in properties:
            # Check prop is really a PropIntel sub-class:
            if not isinstance(prop, PropIntel):
                raise TypeError("In class %s.%s.Meta attribute '%s' must contain"\
                                    " only PropIntel instances (found %s)" %
                                (cls.__module__, cls.__name__, OBS_TUPLE_NAME,
                                 type(prop)))

            # Determine if the property is concrete or logical:
            concrete = cls.is_concrete_attribute(prop)

            # Get the default value:
            default = cls.get_default_value(prop, concrete=concrete, _dict=_dict)

            # Check to see if there's some plumbing to do:
            new_properties = cls.expand_property(prop, default, _dict)

            # If the expansion generated some new properties,
            # expand (& add any new generated props) as well:
            for new_prop in cls._expand_properties(new_properties, _dict):
                yield new_prop

            # Wrap property setters and getters:
            cls.wrap_accesors(prop, default)

            # Yield this property:
            yield prop

    def process_properties(cls, name, bases, _dict):  # @NoSelf
        """Processes the properties defined in the class's metadata class."""

        # Get the list of properties for this class type (excluding bases):
        try:
            meta = _dict["Meta"]
        except KeyError:
            if len(bases) == 1:
                meta = type("Meta", (bases[0].Meta,), dict(properties=[]))
                cls.set_attribute(_dict, "Meta", meta)
            else:
                raise TypeError("PropertyMeta class %s.%s has not defined a Meta class, and has multiple base classes!" % (cls.__module__, cls.__name__))
        properties = get_unique_list(meta.properties)

        # Check the list of observables is really an iterable:
        if not isinstance(properties, types.ListType):
            raise TypeError("In class %s.%s.Meta attribute '%s' must be a list, not '%s'" %
                            (cls.__module__, cls.__name__, OBS_TUPLE_NAME, type(properties)))

        # Generates the list of _all_ properties available for this class's bases
        all_properties = OrderedDict()
        # Reverse order of the bases:
        for class_type in bases[::-1]:
            # Loop over properties, and update the dictionary:
            if hasattr(class_type, "Meta"):
                for prop in getattr(class_type.Meta, ALL_OBS_SET, []):
                    all_properties[prop.name] = prop

        # Parse & expand the properties:

        for prop in cls._expand_properties(properties, _dict):
            all_properties[prop.name] = prop

        # Set the attribute on the metadata class:
        setattr(cls.Meta, ALL_OBS_SET, all_properties.values())

        logger.debug("Class %s.%s has properties: %s" \
                     % (cls.__module__, cls.__name__, all_properties))

        pass # end of method

    def wrap_accesors(cls, prop, default): # @NoSelf
        """
            Method that creates getter and setter, and the
            corresponding property.
            If an optional default_val is passed to attribute is considered
            concrete and not logical, and a private attribute (prepended
            with an underscore) will be generated.
            If this is not the case, attribute is considered logical, and no
            private attribute is set. This causes values that need to be wrapped
            to only become wrapped when (re)set for the first time.
        """

        getter_name = "_wrapped_get_%s" % prop.name
        setter_name = "_wrapped_set_%s" % prop.name

        # Generate the getter wrapper:
        _getter = cls.wrap_getter(prop)
        setattr(cls, getter_name, _getter)

        # Generate the setter wrapper:
        _setter = cls.wrap_setter(prop)
        setattr(cls, setter_name, _setter)

        # Creates the property
        _property = property(getattr(cls, getter_name), getattr(cls, setter_name))
        setattr(cls, prop.name, _property)

        # Wrap the underlying variable if needed
        # (e.g. if it's a list, tuple, dict, or other mutable class):
        varname = prop.private_name_format % { 'prop_name' : prop.name }
        default_found, default = default
        if default_found:
            default = cls.create_value(varname, default)
            setattr(cls, varname, default)

    def is_concrete_attribute(cls, prop): # @NoSelf
        """This methods returns True if there exists a class attribute
        for the given property. The attribute is searched locally
        only"""
        return (cls.__dict__.has_key(prop.name) and
                type(cls.__dict__[prop.name]) != types.FunctionType)

    def get_default_value(cls, prop, concrete=False, _dict={}):  # @NoSelf
        """This method returns a default value for the given PropIntel.
        There are three ways a default value can be defined, depending:
         - by setting a default value in the PropIntel
         - if it's a concrete property: the current (public)value
         - if it's a logical property: by getting the private attribute 
           '_%{prop_name}s' if this exists
        If the property is concrete, the concrete flag should be set to True and
        the (local) dictionary should be passed to this method.
        If no default value is defined anywhere, None is returned.
        """
        if hasattr(prop, "default"):
            return True, prop.default
        elif concrete:
            return True, _dict[prop.name]
        elif hasattr(cls, prop.get_private_name()):
            return True, getattr(cls, prop.get_private_name())
        else:
            return False, None

    def check_value_change(cls, old, new): # @NoSelf
        """Checks whether the value of the property changed in type
        or if the instance has been changed to a different instance.
        If true, a call to model._reset_property_notification should
        be called in order to re-register the new property instance
        or type"""
        return  type(old) != type(new) or \
               isinstance(old, wrappers.ObsWrapperBase) and (old != new)

    def set_attribute(cls, _dict, name, value): # @NoSelf
        """Sets an attribute on the class and the dict"""
        _dict[name] = value
        setattr(cls, name, value)

    def del_attribute(cls, _dict, name): # @NoSelf
        """Deletes an attribute from the class and the dict"""
        del _dict[name]
        delattr(cls, name)

    def create_value(cls, prop, val, model=None): # @NoSelf
        """This is used to wrap a value to be assigned to a
        property. Depending on the type of the value, different values
        are created and returned. For example, for a list, a
        ListWrapper is created to wrap it, and returned for the
        assignment. model is different from None when the value is
        changed (a model exists). Otherwise, during property creation
        model is None"""

        if isinstance(val, tuple):
            # this might be a class instance to be wrapped
            # (thanks to Tobias Weber for
            # providing a bug fix to avoid TypeError (in 1.99.1)
            if len(val) == 3:
                try:
                    wrap_instance = isinstance(val[1], val[0]) and \
                        (isinstance(val[2], tuple) or
                         isinstance(val[2], list))
                except TypeError:
                    pass # not recognized, it must be another type of tuple
                else:
                    if wrap_instance:
                        res = wrappers.ObsUserClassWrapper(val[1], val[2])
                        if model: res.__add_model__(model, prop.name)
                        return res
                    pass
                pass
            pass

        elif isinstance(val, list):
            res = wrappers.ObsListWrapper(val)
            if model: res.__add_model__(model, prop.name)
            return res

        elif isinstance(val, dict):
            res = wrappers.ObsMapWrapper(val)
            if model: res.__add_model__(model, prop.name)
            return res

        return val

    # ------------------------------------------------------------
    #               Services
    # ------------------------------------------------------------

    # Override these:
    def wrap_getter(cls, prop): # @NoSelf
        """
        Returns a (wrapped) getter function. This allows for metaclasses
        that need to catch get or set calls for e.g. notifying observers.
        
        prop_name is the name off the property.
        """
        if type(cls).is_concrete_attribute(cls, prop):
            # We have a concrete property, so we can use the default getattr.
            # Subtle difference is that we prepend the attribute name with
            # an underscore. This attribute is set in the
            # __create_property_wrapper__ function.
            def _getter(self):
                return getattr(self, prop.get_private_name())
        else:
            # The concrete property does not exist, so we're falling back to
            # a logical getter. If that's not available an error is raised:
            _getter = getattr(cls, prop.get_getter_name())
        return _getter


    def wrap_setter(cls, prop): # @NoSelf
        """
        Similar to wrap_getter, but for wrapping setters.
        """
        if type(cls).is_concrete_attribute(cls, prop):
            # We have a concrete property, so we can use the default setattr.
            # Subtle difference is that we prepend the attribute name with
            # an underscore. This attribute is set in the
            # __create_property_wrapper__ function.
            def _setter(self, value):
                return setattr(self, prop.get_private_name(), value)
        else:
            # The concrete property does not exist, so we're falling back to
            # a logical getter. If that's not available return None:
            _setter = getattr(cls, prop.get_setter_name(), None)

        return _setter

    def expand_property(cls, prop, default, _dict):  # @NoSelf
        """
            This method is called for each property before its
            setter and getter have been wrapped. This allows
            to 'expand' certain compact representations of common idioms, such
            as properties which can only have a value from a list of options,
            special business logic, ...
            
            This method can also return an iterable containing 'additional'
            PropIntel objects generated from the passed one.
        """
        if isinstance(prop, OptionPropIntel):
            pr_prop = prop.get_private_name()
            pr_optn = "%ss" % pr_prop
            getter_name = prop.get_getter_name()
            setter_name = prop.get_setter_name()

            # Set private attribute on the class:
            found_default, default = default
            if found_default:
                cls.set_attribute(_dict, pr_prop, default)
            else:
                cls.set_attribute(_dict, pr_prop, prop.options.values()[0])
            # Set option list on the class:
            cls.set_attribute(_dict, pr_optn, prop.options)

            # Get the getters & setters:
            existing_getter = getattr(cls, getter_name, None)
            existing_setter = getattr(cls, setter_name, None)

            # Wrap them & reset them:
            getter, setter = prop.__create_accesors__(pr_prop, existing_getter, existing_setter)
            cls.set_attribute(_dict, getter_name, getter)
            cls.set_attribute(_dict, setter_name, setter)

        return []



    pass # end of class
# ----------------------------------------------------------------------



class ObservablePropertyMeta (PropertyMeta):
    """
        Classes instantiated by this meta-class must provide a method named
        notify_property_change(self, prop_name, old, new).
    """

    def __init__(cls, name, bases, dict): # @NoSelf @ReservedAssignment
        PropertyMeta.__init__(cls, name, bases, dict)
        return

    def wrap_setter(cls, prop): # @NoSelf
        """The setter follows the rules of the getter. First search
        for property variable, then logical custom setter. If no
        setter is found, None is returned (i.e. the property is
        read-only.)"""

        _inner_setter = PropertyMeta.wrap_setter(cls, prop)
        _inner_getter = type(cls).wrap_getter(cls, prop)

        def _setter(self, val):
            # Get the old value
            old = _inner_getter(self)
            # Wrap the new value
            new = type(self).create_value(prop, val, self)
            # Set the new value
            _inner_setter(self, new)
            # Check if we've really changed it, and reset notifications if so:
            if type(self).check_value_change(old, new):
                self._reset_property_notification(prop, old)
                pass
            # Notify any interested party we have set this property!
            self.notify_property_value_change(prop.name, old, val)
            return
        return _setter

    pass # end of class
# ----------------------------------------------------------------------

class ObservablePropertyMetaMT (ObservablePropertyMeta):
    """This class provides multi-threading support for accessing
    properties, through a locking mechanism. It is assumed a lock is
    owned by the class that uses it. A Lock object called _prop_lock
    is assumed to be a member of the using class. see for example class
    ModelMT"""
    def __init__(cls, name, bases, _dict):  # @NoSelf
        ObservablePropertyMeta.__init__(cls, name, bases, _dict)
        return

    def get_setter(cls, prop): # @NoSelf
        """The setter follows the rules of the getter. First search
        for property variable, then logical custom getter/setter pair
        methods"""

        _inner_setter = ObservablePropertyMeta.get_setter(cls, prop.name)
        def _setter(self, val):
            with self._prop_lock:
                _inner_setter(self, val)
        return _setter

    pass # end of class
# ----------------------------------------------------------------------

class UUIDMeta(ObservablePropertyMetaMT):
    """
        Classes instantiated by this meta-class will be registered in an 
        object pool using their UUID attributes.
    """

    object_pool = ThreadedObjectPool()

    def expand_property(cls, prop, default, _dict):  # @NoSelf
        """Expands the UUID property"""
        if prop.name == "uuid":
            # Set private property and create public property
            def get_uuid(self):
                """The unique user id (UUID) for this object"""
                return self._uuid
            cls.set_attribute(_dict, "get_uuid", get_uuid)
            def set_uuid(self, value):
                type(cls).object_pool.remove_object(self)
                self._uuid = value
                type(cls).object_pool.add_object(self)
            cls.set_attribute(_dict, "set_uuid", set_uuid)
            cls.set_attribute(_dict, "_uuid", None)
            return []
        else:
            # Nothing special to do:
            return ObservablePropertyMetaMT.expand_property(cls, prop, default, _dict)

    def __call__(cls, *args, **kwargs): # @NoSelf
        """
        This method checks if the passed kwargs contained a "uuid" key, if
        so it is popped, the class instance is created and the uuid is set on it.
        Instance is then returned. 
        """
        # Check if uuid has been passed (e.g. when restored from disk)
        # if not, generate a new one
        try:
            uuid = kwargs.pop("uuid")
        except KeyError:
            uuid = get_new_uuid()

        # Create instance:
        instance = ObservablePropertyMetaMT.__call__(cls, *args, **kwargs)

        # Set the UUID (will invoke above setter)
        instance.uuid = uuid

        return instance

    pass # end of class
# ----------------------------------------------------------------------

try:
    from gobject import GObjectMeta
    class ObservablePropertyGObjectMeta (ObservablePropertyMeta, GObjectMeta):
        pass
except:
    class ObservablePropertyGObjectMeta (ObservablePropertyMeta):
        pass
    pass
