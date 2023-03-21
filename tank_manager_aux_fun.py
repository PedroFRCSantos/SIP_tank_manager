import requests

import random
import string

def requestHTTP(commandURL):
    resposeIsOk = -1
    response = None

    try:
        response = requests.get(commandURL)
        resposeIsOk = 0

        response = response.json()
    except requests.exceptions.Timeout:
        # Maybe set up for a retry, or continue in a retry loop
        resposeIsOk = 1
        print("Connection time out")
    except requests.exceptions.TooManyRedirects:
        # Tell the user their URL was bad and try a different one
        resposeIsOk = 2
        print("Too many redirections")
    except requests.exceptions.RequestException as e:
        # catastrophic error. bail.
        #raise SystemExit(e)
        resposeIsOk = 3
        print("Fatal error")

    return resposeIsOk, response

def tankIsOnLine(deviceType : str, pumpIP : str):
    resposeIsOk = -1
    isTurnOn = False

    if deviceType == 'shelly1' or deviceType == 'shelly2' or deviceType == 'shelly2_1' or deviceType == 'shelly2_2':
        commandURL = u"http://" + pumpIP + u"/status"
        response = None

        resposeIsOk, response = requestHTTP(commandURL)

        if resposeIsOk == 0:
            if deviceType == 'shelly1' or deviceType == 'shelly2_1':
                isTurnOn = bool(response['relays'][0]['ison'])
            elif deviceType == 'shelly2':
                isTurnOn = []
                isTurnOn.append(bool(response['relays'][0]['ison']))
                isTurnOn.append(bool(response['relays'][1]['ison']))
            else:
                isTurnOn = bool(response['relays'][1]['ison'])
    else:
        pass
        # TODO: another supported device

    return resposeIsOk, isTurnOn

def generateRandomString(numberOfChars):
    letters = string.ascii_lowercase + string.ascii_uppercase
    resultStr = ''.join(random.choice(letters) for i in range(numberOfChars))

    return resultStr

