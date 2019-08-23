# mcasttunnel

## Description
Tunnels UDP multicast packets over TCP.

Intended to be used like `udptunnel` but when multicasting with loopback enabled
is required (since `udptunnel` disables multicast loopback it cannot be used to
receive multicast packets and tunnel them from the same host it is running on and
sends received data on the multicast group).

## Requirements

Python 3.x

## Usage

Give `python3 mcasttunnel.py -h` to get info on the command line arguments and 
usage.