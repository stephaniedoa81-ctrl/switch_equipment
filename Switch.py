

#%% #Library importing
import time
import sys
import numpy as np
from NvidiaCmd import SW_CMD as Nvida_SW_CMD
from SSH import Ssh
#import pyvisa
from numpy import array
#rm = pyvisa.ResourceManager()
# instr = rm.open_resource("GPIB0::2::INSTR")

class Switch:
    def __init__(self, switch_IP, switch_user_name, switch_pw):
        ssh = Ssh(switch_IP, 22, switch_user_name, switch_pw)
        self.CMD = Nvida_SW_CMD(ssh)

if __name__ == "__main__":
    switch_type = "Nvidia"
    if switch_type == "Arista1":
        switch_IP = '10.74.179.248'
        switch_user_name = "neo1234"
        switch_pw = "neo1234"
    if switch_type == "Arista2":
        switch_IP = '10.74.179.248'
        switch_user_name = "neo1234"
        switch_pw = "neo1234"
    elif switch_type == "Nvidia":
        #switch_IP = '10.74.181.250'
        switch_IP = '192.168.1.236'
        switch_user_name = "admin"
        switch_pw = "password"
    cswitch = Switch(switch_IP, switch_user_name, switch_pw)
    port = 31
    d = cswitch.CMD.Get_all_lanes(port)
    print(d)

#for lane in range(1,2):
#    d = CMD.Get_one_lane(port, lane)
#    print(d)
