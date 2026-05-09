import os
import time
import busio
import digitalio
import board
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn
import pwmio
from enum import Enum
import numpy as np
import logging
from logging.handlers import RotatingFileHandler
import mariadb
import sys
from secrets import db_user, db_password, db_name


# IO-pin setup for IR-leds with pwm output signal
ir_led0_pwm = pwmio.PWMOut(board.D14, frequency=38000, duty_cycle=32768)   # 50% duty cycle = 65535 / 2 = 32768
ir_led1_pwm = pwmio.PWMOut(board.D15, frequency=38000, duty_cycle=32768)

# SPI setup
spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)  # create the spi bus
cs = digitalio.DigitalInOut(board.D8)   # create the cs (chip select)
mcp = MCP.MCP3008(spi, cs)  # create a mcp object


class SensorTrigState(Enum):
    NO_TRIG = 0
    TRIG = 1
    UNKNOWN = 2


class SensorSample:
    def __init__(self):
        self.value: int = 0
        self.timestamp: int = 0
        self.trig_state = SensorTrigState.UNKNOWN
        
    def set_sample(self, value, timestamp, trig_state):
        self.value = value
        self.timestamp = timestamp
        self.trig_state = trig_state
    
    def get_sample(self):
        return self.value, self.timestamp, self.trig_state
    

class IrSensor:
    def __init__(self, mcp_channel :int, trig_threshold: int):
        self.mcp_channel = mcp_channel
        self.trig_threshold = trig_threshold
        self.sensor = AnalogIn(mcp, self.mcp_channel)
        
    def get_sensor_data(self):
        # read sensor value and timestamp
        value = self.sensor.value
        timestamp = round(time.time()*1000)
        
        # evaluate readout value to determine if sensor is trigged
        trig_state = SensorTrigState.UNKNOWN    # default value
        if(value < self.trig_threshold):    # detect any sensor trig. value is below threshold = TRIG, value is above threshold = NO_TRIG
            trig_state = SensorTrigState.TRIG   # trig detected
        else:
            trig_state = SensorTrigState.NO_TRIG    # no trig detected
        return value, timestamp, trig_state


class SensorHandler:
    def __init__(self, num_sensors: int, num_sample_columns: int, num_consecutive_trigs: int):
        self.num_sensors = num_sensors
        self.num_sample_columns = num_sample_columns
        self.num_consecutive_trigs = num_consecutive_trigs
        self.trig_threshold = 1000  # a digital value (0 - 65535) to represent a threshold for a trigged/blocked sensor
        
        self.sensors = []   # create sensors and store in a list
        for i in range(self.num_sensors):
            self.sensors.append(f"sensor{i}")
            self.sensors[i] = IrSensor(i, self.trig_threshold)


"""
test = SensorHandler(2, 3, 5)

for sensor in test.sensors:
    print(sensor.get_sensor_data()[0])
"""
