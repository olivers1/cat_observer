import os
import time
import busio
import digitalio
import board
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn
import pwmio
from enum import Enum
import logging
from logging.handlers import RotatingFileHandler
import mariadb
import sys
from secrets import db_user, db_password, db_name
from collections import deque


# IO-pin setup for IR-leds with pwm output signal
ir_led0_pwm = pwmio.PWMOut(board.D14, frequency=38000, duty_cycle=32768)   # 50% duty cycle = 65535 / 2 = 32768
ir_led1_pwm = pwmio.PWMOut(board.D15, frequency=38000, duty_cycle=32768)

# SPI setup
spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)  # create the spi bus
cs = digitalio.DigitalInOut(board.D8)   # create the cs (chip select)
mcp = MCP.MCP3008(spi, cs)  # create a mcp object

NUM_SENSORS = 2

# setup logging to files
filename_debug = "debug.log"  #"/var/log/cat_observer_app/debug.log"  
filename_info = "info.log"    #"/var/log/cat_observer_app/info.log"    
# logging handlers
console = logging.StreamHandler()
console.setLevel(logging.INFO)     # set the log level which is printed to terminal output

file_handler_debug = RotatingFileHandler(
    filename_debug,
    mode="w",              # overwrite after rotation
    maxBytes= 5 * 1024 * 1024,  # 5 MB
    backupCount=5,         # keep 5 old file
    encoding="utf-8"
)
file_handler_debug.setLevel(logging.DEBUG)

file_handler_info = RotatingFileHandler(
    filename_info,
    mode='w',                  # overwrite after rotation
    maxBytes=5 * 1024 * 1024,  # 5 MB max
    backupCount=1,             # keep 1 old files
    encoding='utf-8'
)
file_handler_info.setLevel(logging.INFO)

# logging config
logging.basicConfig(
    level=logging.DEBUG, handlers=[console, file_handler_debug, file_handler_info],
    style="{",
    format="{asctime} - {funcName} - {levelname}: {message}",
    )


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
    def __init__(self, mcp_channel :int, sensor_trig_threshold: int):
        self.mcp_channel = mcp_channel
        self.sensor_trig_threshold = sensor_trig_threshold
        
    def get_sensor_data(self):
        # read sensor value and timestamp
        sensor_read = AnalogIn(mcp, self.mcp_channel)
        value = sensor_read.value
        timestamp = round(time.time()*1000)
        
        # evaluate readout value to determine if sensor was trigged (blocked)
        trig_state = SensorTrigState.UNKNOWN
        if(value < self.sensor_trig_threshold):     # detect sensor trig. below threshold == trig, above threshold = no trig
            trig_state = SensorTrigState.TRIG       # trig detected
        else:
            trig_state = SensorTrigState.NO_TRIG    # no trig detected
        return value, timestamp, trig_state


class SensorHandler:
    def __init__(self, max_samples: int, num_consecutive_trigs: int):
        self.max_samples = max_samples
        self.num_consecutive_trigs = num_consecutive_trigs
        self.trig_threshold = 1000  # a digital value (0 - 65535) to represent the threshold for a trigged/blocked sensor
        
        self.sensors = [    # create sensors and store in a list
            IrSensor(sensor_id, self.trig_threshold)
            for sensor_id in range(NUM_SENSORS)
        ]

        self.logs = deque(maxlen=self.max_samples)    # logs to store sensor samples in deque list


    def register_log_sample(self, row):
        self.row = row
        sensor_row = []
        for sensor in self.row:
            sensor_sample = SensorSample()
            sensor_sample.set_sample(*sensor)   # store sensor data as SensorSample object
            sensor_row.append(sensor_sample)    # add SensorSample object as columns in the same row
        
        self.logs.appendleft(sensor_row)    # store SensorSample data as a new row in the deque list

    def reset_logs(self):
        self.logs.clear()   # clear all logs
        logging.debug("logs cleared")
        

class SensorsState(Enum):
    NO_TRIG = 0
    EXACTLY_ONE_TRIG = 1
    ALL_TRIG = 2
    UNKNOWN = 3


class AppLoggingState(Enum):
    INIT = 0
    IDLE = 1
    LOG_START = 2
    LOGGING = 3
    LOG_STOP = 4
    LOG_EVALUATION = 5


