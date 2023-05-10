#!/usr/bin/env python

# Python 2/3 compatibility imports
from __future__ import print_function
from curses.ascii import isdigit

# standard library imports
import json
from pickle import NONE
from threading import Thread, Lock
import copy
from datetime import datetime
from time import sleep

# request HTTP
import requests

# local module imports
from blinker import signal
import gv  # Get access to SIP's settings, gv = global variables
from sip import template_render
from urls import urls  # Get access to SIP's URLs
import web
from webpages import ProtectedPage

from tank_manager_aux_fun import *

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
        u"/tankDefJSon", u"plugins.tank_manager.tank_definitions_json",
        u"/tankstatusjson", u"plugins.tank_manager.check_tank_status_json",
        u"/tankdelete", u"plugins.tank_manager.tank_delete_settings",
        u"/tankisonline", u"plugins.tank_manager.check_tank_is_online",
        u"/tankstatus", u"plugins.tank_manager.check_tank_status",
        u"/tanksendpermition", u"plugins.tank_manager.tank_autorize_start_stop_non_priority"
    ]
)
# fmt: on

# Add this plugin to the plugins menu
gv.plugin_menu.append([u"Tank Manager", u"/tankman"])

tankActivityStatus = [] # True - is pumping wather to tank

tankManager = {}
tankStateTank = [] # List of state of tanks, shared variable
tankPermitionEnergy = [] # if energy manager is install and eneble, ask authorization to start to fill tank, if any consuption is associated
tackmanagerLock = Lock()

threadMainTank = None
isTackRunning = True

def sendLocalHTTPRequest(urlName, arguments):
    try:
        if gv.sd['htip'] == '::':
            requests.get("http://127.0.0.1" + ":" + str(gv.sd['htp']) +"/" + urlName + arguments)
        else:
            requests.get("http://"+ str(gv.sd['htip']) + ":" + str(gv.sd['htp']) +"/" + urlName + arguments)

        return True
    except:
        return False

def getListOfPupms():
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

    return listOfPumps

