# coding=UTF-8
# ex:ts=4:sw=4:et=on

# Author: Mathijs Dumon
# This work is licensed under the Creative Commons Attribution-ShareAlike 3.0 Unported License. 
# To view a copy of this license, visit http://creativecommons.org/licenses/by-sa/3.0/ or send
# a letter to Creative Commons, 444 Castro Street, Suite 900, Mountain View, California, 94041, USA.

from generic.views import DialogView

class ProjectView(DialogView):
    title = "Edit Project"
    subview_builder = "project/glade/project.glade"
    subview_toplevel = "nbk_edit_project"
    resizable = False
    
    __widgets_to_hide__ = (
        "project_display_calc_color",
        "lbl_calccolor")
