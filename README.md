# mcasttunnel

## Description
Tunnels UDP multicast packets over TCP.

Intended to be used like `udptunnel` but when multicasting with loopback enabled
is required (since `udptunnel` disables multicast loopback it cannot be used to
receive multicast packets and tunnel them from the same host it is running on and
sends received data on the multicast group).

It can run either in TCP server (multi-threaded supporting multiple concurrent TCP clients)
or TCP client mode.

For each TCP connection 2 sockets (in addition to the one for the TCP data 
exchange, 1 to send UDP multicast packets and 1 to receive them) and 5 threads 
are spawned (1 to control the others and 2 pairs of reception-transmission 
threads for TCP and UDP). The 2 distinct sockets for UDP multicast are used in 
order to utilize a different (random) port for transmission in order to be able
to recognize (and discard) multicast packets that have originated from the 
instance itself.

The TCP client automatically retries every 1 second to connect if the connection
attempt fails or the connection is broken.


## Requirements

Python 3.x

## Usage

Give `python3 mcasttunnel.py -h` to get info on the command line arguments and 
usage.