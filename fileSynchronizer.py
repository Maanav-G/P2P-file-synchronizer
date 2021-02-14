#!/usr/bin/python
# -*- coding: cp1252 -*-

# ==============================================================================
# description     :This is a skeleton code for programming assignment 2
# usage           :python skeleton.py trackerIP trackerPort
# python_version  :2.7
# Authors         :Chenhe Li, Yongyong Wei, Rong Zheng
# ==============================================================================

import socket
import sys
import threading
import json
import time
import os
import ssl
import os.path
import glob
import json
import optparse


# Validate the IP address of the correct format
def validate_ip(s):
    """
    Arguments:
    s -- dot decimal IP address in string
    Returns:
    True if valid; False otherwise
    """

    a = s.split('.')
    if len(a) != 4:
        return False
    for x in a:
        if not x.isdigit():
            return False
        i = int(x)
        if i < 0 or i > 255:
            return False
    return True

# Validate the port number is in range [0, 2^16-1]


def validate_port(x):
    """
    Arguments:
    x -- port number
    Returns:
    True if valid; False, otherwise
    """

    if not x.isdigit():
        return False
    i = int(x)
    if i < 0 or i > 65535:
        return False
    return True


# Get file info in the local directory (subdirectories are ignored)
# NOTE: Exclude files with .so, .py, .dll suffixes
def get_file_info():
    """
    Return: a JSON array of {"name":file,"mtime":mtime}
    """
    # YOUR CODE
    cwd = os.getcwd()
    filedict = {}
    fileslist1 = []
    fileslist2 = []
    cwd1 = directory = os.listdir(cwd)
    # search for files
    for files in cwd1:
        #print files
        if files.find("so") == -1 and files.find("py") == -1 and files.find("dll") == -1 and os.path.isfile(files):
            filename = files
            filepath = os.path.join(cwd, filename)
            mtime = os.path.getmtime(filepath)
            fileslist1.append(filename)
            fileslist2.append(mtime)
    filedict['filename'] = fileslist1
    filedict['mtime'] = fileslist2
    return filedict
# Check if a port is available


def check_port_avaliable(check_port):
    """
    Arguments:
    check_port -- port number
    Returns:
    True if valid; False otherwise
    """
    if str(check_port) in os.popen("netstat -na").read():
        return False
    return True

# Get the next available port by searching from initial_port to 2^16 - 1
# Hint: use check_port_avaliable() function


def get_next_avaliable_port(initial_port):
    """
    Arguments:
    initial_port -- the first port to check
    Return:
    port found to be available; False if no port is available.
    """
    # YOUR CODE
    i = initial_port
    while i <= 65535:
        if (check_port_avaliable(i)):
            return i
        else:
            i+1


class FileSynchronizer(threading.Thread):
    def __init__(self, trackerhost, trackerport, port, host='0.0.0.0'):

        threading.Thread.__init__(self)
        # Port for serving file requests
        self.port = port  # YOUR CODE
        self.host = host  # YOUR CODE

        # Tracker IP/hostname and port
        self.trackerhost = trackerhost  # YOUR CODE
        self.trackerport = trackerport  # YOUR CODE

        self.BUFFER_SIZE = 8192

        # Create a TCP socket to communicate with tracker
        self.client = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)  # YOUR CODE
        self.client.settimeout(180)

        # Store the message to be sent to tracker. Initialize to Init message
        # that contains port number and local file info.
        # YOUR CODE
        filelist = get_file_info()
        self.msg = {}
        self.msg['port'] = self.port
        self.msg['file'] = filelist
        # Create a TCP socket to serve file requests
        self.server = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)  # YOUR CODE

        try:
            self.server.bind((self.host, self.port))
        except socket.error:
            print('Bind failed %s' % (socket.error))
            sys.exit()
        self.server.listen(10)

    # Not currently used. Ensure sockets are closed on disconnect
    def exit(self):
        self.server.close()

    # Handle file request from a peer
    def process_message(self, conn, addr):
        """
        Arguments:
        self -- self object
        conn -- socket object for an accepted connection from a peer
        addr -- address bound to the socket of the accepted connection
        """
        # YOUR code
        # Step 1. read the file name contained in the request
        directory = os.getcwd()
        filelist = json.loads(get_file_info())
        #print filelist
        # Step 2. read the file from local directory (assuming binary file < 4MB)
        filename = filelist['filename'][0]
        filename = os.path.join(directory, filename)
        txt = open(filename).read(4096)
        # Step 3. send the file to the requester
        while True:
            conn.sendall(txt)
        conn.close

    def run(self):
        self.client.connect((self.trackerhost, self.trackerport))
        t = threading.Timer(2, self.sync)
        t.start()
        print('Waiting for connections on port %s' % (self.port))
        while True:
            conn, addr = self.server.accept()
            threading.Thread(target=self.process_message,
                             args=(conn, addr)).start()

    # Send Init or KeepAlive message to tracker, handle directory response message
    # and call self.syncfile() to request files from peers
    def sync(self):
        print ('connect to:'+self.trackerhost, self.trackerport)
        # Step 1. send Init msg to tracker
        # YOUR CODE
        print (self.msg)
        self.client.send(
            bytes(
                json.dumps(self.msg),
                'utf-8'
            ))

        # Step 2. receive a directory response message from tracker
        directory_response_message = ''
        # YOUR CODE
        while True:
            print("msg recved")
            part = self.client.recv(self.BUFFER_SIZE)
            p = part.decode('utf-8')
            print(part)
            directory_response_message = directory_response_message + p
            if len(part) < self.BUFFER_SIZE:
                break

        # Step 3. parse the directory response message. if it contains new or
        # more up-to-date files, request the files from the respective peers.
        # NOTE: compare the modified time of the files in the message and
        # that of local files of the same name.
        # YOUR CODE

        # Step 4. construct the KeepAlive message
        # YOUR CODE
        self.msg["port"] = self.port

        self.client.send(
            bytes(
                json.dumps(self.msg),
                'utf-8'
            ))
        # self.client.sendall(json.dumps(self.msg))
        # Step 4. start a timer
        t = threading.Timer(5, self.sync)
        t.start()


if __name__ == '__main__':
    # parse commmand line arguments
    parser = optparse.OptionParser(usage="%prog ServerIP ServerPort")
    options, args = parser.parse_args()
    if len(args) < 1:
        parser.error("No ServerIP and ServerPort")
    elif len(args) < 2:
        parser.error("No ServerIP or ServerPort")
    else:
        if validate_ip(args[0]) and validate_port(args[1]):
            tracker_ip = args[0]
            tracker_port = int(args[1])

        else:
            parser.error("Invalid ServerIP or ServerPort")

    # get the next available port
    synchronizer_port = get_next_avaliable_port(8000)
    print ("client using: "+str(synchronizer_port))
    synchronizer_thread = FileSynchronizer(
        tracker_ip, tracker_port, synchronizer_port)
    synchronizer_thread.start()