def askAllTankState():
    # For all tanks check all states, useful if any signal of change or any periodic check
    tackmanagerLock.acquire()
    localTankThread = copy.deepcopy(tankManager)
    tackmanagerLock.release()

    # check if tanks are on-line
    listOfResults = []
    for i in range(len(localTankThread[u"TankName"])):
        if len(localTankThread[u"TankIpTop"][i]) > 0:
            resposeIsOkTop, isTurnOnTop = tankIsOnLine(localTankThread[u"TankDeviceTopType"][i], localTankThread[u"TankIpTop"][i])
        else:
            resposeIsOkTop = None
            isTurnOnTop = None

        if len(localTankThread[u"TankIpMid"][i]) > 0:
            resposeIsOkMid, isTurnOnMid = tankIsOnLine(localTankThread[u"TankDeviceMidType"][i], localTankThread[u"TankIpMid"][i])
        else:
            resposeIsOkMid = None
            isTurnOnMid = None

        if len(localTankThread[u"TankIpSOS"][i]) > 0:
            resposeIsOkSOS, isTurnOnSOS = tankIsOnLine(localTankThread[u"TankDeviceSOSType"][i], localTankThread[u"TankIpSOS"][i])
        else:
            resposeIsOkSOS = None
            isTurnOnSOS = None

        listTMPdata = {}
        listTMPdata['IsOk'] = [resposeIsOkTop, resposeIsOkMid, resposeIsOkSOS]
        listTMPdata['IsTurnOn'] = [isTurnOnTop, isTurnOnMid, isTurnOnSOS]
        listTMPdata['CurrentDateTime'] = [datetime.now(), datetime.now(), datetime.now()]
        listOfResults.append(listTMPdata)

    # save in plug-in global variable the new data
    tackmanagerLock.acquire()
    if u"TankIsOnline" not in tankManager:
        tankManager[u"TankIsOnline"] = []
    if len(tankManager[u"TankIsOnline"]) < len(tankManager[u"TankName"]):
        increase = [False] * (len(localTankThread[u"TankName"]) - len(tankManager[u"TankIsOnline"]))
        tankManager[u"TankIsOnline"].extend(increase)
    elif len(tankManager[u"TankIsOnline"]) > len(tankManager[u"TankName"]):
        tankManager[u"TankIsOnline"] = tankManager[u"TankIsOnline"][:len(tankManager[u"TankName"])]

    if u"TankIOn" not in tankManager:
        tankManager[u"TankIOn"] = []
    if len(tankManager[u"TankIOn"]) < len(tankManager[u"TankName"]):
        increase = [False] * (len(localTankThread[u"TankName"]) - len(tankManager[u"TankIOn"]))
        tankManager[u"TankIOn"].extend(increase)
    elif len(tankManager[u"TankIOn"]) > len(tankManager[u"TankName"]):
        tankManager[u"TankIOn"] = tankManager[u"TankIOn"][:len(tankManager[u"TankName"])]

    if u"TankLastTimeOnline" not in tankManager:
        tankManager[u"TankLastTimeOnline"] = []
    if len(tankManager[u"TankLastTimeOnline"]) < len(tankManager[u"TankName"]):
        increase = [datetime.now()] * (len(localTankThread[u"TankName"]) - len(tankManager[u"TankLastTimeOnline"]))
        tankManager[u"TankLastTimeOnline"].extend(increase)
    elif len(tankManager[u"TankLastTimeOnline"]) > len(tankManager[u"TankName"]):
        tankManager[u"TankLastTimeOnline"] = tankManager[u"TankLastTimeOnline"][:len(tankManager[u"TankName"])]

    for i in range(min(len(localTankThread[u"TankName"]), len(tankManager[u"TankName"]))):
        tankManager[u"TankIsOnline"][i] = listOfResults[i]['IsOk']
        tankManager[u"TankIOn"][i] = listOfResults[i]['IsTurnOn']
        tankManager[u"TankLastTimeOnline"][i] = listOfResults[i]['CurrentDateTime']

        if len(localTankThread[u"TankIpTop"][i]) > 0:
            tankStateTank[i][0] = listOfResults[i]['IsTurnOn'][0]
        else:
            tankStateTank[i][0] = None

        if len(tankManager[u"TankIpMid"][i]) > 0:
            tankStateTank[i][1] = listOfResults[i]['IsTurnOn'][1]
        else:
            tankStateTank[i][1] = None

        if len(localTankThread[u"TankIpSOS"][i]) > 0:
            tankStateTank[i][2] = listOfResults[i]['IsTurnOn'][2]
        else:
            tankStateTank[i][2] = None
            
    tackmanagerLock.release()

