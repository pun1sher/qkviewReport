from iHealth_oauth_client import oAuthClient
from datetime import datetime
from docxgen import docxgen
import json,os
import requests,re,sys
import xmltodict, base64

'''
Version 2 - 03Sept2025 - Add support to retrieve device failover status
Version 2.1 - 06Sept2025 - Add SSL TPS Graph 

'''

oauth_clientId = os.getenv('IHF5_CLIENT')
oauth_client_secret = os.getenv('IHF5_SECRET')
oauth_client = oAuthClient('https://identity.account.f5.com/oauth2/ausp95ykc80HOU7SQ357/v1/token')
token = oauth_client.get_auth_token(oauth_clientId,oauth_client_secret)


def decodeQkviewCommands(responseText):
  dictOut = xmltodict.parse(responseText)
  encoded = dictOut['commands']['command']['output']
  if len(encoded) % 4 == 3:
    encoded += '='
  elif len(encoded) % 4 == 2:
    encoded += '=='
  decoded = base64.b64decode(encoded).decode(encoding='UTF-8')
  return decoded

def retrieveNodeCount(lines) -> int:
    nodes = sum(1 for item in lines if item.startswith('ltm node'))
    return nodes   

def retrievePoolCount(lines) -> int:
  pools = sum(1 for item in lines if item.startswith('ltm pool'))
  return pools

def retrieveRuleCount(lines) -> int:
    rules = sum(1 for item in lines if item.startswith('ltm rule'))
    return rules

def retrieveVirtualCount(lines) -> int:
    virtuals = sum(1 for item in lines if item.startswith('ltm virtual'))
    return virtuals

def retrieveMonitorCounts(lines) -> int:
    monitors = sum(1 for item in lines if item.startswith('ltm monitor'))
    return monitors

def retrieveAuthPartitions(lines) -> int:
    authPartitions = sum(1 for item in lines if item.startswith('auth partition'))
    return authPartitions


def retrieveInterfaces(qkvNum:int):
    interfaces = {}
    url = f'{baseIhealthApiURL}/commands/b8cf79d200280103db9dd185d33534abe7787521'
    response = requests.request("GET", url, headers=headers)
    if response.status_code == 200:
        lines = decodeQkviewCommands(response.text).splitlines(keepends=True)
        for i in range(0,len(lines)):
            if lines[i].startswith('***') or lines[i].startswith('Name') or lines[i].startswith('===') or lines[i] == '\n':
                continue
            fields = lines[i].split()
            interface = fields[0]
            status = fields[1]
            media = fields[15]
            if len(fields) == 19:
                trunk = fields[17]
            else:
                trunk = ''
            if not interface.startswith('0') and status == 'up' and '21000' not in media and '42000' not in media and interface != 'mgmt':
                interfaces[interface] = {'status': status, 'media': media, 'trunk': trunk}
        return interfaces

    else: 
       print(f'Error - {response.status_code} - {response.text}')
       return {}


