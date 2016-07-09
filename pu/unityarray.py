#!/usr/bin/eval python
'''
PU - Python for Unity
Simple python bindings for snapshots on Unity
Draws from EMC Perl examples and EMC OpenStack driver(s) at https://github.com/emc-openstack/vnxe-cinder-driver
'''
# Turn this into a module, then turn it into something
# more object oriented.
# 2 July 2016
# Dickerson

import json
import logging
import sys

import requests
from requests.auth import HTTPBasicAuth


class unityarray:
    ''' class unityarray - a storage device which we creates snaps, LUNS, and filesystems
    '''

    def __init__(self, ipaddr, user='admin', password='Password123#'):
        ''' Create an array
        :param ipaddr: ip address
        :param user: administrative login
        :param password: Password
        :return:
        '''
        # Use the session to avoid repeatedly creating TCP sessions to the array

        # Urllib is noisy about bad certificates - turn this off.
        from requests.packages.urllib3.exceptions import InsecureRequestWarning
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

        def _ping(ip):
            '''
            from http://stackoverflow.com/questions/2953462/pinging-servers-in-python
            :param ip: ip address
            :return: true if reachable
            '''
            import subprocess, platform
            # Ping parameters as function of OS
            ping_str = "-n 1" if platform.system().lower() == "windows" else "-c 1"
            args = "ping " + " " + ping_str + " " + ip
            need_sh = False if platform.system().lower() == "windows" else True
            # Ping
            return subprocess.call(args, shell=need_sh) == 0

        def _authenticate(urlbase, name, passw, timeout):
            logging.debug('checking authentication')
            u = self.urlbase + '/api/types/system/instances'  # Simple get to check login access
            try:
                r = self.session.get(url=u,
                                     verify=False,
                                     headers=self.headers,
                                     auth=HTTPBasicAuth(user, password),
                                     timeout=self.timeout
                                     )
                if not r.ok:
                    self._printError("GET", r)
                cookies = r.cookies
                csrf_token = r.headers['emc-csrf-token']  # Add to headers to reduce risk of client side injection
                self.headers['EMC-CSRF-TOKEN'] = csrf_token
                self.cookies = self.session.cookies
                rc = True
            except:
                e = sys.exc_info()
                logging.critical(e)
                raise
            return rc

        # Ping the ipaddr to see if it is reachable
        try:
            rc = _ping(ipaddr)
            logging.debug('ping of {} succeeded'.format(ipaddr))
        except:
            logging.fatal("can't ping array {}".format(ipaddr))
            raise

        self.urlbase = 'https://{}:443'.format(ipaddr)
        logging.debug('host: {} - user: {} - password: {}'.format(ipaddr, user, password))
        self.headers = {'Accept': 'application/json',
                        '.Content-Type': 'application/json',
                        'Accept_language': 'en_US',
                        'X-EMC-REST-CLIENT': 'true'
                        }
        self.timeout = 12
        self.session = requests.Session()
        self.user = user
        self.password = password
        self.ipaddr = ipaddr
        self.oneGB = 1 * 1024 * 1024 * 1024
        if not _authenticate(self.urlbase, self.ipaddr, self.password, self.timeout):
            logging.critical("couldn't authenticate to array {}".format(ipaddr))

        logging.info('array instantiated')

    def _getSnapIdByName(self, snapName):
        '''

        :param snapName:
        :return:
         snapID
         False if the snapshot name doesn't already exist
        '''

        u = self.urlbase + '/api/types/snap/instances'  # All Snapshots
        returnCode = False
        ids = self._getIds(u)
        for snapId in ids:
            u = self.urlbase + '/api/instances/snap/{}?fields=name'.format(snapId)
            logging.debug(u)
            snapInstance = self.session.get(url=u)
            if snapInstance.ok:
                snapJson = (json.loads(snapInstance.content.decode('utf-8')))
                thisSnapName = snapJson['content']['name']
                if thisSnapName == snapName:
                    returnCode = snapJson['content']['id']
                    break
            else:
                self._printError("GET", snapInstance)
        return (returnCode)

    def _prettyJson(self, j):
        '''
        utility routine to print indented JSON
        :param j:
        :return:
        '''
        print(json.dumps(j, indent=2, sort_keys=True))

    def _getJSON(self, u):
        r = self.session.get(url=u)
        if r.ok:
            return (json.loads(r.content.decode('utf-8')))
        else:
            self._printError("GET", r)
            return False

    def _getAndPrintJson(self, u):
        '''
        get from the REST API and print
        mostly this is for debugging and understanding the API
        :param u:
        :return:
        '''
        logging.debug(u)
        instance = self._getJSON(u)
        if instance:
            self._prettyJson(instance)

    def _getIds(self, url):
        '''
        convenience routine to walk a list of instances, luns, etc
        and return their IDs
        :param url:
        :return:
        '''
        idList = []
        logging.debug(url)
        ids = self.session.get(url)
        if not ids.ok:
            self._printError("GET", ids)
        js = json.loads(ids.content.decode('utf-8'))
        # prettyJson(js)
        for entry in js['entries']:
            id = entry['content']['id']
            idList.append(id)
            # print ('id: {} idList: {}'.format(id,idList))
        return idList

    def _mapNameToStorageResourceID(self, lunName):
        instances = self._getIds(self.urlbase + '/api/types/lun/instances')
        storageResourceID = ""
        for i in instances:
            u = self.urlbase + '/api/instances/lun/{}?fields=name,storageResource'.format(i)
            logging.debug(u)
            lunInstance = self.session.get(url=u)
            if lunInstance.ok:
                lunJSON = (json.loads(lunInstance.content.decode('utf-8')))
                thisLunName = lunJSON['content']["name"]
                if thisLunName == lunName:
                    # storageResourceID = lunJSON['content']['storageResource']['id']
                    storageResourceID = lunJSON['content']['storageResource']
                    break
            else:
                self._printError("GET", lunInstance)
        return (storageResourceID)

    def _restToJSON(self, url):
        """ Utility code used for the numerous get requests which take a REST value and traslate to JSON"""
        returnValue = False
        logging.debug(url)
        instance = self.session.get(url=url)
        if instance.ok:
            returnValue = (json.loads(instance.content.decode('utf-8')))['content']
        else:
            self._printError("GET", instance)
        return returnValue

    def basicSystemInfo(self):
        """
        :return: string with systemInformation Fields

        """
        fields = "id,model,name,softwareVersion,apiVersion,earliestApiVersion"
        url = self.urlbase + '/api/instances/basicSystemInfo/0' + '?fields=' + fields
        return (self._restToJSON(url))

    def system(self):
        """ system"""
        fields = "id,health,name,model,serialNumber,internalModel,platform,macAddress,isEULAAccepted,isUpgradeComplete,isAutoFailbackEnabled,currentPower,avgPower"
        fields = "id,health,name,model,serialNumber,internalModel,platform,macAddress,isEULAAccepted"
        fields = fields + ",isUpgradeComplete"
        # There are a couple of additional fields which apparently do not work with virtualized Unity:
        # isAutoFailbackEnabled, currentPower, avgPower
        url = self.urlbase + '/api/instances/system/0' + '?fields=' + fields
        logging.debug(url)
        return self._restToJSON(url)

    def snapByName(self, lunName, snapName):
        """

        :rtype: JSON object representing the SNAP ID - or False
        """
        returnCode = False
        # map the lunName to the storageResourceID
        storageResourceID = self._mapNameToStorageResourceID(lunName)
        if not storageResourceID:
            logging.warning("couldn't find a LUN named {}".format(lunName))
            return returnCode

        # make sure the snap shot doesn't already exist
        if self._getSnapIdByName(snapName):
            logging.warning("snapshot name {} already exists - please pick a different name".format(snapName))
            return returnCode

        # create the snap
        u = self.urlbase + '/api/types/snap/instances'
        storageResourceID = json.dumps(storageResourceID)
        body = '{' + '"storageResource" : {} , "name" : "{}" '.format(storageResourceID, snapName) + '}'

        r = self.session.post(url=u, data=body, headers=self.headers, verify=False)
        if r.ok:
            returnCode = pu.snap(array=self, name=snapName)
        return returnCode

    def deleteSnap(self, snapName='', snapID=''):
        '''

        :param snapName: a string with the logical name of the snapShot
        :return: False on failure, True on success
        '''
        returnCode = False
        if not snapName and not snapID:
            print('need to provide either snapName or snapID')
            return returnCode
        if not snapID:
            # If we were provided a name, and not iD find the ID
            # If we received both, ID over-rides name
            snapID = self._getSnapIdByName(snapName)
        if snapID:
            returnCode = self._deleteSnapByID(snapID)
        return (returnCode)

    def _deleteSnapByID(self, snapID):
        '''
        Delete a SNAP shot by Snap ID
        :param snapID: A String with the snapID
        :return: False on failure, True on success
        '''
        returnCode = False
        logging.debug('_deleteSnapByID({})'.format(snapID))
        # How do we check input here?
        u = self.urlbase + '/api/instances/snap/' + snapID
        r = self.session.delete(url=u, verify=False, headers=self.headers)
        if r.ok:
            returnCode = True
        return (returnCode)

    def listPools(self):
        ''' list all existing pools'''
        returnCode = False
        logging.debug('method listPools')
        u = self.urlbase + '/api/types/pool/instances'
        instances = self._getIds(url=u)
        for i in instances:
            fields = 'id,health,name,description,storageResourceType,raidType,sizeFree,sizeTotal,sizeUsed,\
                    sizeSubscribed,alertThreshold,isFASTCacheEnabled,tiers,creationTime,isEmpty,poolFastVP,\
                    isHarvestEnabled,harvestState,isSnapHarvestEnabled,poolSpaceHarvestHighThreshold,\
                    poolSpaceHarvestLowThreshold,snapSpaceHarvestHighThreshold, snapSpaceHarvestLowThreshold,\
                    metadataSizeSubscribed,snapSizeSubscribed,metadataSizeUsed,snapSizeUsed,\
                    rebalanceProgress'

            u = self.urlbase + '/api/instances/pool/{}'.format(i) + '?fields=' + fields
        j = self._getJSON(u)
        if j:
            returnCode = j
        return returnCode

    def _printError(self, verb, response):
        errorText = ""
        errorCode = response.status_code
        msgs = json.loads(response.text)['error']['messages']
        for m in msgs:
            errorText = errorText + m['en-US']
        logging.warning(
            '{} failed with status {} details: {}'.format(verb, errorCode, errorText))

    def createLUN(self, name, pool, size=(3 * 1024 * 1024 * 1024), description="", lunParameters="",
                  isThinEnabled=True, fastVPParameters="",
                  defaultNode="", hostAccess="", ioLimitParameters=""):
        ''' Build new LUN'''

        returnCode = False

        logging.debug('createLun({} {},...)'.format(name, description))

        if not name:
            logging.critical('must supply a name in createLUN()')
            return False

        ## Create LUN Parameters
        poolID = self._getPoolIdByPoolName(pool)
        poolDict = {}
        poolDict['id'] = poolID

        # create lunParameters Structure
        lpDict = {}
        lpDict['size'] = size
        lpDict['pool'] = poolDict
        if isThinEnabled:
            lpDict['isThinEnabled'] = isThinEnabled

        # Form the message body for lunCreate API
        bodyDict = {}
        bodyDict['name'] = name
        if description:
            description = description[0:170]  # max 170 characters
            bodyDict['description'] = description
        bodyDict['lunParameters'] = lpDict
        body = json.dumps(bodyDict)
        # print(body)

        # Create the LUN
        u = self.urlbase + '/api/types/storageResource/action/createLun'
        r = self.session.post(url=u, data=body, headers=self.headers, verify=False)
        if r.ok:
            js = json.loads(r.content.decode('utf-8'))
            lunID = js['content']['storageResource']['id']
            returnCode = lunID
        else:
            self._printError("POST", r)
            returnCode = False

        return returnCode

    def deleteStorage(self, id=None, name=None, resourceType='lun'):
        '''

        :param lunID: an internal ID which references the resource of filesystem ID, typically as returned by _getIDs()
        :param lunName: name of the resource to be deleted
        :param resourceType: lun|block -or- fs|file --- defaults to lun
        :return: True on success; else False
        '''
        resourceType.lower()  # make it simple on our users
        storageResource = {}
        if not resourceType in ('lun', 'fs', 'filesystem'):
            logging.error(
                "must pass valid resourceType to deleteStorage 'lun','block','fs',or 'file', you passed{}".format(
                    resourceType))
            return False

        lun = None
        if resourceType == "lun":
            # prepare to delete a LUN
            if id:
                storageResource = self.getStorageDict(id=id)
            elif name:
                storageResource = self.getStorageDict(name=name)
            elif not id and not name:
                logging.critical('you must supply id or name to deleteStorage()')
                return False
        else:
            # prepare to delete a file system
            logging.critical('type {} not implemented'.format(resourceType))
            return False

        # following code is germane to deleting a LUN or filesystem

        # Create the command body - current behavior is
        # to dump all snaps and vvols associated with this LUN
        bodyDict = {}
        bodyDict['forceSnapDeletion'] = 'true'
        bodyDict['forceVvolDeletion'] = 'true'
        body = json.dumps(bodyDict)
        id = storageResource['id']
        u = self.urlbase + '/api/instances/storageResource/{}'.format(id)
        # Delete
        r = self.session.delete(url=u, data=body, headers=self.headers, verify=False)
        if r.ok:
            retCode = True
        else:
            logging.warning('failed to retrieve {} name: {} id: {}', resourceType, name, name)
            retCode = False
        return (retCode)

    def getNASServers(self):
        """
            return: list of NAS servers on Success
                    False on failure
        """
        retCode = []
        u = self.urlbase + '/api/types/nasServer/instances'
        ids = self._getIds(u)
        fields = 'id,name,health,homeSP,currentSP,pool,sizeAllocated,isReplicationEnabled,isReplicationDestination,\
        replicationType,defaultUnixUser,defaultWindowsUser,currentUnixDirectoryService,isMultiProtocolEnabled,\
        isWindowsToUnixUsernameMappingEnabled,allowUnmappedUser,cifsServer,preferredInterfaceSettings,fileDNSServer,\
        fileInterface,virusChecker'
        # get rid of the blanks in the string
        fields = fields.replace(" ", "")
        fields = fields.replace('\i', '')
        Valid = False
        for id in ids:
            u = self.urlbase + '/api/instances/nasServer/{}'.format(id) + '?fields=' + fields
            nasJson = self._getJSON(u)
            if nasJson:
                Valid = True
                retCode.append(nasJson)
        if not Valid:
            retCode = False
        return retCode

    def getNASIdFromName(self, nasname):
        '''

        :param nasname: - the name that the user calls this NAS
        :return: integer ID or False
        '''

        u = self.urlbase + '/api/types/nasServer/instances'  # All Snapshots
        returnCode = False
        ids = self._getIds(u)
        for nasId in ids:
            u = self.urlbase + '/api/instances/nasServer/{}?fields=name'.format(nasId)
            logging.debug(u)
            nasInstance = self.session.get(url=u)
            if nasInstance.ok:
                nasJson = (json.loads(nasInstance.content.decode('utf-8')))
                thisNASName = nasJson['content']['name']
                if thisNASName == nasname:
                    returnCode = nasJson['content']['id']
                    break
            else:
                self._printError("GET", nasInstance)
        return (returnCode)

    def getNASById(self, nasID):
        '''
        :param nasID: ID of NAS in question, probably returned by the method self.getNASIdFromName
        :return: string, with JSON as returned form the REST API -or- False
        '''
        serverList = self.getNASServers()
        returncode = False
        for nas in serverList:
            listNasID = nas['content']['id']
            if listNasID == nasID:
                returncode = json.dumps(nas['content'])
                break
        return returncode

    def getNASByName(self, name):
        """

        :param name:
        :return: NAS String or False
        """
        ReturnCode = False
        NasID = self.getNASIdFromName(name)
        if NasID:
            NAS = self.getNASById(NasID)
            if NAS:
                ReturnCode = NAS
        return ReturnCode

    def _getPoolByName(self, name):
        instances = self._getIds(self.urlbase + '/api/types/pool/instances')
        pool = None
        for i in instances:
            u = self.urlbase + '/api/instances/pool/{}?fields=id,name'.format(i)
            logging.debug(u)
            pool = self.session.get(url=u)
            if pool.ok:
                poolJSON = (json.loads(pool.content.decode('utf-8')))
                thisPoolName = poolJSON['content']["name"]
                if thisPoolName == name:
                    # Found what we are looking for.  Return
                    pool = json.dumps(poolJSON['content'])
                    break
            else:
                self._printError("GET", pool)
        return pool

    def _getPoolIdByPoolName(self, poolName):
        poolID = False
        pool = self._getPoolByName(poolName)
        if not pool:
            return False
        if pool:
            poolDict = json.loads(pool)
            poolID = poolDict['id']
        return (poolID)

    def createFileSystem(self, name, pool, size, nasServer, description='', isThinEnabled='true', sizeAllocated=None):
        '''
        Create a Filesytem
        :param description:
        required:
           name - String - up to 95 characters
           pool
           nasServer - JSON, encoded as String, as returned from GetNASByName()
        :param pool:
        :param size:
        :param NasServer:
        :return:
        '''
        # build the fileSystemsParameters Structure
        if size < 3 * self.oneGB:
            # min fs size is 3G
            size = 3 * self.oneGB

        returnCode = False
        logging.debug('createFileSystem {}'.format(name))

        ## Need to create a dictionary representation for the JSON {"id":"poolID"}
        ## Change the pool Variable to contain just that representation

        poolDict = {}
        poolDict['id'] = json.loads(self._getPoolByName(pool))['id']
        pool = poolDict
        del poolDict
        logging.debug(pool)

        ## Need to create a dictionary representation for the JSON { {"id":"nasServerID"}
        ## change the NasServer variable

        # nasServerDict = {}
        # nasServerDict['id'] = json.loads(nasServer)['id']
        # nasServer = nasServerDict
        # del nasServerDict
        logging.debug(nasServer)

        # Create the Body of the Request
        # Starting with the File System Parameters Structure
        fsp = {}
        fsp['pool'] = pool
        fsp['size'] = size
        fsp['supportedProtocols'] = 0
        fsp['isThinEnabled'] = 'true'
        ### The API doesn't seem to like the full nasServer.  Abbreviate it.
        myNasServer = {}
        myNasServer['name'] = nasServer['name']
        myNasServer['id'] = nasServer['id']
        fsp['nasServer'] = myNasServer
        body = {}
        body['name'] = name
        body['description'] = description
        body['fsParameters'] = fsp
        body = json.dumps(body)
        logging.debug(body)

        u = self.urlbase + '/api/types/storageResource/action/createFilesystem'
        r = self.session.post(url=u, data=body, headers=self.headers, verify=False)
        if r.ok:
            js = r.json()
            # js = json.loads(r.content.decode('utf-8'))
            lunID = js['content']['storageResource']['id']
            returnCode = lunID
        else:
            self._printError("POST", r)
        return returnCode

    def getNAS(self, name):
        return self.getStorageDict(resourceType="nas", name=name)

    def getNFS(self, name):
        return self.getStorageDict(resourceType="nfs", name=name)

    def getFS(self, name):
        return self.getStorageDict(resourceType="fs", name=name)

    def getLUN(self, name):
        return self.getStorageDict(resourceType="lun", name=name)


    def getStorageDict(self, resourceType="lun", name="", id=""):
        """

        :param self:
        :param resourceType: "lun" or "fs" or "nas"
        :param name: the resource Name   [ Note - only need name or id, not both ]
        :param id: the resource ID
        :return: dictionary for the storage resource or None
        """
        lunfields = 'id,name,health,description,type,sizeTotal,sizeUsed,sizeAllocated,perTierSizeUsed,isThinEnabled,\
            storageResource,pool,wwn,tieringPolicy,defaultNode,currentNode,snapSchedule,isSnapSchedulePaused,\
            ioLimitPolicy,metadataSize,metadataSizeAllocated,snapWwn,snapsSize,snapsSizeAllocated,hostAccess,snapCount'
        nfsfields = (
            'id,hostName,nasServer,fileInterfaces,nfsv4Enabled,isSecureEnabled,kdcType,servicePrincipalName'
            ',isExtendedCredentialsEnabled,credentialsCacheTTL'
        )
        fsfields = 'id,health,name,description,type,sizeTotal,sizeUsed,sizeAllocated,isReadOnly,isThinEnabled,\
            storageResource,pool,nasServer,tieringPolicy,supportedProtocols,metadataSize,metadataSizeAllocated'
        nasfields = (
            'id,name,health,homeSP,currentSP,pool,sizeAllocated,isReplicationEnabled,replicationType'
            ',defaultUnixUser,defaultWindowsUser,currentUnixDirectoryService,isMultiProtocolEnabled'
            ',isWindowsToUnixUsernameMappingEnabled,allowUnmappedUser,cifsServer,preferredInterfaceSettings'
            ',fileDNSServer,fileInterface,virusChecker'
        )
        resourceType = resourceType.lower()
        if resourceType == 'lun':
            # Here when we are looking for a LUN
            urlAPI = '/api/types/lun/instances'
            fields = lunfields
        elif resourceType == 'nfs':
            # Here when we are looking for a file system
            urlAPI = '/api/types/nfsServer/instances'
            fields = nfsfields
        elif resourceType == 'fs':
            # Here when we are looking for a file system
            urlAPI = '/api/types/filesystem/instances'
            fields = fsfields
        elif resourceType == 'nas':
            # Here when we need a NAS instance ( the filer/data mover )
            urlAPI = '/api/types/nasServer/instances'
            fields = nasfields
        else:
            logging.critical('unknown resource type {} passed to getStorageDict'.format(resourceType))
            return False

        if id != "":
            # get by id
            u = self.urlbase + urlAPI + '?fields=' + fields + '&filter=id eq "{}"'.format(id)
        elif name != "":
            # get by name
            if resourceType == 'nfs':
                u = self.urlbase + urlAPI + '?fields=' + fields + '&filter=hostName eq "{}"'.format(name)
                u = self.urlbase + urlAPI + '?fields=' + fields
            else:
                u = self.urlbase + urlAPI + '?fields=' + fields + '&filter=name eq "{}"'.format(name)
        else:
            return False
        # get the storage Resource based on this name
        sr = self.session.get(url=u)
        if sr.ok:
            tmpDict = sr.json()
            if tmpDict['entries']:
                srDict = json.loads(sr.content.decode('utf-8'))['entries'][0]['content']
            else:
                logging.debug('No value returned from the array for name {}'.format(name))
                srDict = False
            return (srDict)
        else:
            self._printError('GET', sr)
            return None