def runTreadTank():
    global isTackRunning, tankManager, tankStateTank, tankActivityStatus

    lastTime = datetime.now()

    listOfTanksSOS = []
    listOfThanksWaiting = []
    listOfTankNonPriorityWorking = []

    while isTackRunning:
        sleep(1)

        tackmanagerLock.acquire()
        localTankThread = copy.deepcopy(tankManager)
        localTankStatus = copy.deepcopy(tankStateTank)
        tackmanagerLock.release()

        if len(tankActivityStatus) > len(localTankStatus):
            tankActivityStatus = tankActivityStatus[:len(localTankStatus)]
        elif len(tankActivityStatus) < len(localTankStatus):
            numElm2Add = len(localTankStatus) - len(tankActivityStatus)
            for i in range(numElm2Add):
                tankActivityStatus.append(False)

        # if any state change, take actions
        for i in range(len(localTankThread[u"TankName"])):
            if localTankStatus[i][0] != None and not localTankStatus[i][0]: # Top is not fill and any program is running
                # check if ask for permition non priory to fill the tank
                if i not in listOfTanksSOS and i not in listOfThanksWaiting and i not in listOfTankNonPriorityWorking:
                    listOfThanksWaiting.append(i)

                    # get definition of pups to estimate power
                    listOfPumps = getListOfPupms()
                    totalPower = 0.0
                    minumWorkingTime = 0.0
                    for k in localTankThread[u"PumpNeedOn"][i]:
                        if k >= 0 and k < len(listOfPumps['PumpPower']):
                            totalPower = totalPower + float(listOfPumps['PumpPower'][k])
                            spliCurrWorkTime = listOfPumps['PumpMinWorkingTime'][k].split(':')

                            currentMinWorkTime = 0.0
                            if len(spliCurrWorkTime) == 2: # minutes:seconds
                                currentMinWorkTime = float(spliCurrWorkTime[0]) / 60.0 + float(spliCurrWorkTime[1]) / 60.0 / 60.0
                            elif len(spliCurrWorkTime) == 3: # hour:minute:seconds
                                currentMinWorkTime = float(spliCurrWorkTime[0]) + float(spliCurrWorkTime[1]) / 60.0 + float(spliCurrWorkTime[2]) / 60.0 / 60.0

                            if currentMinWorkTime > minumWorkingTime:
                                minumWorkingTime = currentMinWorkTime

                    # send using http request permition to turn on to energy manager
                    argumentEnergy = "?ExtentionName=tankmanager&LinkConn=tanksendpermition&DeviceRef="+ localTankThread[u"TankRef"][i] +"&MinWorkingTime="+ str(minumWorkingTime) +"&EnergyPower="+ str(totalPower)
                    argumentEnergy = argumentEnergy + "&ExpectedWorkingTime=0.25&AvoidIrrigationProgram=yes&HoursCanWait=0&Priority=1"

                    sendLocalHTTPRequest("energy-manager-ask-consuption", argumentEnergy)
                elif i in listOfThanksWaiting:
                    # check if any receive permition relative to this tank
                    tankCanStart = False
                    id2Delete = -1

                    # if energy manager is active, check when permion was given
                    tackmanagerLock.acquire()
                    for l in range(len(tankPermitionEnergy)):
                        if tankPermitionEnergy[l][0] == localTankThread[u"TankRef"][i] and tankPermitionEnergy[l][1]:
                            tankCanStart = True
                            id2Delete = l
                    if id2Delete >= 0:
                        del tankPermitionEnergy[id2Delete]
                    tackmanagerLock.release()

                    if tankCanStart:
                        if not tankActivityStatus[i]:
                            # Start to stop irrigation if any program is running
                            sendLocalHTTPRequest("cv", "?pw=opendoor&mm=1")

                            # manual set position of valves
                            # ON valves
                            for valveId in localTankThread[u"PumpValves2PositionOn"][i]:
                                sendLocalHTTPRequest("sn", "?sid="+ str(valveId) + "&set_to=1")
                            # OFF valves
                            for valveId in localTankThread[u"PumpValves2PositionOff"][i]:
                                sendLocalHTTPRequest("sn", "?sid="+ str(valveId) + "&set_to=0")

                            # manual start all pumps, if plug-in exits
                            for pumpId in localTankThread[u"PumpNeedOn"][i]:
                                sendLocalHTTPRequest("advance-pump-switch-manual", "?PumpId="+ str(pumpId) + "&ChangeStateState=on")

                            # inform energy manger using energy with permition
                            argumentEnergy = "?ExtentionName=tankmanager&DeviceRef="+ localTankThread[u"TankRef"][i] +"&EnergyPower="+ str(totalPower) +"&TurnOffMinDateTime="+ datetime.now().strftime("%Y/%m/%d %H:%M:%S") +"&UrlStop=tanksendpermition"
                            sendLocalHTTPRequest("energy-manager-add-know-consuption", argumentEnergy)

                        tankActivityStatus[i] = True

                        listOfThanksWaiting.remove(i)
                        listOfTankNonPriorityWorking.append(i)
                elif tankActivityStatus[i]: # if already puping wather, check if permition to continue
                    tankCanStop = False

                    # if energy manager is active, check when permion was given
                    tackmanagerLock.acquire()
                    for l in range(len(tankPermitionEnergy)):
                        if tankPermitionEnergy[l][0] == localTankThread[u"TankRef"][i] and not tankPermitionEnergy[l][1]:
                            tankCanStop = True
                            id2Delete = l
                    if id2Delete >= 0:
                        del tankPermitionEnergy[id2Delete]
                    tackmanagerLock.release()

                    if tankCanStop:
                        # manual start all pumps, if plug-in exits
                        for pumpId in localTankThread[u"PumpNeedOn"][i]:
                            sendLocalHTTPRequest("advance-pump-switch-manual", "?PumpId="+ str(pumpId) + "&ChangeStateState=off")
                            sendLocalHTTPRequest("advance-pump-switch-manual", "?PumpId="+ str(pumpId) + "&ChangeStateState=auto")

                        # disable all valves to off
                        for valveId in range(len(gv.srvals)):
                            sendLocalHTTPRequest("sn", "?sid="+ str(valveId + 1) + "&set_to=0")

                        # enable irrigation to auto
                        sendLocalHTTPRequest("cv", "?pw=opendoor&mm=0")

                        tankActivityStatus[i] = False

                        # inform energy manager, stop to using energy for this tank
                        # TODO

                        listOfTankNonPriorityWorking.remove(i)
            if localTankStatus[i][2] != None and not localTankStatus[i][2] and i not in listOfTanksSOS and not tankActivityStatus[i]: # SOS is not fill
                # SOS turn on tank, in the future add fail save
                # Start to stop all irrigation program
                sendLocalHTTPRequest("cv", "?pw=opendoor&mm=1")

                # fix valves position
                # ON valves
                for valveId in localTankThread[u"PumpValves2PositionOn"][i]:
                    sendLocalHTTPRequest("sn", "?sid="+ str(valveId) + "&set_to=1")
                # OFF valves
                for valveId in localTankThread[u"PumpValves2PositionOff"][i]:
                    sendLocalHTTPRequest("sn", "?sid="+ str(valveId) + "&set_to=0")

                # set other valves to off
                for valveId in range(len(gv.srvals)):
                    if valveId + 1 not in localTankThread[u"PumpValves2PositionOn"][i] and valveId + 1 not in localTankThread[u"PumpValves2PositionOff"][i]:
                        sendLocalHTTPRequest("sn", "?sid="+ str(valveId + 1) + "&set_to=0")

                # start pumps if needed and exists plugin
                for pumpId in localTankThread[u"PumpNeedOn"][i]:
                    sendLocalHTTPRequest("advance-pump-switch-manual", "?PumpId="+ str(pumpId) + "&ChangeStateState=on")

                # Inform energy manager, device start in emergy mode, register to avoid this situation
                # get definition of pups to estimate power
                listOfPumps = getListOfPupms()
                totalPower = 0.0
                for k in localTankThread[u"PumpNeedOn"][i]:
                    if k >= 0 and k < len(listOfPumps['PumpPower']):
                        totalPower = totalPower + float(listOfPumps['PumpPower'][k])

                argumentEnergy = "?ExtentionName=tankmanager&DeviceRef="+ localTankThread[u"TankRef"][i] +"&EnergyPower="+ str(totalPower) +"&MandatoryWork&TurnOffMinDateTime=0&UrlStop=tanksendpermition"
                sendLocalHTTPRequest("energy-manager-add-know-consuption", argumentEnergy)

                tankActivityStatus[i] = True

                listOfTanksSOS.append(i)
            elif localTankStatus[i][2] != None and localTankStatus[i][2] and i in listOfTanksSOS: # SOS finish but pumps can be allow to continue
                tankCanContinue = False

                if i not in listOfTankNonPriorityWorking:
                    tackmanagerLock.acquire()
                    for l in range(len(tankPermitionEnergy)):
                        if tankPermitionEnergy[l][0] == localTankThread[u"TankRef"][i] and tankPermitionEnergy[l][1]:
                            tankCanContinue = True
                            id2Delete = l
                    if id2Delete >= 0:
                        del tankPermitionEnergy[id2Delete]
                    tackmanagerLock.release()
                
                if not tankCanContinue:
                    # desable all pups pump
                    for pumpId in localTankThread[u"PumpNeedOn"][i]:
                        sendLocalHTTPRequest("advance-pump-switch-manual", "?PumpId="+ str(pumpId) + "&ChangeStateState=off")
                        sendLocalHTTPRequest("advance-pump-switch-manual", "?PumpId="+ str(pumpId) + "&ChangeStateState=auto")

                    tankActivityStatus[i] = False

                    # close all valves
                    for valveId in range(len(gv.srvals)):
                        sendLocalHTTPRequest("sn", "?sid="+ str(valveId + 1) + "&set_to=0")

                    # enable irrigation to auto
                    sendLocalHTTPRequest("cv", "?pw=opendoor&mm=0")

                # remove from SOS list
                listOfTanksSOS.remove(i)
            elif localTankStatus[i][0] != None and localTankStatus[i][0] and i in listOfTankNonPriorityWorking: # Top is fill, need to stop pump
                # desable all pups pump
                for pumpId in localTankThread[u"PumpNeedOn"][i]:
                    sendLocalHTTPRequest("advance-pump-switch-manual", "?PumpId="+ str(pumpId) + "&ChangeStateState=off")
                    sendLocalHTTPRequest("advance-pump-switch-manual", "?PumpId="+ str(pumpId) + "&ChangeStateState=auto")

                # disable all valves to off
                for valveId in range(len(gv.srvals)):
                    sendLocalHTTPRequest("sn", "?sid="+ str(valveId + 1) + "&set_to=0")

                # enable irrigation to auto
                sendLocalHTTPRequest("cv", "?pw=opendoor&mm=0")

                tankActivityStatus[i] = False

                # save finish know energy to DB

                # inform energy manager that don´t need energy any more
                sendLocalHTTPRequest("energy-manager-ask-consuption", "?ExtentionName=tankmanager&DeviceRef="+ localTankThread[u"TankRef"][i] +"&RemovePermition")

                # remove from non prioruty list
                listOfTankNonPriorityWorking.remove(i)

        # every 30 seconds force state if needed and check if valves are only
        nowTime = datetime.now()
        diffTime = nowTime - lastTime
        secondsInt = int(diffTime.seconds)
        if secondsInt > 30:
            lastTime = nowTime

            # check tank states
            askAllTankState()