class MovementDirection(Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    INVALID = "INVALID"


class TrigEvaluationManager:
    def __init__(self,):
         self.max_samples = 10000
         self.num_consecutive_trigs = 5
         self.readout_frequency = 1 # Hz 
         self.sensor_handler = SensorHandler(self.max_samples, self.num_consecutive_trigs)
         self.verified_sensor_trig_state = []
         self.prev_verified_sensor_trig_state = [SensorTrigState.UNKNOWN, SensorTrigState.UNKNOWN]
         self.current_state = AppLoggingState.INIT  # keeps track of current app logging state
         self.previous_state = AppLoggingState.INIT # keeps track of the previous app logging state

    def run(self):
        while(True):
            row = []
            for sensor in self.sensor_handler.sensors:  # read sensor and store data in a row with a column for each sensor
                row.append(sensor.get_sensor_data())

            self.sensor_handler.register_log_sample(row)    # store sensor data as a SensorSample object in a row with a column for each sensor in a deque list
            
            print("\n----- Latest 5 log rows -----")
            for row in list(self.sensor_handler.logs)[:self.num_consecutive_trigs]:

                print([
                    (
                        sample.timestamp,
                        sample.trig_state.name
                    )
                    for sample in row
                ])
            """
            print("-----")
            for row in self.sensor_handler.logs:
                print([
                    (sample.timestamp, sample.trig_state.name)
                    for sample in row
            ])
            """
        
            self.verify_sensor_trig_states()
            time.sleep(1/self.readout_frequency)    # setting periodic time intervall for sensor readout

            self.update_logging_state()
            logging.debug("current_state: %s", self.current_state.name)

    def verify_sensor_trig_states(self):
        verified = []
        for sensor in range(NUM_SENSORS):
            recent = []
            rows = list(self.sensor_handler.logs)[:self.num_consecutive_trigs]  # extract the latest num_consecutive_trigs log rows for this sensor
            for row in rows:
                recent.append(row[sensor])  # store the extracted rows for this sensor in the recent variable at index of the sensor
             
            if len(recent) < self.num_consecutive_trigs:
                verified.append(SensorTrigState.UNKNOWN)
                continue

            first_state = recent[0].trig_state  # get the trig_state of latest sensor read for this sensor
            stable = all(sample.trig_state == first_state for sample in recent)     # check if all trig_states are equal as the latest
            verified.append(first_state if stable else SensorTrigState.UNKNOWN)     # if all trig_states are equal append the identified trig_state to variable else append UNKNOWN trig_state

        self.verified_sensor_trig_state = verified  # store the verified trig state for both sensors in one variable
        print([state.name for state in self.verified_sensor_trig_state])

        new_state = self.verified_sensor_trig_state
        if new_state != self.prev_verified_sensor_trig_state:
            logging.info("verified_sensor_trig_state Transition: %s → %s", [sensor_id.name for sensor_id in self.prev_verified_sensor_trig_state] , [sensor_id.name for sensor_id in new_state])
            self.prev_verified_sensor_trig_state = new_state.copy()
            

    def update_sensors_state(self):
        sensors_state = SensorsState.UNKNOWN
        if all(s == SensorTrigState.NO_TRIG for s in self.verified_sensor_trig_state):
            sensors_state = SensorsState.NO_TRIG
        elif sum(s == SensorTrigState.TRIG for s in self.verified_sensor_trig_state) == 1:
            sensors_state = SensorsState.EXACTLY_ONE_TRIG
        elif all(s == SensorTrigState.TRIG for s in self.verified_sensor_trig_state):
            sensors_state = SensorsState.ALL_TRIG
        logging.info("sensor_state: %s", sensors_state.name)
        return sensors_state
    
    def update_logging_state(self):
        sensors_state = self.update_sensors_state()

        if self.current_state == AppLoggingState.INIT:
            if sensors_state == SensorsState.NO_TRIG:
                self.enter_state(AppLoggingState.IDLE)
        
        elif self.current_state == AppLoggingState.IDLE:
            if sensors_state == SensorsState.EXACTLY_ONE_TRIG:
                # Detect which sensor triggered first
                #self.first_trig_sensor_id = self.verified_sensor_trig_state.index(SensorTrigState.TRIG)
                self.enter_state(AppLoggingState.LOG_START)

            elif sensors_state == SensorsState.ALL_TRIG:
                #self.first_trig_sensor_id = None    # both sensors trigged at the same time → INVALID
                self.enter_state(AppLoggingState.LOG_START)

            elif sensors_state == SensorsState.NO_TRIG:
                pass
                #self.sensor_handler.reset_logs()    # clear logs
        
        elif self.current_state == AppLoggingState.LOG_START:
            self.enter_state(AppLoggingState.LOGGING)   # change logging state to "logging"

        elif self.current_state == AppLoggingState.LOGGING:
            if sensors_state == SensorsState.NO_TRIG:
                pass

            elif sensors_state == SensorsState.EXACTLY_ONE_TRIG:
                pass
            
            elif sensors_state == SensorsState.ALL_TRIG:
                pass

        elif self.current_state == AppLoggingState.LOG_STOP:
            self.enter_state(AppLoggingState.LOG_EVALUATION)

        elif self.current_state == AppLoggingState.LOG_EVALUATION:
            self.enter_state(AppLoggingState.INIT)
    
    def enter_state(self, new_state):
        if new_state == self.current_state:     # no state change since current state is same as new state
           return
        
        logging.info("AppLoggingState Transition: %s → %s",
            self.current_state.name,
            new_state.name)
        
        self.previous_state = self.current_state
        self.current_state = new_state
        


test_obj = TrigEvaluationManager()
test_obj.run()
