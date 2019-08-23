#!/usr/bin/python3

# MIT License
#
# Copyright (c) 2019 Georgios Migdos
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


import socketserver
import socket
import threading
import queue
import sys
import struct
import argparse
import logging
import time

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('mcasttunnel')


class McastSender(threading.Thread):

    def __init__(self, socket, queue, dst_addr, dst_port):
        threading.Thread.__init__(self, daemon=True)
        self.socket = socket
        self.queue = queue
        self.dst_addr = dst_addr
        self.dst_port = dst_port
        self.stopped = False
        self.stop_evt = threading.Event()
    
    def stop(self):
        self.stop_evt.set()
    
    def run(self):
        while not self.stop_evt.is_set():
            try:
                data_len, data = self.queue.get(timeout=1.0)
                logger.debug('MCASTTX: retrieved for Tx data with LEN: %d' % (data_len))
                try:
                    self.socket.sendto(data, (self.dst_addr, self.dst_port))
                except Exception:
                    logger.exception(sys.exc_info())
                    break
            except queue.Empty:
                pass


class McastReceiver(threading.Thread):

    MAX_PACKET_SIZE_C = 2048

    def __init__(self, socket, queue, own_src):
        threading.Thread.__init__(self, daemon=True)
        self.socket = socket
        self.queue = queue
        self.own_src = own_src
        self.stopped = False
        self.stop_evt = threading.Event()
    
    def stop(self):
        self.stop_evt.set()
    
    def run(self):
        data = b''
        while not self.stop_evt.is_set():
            try:
                data, src = self.socket.recvfrom(McastReceiver.MAX_PACKET_SIZE_C)
                if data is None:
                    logger.debug('MCASTRX: no data / socket closed')
                    break
                try:
                    if src != self.own_src:
                        self.queue.put((len(data), data))
                        logger.debug('MCASTRX: received data with LEN: %d' % (len(data)))
                except Exception:
                    logger.exception(sys.exc_info())
                    break
            except socket.timeout:
                pass


class TcpSender(threading.Thread):

    def __init__(self, socket, queue):
        threading.Thread.__init__(self, daemon=True)
        self.socket = socket
        self.queue = queue
        self.stopped = False
        self.stop_evt = threading.Event()
    
    def stop(self):
        self.stop_evt.set()
    
    def run(self):
        while not self.stop_evt.is_set():
            try:
                (data_len,data) = self.queue.get(timeout=1.0)
                logger.debug('TCPTX: retrieved for Tx data with LEN: %d' % (data_len))
                try:
                    size = len(data).to_bytes(2, 'big', signed=False)
                    self.socket.sendall(size+data)
                except Exception:
                    logger.exception(sys.exc_info())
                    break
            except queue.Empty:
                pass

class TcpReceiver(threading.Thread):

    def __init__(self, socket, queue):
        threading.Thread.__init__(self, daemon=True)
        self.socket = socket
        self.queue = queue
        self.stopped = False
        self.stop_evt = threading.Event()
    
    def stop(self):
        self.stop_evt.set()
    
    def run(self):
        data = b''
        while not self.stop_evt.is_set():
            if data is None:
                logger.debug('TCPRX: no data / socket closed')
                break
            try:
                size = int.from_bytes(self.socket.recv(2), 'big', signed=False)

                
                if size is None or size == 0:
                    logger.debug('TCPRX: no data / socket closed')
                    break
                
                data = self.socket.recv(size)
                logger.debug('TCPRX: received data with SIZE: %d' % (size))
                self.queue.put((size, data))

            except socket.timeout:
                pass
            except socket.error:
                logger.exception('TCPRX: socket error')
                break
            except KeyboardInterrupt:
                break

