# -*- coding: utf-8 -*-
"""
Switch equipment GUI scaffold.

This implementation focuses on placing text overlays exactly where the filled
mock-up shows dynamic content.  The positions are driven by pixel coordinates
measured from ``Filled.png`` (the fully populated example) so that each numeric
slot aligns with the underlying background artwork in ``Background_Picture.png``.

Future code can call ``set_lane_value`` / ``set_lane_chart_from_bytes`` to inject
live data without having to change the layout.
"""

from __future__ import annotations

import argparse
import io
from collections import deque
from dataclasses import dataclass
from pathlib import Path
import sys
import threading
from typing import Callable, Deque, Dict, Iterable, Optional, Sequence, Set, Tuple, Any

import tkinter as tk
from tkinter import ttk
import random
import math
import queue
import time
import os
from datetime import datetime
from pathlib import Path
import csv
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import tkinter.font as tkfont
import numpy as np
import switch_config
from Switch import Switch
from logger import get_logger
logger = get_logger()

SIM = False
SIM_PORT_TIME = 3
SIM_BIN_CROSS_THRESHOLD = False
try:
    from PIL import Image, ImageTk  # type: ignore
except ImportError:  # pragma: no cover - handled at runtime
    Image = ImageTk = None  # type: ignore



# Background resolution gathered from Background_Picture.png.
BACKGROUND_WIDTH = 3078
BACKGROUND_HEIGHT = 1732

# Default window size requested by the user.
WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1000

DEFAULT_SWITCH_IP = switch_config.switch_ip_list[0]#"10.74.181.250"
DEFAULT_SWITCH_CHOICES = switch_config.switch_ip_list
DEFAULT_PORT_CHOICES =switch_config.switch_port_list
SWITCH_TYPE = switch_config.switch_type
BIN5_10_THRESHOLD_RATIO = switch_config.bin5_10_threshold_ratio
LANE_COUNT = 8
BLINK_INTERVAL = 500

COLOR_ORANGE = "#ff7a00"  # orange
COLOR_GREEN  = "#18a84a"  # green
COLOR_LIGHT_BLUE = "#29a8ff"  # light blue
COLOR_DEEP_BLUE = "#2a43b8"  # deep blue
COLOR_RED  = "#e51b23"  # red
COLOR_PURPLE = "#9b59b6"  # purple
COLOR_YELLOW = "#f1c40f"  # yellow
COLOR_TEAL = "#1abc9c"   # teal
COLOR_PINK = "#FFB6C1"

COLOR_SET = (
    COLOR_ORANGE,
    COLOR_GREEN,
    COLOR_LIGHT_BLUE,
    COLOR_DEEP_BLUE,
    COLOR_RED,
    COLOR_PURPLE,
    COLOR_YELLOW,
    COLOR_TEAL
)

@dataclass(frozen=True)
class LaneCoordinate:
    """Single point (in background pixel space) for text placement."""

    x: float
    y: float
    anchor: str = "center"


@dataclass(frozen=True)
class LaneChartBounds:
    """Rectangle (in background pixel space) reserved for lane charts."""

    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top


@dataclass(frozen=True)
class RefreshContext:
    """Details provided to refresh handlers."""

    section: str
    switch_ip: str
    port: str


@dataclass
class SectionRefreshResult:
    """Returned by refresh handlers to describe UI updates."""

    lane_values: Dict[int, Dict[str, str]]
    charts: Dict[Tuple[int, str], Optional["Image.Image"]]

def format_float_or_exponent(num):
    f = float(num)
    if f > 0:
        s = f"{f:.4e}"
    else:
        s = f"{f}"
    return s

class SwitchLaneResult:
    def __init__(self, value):
        # {'tp5_0': '1.67e-12; 0', 
        # 'tp5_1': [4736269119295, 188499, 4, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0], 
        # 'tp3_RXportPwr': 1.438, 
        # 'tp2_TXportPwr': 2.326, 
        # 'tp0': [0, 3, -20, 40, 0, 63], 
        # 'tp4': [0, 0, 2], 
        # 'host_media_ber': '0.0;0.0'}
        logger.info('SwitchLaneResult value =')
        logger.info(value)
        tp5 = value['tp5_0'].split(";")
        logger.info(f'SwitchLaneResult_ex value tp5 ={tp5}')
        self.tp5_pre_fec_ber = tp5[0] 
        self.tp5_post_fec_ber = tp5[1] 
        self.tp0_tap = value['tp0']
        host_media_ber = value['host_media_ber'].split(";")
        #self.tp1_host_ber = host_media_ber[0]
        #self.tp3_media_ber = host_media_ber[1]
        self.tp1_host_ber = format_float_or_exponent(host_media_ber[0]) #f"{float(host_media_ber[0]):4e}"
        self.tp3_media_ber = format_float_or_exponent(host_media_ber[1]) # f"{float(host_media_ber[1]):.4e}"
        logger.info("value['host_media_ber']")
        logger.info(value['host_media_ber'])
        logger.info('self.tp1_host_ber')
        logger.info(self.tp1_host_ber)
        logger.info('self.tp3_media_ber')
        logger.info(self.tp3_media_ber)
        self.tp4_tap = value['tp4']
        self.txp_dBm = value['tp2_TXPwr']
        self.rxp_dBm = value['tp3_RXPwr']
        logger.info('self.tp0_tap')
        logger.info(self.tp0_tap)
# Coordinates derived from the filled mock-up.  They can be fine-tuned later if
# slight adjustments are needed, but they already align well with the supplied
# reference imagery.
LANE_TEXT_COORDS: Dict[str, LaneCoordinate] = {
    "top_ethernet": LaneCoordinate(250, 71, anchor="w"),
    "top_lane": LaneCoordinate(100, 71, anchor="w"),
    "top_pre_fec_ber": LaneCoordinate(240, 468, anchor="w"),
    "top_post_fec_ber": LaneCoordinate(240, 506, anchor="w"),
    "top_tp0_tap": LaneCoordinate(20, 540, anchor="w"),
    "top_tp1_host_ber": LaneCoordinate(20, 675, anchor="w"),
    "top_tp4_tap": LaneCoordinate(240.78, 675, anchor="w"),
    "top_tp3_media_ber": LaneCoordinate(239, 710, anchor="w"),
    "top_txp": LaneCoordinate(97, 820, anchor="center"),
    "top_rxp": LaneCoordinate(270, 820, anchor="center"),
    "bottom_txp": LaneCoordinate(97, 905, anchor="center"),
    "bottom_rxp": LaneCoordinate(270, 905, anchor="center"),
    "bottom_tp3_media_ber": LaneCoordinate(20, 1015, anchor="w"),
    "bottom_tp4_tap": LaneCoordinate(20, 1050, anchor="w"),
    "bottom_tp1_host_ber": LaneCoordinate(239, 1050, anchor="w"),
    "bottom_tp0_tap": LaneCoordinate(210, 1190, anchor="center"),
    "bottom_pre_fec_ber": LaneCoordinate(130, 1224, anchor="w"),
    "bottom_post_fec_ber": LaneCoordinate(130, 1261, anchor="w"),
    "bottom_lane": LaneCoordinate(100, 1288, anchor="w"),
    "bottom_ethernet": LaneCoordinate(250, 1288, anchor="w"),
}

LANE_CHARTS: Dict[str, LaneChartBounds] = {
    "top": LaneChartBounds(left=55, top=80, right=320, bottom=430),
    "bottom": LaneChartBounds(left=55, top=1295, right=320, bottom=1645),
}

def get_datafile_with_timestamp(data_fn = "data_log", data_folder = "data"):
    # Get the current date and time
    now = datetime.now()
    # Format the datetime object into a string suitable for a filename
    # %Y-%m-%d for date (Year-Month-Day)
    # %H-%M-%S for 24-hour time (Hour-Minute-Second)
    timestamp_string = now.strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{data_fn}_{timestamp_string}.csv"
    current_dir = os.getcwd()
    parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
    data_path = os.path.join(parent_dir, data_folder)
    data_path = os.path.join(data_path, filename)
    return data_path

    