def retrieveLicenseInfo(qkvNum:int)-> tuple:
    '''
    Retrieve the show sys license detail page
    extract the Registration Key, Platform ID and Exclusive Version fields
    If platform ID doesn't start with Z we will include platform lifecycle information

    '''
    with open('hardware.json') as hwLifeFile:
        hwLifecycle = json.load(hwLifeFile)

    url = f'{baseIhealthApiURL}/commands/777eb20f70ba1e04308c07d46c40c2c53748dbb2'

    response = requests.request("GET", url, headers=headers)
    if response.status_code != 200:
        print('Error: {response.status_code}')
    else:
        file = decodeQkviewCommands(response.text)
        lines = file.splitlines(keepends=True)
        regKey = re.findall(r'Registration Key\s+([A-Z-]*)', lines[2])[0]
        platformId = re.findall(r'ID\s+([A|C|D|J|S|Z]1[0-3][0-9])',lines[5])[0]
        if  platformId.startswith('BIG-IQ') and   'VE Subs' in file:
            versionPlus = 'VE Subscription'
            licenseInfo = [
             ('Registration Key', regKey),
             ('Platform ID', platformId),
             ('VE Type', versionPlus)   
            ]            
        elif platformId.startswith('Z1'):
            fields = lines[15].strip().split(', ') 
            if fields[1].endswith('15.X'):
                versionPlus = 'V13'
            elif fields[1].endswith('16.X'):
                versionPlus = 'V16'
            elif fields[1].endswith('18.X'):
                versionPlus = 'V18'           
                    
            licenseInfo = [
             ('Registration Key', regKey),
             ('Platform ID', platformId),
             ('VE Type', versionPlus)   
            ]
        else:
            hwLife = hwLifecycle[platformId]  
            licenseInfo = [
             ('Registration Key', regKey),
             ('Platform ID', platformId),
             ('Platform Name', hwLife['platformName']),
             ('End of Sale', hwLife['EoS']),
             ('End of New Software Support', hwLife['EoNSS']),
             ('End of Software Support', hwLife['EoSS']),
             ('End of Technical Support', hwLife['EoTS'])
            ]    
            
    if not 'VCMP Enabled' in file or  not 'Z100' in platformId or not bool(re.match(r'^[r1|r2|r4|r5|BX|CX]',hwLife['platformName'])):
        print('Retrieving Interface Information')
        interfaces = retrieveInterfaces(qkviewNum)
    else:
        interfaces = ['vCMP Guests/F5OS Tenants do not have traditional interface assignments']


    return licenseInfo, interfaces

def retrieveUptime(qkvNum) -> tuple:
    # retrieve and parse the proc_module.xml
    url = f'{baseIhealthApiURL}/files/cHJvY19tb2R1bGUueG1s'
    response = requests.request("GET", url, headers=headers)
    if response.status_code == 200:
        dictOut = xmltodict.parse(response.text)       
        uptimeInt = int(float(dictOut['Qkproc']['uptime_t']['f_uptime']) )
        days = int(uptimeInt / 86400)
        hours = int ((uptimeInt - (days * 86400)) / 3600)
        uptime = str(days) + ' days, ' + str(hours) + ' hours'
        return 'uptime', uptime
    else:
        return 'Uptime',''

def retrieveModuleProvisioning(qkvNum):
    # retrieving module provisioning
    modulesProvisioned = ''
    url = f'{baseIhealthApiURL}/commands/c12723edf7dedb01e5430fe6077a12ec07ef4e14'
    response = requests.request("GET", url, headers=headers)
    if response.status_code != 200:
        print('Unable to retrieve module provisioning for qkview ' + str(qkviewNum))
    else:
        file = decodeQkviewCommands(response.text)
        lines = file.splitlines(keepends=True)
        for line in lines:
            if line.startswith('sys provision'):
                fields = line.split(' ')
                modName = fields[2]
            elif line.startswith('    level'):
                gb, level = line.strip().split('level ')
                if level != 'none':
                    if modulesProvisioned == '':
                        modulesProvisioned = modName
                    else:
                        modulesProvisioned += f', {modName}'
    return modulesProvisioned
            
def retrieveVersion(qkviewNum) -> tuple:
        # Retrieve running version
    url = f'{baseIhealthApiURL}/commands/3af0d910d98f07b78ac322a07920c1c72b5dfc85'
    response = requests.request("GET", url,  headers=headers)
    if response.status_code == 200:
        decoded_cmdOut = decodeQkviewCommands(response.text)
        entries = decoded_cmdOut.split('\n')
        for line in entries:
            fields = line.split(' ')
            if len(fields) > 1:
                if fields[2] == 'yes':
                    firmware_version = fields[7]
        return ('Firmware Version', firmware_version)