def load_commands():
    global tankManager, threadMainTank, tankStateTank

    tackmanagerLock.acquire()
    try:
        with open(u"./data/tank_manager.json", u"r") as f:
            tankManager = json.load(f)  # Read the commands from file
    except IOError:  #  If file does not exist create file with defaults.
        tankManager = {"Log2DB": True, u"PumpValves2PositionOn": [], u"PumpValves2PositionOff": [], u"TankName": [], u"TankRef": [], u"TankSaveEnergy": [], u"TankIpTop": [], u"TankDeviceTopType": [], u"TankIpMid": [], u"TankDeviceMidType": [], u"TankIpSOS": [], u"TankDeviceSOSType": [], u"PumpNeedOn": [], u"URLTankCode": []}


    # set none to initial tank state
    tankStateTank = []
    for i in range(len(tankManager["TankName"])):
        tankStateTank.append([None, None, None])
    tackmanagerLock.release()

    threadMain = Thread(target = runTreadTank)
    threadMain.start()

load_commands()

class tank_settings(ProtectedPage):
    """Valve status"""

    def GET(self):
        global tankManager, withDBLogger, tackmanagerLock

        qdict = web.input()

        addTank = 0
        if "AddTank" in qdict:
            addTank = 1

        listOfPumps = getListOfPupms()

        tackmanagerLock.acquire()
        tankManagerLocal = copy.deepcopy(tankManager)
        tackmanagerLock.release()

        return template_render.tank_manager(tankManagerLocal, addTank, listOfPumps, withDBLogger)