class SwitchEquipmentGUI:
    """GUI that mirrors the filled mock-up using explicit coordinates."""
    def __init__(self, master: Optional[tk.Tk] = None) -> None:


        self.log_data = True
        self.data_log_file = get_datafile_with_timestamp()
        self.root = master or tk.Tk()
        self.root.title("Switch Equipment Monitor")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(
            self.root,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self.scale_x = WINDOW_WIDTH / BACKGROUND_WIDTH
        self.scale_y = WINDOW_HEIGHT / BACKGROUND_HEIGHT

        self.background_image: Optional[tk.PhotoImage] = None
        self._draw_background()

        self.style = ttk.Style(self.root)
        self.style.configure("SwitchCombo.TCombobox", font=("Segoe UI", 11))
        self.root.option_add("*TCombobox*Listbox.font", ("Segoe UI", 11))

        self.top_switch_var = tk.StringVar(value=DEFAULT_SWITCH_IP)
        self.bottom_switch_var = tk.StringVar(value=DEFAULT_SWITCH_IP)
        self.top_port_var = tk.StringVar()
        self.bottom_port_var = tk.StringVar()

        # self.refresh_handlers: Dict[str, Callable[[RefreshContext], SectionRefreshResult]] = {
            # "top": self._demo_refresh_top,
            # "bottom": self._demo_refresh_bottom,
        # }
        self.refresh_handlers: Dict[str, Callable[[RefreshContext], SectionRefreshResult]] = {
            "top": self._value_refresh_top,
            "bottom": self._value_refresh_bottom,
        }
        self.refresh_handlers_params = None
        self._refresh_lock = threading.Lock()
        self._pending_sections: Deque[str] = deque()
        self._pending_section_ids: Set[str] = set()
        self._refresh_thread: Optional[threading.Thread] = None
        self._indicator_item: Optional[int] = None
        self._indicator_job: Optional[str] = None
        self._indicator_blink_state = False
        self._indicator_error = False

        self._top_fields = tuple(key for key in LANE_TEXT_COORDS if key.startswith("top_"))
        self._bottom_fields = tuple(key for key in LANE_TEXT_COORDS if key.startswith("bottom_"))

        self._build_dropdowns()

        self.chart_images: Dict[Tuple[int, str], Optional[tk.PhotoImage]] = {
            (lane, position): None
            for lane in range(LANE_COUNT)
            for position in LANE_CHARTS
        }
        self.chart_items: Dict[Tuple[int, str], int] = {}

        self.text_items: Dict[Tuple[int, str], int] = {}
        self._build_lane_overlays()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        # start background reader thread
        self.switch_ready = False

        # start periodic task
        self.section_being_read = ""
        self.hardware_state = "connecting to switch"
        # background reader control
        self._stop_hw_reader = threading.Event()

        self.data_list = {}
        self.new_data_available = {}
        self.new_lane_data_available = {}
        self.update_data_once = {}
        self.update_forever = False
        for section in ["top","bottom"]:
            self.data_list[section] = {}
            self.new_lane_data_available[section] = {}
            for lane in range(9):
                self.new_lane_data_available[lane] = False
            self.update_data_once[section] = False

        self.update_start_time = time.time()
        self.connect_done = self.connect()
        self.port_sn = [None, None]
        self.port_fw = [None, None]
        self.check_info_done = [None]*4
        self.check_port_info()
        self.FEC_tail_0 = {"top":{}, "bottom":{}}
        self.FEC_tail = {"top":{}, "bottom":{}}
        self.FEC_tail_start_time = {"top":None, "bottom":None}
        self.FEC_tail_duration = {"top":None, "bottom":None}
        for lane in range(8):
            self.FEC_tail_0["top"][lane] = None
            self.FEC_tail_0["bottom"][lane] = None
            self.FEC_tail["top"][lane] = None
            self.FEC_tail["bottom"][lane] = None
        self._hw_thread = threading.Thread(target=self._hardware_reader_loop, daemon=True)
        self._hw_thread.start()
        self._schedule_check()
        self.button_sync = False
        

    def _schedule_check(self):
        #    try:
                self.update_switch_message()
                if self.FEC_tail_duration["top"]:
                    fec_time = self.format_FEC_time(self.FEC_tail_duration["top"])                       
                    self.top_duration_label.config(text=fec_time,font=self.bold_header_font) 
                if self.FEC_tail_duration["bottom"]:
                    fec_time = self.format_FEC_time(self.FEC_tail_duration["bottom"])                       
                    self.bottom_duration_label.config(text=fec_time,font=self.bold_header_font) 
                
                #if self.switch_ready:
                #    self.check_blocking_other_button()
                #self.root.after(500, self._schedule_check)  # run every 1000 ms
                read_port = "None"
                if self.section_being_read == "top":
                    read_port = (self.top_port_var.get() or "").strip()
                    #self.port_status_label.config(text=f"port read = {read_port}",font=self.bold_header_font)
                    self.start_blink()
                elif self.section_being_read == "bottom":
                    read_port = (self.bottom_port_var.get() or "").strip()
                    #self.port_status_label.config(text=f"port read = {read_port}",font=self.bold_header_font)
                    self.start_blink()
                else:
                    #self.port_status_label.config(text="port read = None",font=self.bold_header_font)
                    self.stop_blink()
                if self.switch_ready:
                    #self.update_switch_message()
                    self.check_blocking_other_button()
                self.root.after(1000, self._schedule_check)  # run every 1000 ms
                #logger.info(f"checking if port {read_port} being read")
                #
        #    except:
        #        logger.exception("error setup periodic harware check")

    # def _schedule_check(self):
        # #    try:
                # read_port = "None"
                # if self.section_being_read == "top":
                    # read_port = (self.top_port_var.get() or "").strip()
                    # self.port_status_label.config(text=f"port read = {read_port}",font=self.bold_header_font)
                    # self.start_blink()
                # elif self.section_being_read == "bottom":
                    # read_port = (self.bottom_port_var.get() or "").strip()
                    # self.port_status_label.config(text=f"port read = {read_port}",font=self.bold_header_font)
                    # self.start_blink()
                # else:
                    # self.port_status_label.config(text="port read = None",font=self.bold_header_font)
                    # self.stop_blink()
                # if self.switch_ready:
                    # self.update_switch_message()
                    # self.check_blocking_other_button()
                # self.root.after(1000, self._schedule_check)  # run every 1000 ms
                # #logger.info(f"checking if port {read_port} being read")
                # #
        # #    except:
        # #        logger.exception("error setup periodic harware check")
        

    def format_FEC_time(self, num):
        if num < 60:
            s = f"FEC time(second)={num:.2f}"
        elif num < 3600:
            minute = num / 60
            s = f"FEC time(minute)={minute:.2f}"
        elif num < 3600*24:
            hour = num / 3600
            s = f"FEC time(hour)={hour:.2f}"
        else:
            day = num / (3600*24)
            s = f"FEC time(day)={day:.2f}"
        return s

    def check_port_info(self):
        if self.switch_ready:
            if self.port_fw[0]:
                try:
                    s = f"FW version = {self.port_fw[0]}"
                    logger.info(s)
                    self.top_fw_version_label.config(text=s,font=self.bold_header_font)
                    self.check_info_done[0] = True
                except:
                    logger.exception(f"error FW version = {self.port_fw[0]}")
            if self.port_sn[0]:
                try:
                    s = f"SN = {self.port_sn[0]}"
                    logger.info(s)
                    self.top_SN_label.config(text=s,font=self.bold_header_font)
                    self.check_info_done[1] = True
                except:
                    logger.exception(f"error FW version = {self.port_fw[0]}")

            if self.port_fw[1]:
                try:
                    s = f"FW version = {self.port_fw[1]}"
                    logger.info(s)
                    self.bottom_fw_version_label.config(text=s,font=self.bold_header_font)
                    self.check_info_done[2] = True
                except:
                    logger.exception(f"error FW version = {self.port_fw[0]}")
            if self.port_sn[1]:
                try:
                    s = f"SN = {self.port_sn[1]}"
                    logger.info(s)
                    self.bottom_SN_label.config(text=s,font=self.bold_header_font)
                    self.check_info_done[3] = True
                except:
                    logger.exception(f"error FW version = {self.port_fw[0]}")
            b = True
            for b1 in self.check_info_done:
                b = b and b1
            if b:
                logger.info(f"self.check_info_done {self.check_info_done}")
                return
        self.root.after(300, self.check_port_info)  # run every 1000 ms
        
    def check_blocking_other_button(self):
        #try:
            if self.update_data_once["top"] or self.update_data_once["bottom"]:
                try:
                    self.auto_refresh_button.configure(state="disabled")
                except Exception:
                    logger.exception("error blocking other button")
            else:
                try:
                    self.auto_refresh_button.configure(state="normal")
                except Exception:
                    logger.exception("error unblocking other button")
            if self.update_forever:
                try:
                    self.refresh_button.configure(state="disabled")
                except Exception:
                    logger.exception("error blocking other button")
            else:
                try:
                    self.refresh_button.configure(state="normal")
                except Exception:
                    logger.exception("error unblocking other button")
        #except:
            #logger.exception("error blocking other button")

    def _notify_section_ready(self, sec: str):
        with self._refresh_lock:
            # 1) mark this section ready
            self.new_data_available[sec] = True

            # 2) enqueue this section (dedupe)
            if sec not in self._pending_section_ids:
                self._pending_sections.append(sec)
                self._pending_section_ids.add(sec)

            # 3) (re)start refresh thread if it exited
            if self._refresh_thread is None or not self._refresh_thread.is_alive():
                self.root.after(0, lambda: self.start_blink())
                self._refresh_thread = threading.Thread(
                    target=self._process_refresh_queue, daemon=True
                )
                self._refresh_thread.start()

    def _hardware_reader_loop(self) -> None:
        """Background data acquisition loop.

        In SIM mode, each section takes ~10 seconds to produce 8-lane data.
        When auto-refresh is enabled, the GUI is refreshed immediately per section.
        """
        self.section_being_read = ""
        logger.info(f'self.switch_ready = {self.switch_ready}')
        logger.info(f'self.connect_done = {self.connect_done}')
        logger.info("switch connected")
        logger.info("waiting for port selection")
        self.hardware_state = "waiting for port selection"
        while not (self.switch_ready):
            if self.connect_done:
                port_configure = self._both_sections_configured()
                if port_configure:
                    top_port = (self.top_port_var.get() or "").strip()
                    bottom_port = (self.bottom_port_var.get() or "").strip()
                    break
            time.sleep(5)
        logger.info("ports selected, ready to update")
        logger.info(f'self.switch_ready = {self.switch_ready}')
        logger.info(f'self.connect_done = {self.connect_done}')
        if SWITCH_TYPE == "NVIDIA":
            self.hardware_state = "reading top port info"
        else:
            self.hardware_state = "reading top port info and first FEC histogram"
        portS = (self.top_port_var.get() or "").strip()
        port = int(portS)    
        if port:                            
            r = self.switch.CMD.GetPortInfo(port)
            if r[0]:
                self.port_sn[0] = r[1]["sn"]
                self.port_fw[0] = r[1]["fw"]
            self.FEC_tail_start_time["top"] = time.time()
            for lane in range(8):
                if SWITCH_TYPE == "NVIDIA":
                    self.FEC_tail_0["top"][lane] = [0] * 16
                else:
                    ethernet = (port -1) * 8 + lane
                    self.FEC_tail_0["top"][lane] = self.switch.CMD.GetFECHistogram(ethernet)
        if SWITCH_TYPE == "NVIDIA":
            self.hardware_state = "reading bottom port info"
        else:
            self.hardware_state = "reading bottom port info and first FEC histogram"
        portS = (self.bottom_port_var.get() or "").strip()
        port = int(portS)    
        if port:                            
            r = self.switch.CMD.GetPortInfo(port)
            if r[0]:
                self.port_sn[1] = r[1]["sn"]           
                self.port_fw[1] = r[1]["fw"]
            self.FEC_tail_start_time["bottom"] = time.time()
            for lane in range(8):
                if SWITCH_TYPE == "NVIDIA":
                    self.FEC_tail_0["bottom"][lane] = [0] * 16
                else:
                    ethernet = (port -1) * 8 + lane
                    self.FEC_tail_0["bottom"][lane] = self.switch.CMD.GetFECHistogram(ethernet)
        self.switch_ready = True
        self.hardware_state = "switch ready"
        logger.info("done waiting for port, ready to read switch")
        while not self._stop_hw_reader.is_set():
            if self.update_forever:
                self.update_one_set()
            elif self.update_data_once["top"] == True and self.update_data_once["bottom"] == True:  
                self.update_one_set()
            time.sleep(5)
            
    def update_one_set(self):
            try:
                start_time = time.time()
                self.section_being_read = ""
                for section in ("top", "bottom"):
                    self.section_being_read = section
                    #self.update_data_once[section] = False
 
                    # Simulate blocking hardware read latency per section (~10s).
                    if SIM:
                        section_values = {}
                        for _lane in range(LANE_COUNT):
                            section_values[_lane+1] = self.generate_demo_value()
                            self.new_lane_data_available[section][_lane] = True
                        time.sleep(SIM_PORT_TIME)
                        # Publish latest data + mark availability atomically.
                        with self._refresh_lock:
                            self.data_list[section] = section_values
                            self.new_data_available[section] = True
                    else:
                        if section == "top":
                            portS = (self.top_port_var.get() or "").strip()
                            port = int(portS)    
                            sn = self.port_sn[0]
                            fw = self.port_fw[0]
                        else:
                            portS = (self.bottom_port_var.get() or "").strip()
                            port = int(portS)    
                            sn = self.port_sn[1]
                            fw = self.port_fw[1]
                        if port:                            
                            logger.info("read data")  
                            self.hardware_state = f"reading port {port}"
                            section_values = self.switch.CMD.Get_all_lanes(port)
                            # Publish latest data + mark availability atomically.
                            logger.info(f"section_values port {port}")
                            logger.info(section_values)
                            with self._refresh_lock:
                                self.data_list[section] = section_values
                                self.new_data_available[section] = True
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            self.FEC_tail_duration[section] =  time.time() - self.FEC_tail_start_time[section]
                            if self.log_data:
                                for lane in range(8):
                                    lane_data = self.data_list[section][lane+1]
                                    logger.info(f"lane_data for lane {lane}")
                                    logger.info(lane_data)
                                    logger.info(f"lane_data['tp5_1']")
                                    logger.info(lane_data['tp5_1'])
                                    if not SWITCH_TYPE == "NVIDIA":
                                        logger.info("Process Arista")
                                        self.compute_tail(section, lane, lane_data['tp5_1'])
                                    else:
                                        logger.info("Process NVIDIA")
                                        self.FEC_tail[section][lane] = lane_data['tp5_1']
                                    logger.info(f"self.FEC_tail_0[section][lane]")
                                    logger.info(self.FEC_tail_0[section][lane])
                                    logger.info(f"self.FEC_tail[section][lane]")
                                    logger.info(self.FEC_tail[section][lane])
                                    try:
                                        self.save_lane_data_to_csv(sn, fw, port, lane+1, lane_data, self.FEC_tail[section][lane], self.FEC_tail_duration[section],self.data_log_file, timestamp)
                                    except:
                                        logger.exception("Failed to save_lane_data_to_csv = %r", lane_data)
                            self.hardware_state = "switch ready"
                        self.update_data_once[section] = False
                    # If auto-refresh is on, refresh this section immediately.
                    if self.auto_refresh_enabled:
                        self._notify_section_ready(section)

                    logger.info(f"hardware loop section ready: {section} (elapsed={time.time() - start_time:.3f}s)")
                self.section_being_read = ""

            except Exception as e:
                # Keep the loop alive; report to console for now.
                logger.info("HW read error:", e)
    
    def compute_tail(self, section, lane, tail):
        logger.info(f"compute_tail section {section}, lane {lane}")
        logger.info(f"next setup for section {section}, lane {lane}")
        logger.info("tail")
        logger.info(tail)
        self.FEC_tail[section][lane] = [x for x in tail]
        for i, (x , y) in enumerate(zip(tail, self.FEC_tail_0[section][lane])):
            self.FEC_tail[section][lane][i] = x - y
        logger.info("self.FEC_tail[section][lane]")
        logger.info(self.FEC_tail[section][lane])
        logger.info("self.FEC_tail_0[section][lane]")
        logger.info(self.FEC_tail_0[section][lane])
        logger.info(f"compute_tail section {section}, lane {lane} done")
        
    def connect(self):
        switch_IP = self.top_switch_var.get()
        try:
            logger.info(self.top_switch_var.get())
            logger.info(self.bottom_switch_var.get())
            switch_user_name = "admin"
            switch_pw = "password"
            self.switch = Switch(switch_IP, switch_user_name, switch_pw)
            logger.info(f"self.switch {self.switch}")
            return True
        except:
            logger.info("faile to connect to switch at {switch_IP}")
            return False            
        
    def on_close(self) -> None:
        self._stop_hw_reader.set()
        self.root.destroy()
        logger.info("self._stop_hw_reader.set()")
        logger.info("self.root.destroy()")

    # ------------------------------------------------------------------ #
    # Rendering helpers                                                   #
    # ------------------------------------------------------------------ #
    def _draw_background(self) -> None:
        #background_path = Path(__file__).with_name("Background_Picture.png")
        background_path = Path(__file__).with_name("Background_Picture_update.png")
        if Image is None or ImageTk is None:
            self.canvas.configure(background="#f5f5f5")
            self.canvas.create_text(
                WINDOW_WIDTH / 2,
                WINDOW_HEIGHT / 2,
                text=f"Install Pillow to display {background_path}", # Background_Picture.png",
                fill="#aa0000",
                font=("Segoe UI", 14, "bold"),
            )
            return
        if not background_path.exists():
            self.canvas.configure(background="#f5f5f5")
            self.canvas.create_text(
                WINDOW_WIDTH / 2,
                WINDOW_HEIGHT / 2,
                text="Background_Picture.png not found",
                fill="#aa0000",
                font=("Segoe UI", 14, "bold"),
            )
            return

        image = Image.open(background_path)
        image = image.resize((WINDOW_WIDTH, WINDOW_HEIGHT), Image.Resampling.LANCZOS)
        self.background_image = ImageTk.PhotoImage(image)
        self.canvas.create_image(0, 0, anchor="nw", image=self.background_image)

    def _build_dropdowns(self) -> None:
        def create_combo(var: tk.StringVar, values: Iterable[str], center: Tuple[float, float], width: int) -> ttk.Combobox:
            combo = ttk.Combobox(
                self.canvas,
                textvariable=var,
                values=tuple(values),
                state="readonly",
                justify="center",
                style="SwitchCombo.TCombobox",
            )
            cx, cy = center
            self.canvas.create_window(
                cx,
                cy,
                anchor="center",
                window=combo,
                width=width,
                height=26,
            )
            return combo

        top_switch_center = (320.0 * self.scale_x, 23.0 * self.scale_y)
        #top_port_center = (640.0 * self.scale_x, 23.0 * self.scale_y)
        top_port_center = (540.0 * self.scale_x, 23.0 * self.scale_y)
        bottom_switch_center = (
            320.0 * self.scale_x,
            (BACKGROUND_HEIGHT - 23.0) * self.scale_y,
        )
        # bottom_port_center = (
            # 640.0 * self.scale_x,
            # (BACKGROUND_HEIGHT - 23.0) * self.scale_y,
        # )
        bottom_port_center = (
            540.0 * self.scale_x,
            (BACKGROUND_HEIGHT - 23.0) * self.scale_y,
        )

        #self.switch_combo_top = create_combo(
        #    self.top_switch_var, (DEFAULT_SWITCH_IP,), top_switch_center, 120
        #)
        self.switch_combo_top = create_combo(
            self.top_switch_var, DEFAULT_SWITCH_CHOICES, top_switch_center, 120
        )
        self.port_combo_top = create_combo(
            self.top_port_var, DEFAULT_PORT_CHOICES, top_port_center, 40
        )
        #self.switch_combo_bottom = create_combo(
        #    self.bottom_switch_var, (DEFAULT_SWITCH_IP,), bottom_switch_center, 120
        #)
        self.switch_combo_bottom = create_combo(
            self.top_switch_var, DEFAULT_SWITCH_CHOICES, bottom_switch_center, 120
        )
        self.port_combo_bottom = create_combo(
            self.bottom_port_var, DEFAULT_PORT_CHOICES, bottom_port_center, 40
        )

        def on_combo_changed(_event=None) -> None:
            # Enable/disable refresh controls as selections change.
            self._update_refresh_controls_enabled_state()
            # If auto-refresh is enabled and configuration is complete, refresh both sections.
            if getattr(self, "auto_refresh_enabled", False) and self._both_sections_configured():
                self.request_refresh("all")

        for widget in (
            self.switch_combo_top,
            self.port_combo_top,
            self.switch_combo_bottom,
            self.port_combo_bottom,
        ):
            widget.bind("<<ComboboxSelected>>", on_combo_changed)

        # ---------- Fonts ----------
        self.bold_button_font = tkfont.Font(size=9, weight="bold")
        self.bold_header_font = tkfont.Font(size=12, weight="bold")

        style = tb.Style()

        # Apply bold font to buttons via style
        style.configure("Bold.TButton", font=self.bold_button_font)

        # Apply bold font to labelframe title
        style.configure("Bold.TLabelframe.Label", font=self.bold_header_font)
        logger.info(f"top_switch_center y = {top_switch_center[1]}")
        logger.info(f"bottom_switch_center y = {bottom_switch_center[1]}")

        self.top_SN_label = tb.Label(self.canvas, text="SN = xxxxxxxx", font=("Arial", 12, "bold"))

        button_x = WINDOW_WIDTH - 1450
        button_y = int(top_switch_center[1]) # 12 #36
        self.canvas.create_window(
            button_x,
            button_y,
            anchor="center",
            window=self.top_SN_label,
            width=190,
            height=28,
        )

        self.top_fw_version_label = tb.Label(self.canvas, text="FW version = x.x.x.x", font=("Arial", 12, "bold"))

        button_x = button_x + 180
        button_y = int(top_switch_center[1])#12 #36
        self.canvas.create_window(
            button_x,
            button_y,
            anchor="center",
            window=self.top_fw_version_label,
            width=190,
            height=28,
        )

        # Duration Label
        self.top_duration_label = tb.Label(self.canvas, text="", font=self.bold_header_font)
        #self.status_label.pack()
        button_x = button_x + 160
        button_y = int(top_switch_center[1])#12 #36
        self.canvas.create_window(
            button_x,
            button_y,
            anchor="center",
            window=self.top_duration_label,
            width=200,
            height=28,
        )

        self.bottom_SN_label = tb.Label(self.canvas, text="SN = xxxxxxxx", font=("Arial", 12, "bold"))

        button_x = WINDOW_WIDTH - 1450
        button_y = int(bottom_switch_center[1]) + 2#12 #36
        self.canvas.create_window(
            button_x,
            button_y,
            anchor="center",
            window=self.bottom_SN_label,
            width=190,
            height=28,
        )

        self.bottom_fw_version_label = tb.Label(self.canvas, text="FW version = x.x.x.x", font=("Arial", 12, "bold"))

        button_x = button_x + 180
        button_y = int(bottom_switch_center[1]) + 2#12 #36
        self.canvas.create_window(
            button_x,
            button_y,
            anchor="center",
            window=self.bottom_fw_version_label,
            width=190,
            height=28,
        )

        self.bottom_duration_label = tb.Label(self.canvas, text="", font=self.bold_header_font)
        button_x = button_x + 160
        button_y = int(bottom_switch_center[1]) + 2#12 #36
        self.canvas.create_window(
            button_x,
            button_y,
            anchor="center",
            window=self.bottom_duration_label,
            width=200,
            height=28,
        )


        self.auto_refresh_enabled = False


        style.configure("AutoOff.TButton",
                        font=self.bold_button_font,
                        background=COLOR_PINK)

        style.configure("AutoOn.TButton",
                        font=self.bold_button_font,
                        background=COLOR_LIGHT_BLUE)

        
        self.auto_refresh_button = tb.Button(
            self.canvas,
            text="Auto Refresh: OFF",
            command=self.toggle_auto_refresh,
            width=12,
            style="AutoOff.TButton"
            )

        button_x = WINDOW_WIDTH - 850
        button_y = 12 #36
        self.canvas.create_window(
            button_x,
            button_y,
            anchor="center",
            window=self.auto_refresh_button,
            width=140,
            height=28,
        )


        self.refresh_button = tb.Button(
            self.canvas,
            text="Refresh All",
            command=lambda: self.request_refresh("all"),
            width=12,
            style="Bold.TButton"
        )
        button_x = button_x + 170
        button_y = 12 #36
        self.canvas.create_window(
            button_x,
            button_y,
            anchor="center",
            window=self.refresh_button,
            width=140,
            height=28,
        )

        # Initialize control enabled/disabled state.
        self._update_refresh_controls_enabled_state()

        indicator_radius = 10
        indicator_center_x = button_x + 170
        indicator_center_y = button_y
        self._indicator_item = self.canvas.create_oval(
            indicator_center_x - indicator_radius,
            indicator_center_y - indicator_radius,
            indicator_center_x + indicator_radius,
            indicator_center_y + indicator_radius,
            fill="#2ecc71",
            outline="",
        )
        self._indicator_item_save = self._indicator_item 
        
        # self.port_status_label = tb.Label(self.canvas, text="port read = None", font=("Arial", 12, "bold"))

        # button_x = button_x + 340
        # button_y = 12 #36
        # self.canvas.create_window(
            # button_x,
            # button_y,
            # anchor="center",
            # window=self.port_status_label,
            # width=140,
            # height=28,
        # )

        # Status Label
        self.status_label = tb.Label(self.canvas, text="wait for port selection", font=self.bold_header_font)
        #self.status_label.pack()
        button_x = button_x + 400 # 250
        button_y = 12 #36
        self.canvas.create_window(
            button_x,
            button_y,
            anchor="center",
            window=self.status_label,
            width=420,
            height=28,
        )

       
 
    def update_switch_message(self):
        self.log_data = True
        if self.hardware_state.find("reading ") >= 0:
            self.status_label.config(text=self.hardware_state,font=self.bold_header_font)
        if not self.hardware_state == "switch ready":
            self.status_label.config(text=self.hardware_state,font=self.bold_header_font)
        elif len(self.section_being_read) == 0:
            message = "switch is ready"
            self.status_label.config(text=message,font=self.bold_header_font)       

        if self.switch_ready:
            if self.update_forever:
                # message = "auto refresh  = ON"
                # self.status_label.config(text=message,font=self.bold_header_font)
                self.start_blink()
            elif self.update_data_once["top"] or self.update_data_once["bottom"]:
                # message = "refresh once"
                # self.status_label.config(text=message,font=self.bold_header_font)
                self.start_blink()
            elif len(self.section_being_read) > 0:
                # self.status_label.config(text=self.hardware_state,font=self.bold_header_font)
                # self.top_duration_label.config(text="") 
                # self.bottom_duration_label.config(text="") 
                self.start_blink()
        
    def _build_lane_overlays(self) -> None:
        lane_stride = BACKGROUND_WIDTH / LANE_COUNT
        text_font = ("Segoe UI", 12)
        small_font = ("Segoe UI", 11)

        for lane in range(LANE_COUNT):
            offset_x = lane * lane_stride
            for key, coord in LANE_TEXT_COORDS.items():
                canvas_x = (offset_x + coord.x) * self.scale_x
                canvas_y = coord.y * self.scale_y
                item_id = self.canvas.create_text(
                    canvas_x,
                    canvas_y,
                    text="",
                    font=small_font if "tp" in key or "ber" in key else text_font,
                    fill="#1f2f5c",
                    anchor=coord.anchor,
                )
                self.text_items[(lane, key)] = item_id

            for position, bounds in LANE_CHARTS.items():
                chart_x = (offset_x + bounds.left) * self.scale_x
                chart_y = bounds.top * self.scale_y
                width = bounds.width * self.scale_x
                height = bounds.height * self.scale_y
                rect_id = self.canvas.create_rectangle(
                    chart_x,
                    chart_y,
                    chart_x + width,
                    chart_y + height,
                    outline="",
                    fill="",
                )
                self.chart_items[(lane, position)] = rect_id

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #
    def run(self) -> None:
        self.root.mainloop()

    def set_switch_ips(self, addresses: Iterable[str]) -> None:
        values = tuple(dict.fromkeys(addresses)) or (DEFAULT_SWITCH_IP,)
        self.switch_combo_top["values"] = values
        self.switch_combo_bottom["values"] = values
        if self.top_switch_var.get() not in values:
            self.top_switch_var.set(values[0])
        if self.bottom_switch_var.get() not in values:
            self.bottom_switch_var.set(values[0])

    def set_ports(self, ports: Iterable[str]) -> None:
        values = tuple(dict.fromkeys(str(p) for p in ports)) or DEFAULT_PORT_CHOICES
        self.port_combo_top["values"] = values
        self.port_combo_bottom["values"] = values
        if self.top_port_var.get() not in values:
            self.top_port_var.set("")
        if self.bottom_port_var.get() not in values:
            self.bottom_port_var.set("")

    def set_lane_value(self, lane: int, field: str, value: str) -> None:
        item = self.text_items.get((lane, field))
        if item is None:
            raise KeyError(f"Unknown field '{field}' for lane {lane}")
        self.canvas.itemconfigure(item, text=value)

    def set_global_value(self, field: str, value: str) -> None:
        for lane in range(LANE_COUNT):
            self.set_lane_value(lane, field, value)

    # def set_refresh_handler(
        # self, section: str, handler: Callable[[RefreshContext], SectionRefreshResult],
    # ) -> None:
        # sections = self._normalize_sections(section)
        # if not sections:
            # raise ValueError("section must be 'top', 'bottom', or 'all'")
        # for sec in sections:
            # self.refresh_handlers[sec] = handler

    def set_refresh_handler(
        self, section: str, handler: Callable[[RefreshContext], SectionRefreshResult],
        param: Any = None,
    ) -> None:
        sections = self._normalize_sections(section)
        if not sections:
            raise ValueError("section must be 'top', 'bottom', or 'all'")
        for sec in sections:
            self.refresh_handlers[sec] = handler
            self.refresh_handlers_params[sec] = param


    def _both_sections_configured(self) -> bool:
        """Return True only if BOTH sections have a non-empty IP and port selected."""
        top_ip = (self.top_switch_var.get() or "").strip()
        bottom_ip = (self.bottom_switch_var.get() or "").strip()
        top_port = (self.top_port_var.get() or "").strip()
        bottom_port = (self.bottom_port_var.get() or "").strip()
        return bool(top_ip and bottom_ip and top_port and bottom_port)

    def _update_refresh_controls_enabled_state(self) -> None:
        """Enable/disable refresh controls based on whether both sections are configured."""
        ok = self._both_sections_configured()

        if hasattr(self, "refresh_button") and self.refresh_button is not None:
            try:
                self.refresh_button.configure(state=("normal" if ok else "disabled"))
            except Exception:
                pass

        if hasattr(self, "auto_refresh_button") and self.auto_refresh_button is not None:
            try:
                self.auto_refresh_button.configure(state=("normal" if ok else "disabled"))
            except Exception:
                pass

        # If configuration becomes invalid while auto-refresh is on, force it off.
        if not ok and getattr(self, "auto_refresh_enabled", False):
            self.auto_refresh_enabled = False
            try:
                self.auto_refresh_button.config(
                    text="Auto Refresh: OFF",
                    style="AutoOff.TButton",
                )
            except Exception:
                pass

    def request_refresh(self, section: str) -> None:
        if len(self.section_being_read) > 0:
            return
        # Block refresh until BOTH top and bottom have IP + port selected.
        if not self._both_sections_configured():
            logger.info("Refresh blocked: set IP and Port for BOTH top and bottom.")
            return
        sections = self._normalize_sections(section)
        if not sections:
            return

        def schedule_start() -> None:
            self._start_indicator()

        self.root.after(0, schedule_start)
        with self._refresh_lock:
            try:
                for sec in sections:
                    self.update_forever = False
                    self.update_data_once[sec] = True
            except:
                logger.exception("error set up update flags")
            for sec in sections:
                # Manual refresh should use the latest data we already have.
                if sec in self.data_list and self.data_list[sec]:
                    self.new_data_available[sec] = True

                if sec not in self._pending_section_ids:
                    self._pending_sections.append(sec)
                    self._pending_section_ids.add(sec)


            if self._refresh_thread is None or not self._refresh_thread.is_alive():
                self._refresh_thread = threading.Thread(
                    target=self._process_refresh_queue,
                    daemon=True,
                )
                self._refresh_thread.start()

    def set_lane_chart_from_bytes(
        self, lane: int, position: str, data: bytes
    ) -> None:
        bounds = LANE_CHARTS[position]
        self._place_chart_image(
            lane,
            position,
            Image.open(io.BytesIO(data)) if Image is not None else None,
            bounds,
        )

    def set_lane_chart_from_path(
        self, lane: int, position: str, path: Path
    ) -> None:
        self._place_chart_image(
            lane,
            position,
            Image.open(path) if Image is not None else None,
            LANE_CHARTS[position],
        )

    def clear_lane_chart(self, lane: int, position: str) -> None:
        rect_id = self.chart_items[(lane, position)]
        bounds = LANE_CHARTS[position]
        offset_x = lane * (BACKGROUND_WIDTH / LANE_COUNT)
        canvas_x = (offset_x + bounds.left + bounds.width / 2) * self.scale_x
        canvas_y = (bounds.top + bounds.height / 2) * self.scale_y
        self.canvas.delete(rect_id)
        new_id = self.canvas.create_text(
            canvas_x,
            canvas_y,
            text="   ",#"Chart\nplaceholder",
            font=("Segoe UI", 12, "italic"),
            fill="#1f2f5c",
            justify="center",
        )
        self.chart_items[(lane, position)] = new_id
        self.chart_images[(lane, position)] = None

    def populate_demo_values(self) -> None:
        """Populate every text slot with representative demo values."""

        top_context = self._build_refresh_context("top")
        bottom_context = self._build_refresh_context("bottom")
        top_result = self._demo_refresh_top(top_context)
        bottom_result = self._demo_refresh_bottom(bottom_context)

        self._apply_refresh_result("top", top_result)
        self._apply_refresh_result("bottom", bottom_result)

        for lane in range(LANE_COUNT):
            for position in LANE_CHARTS:
                self.clear_lane_chart(lane, position)

        if DEFAULT_PORT_CHOICES:
            self.top_port_var.set("")
            self.bottom_port_var.set("")
        self.top_switch_var.set(self.top_switch_var.get() or DEFAULT_SWITCH_IP)
        self.bottom_switch_var.set(self.bottom_switch_var.get() or DEFAULT_SWITCH_IP)

    # ------------------------------------------------------------------ #
    # Internal utilities                                                  #
    # ------------------------------------------------------------------ #
    def _place_chart_image(
        self,
        lane: int,
        position: str,
        image: Optional["Image.Image"],
        bounds: LaneChartBounds,
    ) -> None:
        target_id = self.chart_items[(lane, position)]
        self.canvas.delete(target_id)
        offset_x = lane * (BACKGROUND_WIDTH / LANE_COUNT)
        x0 = (offset_x + bounds.left) * self.scale_x
        y0 = bounds.top * self.scale_y
        width = bounds.width * self.scale_x
        height = bounds.height * self.scale_y

        if image is None or ImageTk is None:
            self.chart_items[(lane, position)] = self.canvas.create_rectangle(
                x0,
                y0,
                x0 + width,
                y0 + height,
                outline="#1f2f5c",
                dash=(3, 3),
            )
            self.chart_images[(lane, position)] = None
            return

        resized = image.resize((int(width), int(height)), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(resized)
        item_id = self.canvas.create_image(x0, y0, anchor="nw", image=photo)
        self.chart_items[(lane, position)] = item_id
        self.chart_images[(lane, position)] = photo

    # ------------------------------------------------------------------ #
    # Refresh orchestration                                              #
    # ------------------------------------------------------------------ #
    def _normalize_sections(self, section: str) -> Tuple[str, ...]:
        if section == "all":
            return ("top", "bottom")
        if section in {"top", "bottom"}:
            return (section,)
        return ()

    def do_convert(self, lane_data):
        try:
            logger.info('do_convert')
            obj = SwitchLaneResult(lane_data)
            logger.info("Converted: %r", obj)
            logger.info('obj.tp1_host_ber')
            logger.info(obj.tp1_host_ber)
            logger.info('obj.tp3_host_ber')
            logger.info(obj.tp3_media_ber)
            return obj
        except Exception:
            logger.exception("Failed to convert lane_data=%r", lane_data)
            return None

    def _process_refresh_queue(self) -> None:
        while True:
            with self._refresh_lock:
                if not self._pending_sections:
                    self._pending_section_ids.clear()
                    self._refresh_thread = None
                    self.root.after(0, self._stop_indicator_success)
                    return

                # Peek first; only pop when data is actually ready.
                peek = self._pending_sections[0]
                if not self.new_data_available.get(peek, False):
                    section = None
                else:
                    section = self._pending_sections.popleft()
                    self._pending_section_ids.discard(section)

            if section is None:
                time.sleep(0.05)
                continue
            handler = self.refresh_handlers.get(section)
            if handler is None:
                continue
            try:
                section_data_list = self.data_list[section]
                logger.info('section_data_list=')
                logger.info(section_data_list)
                if section.lower() == "top":
                    current_port = (self.top_port_var.get() or "").strip()
                else:
                    current_port = (self.bottom_port_var.get() or "").strip()
                demo_value = {}
                for lane in range(8):
                    logger.info('self.FEC_tail[section][lane]')
                    logger.info(self.FEC_tail[section][lane])
                    lane_data = section_data_list[lane+1]
                    bar_data = self.FEC_tail[section][lane]  #lane_data['tp5_1']
                    logger.info(f'lane_data={lane}')
                    logger.info(lane_data)
                    logger.info('bar_data')
                    logger.info(bar_data)
                    self.draw_lane_bar_graph(bar_data, lane, section)
                    demo_value[lane] = self.do_convert(lane_data)
                    logger.info(f'demo lane_data={demo_value[lane]}')
                    logger.info(demo_value[lane])
                logger.info('demo_value')
                logger.info(demo_value)
                params = demo_value
                context = self._build_refresh_context(section)
                logger.info('context=')
                logger.info(context)
                logger.info('params=')
                logger.info(params)
                result = handler(context, params)
                logger.info(f"self._pending_sections after pop= {self._pending_sections}")
                logger.info(f"Updating section {section}")
                current_time = time.time()
                duration = (current_time-self.update_start_time)
                logger.info(f"duration since last update = {duration} seconds")
                self.update_start_time = time.time()
                logger.info(f"self.new_data_available = {self.new_data_available}")
                self.new_data_available[section] = False
                logger.info(f"self.new_data_available = {self.new_data_available}")
            except Exception as exc:  # pragma: no cover - user's handler failure
                logger.exception("error handle refresh")
                self.root.after(
                   0, lambda s=section, e=exc: self._handle_refresh_error(s, exc)
                )
                continue
            self.root.after(
                0, lambda s=section, res=result: self._apply_refresh_result(s, res)
            )

    def _build_refresh_context(self, section: str) -> RefreshContext:
        if section == "top":
            return RefreshContext(
                section=section,
                switch_ip=self.top_switch_var.get(),
                port=self.top_port_var.get(),
            )
        return RefreshContext(
            section=section,
            switch_ip=self.bottom_switch_var.get(),
            port=self.bottom_port_var.get(),
        )

    def _apply_refresh_result(self, section: str, result: SectionRefreshResult) -> None:
        for lane, values in result.lane_values.items():
            for field, value in values.items():
                try:
                    self.set_lane_value(lane, field, value)
                except KeyError:
                    continue

        for (lane, position), image in result.charts.items():
            if image is None:
                self.clear_lane_chart(lane, position)
            else:
                self._place_chart_image(lane, position, image, LANE_CHARTS[position])

    def _start_indicator(self) -> None:
        if self._indicator_item is None:
            return
        if self._indicator_job is not None:
            return
        self._indicator_error = False
        self._indicator_blink_state = False
        self.canvas.itemconfigure(self._indicator_item, fill="#ffd60a")
        self._indicator_job = self.root.after(BLINK_INTERVAL, self._blink_indicator)

    def _blink_indicator(self) -> None:
        if self._indicator_item is None:
            self._indicator_job = None
            return
        if self._indicator_error:
            self.canvas.itemconfigure(self._indicator_item, fill="#d90429")
            self._indicator_job = None
            return
        self._indicator_blink_state = not self._indicator_blink_state
        fill = "#ffd60a" if self._indicator_blink_state else "#ffe680"
        self.canvas.itemconfigure(self._indicator_item, fill=fill)

        self._indicator_job = self.root.after(BLINK_INTERVAL, self._blink_indicator)

    def _stop_indicator_success(self) -> None:
        if self._indicator_item is None:
            return
        if self._indicator_job is not None:
            self.root.after_cancel(self._indicator_job)
            self._indicator_job = None
        fill = "#d90429" if getattr(self, "_indicator_error", False) else "#2ecc71"
        self.canvas.itemconfigure(self._indicator_item, fill=fill)

    def start_blink(self) -> None:
        """Start blinking indicator (safe to call from main thread)."""
        # ensure we start from a known state
        if getattr(self, "_indicator_job", None) is None:
            self._indicator_blink_state = False
            # call immediately to show first change
            self._blink_indicator()

    def stop_blink(self) -> None:
        """Stop blinking and set indicator back to a steady green. Safe to call from main thread."""
        job = getattr(self, "_indicator_job", None)
        if job:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass
        self._indicator_job = None
        self._indicator_blink_state = False
        # set steady green (adjust color as you like)
        if self._indicator_item is not None:
            self.canvas.itemconfigure(self._indicator_item, fill="#00c853")  # e.g. steady green
  

    def _handle_refresh_error(self, section: str, exc: Exception) -> None:
        self._indicator_error = True
        if self._indicator_job is not None and self._indicator_item is not None:
            self.root.after_cancel(self._indicator_job)
            self._indicator_job = None
        if self._indicator_item is not None:
            self.canvas.itemconfigure(self._indicator_item, fill="#d90429")
        logger.info(f"[refresh] error refreshing {section}: {exc}", file=sys.stderr)

    # ------------------------------------------------------------------ #
    # Demo refresh handlers (defaults to keep layout usable)             #
    # ------------------------------------------------------------------ #
    def _demo_refresh_top(self, context: RefreshContext) -> SectionRefreshResult:
        lane_values: Dict[int, Dict[str, str]] = {}
        for lane in range(LANE_COUNT):
            lane_values[lane] = {
                "top_pre_fec_ber": f"{2.0 + lane * 0.05:.2E}",
                "top_post_fec_ber": f"{1.0 + lane * 0.05:.2E}",
                "top_tp0_tap": f"TP0 {context.port or '—'}.{lane}",
                "top_tp1_host_ber": f"{1.5 + lane * 0.02:.3E}",
                "top_tp4_tap": f"Tap {lane % 4 + 1}",
                "top_tp3_media_ber": f"{1.2 + lane * 0.03:.3E}",
                "top_txp": f"{-4.0 + lane * 0.15:.2f}",
                "top_rxp": f"{-3.2 + lane * 0.15:.2f}",
            }
        return SectionRefreshResult(lane_values=lane_values, charts={})

    def _demo_refresh_bottom(self, context: RefreshContext) -> SectionRefreshResult:
        lane_values: Dict[int, Dict[str, str]] = {}
        for lane in range(LANE_COUNT):
            lane_values[lane] = {
                "bottom_txp": f"{-4.8 + lane * 0.12:.2f}",
                "bottom_rxp": f"{-3.7 + lane * 0.12:.2f}",
                "bottom_tp3_media_ber": f"{2.5 + lane * 0.04:.3E}",
                "bottom_tp4_tap": f"Tap {lane % 4 + 1}",
                "bottom_tp1_host_ber": f"{1.6 + lane * 0.02:.3E}",
                "bottom_tp0_tap": f"TP0 {context.port or '—'}.{lane}",
                "bottom_post_fec_ber": f"{2.8 + lane * 0.05:.2E}",
                "bottom_pre_fec_ber": f"{4.4 + lane * 0.05:.2E}",
            }
        return SectionRefreshResult(lane_values=lane_values, charts={})


    def _value_refresh_top(self, context: RefreshContext, result) -> SectionRefreshResult:
        logger.info("_value_refresh_top, result")
        logger.info(result)
        lane_values: Dict[int, Dict[str, str]] = {}
        value = result
        portS = (self.top_port_var.get() or "").strip()
        port = int(portS)    
        for lane in range(LANE_COUNT):
            ethernet = (port - 1) * 8 + lane 
            lane_values[lane] = {
                "top_ethernet": f"{ethernet}",
                "top_lane": f"{lane + 1}",
                "top_pre_fec_ber": f"{value[lane].tp5_pre_fec_ber}",
                "top_post_fec_ber": f"{value[lane].tp5_post_fec_ber}",
                "top_tp0_tap": f"{value[lane].tp0_tap}",
                "top_tp1_host_ber": f"{value[lane].tp1_host_ber}",
                "top_tp4_tap": f"{value[lane].tp4_tap}",
                "top_tp3_media_ber": f"{value[lane].tp3_media_ber}",
                "top_rxp": f"{value[lane].rxp_dBm}",
                "top_txp": f"{value[lane].txp_dBm}"
            }
        return SectionRefreshResult(lane_values=lane_values, charts={})

    def _value_refresh_bottom(self, context: RefreshContext, result) -> SectionRefreshResult:
        lane_values: Dict[int, Dict[str, str]] = {}
        value = result
        portS = (self.bottom_port_var.get() or "").strip()
        port = int(portS)    
        for lane in range(LANE_COUNT):
            ethernet = (port - 1) * 8 + lane 
            lane_values[lane] = {
                "bottom_txp": f"{value[lane].txp_dBm}",
                "bottom_rxp": f"{value[lane].rxp_dBm}",
                "bottom_tp3_media_ber": f"{value[lane].tp3_media_ber}",
                "bottom_tp4_tap": f"{value[lane].tp4_tap}",
                "bottom_tp1_host_ber": f"{value[lane].tp1_host_ber}",
                "bottom_tp0_tap": f"{value[lane].tp0_tap}",
                "bottom_post_fec_ber": f"{value[lane].tp5_post_fec_ber}",
                "bottom_pre_fec_ber": f"{value[lane].tp5_pre_fec_ber}",
                "bottom_lane": f"{lane + 1}",
                "bottom_ethernet": f"{ethernet}",
            }
        return SectionRefreshResult(lane_values=lane_values, charts={})
        

    def populate_values(self, value_top, value_bottom) -> None:
        """Populate every text slot with representative demo values."""

        top_context = self._build_refresh_context("top")
        bottom_context = self._build_refresh_context("bottom")
        top_result = self._value_refresh_top(top_context, value_top)
        bottom_result = self._value_refresh_bottom(bottom_context, value_bottom)

        self._apply_refresh_result("top", top_result)
        self._apply_refresh_result("bottom", bottom_result)

        for lane in range(LANE_COUNT):
            for position in LANE_CHARTS:
                self.clear_lane_chart(lane, position)

        if DEFAULT_PORT_CHOICES:
            self.top_port_var.set("")
            self.bottom_port_var.set("")
        self.top_switch_var.set(self.top_switch_var.get() or DEFAULT_SWITCH_IP)
        self.bottom_switch_var.set(self.bottom_switch_var.get() or DEFAULT_SWITCH_IP)
        
    def toggle_auto_refresh(self):
        # Only allow auto-refresh when BOTH sections have IP + port selected.
        if not self.auto_refresh_enabled and not self._both_sections_configured():
            logger.info("Auto Refresh blocked: set IP and Port for BOTH top and bottom.")
            return
        self.auto_refresh_enabled = not self.auto_refresh_enabled

        if self.auto_refresh_enabled:
            self.auto_refresh_button.config(
                text="Auto Refresh: ON",
                style="AutoOn.TButton"
            )
            try:
                self.update_forever = True
                for sec in ("top", "bottom"):
                    self.update_data_once[sec] = False
                if hasattr(self, "refresh_button") and self.refresh_button is not None:
                    try:
                        self.refresh_button.configure(state="disabled")
                    except Exception:
                        pass
            except:
                logger.exception("error set up update flags")
            # If data is already available, refresh immediately.
            for sec in ("top", "bottom"):
                if self.new_data_available.get(sec, False):
                    self._notify_section_ready(sec)
        else:
            try:
                self.update_forever = False
                for sec in ("top", "bottom"):
                    self.update_data_once[sec] = False
                if hasattr(self, "refresh_button") and self.refresh_button is not None:
                    try:
                        self.refresh_button.configure(state="normal")
                    except Exception:
                        pass
            except:
                logger.exception("error set up update flags")
            self.auto_refresh_button.config(
                text="Auto Refresh: OFF",
                style="AutoOff.TButton"
            )

    def generate_demo_value(self) -> dict:
        return {
            # scientific notation around 1e-12
            "tp5_0": f"{random.uniform(1.0e-12, 3.0e-12):.2e}; {random.uniform(1.0e-12, 3.0e-12):.2e}",

            # first element ~4e12–6e12, second ~100k–300k, rest mostly small ints
            "tp5_1": [
                random.randint(4_000_000_000_000, 6_000_000_000_000),
                random.randint(100_000, 300_000),
                random.randint(0, 10),
                *[random.randint(0, 3) for _ in range(13)]
            ],

            # optical power-like values (1–3 range)
            "tp3_RXPwr": round(random.uniform(1.0, 2.5), 3),
            "tp2_TXPwr": round(random.uniform(1.5, 3.5), 3),

            # small control-like integers
            "tp0": [
                random.randint(0, 2),
                random.randint(0, 5),
                random.randint(-25, -15),
                random.randint(35, 45),
                random.randint(0, 5),
                random.randint(50, 70),
            ],

            "tp4": [
                random.randint(0, 2),
                random.randint(0, 2),
                random.randint(0, 5),
            ],

            # BER-like strings near zero
            "host_media_ber": [
                f"{random.choice([0.0, random.uniform(0.0, 1e-6)]):.1e}",
                f"{random.choice([0.0, random.uniform(0.0, 1e-6)]):.1e}",
            ],
        }
        
    def darker_color(self, hex_color, factor=0.25):
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        r = int(r * (1 - factor))
        g = int(g * (1 - factor))
        b = int(b * (1 - factor))
        return f"#{r:02x}{g:02x}{b:02x}"

    def draw_log_bars_cover_text_with_bins(
        self,
        canvas: tk.Canvas,
        values,
        *,
        x=10,
        y=10,
        width=250,
        bar_h=15, #17,
        gap=1,
        # colors=[
            # "#bcbd22", "#b2df8a","#bcbd22", "#b2df8a",  
            # "#bcbd22", "#b2df8a","#bcbd22", "#b2df8a",  
            # "#bcbd22", "#b2df8a","#bcbd22", "#b2df8a",  
            # "#bcbd22", "#b2df8a","#bcbd22", "#b2df8a"
        # ],
        colors = ["#b2df8a"]*16,
        number_of_bars=12,
        tag="demo_bars",
        clear=True,
        min_nonzero_frac=0.02,
        min_width_px=3, #8,
        text=True,
        text_left_inset=1, #6,
        text_right_pad=8,
        base_font_family="Arial",
        base_font_size=7,
        base_font_weight="bold",
        vpad=0,
        text_fill="black",
        # --- BIN label options ---
        show_bins=True,
        bin_prefix="BIN",
        bin_font_family="Arial",
        bin_font_size=7,
        bin_font_weight="normal",
        bin_pad=6,          # space between BIN text and bar start
        bin_fill="black",
    ):
        """
        Same as draw_log_bars_cover_text, but with BIN labels drawn to the left
        and the bars automatically shifted right to make room.
        Clarified on FEC tail color coding with Hock: for the first revision, we'll make it simple:
        BIN0-4: use green
        BIN5-10: any non-zero number should make the bar orange
        BIN11 and above: any non-zero number should make the bar red
        """
        dynamic_threshold = int(values[0]*BIN5_10_THRESHOLD_RATIO)
        if SIM_BIN_CROSS_THRESHOLD:
            num_bin_cross_threshold = random.randint(1, 7)
            for k in range(num_bin_cross_threshold):
               sim_bin = random.randint(1, 14)
               sim_bin_offset = random.randint(-dynamic_threshold, dynamic_threshold)
               values[sim_bin] = dynamic_threshold + sim_bin_offset
        vals = list(values[:number_of_bars])
        if len(vals) < number_of_bars:
            vals += [0] * (number_of_bars - len(vals))

        # Log scaling
        tvals = [math.log10(v + 1) for v in vals]
        vmax = max(tvals) if (tvals and max(tvals) > 0) else 1.0
        fracs = [tv / vmax for tv in tvals]

        if clear:
            canvas.delete(tag)

        # Auto-scale VALUE font to fit vertically (same logic as your original)
        max_text_height = max(bar_h - 2 * vpad, 2)
        font_size = base_font_size
        fnt = tkfont.Font(
            family=base_font_family,
            size=font_size,
            weight=base_font_weight,
        )
        while font_size > 3 and fnt.metrics("linespace") > max_text_height:
            font_size -= 1
            fnt = tkfont.Font(
                family=base_font_family,
                size=font_size,
                weight=base_font_weight,
            )

        if not text:
            fnt = None

        # BIN font (independent from value font)
        bin_fnt = None
        bin_space = 0
        if show_bins:
            bin_fnt = tkfont.Font(
                family=bin_font_family,
                size=bin_font_size,
                weight=bin_font_weight,
            )
            # Reserve space for the widest BIN label (e.g., BIN13)
            max_label = f"{bin_prefix}{number_of_bars - 1}"
            bin_space = bin_fnt.measure(max_label) + bin_pad

        # Shift bars to the right so BIN labels fit on the left
        x_bar = x + bin_space
        usable_width = max(width - bin_space, 1)
        n_colors = len(colors)
        bar_color_list = [colors[i] for i in range(n_colors)] # 2 shades of green
        for i in range(1,n_colors):
            if (values[i] > dynamic_threshold) and (i >= 5 and i <= 10):
                bar_color_list[i] = "#ff7f0e" # orange
            if (values[i] > 0) and (i >= 11):
                bar_color_list[i] = COLOR_RED

        for i, (v, frac) in enumerate(zip(vals, fracs)):
            if v > 0:
                frac = max(frac, min_nonzero_frac)

            # bar width from log-scaled fraction
            w = max(int(usable_width * frac), min_width_px)

            label = str(v)

            # ensure bar wide enough to cover VALUE label text
            if text and fnt:
                text_w = fnt.measure(label)
                required_w = text_left_inset + text_w + text_right_pad
                w = max(w, required_w)

            y0 = y + i * (bar_h + gap)
            y1 = y0 + bar_h

            # BIN label to the left of bars
            if show_bins and bin_fnt:
                bar_color = bar_color_list[i % n_colors]
                bin_color = self.darker_color(bar_color, 0.35)

                canvas.create_text(
                    x_bar - bin_pad,
                    y0 + bar_h // 2,
                    text=f"{bin_prefix}{i}",
                    anchor="e",
                    font=bin_fnt,
                    fill=bin_color,
                    tags=(tag,),
                )            
                # canvas.create_text(
                    # x_bar - bin_pad,
                    # y0 + bar_h // 2,
                    # text=f"{bin_prefix}{i}",
                    # anchor="e",      # right-align text at x_bar - bin_pad
                    # fill=bin_fill,
                    # font=bin_fnt,
                    # tags=(tag,),
                # )

            # bar rectangle
            canvas.create_rectangle(
                x_bar, y0, x_bar + w, y1,
                fill=bar_color_list[i % len(colors)],
                width=0,
                tags=(tag,),
            )

            # VALUE text inside bar
            if text and fnt:
                canvas.create_text(
                    x_bar + text_left_inset,
                    y0 + bar_h // 2,
                    text=label,
                    anchor="w",
                    fill=text_fill,
                    font=fnt,
                    tags=(tag,),
                )

        canvas.configure(
            scrollregion=(
                0,
                0,
                x_bar + usable_width + 200,
                y + len(vals) * (bar_h + gap),
            )
        )        

    def draw_lane_bar_graph(self, values, lane: int, position: str) -> None:
        rect_id = self.chart_items[(lane, position)]
        bounds = LANE_CHARTS[position]
        offset_x = lane * (BACKGROUND_WIDTH / LANE_COUNT) - 150
        offset_y = -164 #was -160
        canvas_x = (offset_x + bounds.left + bounds.width / 2) * self.scale_x
        canvas_y = (offset_y + bounds.top + bounds.height / 2) * self.scale_y
        canvas = self.canvas
       
        lane_width = bounds.width * self.scale_x * 1.2 #0.9
        left_x = canvas_x - lane_width / 2

        try:        
            self.draw_log_bars_cover_text_with_bins(
                canvas, values,
                x=canvas_x, y=canvas_y, width=lane_width,
                tag=f"{position}_bars_{lane}",
                number_of_bars=16,
                gap=0,
                vpad=0,
                clear=True,
                show_bins=True,
                bar_h=13, bin_font_size=8, base_font_size=8
            )                  
        except:
            logger.exception("error drawing bar graphs")
        
    def convert_lane_data(self,sn, fw, port, lane, raw, FEC_tail, duration):
        lane_d = {}
        lane_d["SN"] = sn
        lane_d["FW version"] = fw
        lane_d["lane"] = lane
        lane_d["port"] = port
        lane_d["lane"] = lane
        et = (int(port) - 1) * 8 + int(lane) -1
        lane_d["Ethernet"] = str(et)
        lane_d["tp0"] = raw["tp0"]
        host_media_ber = raw["host_media_ber"].split(";")
        #lane_d["tp1 host ber"] = host_media_ber[0]
        #lane_d["tp3 media ber"] = host_media_ber[1]
        host_ber = format_float_or_exponent(host_media_ber[0]) #f"{float(host_media_ber[0]):4e}"
        media_ber = format_float_or_exponent(host_media_ber[1]) # f"{float(host_media_ber[1]):.4e}"
        lane_d["tp1 host ber"] = host_ber
        lane_d["tp3 media ber"] = media_ber
        lane_d["tp2 TX power dBm"] = raw["tp2_TXPwr"]
        lane_d["tp3 RX power dBm"] = raw["tp3_RXPwr"]
        lane_d["tp4"] = raw["tp4"]
        tp5_0 = raw["tp5_0"].split(";")
        lane_d["tp5 pre FEC ber"] = tp5_0[0]
        lane_d["tp5 post FEC ber"] = tp5_0[1]
        # lane_d["FEC Tail"] = raw["tp5_1"]
        # tail = ""
        # for lane in range(7):
            # tail += f"{FEC_tail[lane]},"
        # tail += f"{FEC_tail[7]}"
        # lane_d["Computed FEC Tail"] = tail
        for i in range(16):
            lane_d[f"FEC_tail_{i}"] = raw["tp5_1"][i]
        for i in range(16):
            lane_d[f"Computed_FEC_tail_{i}"] = FEC_tail[i]
        
        lane_d["FEC time(s)"] = duration
        return lane_d

    def save_lane_data_to_csv(self, sn, fw, port, lane, raw, FEC_tail, duration, filename="lane_log.csv", timestamp = None):
        data = self.convert_lane_data(sn, fw, port, lane, raw, FEC_tail, duration)

        # Flatten lists (convert to string)
        for key, value in data.items():
            if isinstance(value, list):
                data[key] = ",".join(map(str, value))
            else:
                data[key] = value

        if timestamp:
            data["timestamp"] = timestamp

        file_exists = os.path.isfile(filename)

        with open(filename, mode='a', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=data.keys())

            # Write header only once
            if not file_exists:
                writer.writeheader()

            writer.writerow(data)
 

def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Render the switch equipment GUI overlay."
    )
    parser.add_argument(
        "--populate-demo",
        action="store_true",
        help="Populate every text box with demo values for layout verification.",
    )
    args = parser.parse_args(argv)

    app = SwitchEquipmentGUI()
    if args.populate_demo:
        app.populate_demo_values()
    app.run()


if __name__ == "__main__":
    main()