def retrieveCPUandMemory(qkvNum) -> tuple:
    # retrieve CPU and Memory counts
    url = f'{baseIhealthApiURL}/files/SFdJTkZP'
    response = requests.request("GET", url, headers=headers)
    if response.status_code != 200:
        print('Error: ' + str(response.status_code))
    else:
        content = response.text.split('\n')
        (gb,vCPUcount) = content[1].split('=')
        (gb,mem) = content[2].split('=') 
        memSize = round(int(mem) / 1048576,2)
        cpuMemory = [('vCPU Count', vCPUcount), ('Memory', memSize)]
        return cpuMemory

def retrieveFailoverStatus(qkviewNum) -> str:
    # retrieve device failover status (active, standby, standalone)

    url = f'{baseIhealthApiURL}/commands/e161b8be18af33223a4f3b345aa6d6ca9645dcdf'
    response = requests.request("GET", url,  headers=headers)
    if response.status_code == 200:
        decoded_cmdOut = decodeQkviewCommands(response.text)   
        lines = decoded_cmdOut.split('\n')
        (gb,failoverStatus) = lines[4].split('   ')
        return failoverStatus
    


def retrieveDeviceInfo(qkvNum)-> tuple:
    '''
    Retrieve device level information (CPUs, Memory, provisioned modules, serial number)
    '''
    url = f'{baseIhealthApiURL}'
    response = requests.request("GET", url,  headers=headers)
    if response.status_code != 200:
        print(f'Qkview {qkvNum} is unavailable, please login to iHealth to verify status of qkview.  Exiting ...' )
        sys.exit()

    dictOut = xmltodict.parse(response.text)
    if 'chassis_serial' in dictOut['qkview']:
        chassisSerial = dictOut['qkview']['chassis_serial']
    else:
        chassisSerial = 'Unavailable'
    hostName = dictOut['qkview']['hostname']
    gDate = dictOut['qkview']['generation_date'] 
    gDate2 = int(gDate) / 1000.0
    qkviewDate = datetime.fromtimestamp(gDate2).strftime("%Y-%m-%d %H:%M:%S")

    # retrieve failover status
    failoverState = retrieveFailoverStatus(qkvNum)
    # retrieve uptime
    (uptimeMsg, uptime) = retrieveUptime(qkvNum)
    # retrieve firmware version
    (firmwareMsg, firmwareVersion) = retrieveVersion(qkvNum)
    # retrieve provision modules
    provisionModules = retrieveModuleProvisioning(qkvNum)
    # retrieve CPU and Memory
    cpuMemory = retrieveCPUandMemory(qkvNum)
 

    deviceInfo = [
        ('hostName', hostName),
        ('serialNumber', chassisSerial),
        ('failoverState', failoverState),
        ('provisionModules', provisionModules),
        ('vcpuCount', cpuMemory[0][1]),
        ('memory', str(cpuMemory[1][1])),
        ('firmwareVersion', firmwareVersion),
        ('qkviewDate', qkviewDate),
        (uptimeMsg, uptime)
    ]

    return deviceInfo

