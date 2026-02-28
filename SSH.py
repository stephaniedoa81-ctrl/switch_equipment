# ==================================================================================
# Project: GoogleLineSys
# Authors:
# - Lei Zhang (lei.zhang1@lumentum.com)
# - Breno Alves (breno.alves@lumentum.com)
# ==================================================================================


import sys
from datetime import datetime
import os
from os import path
import time

import paramiko

#from GoogleLineSys.logger import get_logger
from logger import get_logger
logger = get_logger()

#from paramiko import RSAKey
# from paramiko.py3compat import decodebytes
    

class Ssh:

    #client = paramiko.SSHClient()
    #_fn= os.getcwd() + now.strftime('/Test Data/CmdLog_%m_%d_%Y_%H_%M_%S.txt')
    #_sMsg=""

    def log(self, strdata):
        # f=open(self._fn,"a")
        # f.write(strdata)
        # f.close
        logger.info(strdata)

    def __init__(self,hostname="10.54.18.8",port=22,username="neo1234",password="neo1234"):
        self._hostname=hostname
        self._port=port
        self._username=username
        self._password=password
        self._errCount=0

        if not os.path.exists('Cmd Data'):
            os.mkdir('Cmd Data')


        # self._fn = os.getcwd() + datetime.now().strftime("/Cmd Data/CmdLog_%m_%d_%Y_%H_%M_%S.txt")

        # f=open(self._fn,"w")
        # f.write('======================Command Log=======================\r\n\r\n')
        # f.close    
       
    # def open(self):
        
        # try:
         
            # self._client = paramiko.SSHClient()


            # self._client.load_system_host_keys()

            # #self._client.set_missing_host_key_policy(paramiko.WarningPolicy)
            # self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy()) 



            # self._client.connect(hostname=self._hostname, port=22, username=self._username, password=self._password)
            # #out= self._client.get_host_keys()
            # self._chan=self._client.invoke_shell()
            # out=self._chan.recv(2000)
            # print (out)
            # sMsg="SSH is connected to %s !" % self._hostname
            # self.log(sMsg)        
            # print (sMsg)

        # except paramiko.AuthenticationException:
            # self._errCount +=1
            # sMsg="Authentication failed when connecting to %s" % self._hostname
            # self.log(sMsg)        
            # print (sMsg)
     
            # self._client.close()

            # raise Exception(sMsg) 

        # except:
            # self._errCount +=1
            # sMsg="Could not SSH to %s, waiting for it to start" % self._hostname
            # self.log(sMsg)        
            # print (sMsg)
      
            # self._client.close()
            # raise Exception(sMsg) 

    def open(self):
        
        #try:
         
            self._client = paramiko.SSHClient()


            self._client.load_system_host_keys()

            #self._client.set_missing_host_key_policy(paramiko.WarningPolicy)
            self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy()) 



            self._client.connect(hostname=self._hostname, port=22, username=self._username, password=self._password)
            #out= self._client.get_host_keys()
            self._chan=self._client.invoke_shell()
            out=self._chan.recv(2000)
            print (out)
            sMsg="SSH is connected to %s !" % self._hostname
            self.log(sMsg)        
            print (sMsg)

        # except paramiko.AuthenticationException:
            # self._errCount +=1
            # sMsg="Authentication failed when connecting to %s" % self._hostname
            # self.log(sMsg)        
            # print (sMsg)
     
            # self._client.close()

            # raise Exception(sMsg) 

        # except:
            # self._errCount +=1
            # sMsg="Could not SSH to %s, waiting for it to start" % self._hostname
            # self.log(sMsg)        
            # print (sMsg)
      
            # self._client.close()
            # raise Exception(sMsg) 
        

    def close(self):
        self._client.close()

    @property
    def HostName(self):
        return self._hostname

    @HostName.setter
    def IP(self, val):
        self._hostname = val



    def send(self,sCmd,dwellTime=0.4):

        sOut=""
        status=False
       # sOut=stdout.read().decode().strip()
        try:
            
            self._chan.send(sCmd+'\r')
            #stdin, stdout, stderr = self._client.exec_command(sCmd+'\r')
            #while not self._session.recv_ready():

            time.sleep(dwellTime)

            for kk in range(0,100):
                buf=self._chan.recv(40000)
                sOut += buf.decode('utf-8').strip()
 
                if  sOut.find("switch>") !=-1 or sOut.find(")#") !=-1 or sOut.find("]$") or  sOut.find('[yes/no/cancel/diff]:') !=-1!=-1: 



                    #if sOut.find(sCmd) !=-1:
                    status=True
                    break

                if kk >= 99:
                    print ("Error! Time out")
                    break
            
        except paramiko.ChannelException:
            self._errCount +=1
            print ("Error! Channel Exception")

            self.log(time.strftime('%H:%M:%S >>') +"Error! Send {0} to SSH {1} failed!".format(sCmd, self._hostname))


            self.close()
            self.open()
  

        except paramiko.CouldNotCanonicalize:
            self._errCount +=1
            print ("Error! CouldNotCanonicalize")

            self.log(time.strftime('%H:%M:%S >>') +"Error! Send {0} to SSH {1} failed!".format(sCmd, self._hostname))

            self.close()
            self.open()


        except paramiko.BadHostKeyException:
            self._errCount +=1
            print ("Error! BadHostKeyException")

            self.log(time.strftime('%H:%M:%S >>') +"Error! Send {0} to SSH {1} failed!".format(sCmd, self._hostname))



            self.close()
            self.open()


        except paramiko.ChannelException:
            self._errCount +=1
            print ("Error! Send {0} to SSH {1} failed!".format(sCmd, self._hostname))

            self.log(time.strftime('%H:%M:%S >>') +"Error! Send {0} to SSH {1} failed!".format(sCmd, self._hostname))


            print ("Error! too many errors, reinitiaize the SSH channel")
            self.close()
            self.open()

        except:

            self._errCount +=1
            print ("Error! Send {0} to SSH {1} failed!".format(sCmd, self._hostname))

            self.log(time.strftime('%H:%M:%S >>') +"Error! Send {0} to SSH {1} failed!".format(sCmd, self._hostname))

            print ("Error! too many errors, reinitiaize the SSH channel")

            self.close()
            self.open()
         



        #tdout = self._client.exec_command(sCmd)
        finally:
            print (">> %s " % sCmd)

            sOut1=sOut.replace(sCmd+'\r\n',"")   
            print ("<< %s " % sOut1)


            self.log(time.strftime('[%H:%M:%S] >>') +"  %s \r\n" % sCmd)
            self.log("<< %s \r\n" % sOut1)


        #f.close 
        return sOut1, status

    # def download(self,sCmd):

    #     sOut=""
    #     status=False
    #    # sOut=stdout.read().decode().strip()
    #     try:
            
    #         self._chan.send(sCmd+'\r')
    #         #stdin, stdout, stderr = self._client.exec_command(sCmd+'\r')
    #         #while not self._session.recv_ready():

    #         print (">> %s " % sCmd)

    #         sOut1=sOut.replace(sCmd+'\r\n',"")   

    #         time.sleep(0.01)

    #         while True:
    #         #sOut=stdout.read().decode().strip()
    #             #sReceived=self._chan.recv(10000)
    #             sOut = self._chan.recv(4096).decode('utf-8').strip()

    #             if sOut.find("complete  verify succeed") !=-1 : 
    #                 status=True
    #                 break

    #             print (sOut)
            
    #     except paramiko.ChannelException:
    #         self._errCount +=1
    #         print ("Error! Channel Exception")

    #         self.log(time.strftime('%H:%M:%S >>') +"Error! Send {0} to SSH {1} failed!".format(sCmd, self._hostname))


    #         self.close()
 
    #     except:

    #         self._errCount +=1
    #         print ("Error! Send {0} to SSH {1} failed!".format(sCmd, self._hostname))

    #         self.log(time.strftime('%H:%M:%S >>') +"Error! Send {0} to SSH {1} failed!".format(sCmd, self._hostname))

    #         print ("Error! too many errors, reinitiaize the SSH channel")

    #         self.close()
         
    #     #tdout = self._client.exec_command(sCmd)
    #     finally:
    #         self.log(time.strftime('[%H:%M:%S] >>') +"  %s \r\n" % sCmd)
    #         self.log("<< %s \r\n" % sOut)

    #     #f.close 
    #     return sOut1, status 


    def dfwCommit(self,sCmd,dwellTime=0.4):

        sOut=""
        status=False
       # sOut=stdout.read().decode().strip()
        try:
            
            self._chan.send(sCmd+'\r')
            #stdin, stdout, stderr = self._client.exec_command(sCmd+'\r')
            #while not self._session.recv_ready():

            time.sleep(dwellTime)

            for kk in range(0,100):
                buf=self._chan.recv(10000)
                sOut += str(buf).strip()
 
                if  sOut.find("switch>") !=-1 or sOut.find(")#") !=-1 or sOut.find("]$") !=-1: 
                    if sOut.find(sCmd) !=-1:
                        status=True
                    break

                if kk >= 99:
                    print ("Error! Time out")
                    break


        except:

            self._errCount +=1
            print ("Error! Send {0} to SSH {1} failed!".format(sCmd, self._hostname))

            self.log(time.strftime('%H:%M:%S >>') +"Error! Send {0} to SSH {1} failed!".format(sCmd, self._hostname))

            print ("Error! too many errors, reinitiaize the SSH channel")

            self.close()
            self.open()
         



        #tdout = self._client.exec_command(sCmd)
        finally:
            print (">> %s " % sCmd)

            sOut1=sOut.replace(sCmd+'\r\n',"")   
            print ("<< %s " % sOut1)


            self.log(time.strftime('[%H:%M:%S] >>') +"  %s \r\n" % sCmd)
            self.log("<< %s \r\n" % sOut)


        #f.close 
        return sOut1, status






    def dfwDownload(self,sCmd):

        sOut=""
        status=False
       # sOut=stdout.read().decode().strip()
        try:
            
            self._chan.send(sCmd+'\r')
            #stdin, stdout, stderr = self._client.exec_command(sCmd+'\r')
            #while not self._session.recv_ready():

            print (">> %s " % sCmd)

            #sOut1=sOut.replace(sCmd+'\r\n',"")   

            time.sleep(0.01)

            while True:
            #sOut=stdout.read().decode().strip()
                #sReceived=self._chan.recv(10000)
                sOut = self._chan.recv(4096).decode('utf-8').strip()

                if sOut.find("verify succeed") !=-1 : 
                    status=True
                    break
                if sOut.find("verify failed") !=-1 : 
                    status=False
                    break

                print (sOut)
            print (sOut)
        except paramiko.ChannelException:
            self._errCount +=1
            print ("Error! Channel Exception")

            self.log(time.strftime('%H:%M:%S >>') +"Error! Send {0} to SSH {1} failed!".format(sCmd, self._hostname))


            self.close()
 
        except:

            self._errCount +=1
            print ("Error! Send {0} to SSH {1} failed!".format(sCmd, self._hostname))

            self.log(time.strftime('%H:%M:%S >>') +"Error! Send {0} to SSH {1} failed!".format(sCmd, self._hostname))

            print ("Error! too many errors, reinitiaize the SSH channel")

            self.close()
         
        #tdout = self._client.exec_command(sCmd)
        finally:
            self.log(time.strftime('[%H:%M:%S] >>') +"  %s \r\n" % sCmd)
            self.log("<< %s \r\n" % sOut)

        #f.close 
        return status        