class ConnectionHandler:

    def __init__(self, socket, remote_address, mcast_interface_addr, mcast_grp_addr, mcast_grp_port, mcast_ttl):
        self.socket = socket
        self.remote_address = remote_address
        self.mcast_interface_addr = mcast_interface_addr
        self.mcast_grp_addr = mcast_grp_addr
        self.mcast_grp_port = mcast_grp_port
        self.mcast_ttl = mcast_ttl

    def setup_rx_mcast_socket(self, mcast_interface_addr, mcast_grp_addr, mcast_grp_port, mcast_ttl, timeout=1.0):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_TTL, mcast_ttl)
        sock.bind(('', mcast_grp_port))
        sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF, socket.inet_aton(mcast_interface_addr))
        mreq = struct.pack("=4s4s", socket.inet_aton(mcast_grp_addr), socket.inet_aton(mcast_interface_addr))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_LOOP, 1)
        sock.settimeout(timeout)
        return sock

    def setup_tx_mcast_socket(self, mcast_interface_addr, mcast_ttl=1):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_TTL, mcast_ttl)
        sock.bind((mcast_interface_addr, 0))
        return sock

    def execute(self):
        logger.info("New connection from: %s:%d" % (self.remote_address[0], self.remote_address[1]) )

        rx_queue = queue.Queue()
        tx_queue = queue.Queue()

        rx_mcast_sock = self.setup_rx_mcast_socket(self.mcast_interface_addr, self.mcast_grp_addr, self.mcast_grp_port, self.mcast_ttl)
        tx_mcast_sock = self.setup_tx_mcast_socket(self.mcast_interface_addr, self.mcast_ttl)
        
        tcp_sender = TcpSender(self.socket, tx_queue)
        tcp_sender.start()

        mcast_sender = McastSender(tx_mcast_sock, rx_queue, self.mcast_grp_addr, self.mcast_grp_port)
        mcast_sender.start()
        
        tcp_receiver = TcpReceiver(self.socket, rx_queue)
        tcp_receiver.start()

        mcast_receiver = McastReceiver(rx_mcast_sock, tx_queue, tx_mcast_sock.getsockname())
        mcast_receiver.start()

        tcp_receiver.join()

        mcast_receiver.stop()
        mcast_receiver.join()
        mcast_sender.stop()
        mcast_sender.join()
        tcp_sender.stop()
        tcp_sender.join()
        logger.info("Disconnected: %s:%d" % (self.remote_address[0], self.remote_address[1]) )


class TcpServerConnectionHandler(socketserver.BaseRequestHandler):

    def handle(self):
        conn_handler = ConnectionHandler(self.request, self.client_address, self.server.mcast_interface_addr, self.server.mcast_grp_addr, self.server.mcast_grp_port, self.server.mcast_ttl)
        conn_handler.execute()
        

class TcpClient:

    def connect(self, server_address, server_port, mcast_interface_addr, mcast_grp_addr, mcast_grp_port, mcast_ttl):
        s = socket.socket(family=socket.AF_INET, proto=socket.IPPROTO_TCP, type=socket.SOCK_STREAM)
        try:
            s.connect((server_address, server_port))
            s.settimeout(1.0)
            conn_handler = ConnectionHandler(s, (server_address, server_port), mcast_interface_addr, mcast_grp_addr, mcast_grp_port, mcast_ttl)
            conn_handler.execute()
        except ConnectionRefusedError:
            logger.info("Failed to connect to %s:%d" % (server_address, server_port) )
            time.sleep(1.0)
        s.close()

if __name__ == "__main__":

    argparser = argparse.ArgumentParser(prog='mcasttunnel', description='Tunnel UDP multicast packets over TCP')
    argparser.add_argument('-s', '--server', action='store_true', help='if set run as TCP server, client otherwise')
    argparser.add_argument('-a', '--address', action='store', required=True, help='the server\'s address if running as client, the address of the network interface to listen on when running as server (0.0.0.0 for any interface)')
    argparser.add_argument('-p', '--port', action='store', required=True, help='the port the server listens (or should listen) on')
    argparser.add_argument('-i', '--mcast_interface_addr', action='store', required=True, help='the address of the network interface to be used to send/receive multicast packets')
    argparser.add_argument('-g', '--mcast_grp_addr', action='store', required=True, help='the IP address of the multicast group')
    argparser.add_argument('-r', '--mcast_grp_port', action='store', required=True, help='the port of the multicast group')
    argparser.add_argument('-t', '--mcast_ttl', action='store', required=True, help='the TTL for multicast packets')
    argparser.add_argument('-v', '--verbose', action='store_true', required=False, help='enables verbose output')
    args = argparser.parse_args()

    logger.setLevel(logging.INFO)
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    if args.server:
        socketserver.ThreadingTCPServer.allow_reuse_address = True
        server = socketserver.ThreadingTCPServer((args.address, int(args.port)), TcpServerConnectionHandler)
        server.mcast_interface_addr = args.mcast_interface_addr
        server.mcast_grp_addr = args.mcast_grp_addr
        server.mcast_grp_port = int(args.mcast_grp_port)
        server.mcast_ttl = int(args.mcast_ttl)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        server.shutdown()
    else:
        try:
            client = TcpClient()
            while True:
                client.connect(args.address, int(args.port), args.mcast_interface_addr, args.mcast_grp_addr, int(args.mcast_grp_port), int(args.mcast_ttl))
        except KeyboardInterrupt:
            pass
        

