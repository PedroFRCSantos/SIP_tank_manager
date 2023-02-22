#!/usr/bin/env python

# Python 2/3 compatibility imports
from __future__ import print_function

# standard library imports
import json
from threading import Thread, Lock
import copy

# request HTTP
import requests

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
        u"/tanksaveset", u"plugins.tank_manager.tank_save_settings",
        u"/tankdelete", u"plugins.tank_manager.tank_delete_settings"
    ]
)
# fmt: on

# Add this plugin to the plugins menu
gv.plugin_menu.append([u"Tank Manager", u"/tankman"])

tankManager = {}
tackmanagerLock = Lock()

def load_commands():
    global tankManager

    tackmanagerLock.acquire()
    try:
        with open(u"./data/tank_manager.json", u"r") as f:
            tankManager = json.load(f)  # Read the commands from file
    except IOError:  #  If file does not exist create file with defaults.
        tankManager = {"Log2DB": True, u"PumpValves2Position": [], u"TankName": [], u"TankSaveEnergy": [], u"TankIpTop": [], u"TankDeviceTopType": [], u"TankIpMid": [], u"TankDeviceMidType": [], u"TankIpSOS": [], u"TankDeviceSOSType": [], u"PumpNeedOn": []}
    tackmanagerLock.release()

load_commands()

class tank_settings(ProtectedPage):
    """Valve status"""

    def GET(self):
        global tankManager, withDBLogger, tackmanagerLock

        qdict = web.input()

        addTank = 0
        if "AddTank" in qdict:
            addTank = 1

        listOfPumps = {}

        # ask with http request pumps exits
        try:
            if gv.sd['htip'] == '::':
                response = requests.get("http://127.0.0.1" + ":" + str(gv.sd['htp']) +"/advance-pump-list")
            else:
                response = requests.get("http://"+ str(gv.sd['htip']) + ":" + str(gv.sd['htp']) +"/advance-pump-list")
            listOfPumps = response.json()
        except:
            pass

        if "PumpName" not in listOfPumps:
            listOfPumps["PumpName"] = []

        tackmanagerLock.acquire()
        tankManagerLocal = copy.deepcopy(tankManager)
        tackmanagerLock.release()

        return template_render.tank_manager(tankManagerLocal, addTank, listOfPumps, withDBLogger)

class tank_save_settings(ProtectedPage):
    """Valve status"""

    def GET(self):
        global tankManager, tackmanagerLock

        qdict = web.input()

        localDefinitions = {}

        localDefinitions[u"Log2DB"] = u"pumpUseDB" in qdict

        numberOfTanks = 0
        for key in qdict:
            if len(key) > len("tankName") and key[:len("tankName")] == "tankName":
                numberOfTanks = numberOfTanks + 1

        localDefinitions[u"TankName"] = []

        localDefinitions[u"TankIpTop"] = []
        localDefinitions[u"TankDeviceTopType"] = []

        localDefinitions[u"TankIpMid"] = []
        localDefinitions[u"TankDeviceMidType"] = []

        localDefinitions[u"TankIpSOS"] = []
        localDefinitions[u"TankDeviceSOSType"] = []

        for i in range(numberOfTanks):
            # read tank name
            if "tankName" + str(i) in qdict:
                localDefinitions[u"TankName"].append(qdict["tankName" + str(i)])
            else:
                # fail, missing data in form
                web.seeother(u"/tankmaset")

            # read tank ip device top
            if "deviceIPTop" + str(i) in qdict:
                localDefinitions[u"TankIpTop"].append(qdict["deviceIPTop" + str(i)])
            else:
                # fail, missing data in form
                web.seeother(u"/tankmaset")

            # read tank device type top
            if "tankDeviceTop" + str(i) in qdict:
                localDefinitions[u"TankDeviceTopType"].append(qdict["tankDeviceTop" + str(i)])
            else:
                # fail, missing data in form
                web.seeother(u"/tankmaset")

            # read tank ip device middle
            if "deviceIPMid" + str(i) in qdict:
                localDefinitions[u"TankIpMid"].append(qdict["deviceIPMid" + str(i)])
            else:
                # fail, missing data in form
                web.seeother(u"/tankmaset")

            # read tank device type top
            if "tankDeviceMid" + str(i) in qdict:
                localDefinitions[u"TankDeviceMidType"].append(qdict["tankDeviceMid" + str(i)])
            else:
                # fail, missing data in form
                web.seeother(u"/tankmaset")

            # read tank ip device SOS
            if "deviceIPSOS" + str(i) in qdict:
                localDefinitions[u"TankIpSOS"].append(qdict["deviceIPSOS" + str(i)])
            else:
                # fail, missing data in form
                web.seeother(u"/tankmaset")

            # read tank device type top
            if "tankDeviceSOS" + str(i) in qdict:
                localDefinitions[u"TankDeviceSOSType"].append(qdict["tankDeviceSOS" + str(i)])
            else:
                # fail, missing data in form
                web.seeother(u"/tankmaset")

        localDefinitions[u"PumpNeedOn"] = []
        for key in qdict:
            if len(key) > len("pumpSelectFrom") and key[:len("pumpSelectFrom")] == "pumpSelectFrom":
                if key[len("pumpSelectFrom"):].isdigit():
                    pumpId = int(key[len("pumpSelectFrom"):])
                    localDefinitions[u"PumpNeedOn"].append(pumpId)

        tackmanagerLock.acquire()
        tankManager = copy.deepcopy(localDefinitions)
        # save to file
        with open(u"./data/tank_manager.json", u"w") as f:  # write the settings to file
            json.dump(tankManager, f, indent=4)
        tackmanagerLock.release()

        web.seeother(u"/tankmaset")

class tank_delete_settings(ProtectedPage):
    """Valve status"""

    def GET(self):
        qdict = web.input()

        web.seeother(u"/tankmaset")  # Return to definition pannel

class tank_home(ProtectedPage):
    """Valve status"""

    def GET(self):
        global tankManager

        qdict = web.input()

        tackmanagerLock.acquire()
        localDefinitions = copy.deepcopy(tankManager)
        tackmanagerLock.release()

        return template_render.tank_manager_home(localDefinitions, 1)
