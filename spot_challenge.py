#!/usr/bin/env python3

import json
import requests
import time
import jwt
import numpy as np
import bosdyn.client
from bosdyn.client import create_standard_sdk, ResponseError
from bosdyn.client.lease import LeaseClient, LeaseKeepAlive
from bosdyn.client.robot import RobotStateClient
from bosdyn.client.estop import EstopEndpoint, EstopKeepAlive
from bosdyn.client.robot_command import RobotCommandClient, blocking_stand, RobotCommandBuilder
from bosdyn.geometry import EulerZXY

hostname = "YOUR SCOUT HOSTNAME"
username = "YOUR SCOUT USERNAME"
password = "YOUR SCOUT PASSWORD"

# Get a set of cookies to be authenticated.
cookies_response = requests.get(f'https://{hostname}', verify=False)
cookies = requests.utils.dict_from_cookiejar(cookies_response.cookies)

# Authenticates the cookies by issuing a login request.
login_response = requests.post(f'https://{hostname}/api/v0/login', data={
    'username': username,
    'password': password
}, headers={'x-csrf-token': cookies['x-csrf-token']}, cookies=cookies, verify=False)

if not login_response.ok:
    print(f'Authentication failed: {login_response.text}')
    exit()
else:
    print(f'Authenticated! Logged in as: {login_response.json()["username"]}.')

# Spot-Steuerung
class SpotController:
    def __init__(spot, robot_ip):
        # creating an SDK object
        spot.sdk = create_standard_sdk('understanding-spot')

        # creating a robot object to retrieve the robot id
        spot.robot = spot.sdk.create_robot(robot_ip)

        # managing lease-Service with lease-client
        spot.lease_client = spot.robot.ensure_client(LeaseClient.default_service_name)
        spot.robot_state_client = spot.robot.ensure_client(RobotStateClient.default_service_name)

        # creating a RobotIdClient of the robot-id service
        spot.id_client = spot.robot.ensure_client('robot-id')

        # creating an E-Stop client
        spot.estop_client = spot.robot.ensure_client('estop')

        # creating and register an E-Stop Endpoint
        spot.estop_endpoint = EstopEndpoint(client=spot.estop_client, name='my_estop', estop_timeout=9.0)
        spot.estop_endpoint.force_simple_setup()

        # get E-Stop status
        estop_status = spot.estop_client.get_status()
        print("E-Stop Status:", estop_status)

        # creating and start E-Stop Keep Alive
        spot.estop_keep_alive = EstopKeepAlive(spot.estop_endpoint)

        # create a RobotCommandClient
        spot.command_client = spot.robot.ensure_client(RobotCommandBuilder.default_service_name)

    def acquire_lease(spot):
        # creating acquire-lease in case there is no remote mission callback
        lease_proto = spot.lease_client.acquire()

        # KeepAlive-function
        lease = LeaseKeepAlive(spot.lease_client, lease_proto)
        return lease

    def release_lease(spot, lease):
        lease.release()

    def get_robot_state(spot):
        state = spot.robot_state_client.get_robot_state()
        return state

    def power_on_robot(spot, timeout_sec=20):
        spot.robot.power_on(timeout_sec)

    def is_robot_powered_on(spot):
        return spot.robot.is_powered_on()

    def wait_for_time_sync(spot):
        spot.robot.time_sync.wait_for_sync()

    
    def stand_robot(spot, timeout_sec=10):
        # wraps several RobotCommand RPC calls
        blocking_stand(spot.command_client, timeout_sec=timeout_sec)

    def rotate_around_z(spot, angle):
        # Command Spot to rotate about the Z-axis.
        footprint_R_body = EulerZXY(yaw=angle, roll=0.0, pitch=0.0)
        cmd = RobotCommandBuilder.synchro_stand_command(footprint_R_body=footprint_R_body)
        spot.command_client.robot_command(cmd)

    def raise_up(spot, height):
        # Command Spot to raise up.
        cmd = RobotCommandBuilder.synchro_stand_command(body_height=height)
        spot.command_client.robot_command(cmd)

    # setting spot-commands to move
    def move_robot(spot, linear_velocity, angular_velocity):
        command = spot.robot.command_builder.safe_power_off_command()
        command.set_linear_velocity(linear_velocity)
        command.set_angular_velocity(angular_velocity)
        spot.robot.command_client.robot_command(command)

    #power off Spot     
    def power_off_robot(spot, cut_immediately=False):
        spot.robot.power_off(cut_immediately)

# SpotController
if __name__ == "__main__":
    spot_controller = SpotController('192.168.80.3')

    try:
        # Lease to control robot
        lease = spot_controller.acquire_lease()

        # robotstate
        robot_state = spot_controller.get_robot_state()
        print("Robot State:", robot_state)

        # power on the robot
        spot_controller.power_on_robot()

        # check if the robot is powered on and print information (output) 
        if spot_controller.is_robot_powered_on():
            print("Robot is powered on.")
        else:
            print("Robot is not powered on.")

        # wait for time synchronization
        spot_controller.wait_for_time_sync()

        # stand the robot
        spot_controller.stand_robot()

        # rotate Spot about the Z-axis
        spot_controller.rotate_around_z(angle=0.4)

        # raise up Spot
        spot_controller.raise_up(height=0.1)

        # movement of Spot
        spot_controller.move_robot(linear_velocity=0.2, angular_velocity=0.1)

        # power off the robot (optionally cut power immediately)
        spot_controller.power_off_robot(cut_immediately=False)

    except ResponseError as e:
        print(f"Malfunction: {e}")

    finally:
        # Lease Freigabe
        spot_controller.release_lease(lease)

