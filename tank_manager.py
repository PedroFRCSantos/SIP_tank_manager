#!/usr/bin/env python

# Python 2/3 compatibility imports
from __future__ import print_function

# standard library imports
import json
from threading import Thread, Lock

# local module imports
from blinker import signal
import gv  # Get access to SIP's settings, gv = global variables
from sip import template_render
from urls import urls  # Get access to SIP's URLs
import web
from webpages import ProtectedPage

try:
    from db_logger import db_logger_read_definitions
    from db_logger_generic_table import create_generic_table, add_date_generic_table
    withDBLogger = True
except ImportError:
    withDBLogger = False


# Add a new url to open the data entry page.
# fmt: off
urls.extend(
    [
        u"/tankman", u"plugins.tank_manager.tank_home",
        u"/tankmaset", u"plugins.tank_manager.tank_settings",
    ]
)
# fmt: on

# Add this plugin to the plugins menu
gv.plugin_menu.append([u"Tank Manager", u"/tankman"])

tankManager = {}

def load_commands():
    global tankManager
    try:
        with open(u"./data/advance_control.json", u"r") as f:
            tankManager = json.load(f)  # Read the commands from file
    except IOError:  #  If file does not exist create file with defaults.
        tankManager = {"Log2DB": True, u"pumpValves2Position": [], u"tankName": [], u"tankSaveEnergy": []}

class tank_settings(ProtectedPage):
    """Valve status"""

    def GET(self):
        global tankManager

        qdict = web.input()

        return template_render.tank_manager(tankManager)

class tank_home(ProtectedPage):
    """Valve status"""

    def GET(self):
        global tankManager

        qdict = web.input()

        return template_render.tank_manager(tankManager)