class tank_save_settings(ProtectedPage):
    """Valve status"""

    def GET(self):
        global tankManager, tackmanagerLock, tankStateTank

        qdict = web.input()

        localDefinitions = {}

        localDefinitions[u"Log2DB"] = u"pumpUseDB" in qdict

        numberOfTanks = 0
        for key in qdict:
            if len(key) > len("tankName") and key[:len("tankName")] == "tankName":
                numberOfTanks = numberOfTanks + 1

        localDefinitions[u"TankName"] = []
        localDefinitions[u"URLTankCode"] = []
        localDefinitions[u"TankRef"] = []

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
                localDefinitions[u"URLTankCode"].append(generateRandomString(5))
                localDefinitions[u"TankRef"].append(generateRandomString(7))
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

        if len(tankManager[u"TankName"]) > len(tankStateTank):
            tmpStateLevels = [None, None, None] # Top, Middle, SOS, if exits
            tankStateTank.append(tmpStateLevels)
        elif len(tankManager[u"TankName"]) < len(tankStateTank):
            tankStateTank = tankStateTank[:len(tankManager[u"TankName"])]
        tackmanagerLock.release()

        web.seeother(u"/tankmaset")

class tank_definitions_json(ProtectedPage):
    """Valve status"""

    def GET(self):
        global tankManager, tackmanagerLock

        web.header(u"Access-Control-Allow-Origin", u"*")
        web.header(u"Content-Type", u"application/json")

        tackmanagerLock.acquire()
        data2Return = json.dumps(tankManager)
        tackmanagerLock.release()

        return data2Return

