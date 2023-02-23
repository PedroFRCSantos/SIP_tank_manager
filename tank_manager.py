#!/usr/bin/env python

# Python 2/3 compatibility imports
from __future__ import print_function
from curses.ascii import isdigit

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
        tankManager = {"Log2DB": True, u"PumpValves2PositionOn": [], u"PumpValves2PositionOff": [], u"TankName": [], u"TankSaveEnergy": [], u"TankIpTop": [], u"TankDeviceTopType": [], u"TankIpMid": [], u"TankDeviceMidType": [], u"TankIpSOS": [], u"TankDeviceSOSType": [], u"PumpNeedOn": []}
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

        localDefinitions[u"PumpValves2PositionOn"] = []
        localDefinitions[u"PumpValves2PositionOff"] = []

        localDefinitions[u"TankIpTop"] = []
        localDefinitions[u"TankDeviceTopType"] = []

        localDefinitions[u"TankIpMid"] = []
        localDefinitions[u"TankDeviceMidType"] = []

        localDefinitions[u"TankIpSOS"] = []
        localDefinitions[u"TankDeviceSOSType"] = []

        localDefinitions[u"TankSaveEnergy"] = []

        localDefinitions[u"PumpNeedOn"] = []

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
            
            list2ValvesOn = []
            for key in qdict:
                if len(key) > len("valvesNeedTank"+ str(i) +"ON") and key[:len("valvesNeedTank"+ str(i) +"ON")] == "valvesNeedTank"+ str(i) +"ON":
                    if key[len("valvesNeedTank"+ str(i) +"ON"):].isdigit():
                        valveId = int(key[len("valvesNeedTank"+ str(i) +"ON"):])
                        list2ValvesOn.append(valveId)
            localDefinitions[u"PumpValves2PositionOn"].append(list2ValvesOn)

            list2ValvesOff = []
            for key in qdict:
                if len(key) > len("valvesNeedTank"+ str(i) +"Off") and key[:len("valvesNeedTank"+ str(i) +"Off")] == "valvesNeedTank"+ str(i) +"Off":
                    if key[len("valvesNeedTank"+ str(i) +"Off"):].isdigit():
                        valveId = int(key[len("valvesNeedTank"+ str(i) +"Off"):])
                        list2ValvesOff.append(valveId)
            localDefinitions[u"PumpValves2PositionOff"].append(list2ValvesOff)

            localDefinitions[u"TankSaveEnergy"].append("tankSaveEnergy"+ str(i) in qdict)

            listOfPumps2TurnOn = []
            for key in qdict:
                if len(key) > len("pumpSelect"+ str(i) +"Use") and key[:len("pumpSelect"+ str(i) +"Use")] == "pumpSelect"+ str(i) +"Use":
                    if qdict[key].isdigit():
                        pumpId = int(qdict[key])
                        listOfPumps2TurnOn.append(pumpId)
            localDefinitions[u"PumpNeedOn"].append(listOfPumps2TurnOn)

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

        if "PumpId" in qdict and qdict["PumpId"].isdigit():
            pumpId2Delete = int(qdict["PumpId"])

            tackmanagerLock.acquire()
            if pumpId2Delete < len(tankManager[u"TankName"]):
                del tankManager[u"TankName"][pumpId2Delete]

                del tankManager[u"TankSaveEnergy"][pumpId2Delete]

                del tankManager[u"TankIpTop"][pumpId2Delete]
                del tankManager[u"TankDeviceTopType"][pumpId2Delete]

                del tankManager[u"TankIpMid"][pumpId2Delete]
                del tankManager[u"TankDeviceMidType"][pumpId2Delete]

                del tankManager[u"TankIpSOS"][pumpId2Delete]
                del tankManager[u"TankDeviceSOSType"][pumpId2Delete]

                del tankManager[u"PumpNeedOn"][pumpId2Delete]

                del tankManager[u"PumpValves2PositionOn"][pumpId2Delete]
                del tankManager[u"PumpValves2PositionOff"][pumpId2Delete]

                # save to file
                with open(u"./data/tank_manager.json", u"w") as f:  # write the settings to file
                    json.dump(tankManager, f, indent=4)
            tackmanagerLock.release()

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
