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
Two queues are used for each TCP connection to buffer incoming packets (one for 
TCP, one for UDP) before transmission.

The TCP client automatically retries every 1 second to connect if the connection
attempt fails or the connection is broken.


## Requirements

Python 3.x

## Usage

        usage: mcasttunnel [-h] [-s] -a ADDRESS -p PORT -i MCAST_INTERFACE_ADDR -g
                          MCAST_GRP_ADDR -r MCAST_GRP_PORT -t MCAST_TTL [-v]

        Tunnel UDP multicast packets over TCP

        optional arguments:
          -h, --help            show this help message and exit
          -s, --server          if set run as TCP server, client otherwise
          -a ADDRESS, --address ADDRESS
                                the server's address if running as client, the address
                                of the network interface to listen on when running as
                                server (0.0.0.0 for any interface)
          -p PORT, --port PORT  the port the server listens (or should listen) on
          -i MCAST_INTERFACE_ADDR, --mcast_interface_addr MCAST_INTERFACE_ADDR
                                the address of the network interface to be used to
                                send/receive multicast packets
          -g MCAST_GRP_ADDR, --mcast_grp_addr MCAST_GRP_ADDR
                                the IP address of the multicast group
          -r MCAST_GRP_PORT, --mcast_grp_port MCAST_GRP_PORT
                                the port of the multicast group
          -t MCAST_TTL, --mcast_ttl MCAST_TTL
                                the TTL for multicast packets
          -v, --verbose         enables verbose output