class check_tank_status_json(ProtectedPage):
    """Valve status"""

    def GET(self):
        return "ok"

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

                del tankStateTank[pumpId2Delete]

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

        return template_render.tank_manager_home(localDefinitions)

class check_tank_is_online(ProtectedPage):
    def GET(self):
        global tackmanagerLock, tankManager

        qdict = web.input()

        colorStatus = "white"

        if "tankId" in qdict and "sensorIdx" in qdict:
            tankId = int(qdict["tankId"])
            sensorIdx = int(qdict["sensorIdx"])

            tackmanagerLock.acquire()
            if sensorIdx >= 0 and sensorIdx < 3 and u"TankLastTimeOnline" in tankManager and len(tankManager[u"TankLastTimeOnline"]) and tankId >= 0 and tankId < len(tankManager[u"TankLastTimeOnline"]):
                lastSeen = tankManager[u"TankLastTimeOnline"][tankId][sensorIdx]
                timeNow = datetime.datetime.now()

                diff = timeNow - lastSeen

                if diff.seconds > 45:
                    return "red"
                else:
                    return "green"
            tackmanagerLock.release()

        return colorStatus

class check_tank_status(ProtectedPage):
    def GET(self):
        global tackmanagerLock, tankManager

        qdict = web.input()

        tankStatus = "None"

        if "tankId" in qdict and "sensorIdx" in qdict:
            tankId = int(qdict["tankId"])
            sensorIdx = int(qdict["sensorIdx"])

            tackmanagerLock.acquire()
            if sensorIdx >= 0 and sensorIdx < 3 and u"TankIOn" in tankManager and len(tankManager[u"TankIOn"]) and tankId >= 0 and tankId < len(tankManager[u"TankIOn"]):
                if tankManager[u"TankIOn"][tankId][sensorIdx]:
                    tankStatus = "True"
                else:
                    tankStatus = "False"
            tackmanagerLock.release()

        return tankStatus

class url_notification_tank_change():
    def GET(self):
        global tackmanagerLock, tankManager

        qdict = web.input()

        if "tankRef" in qdict and "tankSensorLoc" in qdict:
            tankRef = qdict["tankRef"]
            tankSenLoc = qdict["tankSensorLoc"]
            tankSenNewStat = qdict["tankSensorNewStat"]

            idxTank = -1
            for i in range(len(tankManager[u"URLTankCode"])):
                if tankManager[u"URLTankCode"][i] == tankRef and (tankSenNewStat == 'on' or tankSenNewStat == 'off') \
                    and (tankSenLoc == 'sos' or tankSenLoc == 'mid' or tankSenLoc == 'top'):
                    newState = tankSenNewStat == 'on'
                    idxTank = i

            if idxTank >= 0:
                idTankLevel = 0
                if tankSenLoc == 'mid':
                    idTankLevel = 1
                elif tankSenLoc == 'sos':
                    idTankLevel = 2

                # if signal send from device, check new status
                askAllTankState()

class tank_autorize_start_stop_non_priority():
    """Energy manager autorize to start/stop tank non priority"""
    def GET(self):
        global tackmanagerLock, tankManager, tankPermitionEnergy

        qdict = web.input()
        if "DeviceRef" in qdict and "DevicePermition" in qdict and (qdict["DevicePermition"] == 'on' or qdict["DevicePermition"] == 'off'):
            tankRef = qdict["DeviceRef"]

            tackmanagerLock.acquire()
            # Check if thank ref exists
            if tankRef in tankManager["TankRef"]:
                isFound = False
                foundId = -1

                for i in range(len(tankPermitionEnergy)):
                    if tankPermitionEnergy[i][0] == tankRef:
                        tankPermitionEnergy[i][1] = qdict["DevicePermition"] == 'on'
                        isFound = True
                        foundId = i

                if isFound:
                    tankPermitionEnergy[foundId] = [tankRef, qdict["DevicePermition"] == 'on']
                else:
                    tankPermitionEnergy.append([tankRef, qdict["DevicePermition"] == 'on'])
            tackmanagerLock.release()
