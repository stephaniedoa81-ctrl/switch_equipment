from time import sleep
import time
from random import randint
import numpy as np
import re
import math
import ast
import re
from typing import List, Optional, Tuple
from logger import get_logger
logger = get_logger()

_RX_RE = re.compile(r"RX(\d+)Power:\s*([+-]?\d+(?:\.\d+)?)\s*dBm", re.IGNORECASE)
_TX_RE = re.compile(r"TX(\d+)Power:\s*([+-]?\d+(?:\.\d+)?)\s*dBm", re.IGNORECASE)

class RspHeader:
   def __init__(self): #Elements will be added later
       pass


class ArgHeader:
   def __init__(self): #Elements will be added later
       pass


class SW_CMD:


    def __init__(self, Ssh):
        self._ssh = Ssh
        self._ssh.open()

        #self.enable()
        #self.config()

        #self.disablePaging()
        


    def Get_all(self, ethernet:int):
        CMD = self
        d = {}
        st = time.time()
        d['tp5_0'] = CMD.GetBER(ethernet)
        dt = time.time()-st
        st = time.time()
        print(f'tp5_0 time = {dt} seconds')
        d['tp5_1'] = CMD.GetFECHistogram(ethernet)
        dt = time.time()-st
        st = time.time()
        print(f'tp5_1 time = {dt} seconds')
        d['tp3_RxPwr'] = CMD.GetRXLanePwr(ethernet)
        dt = time.time()-st
        st = time.time()
        print(f'tp3 time = {dt} seconds')
        d['tp2_TxPwr'] = CMD.GetTXLanePwr(ethernet)
        dt = time.time()-st
        st = time.time()
        print(f'tp2 time = {dt} seconds')
        #d['tp0'] = CMD.GetTP0(ethernet)
        #dt = time.time()-st
        #st = time.time()
        #print(f'tp0 time = {dt} seconds')
        d['tp4'] = CMD.GetTP4(ethernet)
        dt = time.time()-st
        st = time.time()
        print(f'tp4 time = {dt} seconds')
        r = CMD.GetHostMediaBER(ethernet)
        print(r)
        if r['result']:
            d['host_media_ber'] = r['data']
        else:
            d['host_media_ber'] = "N/A; N/A"
        dt = time.time()-st
        st = time.time()
        print(f'host_media time = {dt} seconds')
        return d

    def Get_all_port(self, port:int):
        ethernet_list = [(port -1) * 8 + i for i in range(8)]
        CMD = self
        list_item=['tp5_0', 'tp5_1', 'tp3_RXPwr', 'tp2_TXPwr', 'tp0', 'tp4']
        d = {}
        st = time.time()
        stt = st
        for lane in range(1,9):
            d[lane] = {}
            for item in list_item:
                d[lane][item] = None
        r0 = CMD.GetTXRXPortPwr(port)
        dt = time.time()-st
        st = time.time()
        print(f'tp3+tp2 time = {dt} seconds')
        r1 = CMD.GetHostMediaPortBER(port)
        dt = time.time()-st
        st = time.time()
        print(f'host media time = {dt} seconds')
        for lane in range(1,9):
            d[lane]['tp3_RXPwr'] = r0[0][lane-1]
            d[lane]['tp2_TXPwr'] = r0[1][lane-1]
            if r1['result']:
                d[lane]['host_media_ber'] = r1['data'][lane]
            else:
                d[lane]['host_media_ber'] = "N/A; N/A"
        for ethernet in ethernet_list:
            lane = ethernet%8 + 1
            st = time.time()
            d[lane]['tp5_0'] = CMD.GetBER(ethernet)
            dt = time.time()-st
            st = time.time()
            print(f'tp5_0 time = {dt} seconds')
            d[lane]['tp5_1'] = CMD.GetFECHistogram(ethernet)
            dt = time.time()-st
            st = time.time()
            print(f'tp5_1 time = {dt} seconds')
            #d[lane]['tp0'] = CMD.GetTP0(ethernet)
            #dt = time.time()-st
            #st = time.time()
            #print(f'tp0 time = {dt} seconds')
            d[lane]['tp0'] = [0, 0, 0, 0]
            d[lane]['tp4'] = CMD.GetTP4(ethernet)
            dt = time.time()-st
            st = time.time()
            print(f'tp4 time = {dt} seconds')
        dt = time.time()-stt
        print(f'total time = {dt} seconds')
        return d
        
    def GetBER(self, ethernet:int):
        for i in range (3):
            sCmd = f"portstat -f -i Ethernet{ethernet}"
            sReturn = self._ssh.send(sCmd, 2)
            print (sReturn)
            r = self.parse_fec_ber(sReturn, ethernet)
            if r[0]:
                return r[1]
        return ["N/A; N/A"]

    def GetFECHistogram(self, ethernet:int):
        sCmd = f"show interface counters fec-histogram Ethernet{ethernet}"
        sReturn = self._ssh.send(sCmd, 2)
        r = self.parse_bin_counters(sReturn)
        return r

    def GetRXLanePwr(self, ethernet:int):
        lane = (ethernet % 8) + 1
        power_string =  f'RX{lane}Power'
        sCmd = f'show interface trans eeprom -d Ethernet{ethernet} | grep {power_string}'
        sReturn = self._ssh.send(sCmd, 2)
        r = self.parse_power(sReturn, power_string)
        return r


    def GetTXLanePwr(self, ethernet:int):
        lane = (ethernet % 8) + 1 
        power_string =  f'TX{lane}Power'
        sCmd = f'show interface trans eeprom -d Ethernet{ethernet} | grep {power_string}'
        sReturn = self._ssh.send(sCmd, 2)
        r = self.parse_power(sReturn, power_string)
        return r
        
    def GetTP0(self, ethernet:int):
        lane = (ethernet % 8) + 1
        port = int(math.floor(ethernet / 8)) + 1
        if lane == 1:
            sCmd = f'sudo mlxlink -d /dev/mst/mt53122_pci_cr0 -p {port} --show_serdes_tx |grep "Lane 0"'
        else:
            sCmd = f'sudo mlxlink -d /dev/mst/mt53122_pci_cr0 -p {port}/{lane} --show_serdes_tx |grep "Lane 0"'
        r = self._ssh.send(sCmd, 2)
        return self.parse_lane_values(r)

    def GetTP4(self, ethernet:int):
        sCmd = f"sudo sfputil read-eeprom -p Ethernet{ethernet}"
        sCmd += " -n 11 -o 223 -s 12"
        r = self._ssh.send(sCmd, 2)
        rS1 =  r[0].split()[1:5]
        rS2 =  r[0].split()[5:9]
        rS3 =  r[0].split()[9:13]
        #000000df 00 00 00 00 00 00 00 00  11 11 22 22             |..........""|
        lane = (ethernet % 8)
        value1 = self.expand_lane_map(rS1)[lane]
        value2 = self.expand_lane_map(rS2)[lane]
        value3 = self.expand_lane_map(rS3)[lane]
        return [value1, value2, value3]
        
    def GetHostMediaBER(self, ethernet: int):
        first_ethernet = int(ethernet/8)*8
        sCmd = f"sudo config int trans dom Ethernet{first_ethernet} enable"
        r = self._ssh.send(sCmd, 2)
        sCmd = f" sonic-db-cli -n '' STATE_DB hgetall 'TRANSCEIVER_VDM_REAL_VALUE|Ethernet{first_ethernet}'"
        r = self._ssh.send(sCmd, 2)
        if len(r) >= 2:
            r = r[0]
            r = r.split('{')
            r = r[1].split('}')
            r = r[0].split('"')
            d = ast.literal_eval("{" + r[0] + "}")
            if not len(d) == 0:
                for item in d:
                    print(f'{item}: {d[item]}')
                lane = (ethernet % 8) + 1
                host_item = f'prefec_ber_curr_host_input{lane}'
                media_item = f'prefec_ber_curr_media_input{lane}'
                return {'result': True, 'data':[d[host_item],d[media_item]]}
        return {'result': False}

    def GetTXRXPortPwr(self, port:int):
        ethernet = (port - 1)*8
        sCmd = f'show interface trans eeprom -d Ethernet{ethernet}'
        output = self._ssh.send(sCmd, 2)
        r = self.parse_lane_powers(output[0])
        return r

    def GetHostMediaPortBER(self, port: int):
        first_ethernet = (port - 1)*8
        sCmd = f"sudo config int trans dom Ethernet{first_ethernet} enable"
        r = self._ssh.send(sCmd, 2)
        sCmd = f" sonic-db-cli -n '' STATE_DB hgetall 'TRANSCEIVER_VDM_REAL_VALUE|Ethernet{first_ethernet}'"
        r = self._ssh.send(sCmd, 2)
        if len(r) >= 2:
            r = r[0]
            r = r.split('{')
            r = r[1].split('}')
            r = r[0].split('"')
            d = ast.literal_eval("{" + r[0] + "}")
            if not len(d) == 0:
                for item in d:
                    print(f'{item}: {d[item]}')
                data = {}
                for lane in range (1, 9):
                    host_item = f'prefec_ber_curr_host_input{lane}'
                    media_item = f'prefec_ber_curr_media_input{lane}'
                    data[lane] = [d[host_item],d[media_item]]
                return {'result': True, 'data':data}
        return {'result': False}
      
    def parse_fec_ber(self, equipment_response: list, ethernet: int):
    #def parse_equipment_output(equipment_response):
        """
        Extract FEC_PRE_BER and FEC_POST_BER for Ethernet{ethernet} from SSH command output.
        
        Parameters:
            equipment_response (tuple): (output_string, success_flag)
        
        Returns:
            dict: Parsed data containing interface name, FEC_PRE_BER, and FEC_POST_BER.
        """
        output = equipment_response[0]  # The first element is the actual output string
        
        # Remove command prompt lines
        clean_output = []
        for line in output.splitlines():
            if line.strip().startswith("IFACE") or line.strip().startswith("Ethernet"):
                clean_output.append(line.strip())
        
        # If the data line exists, parse it
        if len(clean_output) >= 2:
            data_line = clean_output[1]
            parts = data_line.split()
            if len(parts) >= 7:
                # return {
                    # "IFACE": parts[0],
                    # "STATE": parts[1],
                    # "FEC_CORR": parts[2],
                    # "FEC_UNCORR": parts[3],
                    # "FEC_SYMBOL_ERR": parts[4],
                    # "FEC_PRE_BER": parts[5],
                    # "FEC_POST_BER": parts[6],
                # }
                print([True, f'{parts[5]}; {parts[6]}'])
                return [True, f'{parts[5]}; {parts[6]}']
        
        #return {"error": "Could not find Ethernet23 or malformed output."}
        return [False]

    def parse_bin_counters(self, equipment_response):
        """
        Parse SONiC 'Symbol Errors Per Codeword' table and return list of numeric values.

        Parameters:
            equipment_response (tuple): (output_string, success_flag)
        
        Returns:
            list[int]: List of codeword counts per BIN (BIN0, BIN1, ...).
        """
        output = equipment_response[0]

        # Split into lines and filter only BIN rows
        values = []
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("BIN"):
                parts = line.split()
                if len(parts) == 2:
                    try:
                        values.append(int(parts[1]))
                    except ValueError:
                        # Handle any malformed numeric string
                        values.append(0)
                        continue

        return values

    def parse_power(self, equipment_response, power_string):
        """
        Parse TX{port}Power or RX{port}Power value (in dBm) from SSH equipment response tuple.

        Parameters:
            equipment_response (tuple): (output_string, success_flag)

        Returns:
            float: Power value in dBm, or None if not found.
        """
        output = equipment_response[0]

        for line in output.splitlines():
            line = line.strip()
            if line.startswith(f"{power_string}:"):
                try:
                    # Split at ':' → get '2.291dBm' → strip 'dBm'
                    value_str = line.split(":")[1].strip().replace("dBm", "")
                    return float(value_str)
                except (IndexError, ValueError):
                    return None
        return None
      

    def parse_lane_values(self, equipment_response):
        """
        Parse 'Lane N' output lines with comma-separated numeric fields.

        Parameters:
            equipment_response (tuple): (output_string, success_flag)

        Returns:
            dict: {"Lane": int, "Values": [list of ints]}
        """
        output = equipment_response[0]

        for line in output.splitlines():
            line = line.strip()
            if line.startswith("Lane"):
                # Example line: "Lane 0 : 0 ,3 ,-20 ,40 ,0 ,63"
                match = re.match(r"Lane\s+(\d+)\s*:\s*(.*)", line)
                if match:
                    lane = int(match.group(1))
                    values_str = match.group(2)

                    # Split by commas, strip whitespace, and convert to int
                    values = []
                    for val in values_str.split(","):
                        val = val.strip()
                        if val:
                            try:
                                values.append(int(val))
                            except ValueError:
                                continue

                    #return {"Lane": lane, "Values": values}
                    return values

        return {"error": "No valid Lane line found"}

    def expand_lane_map(self, XS):
        """
        Expand a list of 2-digit lane codes into 8 individual lane mappings.

        Each number AB maps to two lanes:
        - Lower lane gets B (low nibble)
        - Upper lane gets A (high nibble)
        """
        X = [int(xs) for xs in XS]
        Y = []
        for value in X:
            high = value // 10
            low = value % 10
            Y.append(low)
            Y.append(high)
        return Y

    def parse_lane_powers(self,text: str) -> Tuple[List[Optional[float]], List[Optional[float]]]:
        """
        Parse SONiC 'ChannelMonitorValues' output and return (rx_powers, tx_powers).
        Each is a list of length 8 (lanes 1..8) with floats in dBm or None if missing.
        """
        rx = [None] * 8
        tx = [None] * 8

        for m in _RX_RE.finditer(text):
            lane = int(m.group(1))
            if 1 <= lane <= 8:
                rx[lane - 1] = float(m.group(2))

        for m in _TX_RE.finditer(text):
            lane = int(m.group(1))
            if 1 <= lane <= 8:
                tx[lane - 1] = float(m.group(2))

        return rx, tx

    def Get_all_lanes(self, port:int, log_time = True):
        CMD = self
        list_item=['tp5_0', 'tp5_1', 'tp3_RXPwr', 'tp2_TXPwr', 'tp4']
        d = {}
        st = time.time()
        stt = st
        for lane in range(1,9):
            d[lane] = {}
            for item in list_item:
                d[lane][item] = None
        r0 = CMD.GetTXRXPortPwr(port)
        dt = time.time()-st
        st = time.time()
        r1 = CMD.GetHostMediaPortBER(port)
        dt = time.time()-st
        st = time.time()
        ethernet = (port - 1)*8
        for lane in range(1,9):
            d[lane]['tp3_RXPwr'] = r0[0][lane-1]
            d[lane]['tp2_TXPwr'] = r0[1][lane-1]
            if r1['result']:
                d[lane]['host_media_ber'] = r1['data'][lane]
                try:
                    ber = r1['data'][lane]
                    ber0 = f'{float(ber[0]):.4e}'
                    ber1 = f'{float(ber[1]):.4e}'
                    d[lane]['host_media_ber'] = f'{ber0};{ber1}'
                except:
                    logger.exception("error formatting ber")
            else:
                d[lane]['host_media_ber'] = "N/A; N/A"
            st = time.time()
            d[lane]['tp5_0'] = CMD.GetBER(ethernet)
            dt = time.time()-st
            st = time.time()
            d[lane]['tp5_1'] = CMD.GetFECHistogram(ethernet)
            dt = time.time()-st
            st = time.time()
            #d[lane]['tp0'] = CMD.GetTP0(ethernet)
            #dt = time.time()-st
            #st = time.time()
            #d[lane]['tp0'] = CMD.GetTP0(ethernet)
            d[lane]['tp0'] = [0, 0, 0, 0, 0, 0]
            dt = time.time()-st
            st = time.time()
        dt = time.time()-stt
        if log_time:
            logger.info(f'total time = {dt} seconds')
        return d

    def Get_one_lane(self, port:int, lane:int):
        CMD = self
        list_item=['tp5_0', 'tp5_1', 'tp3_RXPwr', 'tp2_TXPwr', 'tp4']
        d = {}
        st = time.time()
        stt = st
        for lane in range(1,9):
            d[lane] = {}
            for item in list_item:
                d[lane][item] = None
        r0 = CMD.GetTXRXPortPwr(port)
        dt = time.time()-st
        st = time.time()
        print(f'tp3+tp2 time = {dt} seconds')
        r1 = CMD.GetHostMediaPortBER(port)
        dt = time.time()-st
        st = time.time()
        print(f'host media time = {dt} seconds')
        ethernet = (port - 1)*8
        d[lane]['tp3_RXPwr'] = r0[0][lane-1]
        d[lane]['tp2_TXPwr'] = r0[1][lane-1]
        if r1['result']:
            d[lane]['host_media_ber'] = r1['data'][lane]
            try:
                ber = r1['data'][lane]
                ber0 = f'{float(ber[0]):.4e}'
                ber1 = f'{float(ber[1]):.4e}'
                d[lane]['host_media_ber'] = f'{ber0};{ber1}'
            except:
                logger.exception("error formatting ber")
        else:
            d[lane]['host_media_ber'] = "N/A; N/A"
        st = time.time()
        d[lane]['tp5_0'] = CMD.GetBER(ethernet)
        dt = time.time()-st
        st = time.time()
        print(f'tp5_0 time = {dt} seconds')
        d[lane]['tp5_1'] = CMD.GetFECHistogram(ethernet)
        dt = time.time()-st
        st = time.time()
        print(f'tp5_1 time = {dt} seconds')
        #d[lane]['tp0'] = CMD.GetTP0(ethernet)
        #dt = time.time()-st
        #st = time.time()
        #print(f'tp0 time = {dt} seconds')
        d[lane]['tp4'] = CMD.GetTP4(ethernet)
        dt = time.time()-st
        st = time.time()
        print(f'tp4 time = {dt} seconds')
        dt = time.time()-stt
        print(f'total time = {dt} seconds')
        return d