def retrieveObjectCounts(qkvNum) -> tuple:
    cmdDict = {
    'list auth':      '53b31bba9ec57ef5538728ccb35aae530cdb2f05',
    'list pools':     '10c2c9c206c41dcbd6a081ac517aa3e52e2a7741',
    'list mon http':  '2888b5db127fb5839958620845fe041b7b743634',
    'list mon https': '4bac75fe973102f59c8485b234c49e558a5a26f8',
    'list mon tcp':   '515991d0283ecf40d96567cebe22c7f8fef2be80',
    'list mon udp':   '1251806ed1553fa7a97b514ab6744b6ec893dc55',
    'list nodes':     '95a3df823fa0f3e764e0eea24ca0550efaeba97f',
    'list rules':     '8b85e073cc3dcf303db34025e931a5286f26ce77', 
    'list virtuals':  'a11a885a65838bd6f3fc0e8d1ac2e554c1d50a1a'
    } 
    for cmdName in cmdDict:
        cmdId = cmdDict[cmdName]
        url = f'{baseIhealthApiURL}/commands/{cmdId}'
        response = requests.request("GET", url, headers=headers)
        if response.status_code != 200:
            print(f'Qkview {qkvNum} is unavailable, please login to iHealth to verify status of qkview.  Exiting ...' )
            sys.exit()
        else:
            file = decodeQkviewCommands(response.text)
            if cmdName == 'list pools':
                poolCount = retrievePoolCount(file.splitlines(keepends=True))
            elif cmdName == 'list virtuals':
                virtualCount = retrieveVirtualCount(file.splitlines(keepends=True))
            elif cmdName == 'list nodes':
                nodeCount = retrieveNodeCount(file.splitlines(keepends=True))
            elif cmdName == 'list rules':
                ruleCount = retrieveRuleCount(file.splitlines(keepends=True))
            elif cmdName == 'list mon http':
                httpMonCount = retrieveMonitorCounts(file.splitlines(keepends=True))
            elif cmdName == 'list mon https':
                httpsMonCount = retrieveMonitorCounts(file.splitlines(keepends=True))                
            elif cmdName == 'list mon tcp':
                tcpMonCount = retrieveMonitorCounts(file.splitlines(keepends=True))
            elif cmdName == 'list mon udp':
                udpMonCount = retrieveMonitorCounts(file.splitlines(keepends=True))                
            elif cmdName =='list auth':
                countAuthPartitions = retrieveAuthPartitions(file.splitlines(keepends=True))

    objectCounts = [
        ('Nodes', nodeCount),
        ('Pools', poolCount),
        ('Rules', ruleCount),
        ('Virtuals', virtualCount),
        ('Partitions', countAuthPartitions),
        ('HTTP Monitors', httpMonCount),
        ('HTTPS Monitors', httpsMonCount),
        ('TCP Monitors', tcpMonCount),
        ('UDP Monitors', udpMonCount)
    ]
    return objectCounts

def retrieveGraphs(qkvnum, hostName, qkviewDate) -> list:
    graphList = []
    dictGraphs = {
        'active_connections': 'activecons',
        'by_core_cpu': 'blade0cpucores',
        'system_CPU': 'CPU',
        'cpu_plane': 'detailplanestat',
        'memory_breakdown': 'memorybreakdown',
        'ssl_tps': 'SSLTPSGraph',
        'new_connections': 'newcons',
        'throughput': 'throughput'
    }

    qkvDate = datetime.strftime(datetime.strptime(qkviewDate, "%Y-%m-%d %H:%M:%S"), "%Y-%m-%d")

    for key in dictGraphs:
        label = key 
        graphName=dictGraphs[key]
        url = f'{baseIhealthApiURL}/graphs/{graphName}?timespan=30_days'
        gName = label + '_30_day'
        response = requests.request("GET", url, headers=headers)
        if response.status_code == 200:
            imgFile = hostName + '_' + label + '-' + qkvDate +  '-30day.png' 
            imgFileName = path + '/' + imgFile
            f = open( imgFileName, 'wb')
            f.write(response.content)
            f.close()
            graphList.append(imgFileName)
    return graphList
    
def removeGraphImages(imgFiles):
    for file in imgFiles:
        os.remove(file)


