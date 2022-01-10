import os
import pandas as pd
import numpy
import sys
import random
import math
import matplotlib.pyplot as plt
from datetime import datetime
from multiprocessing import Pool
import time

def payload_size_to_time(payload, sf):
    # data_rate_optimisation: BW 125kHz, SF>=11
    BW = 125
    PL = payload+3
    CR = 1
    CRC = 1
    H = 1
    DE = 0
    SF = sf
    npreamble = 8
    if(sf >= 11):
        DE = 1

    Rs = BW/(math.pow(2, SF))
    Ts = 1/(Rs)
    symbol = 8+max(math.ceil((8.0*PL-4.0*SF+28+16*CRC-20.0*H) /
                             (4.0*(SF-2.0*DE)))*(CR+4), 0)
    Tpreamble = (npreamble+4.25)*Ts
    Tpayload = symbol*Ts
    ToA = Tpreamble+Tpayload
    return ToA


def calculate_clock_drift(last_sync_time, current_time):
    time_drift_mode= random.randrange(101)
    if(time_drift_mode<50):
        m = 0.000081083333 #80ppm
        t = 5.4
    elif(time_drift_mode<90):
        m = 0.00006119496855 #60ppm
        t = 5.4
    else:
        m = 0.00002047558923 #20ppm
        t = 5.4

    current_time = current_time-last_sync_time
    return(m*current_time+t)

def calculate_gateway_channel_use(gateway_channel_use,sf):
    return gateway_channel_use + payload_size_to_time(1,sf)

def generate_sensor_events(payload_bytes, sf,slot_length,guard_time,cross_traffic):
    start = random.randrange(3600001)
    #####Timeslot Calculations#####
    if(not cross_traffic):
        x = start % (slot_length+2*guard_time)
        if(x != 0):
            start = start+((slot_length+2*guard_time)-x)+guard_time
    sync_error = 0
    if(not cross_traffic):
        time_drift = sync_error+calculate_clock_drift(0, start)
    else:
        time_drift = 0
    fin = start+payload_size_to_time(payload_bytes, sf)
    return({'start': float(start), 'fin': float(fin), 'sf': sf, 'bytes': int(payload_bytes), 'loss': 0, 'sync_error_ms': sync_error, 'time_drift_ms': time_drift})

def generate_sensor_events_continuation(orig_start_time,payload_bytes, sf,slot_length,guard_time,cross_traffic):
    start = orig_start_time + 3600000
    #####Timeslot Calculations#####
    if(not cross_traffic):
        x = start % (slot_length+2*guard_time)
        if(x != 0):
            start = start+((slot_length+2*guard_time)-x)+guard_time
    sync_error = 0
    if(not cross_traffic):
        time_drift = sync_error+calculate_clock_drift(0, start)
    else:
        time_drift=0
    fin = start+payload_size_to_time(payload_bytes, sf)
    return({'start': float(start), 'fin': float(fin), 'sf': sf, 'bytes': int(payload_bytes), 'loss': 0, 'sync_error_ms': sync_error, 'time_drift_ms': time_drift})


def run_sim(number_of_sensors, SF, payload_bytes, slot_length, guard_time,gw_duty_cycle,max_acceptable_time_drift,cross_traffic_percentage):
    ##########Setup##########
    sim_time=24
    begin_time=5
    total_collision_probability = 0
    gateway_channel_use=0
    result=[]
    gw_max_time=gw_duty_cycle*3600000*sim_time
    max_number_of_sensors=number_of_sensors
    for x in range(0, 10):
        sensors = []
        for i in range(0, number_of_sensors):
            cross_traffic=[]
            for i in range(0,number_of_sensors):
                if(random.random()<(cross_traffic_percentage/100)):
                    cross_traffic.append(True)
                else:
                    cross_traffic.append(False)
            #First power on
            sensors.append(generate_sensor_events(payload_bytes, SF,slot_length,guard_time,cross_traffic[i]))
            for time in range(0,sim_time):
                #24 hours continuation
                sensors.append(generate_sensor_events_continuation((sensors[-1]['start']+sensors[-1]['time_drift_ms']),payload_bytes,SF,slot_length,guard_time,cross_traffic[i]))
                #check for synchronization
                if(sensors[-1]['time_drift_ms']>max_acceptable_time_drift and not cross_traffic[i]):
                    #sync
                    gateway_channel_use = calculate_gateway_channel_use(gateway_channel_use,SF)
                    sensors[-1]['time_drift_ms']=0
                    sensors.append(generate_sensor_events_continuation((sensors[-1]['fin']+sensors[-1]['time_drift_ms']),1,SF,slot_length,guard_time,cross_traffic[i]))
                    sensors[-1]['time_drift_ms']=0
            if(gateway_channel_use>gw_max_time):
                if(i<max_number_of_sensors):
                    max_number_of_sensors=i
        sensors = sorted(sensors, key=lambda k: k['start'])
        losses = 0
        transmissions = 0
        ##########Decision if a packet was lost##########
        for i in range(0, len(sensors)-1):
            if((sensors[i]['fin']+sensors[i]['time_drift_ms']) > (sensors[i+1]['start']+sensors[i+1]['time_drift_ms'])):
                if((sensors[i]['fin']+sensors[i]['time_drift_ms'])>begin_time*3600000):
                    losses += 1
                    transmissions += 1
            else:
                if((sensors[i]['fin']+sensors[i]['time_drift_ms'])>begin_time*3600000):
                    transmissions += 1
        try:
            total_collision_probability += (losses/transmissions)
            result.append(losses/transmissions)
        except:
            pass
    ##########Output##########
    return result


def run_sim_with_fixed_parameters(args):
    x=args[0]
    SF=args[1]
    payload_bytes=args[2]
    slot_length=args[3]
    guard_time=args[4]
    gw_duty_cycle=args[5]
    max_acceptable_time_drift=args[6]
    cross_traffic_percentage=args[7]
    return run_sim(x, SF, payload_bytes, slot_length, guard_time,gw_duty_cycle,max_acceptable_time_drift,cross_traffic_percentage)

def run_sim_parallelized(number_of_sensors,SF,payload_bytes,slot_length,guard_time,gw_duty_cycle,max_acceptable_time_drift,cross_traffic_percentage):
    ##########Run with device range##########
    start=datetime.now()
    with Pool(16) as p:
        devices_against_collision = p.map(run_sim_with_fixed_parameters, [
                                          [i,SF,payload_bytes,slot_length,guard_time,gw_duty_cycle,max_acceptable_time_drift,cross_traffic_percentage] for i in range(0, number_of_sensors,10)])
    output = {'X':[0 for i in range(0,number_of_sensors,10)],'collisions':[devices_against_collision[i] for i in range(0,int(number_of_sensors/10))]}
    for x in range(0, number_of_sensors,10):
        output['X'][int(x/10)]=x
    pd.DataFrame(data=output).to_csv('Sensors SF'+str(SF)+' '+str(cross_traffic_percentage)+'.csv')
    pd.DataFrame(data=output).to_json('Sensors SF'+str(SF)+' '+str(cross_traffic_percentage)+'.json')
    print(datetime.now()-start)
    return output

def run_sim_sweep(number_of_sensors,SF,payload_bytes,slot_length,guard_time,gw_duty_cycle,max_acceptable_time_drift,cross_traffic_percentage):
    print(payload_size_to_time(8,7))
    for test in slot_length:
        print(1.25*payload_size_to_time(test,7))
    for z in SF:
        for x in payload_bytes:
            for y in slot_length:
                for w in cross_traffic_percentage:
                    print("Base parameters\nNumber of Sensors: "+str(number_of_sensors)+"\nSF: "+str(z)+"\nPayload: "+str(x)+"\nSlot Length:"+str(payload_size_to_time(y,z))+"\nGuard Time:"+str(0)+"\nCross Traffic:"+str(w)+"\n\n")
                    run_sim_parallelized(number_of_sensors,z,x,payload_size_to_time(y,z),0,gw_duty_cycle,max_acceptable_time_drift,w)

if __name__ == '__main__':
    ##########Parameters##########
    number_of_sensors = 10000
    SF = 8
    payload_bytes = 8
    slot_length = payload_size_to_time(payload_bytes,SF)
    guard_time = 0 #ms
    gw_duty_cycle=0.01
    max_acceptable_time_drift=200 #ms
    run_sim_sweep(number_of_sensors,[7,8,9,10,11,12],[8],[8],guard_time,gw_duty_cycle,max_acceptable_time_drift,[0,1,2,3,5,6,7,8,10,15,20,25,30,40,50])