def retrieveDiagReport(qkvNum) -> list:
    '''
    function to retrieve and parse the BIG-IP Diagnostic listing and creating a list of en
    '''
    url =  f'{baseIhealthApiURL}/diagnostics'
    response =  requests.request("GET", url, headers=headers)
    if response.status_code != 200:
       return  [f"Error receiving qkview diagnostics {response.status_code} - {response.text}"]
    else:
        diags = response.text 
        dRpt = []
        # convert XML to python dictionary
        diagsDict = xmltodict.parse(diags)
        diagList = diagsDict['diagnostic_output']['diagnostics']['diagnostic']
        for diag in diagList:
            if 'LOW' in diag["run_data"]["h_importance"]:
                continue
            else:
                name = diag['results']['h_header']
                if not diag['results']['h_sols'] is None:
                    if isinstance(diag["results"]["h_sols"]["solution"], list):
                            kbArticle = ''
                            kbLink = ''
                            for sol in diag["results"]["h_sols"]["solution"]:
                                kbArticle += f'{sol["@id"]} '
                                kbLink += f'{sol["#text"]}  '
                    elif isinstance(diag["results"]["h_sols"]["solution"], dict):
                        kbArticle = diag["results"]["h_sols"]["solution"]["@id"]
                        kbLink = diag['results']['h_sols']['solution']['#text']
                else:
                    kbArticle = ''
                    kbLink = '' 
                if diag["fixedInVersions"] is None:
                    fixedVersion = 'None'
                else:
                    if isinstance(diag["fixedInVersions"]["version"], dict):
                        fixedVersion = f'{diag["fixedInVersions"]["version"]["major"]}.{diag["fixedInVersions"]["version"]["minor"]}.{diag["fixedInVersions"]["version"]["maintenance"]}'
                    elif isinstance(diag["fixedInVersions"]["version"], list):
                        fixedVersion = ''
                        for version in diag["fixedInVersions"]["version"]:
                            fixedVersion += f'{version["major"]}.{version["minor"]}.{version["maintenance"]} '
                importance = diag["run_data"]["h_importance"]
                if 'h_cve_ids' in diag["results"]:
                    cveNum =  diag["results"]["h_cve_ids"]["h_cve_ids"]
                else:
                    cveNum = 'None'
                tmp = (name, kbArticle, kbLink, fixedVersion, importance, cveNum )
                dRpt.append(tmp)
        severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        diagRpt = sorted(dRpt, key=lambda x: severity_order.get(x[4].upper(), 99))        
        return diagRpt


##### main #########

qkvLink= input('Paste the link to the qkview: ')
fields = qkvLink.split('/')
qkviewNum = fields[5]

custName = input('Enter customer name: ')
path = 'qkview_output/' + custName
if not os.path.exists(path):
  os.makedirs(path)

baseIhealthApiURL = f'https://ihealth-api.f5.com/qkview-analyzer/api/qkviews/{qkviewNum}' 
headers = {
  'Authorization': 'Bearer ' + token ,
  'Accept': 'application/vnd.f5.ihealth.api.v1.0',
  'User-Agent': 'F5SE'
}

cmdDict = {
  'list auth':      '53b31bba9ec57ef5538728ccb35aae530cdb2f05',
  'list pools':     '10c2c9c206c41dcbd6a081ac517aa3e52e2a7741',
  'list mon http':  '2888b5db127fb5839958620845fe041b7b743634',
  'list mon https': '4bac75fe973102f59c8485b234c49e558a5a26f8',
  'list mon tcp':   '515991d0283ecf40d96567cebe22c7f8fef2be80',
  'list mon udp':   '1251806ed1553fa7a97b514ab6744b6ec893dc55',
  'list nodes':     '95a3df823fa0f3e764e0eea24ca0550efaeba97f',
  'list rules':     '8b85e073cc3dcf303db34025e931a5286f26ce77', 
  'list virtuals':  'a11a885a65838bd6f3fc0e8d1ac2e554c1d50a1a'
}


#retrieve device level information
print('Retrieving Device Information')
device_info = retrieveDeviceInfo(qkviewNum)
deviceName = device_info[0][1]
qkvwDate = device_info[7][1]
#retrieve licensing and platform lifecycle (if hardware)
print('Retrieving Licensing Information')
license_info, interfaces = retrieveLicenseInfo(qkviewNum)

#retrieve object counts
print('Retrieving Object Counts')
object_counts = retrieveObjectCounts(qkviewNum)

print('Retrieving graphs')
graph_objects = retrieveGraphs(qkviewNum, deviceName, qkvwDate )

print('Retrieving Diagnostic report data...')
diags = retrieveDiagReport(qkviewNum)

# create document
doc = docxgen(path)
file = doc.create_device_report(device_info, license_info, interfaces, object_counts, graph_objects, diags)
print(f'file {file} was created')

removeGraphImages(graph_objects)






