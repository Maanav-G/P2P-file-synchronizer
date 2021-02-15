import socket, sys, threading, json,time,os,ssl
import os.path
import glob
import json
import optparse


def validate_ip(s):
    """
    Validate the IP address of the correct format
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

def validate_port(x):
    """Validate the port number is in range [0,2^16 -1 ]
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

def get_file_info():
    """ Get file info in the local directory (subdirectories are ignored) 
    Return: a JSON array of {'name':file,'mtime':mtime}
    i.e, [{'name':file,'mtime':mtime},{'name':file,'mtime':mtime},...]
    Hint: a. you can ignore subfolders, *.so, *.py, *.dll
          b. use os.path.getmtime to get mtime, and round down to integer
    """
    file_arr = []
    files = os.listdir('.')
    for item in files:
        if not(
            item.endswith(".so") or 
            item.endswith(".py") or 
            item.endswith(".dll")
            ):
            file_arr += [{
                "name": item, 
                "mtime": os.path.getmtime(item)
                }]
    print("Files collected from local directory")
    return file_arr
        
def check_port_avaliable(check_port):
    """Check if a port is available
    Arguments:
    check_port -- port number
    Returns:
    True if valid; False otherwise
    """
    if str(check_port) in os.popen("netstat -na").read():
        return False
    return True

def get_next_available_port(initial_port):
    """Get the next available port by searching from initial_port to 2^16 - 1
       Hint: You can call the check_port_avaliable() function
             Return the port if found an available port
             Otherwise consider next port number
    Arguments:
    initial_port -- the first port to check

    Return:
    port found to be available; False if no port is available.
    """
    for port in range(initial_port,65536):
        if (check_port_avaliable(port)):
            return port
    return False

class FileSynchronizer(threading.Thread):
    def __init__(self, trackerhost,trackerport,port, host='0.0.0.0'):

        threading.Thread.__init__(self)
        #Port for serving file requests
        self.port = port 
        self.host = host 

        #Tracker IP/hostname and port
        self.trackerhost = trackerhost 
        self.trackerport = trackerport 

        self.BUFFER_SIZE = 8192

        #Create a TCP socket to communicate with tracker
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
        self.client.settimeout(180)

        #Store the message to be sent to the tracker. 
        #Initialize to the Init message that contains port number and file info.
        #Refer to Table 1 in Instructions.pdf for the format of the Init message
        #You can use json.dumps to conver a python dictionary to a json string
        self.msg = {'port':self.port, 'files': get_file_info()} 
        print ("Stored the message to be sent to the tracker.")

        #Create a TCP socket to serve file requests
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
        try:
            self.server.bind((self.host, self.port))
        except socket.error:
            print('Bind failed %s' % (socket.error))
            sys.exit()
        self.server.listen(10)

    # Not currently used. Ensure sockets are closed on disconnect
    def exit(self):
        self.server.close()

    #Handle file request from a peer(i.e., send the file content to peers)
    def process_message(self, conn,addr):
        """
        Arguments:
        self -- self object
        conn -- socket object for an accepted connection from a peer
        addr -- address bound to the socket of the accepted connection
        """
        #Step 1. read the file name contained in the request through conn
        #receive data
        data = ''
        while True:
            part = conn.recv(self.BUFFER_SIZE).decode('utf-8')
            data = data + part
            print("Step 1. Read the file name contained in the request through conn")
            if len(part) < self.BUFFER_SIZE:
                break
    
        #Step 2. read content of that file(assumming binary file <4MB), you can open with 'rb'
        print("-----------------------------------------------")
        data = data.replace('"', '')
        fileRead = open(data,'rb')
        fileData = fileRead.read()
        fileRead.close()
        print("Step 2. Read content of that file", fileData) 
        
        #Step 3. send the content back to the requester through conn
        # conn.sendall(fileData.encode('utf-8'))
        # conn.send(
        #     bytes(
        #         json.dumps(fileData), 
        #         'utf-8'
        #     )
        # )
        print("Step 3. Send the content back to the requester through conn")
        conn.send(fileData)

        #Step 4. close conn when you are done.
        print("Step 4. Close conn when you are done")
        conn.close()

    def run(self):
        self.client.connect((self.trackerhost,self.trackerport))
        t = threading.Timer(2, self.sync)
        t.start()
        print('Waiting for connections on port %s' % (self.port))
        while True:
            conn, addr = self.server.accept()
            threading.Thread(target=self.process_message, args=(conn,addr)).start()

    #Send Init or KeepAlive message to tracker, handle directory response message
    #and  request files from peers
    def sync(self):
        print ('connect to:'+ self.trackerhost,self.trackerport)

        #Step 1. send Init msg to tracker (Note init msg only sent once)
        #Note: self.msg is initialized with the Init message (refer to __init__)
        #      then later self.msg contains the Keep-alive message
        self.client.send(
            bytes(
                json.dumps(self.msg), 
                'utf-8'
            )
        )
        print("Step 1. Sent Init msg to tracker")

        #Step 2. now receive a directory response message from tracker
        directory_response_message = ''
        while True:
            part = self.client.recv(self.BUFFER_SIZE).decode('utf-8')
            directory_response_message = directory_response_message + part
            if len(part) < self.BUFFER_SIZE:
                break
        print("Step 2. Received a directory response message from tracker")
        print('received from tracker:',directory_response_message)

        #Step 3. parse the directory response message. If it contains new or
        #more up-to-date files, request the files from the respective peers.
        #NOTE: compare the modified time of the files in the message and
        #that of local files of the same name.
        #Hint: a. use json.loads to parse the message from the tracker
        #      b. read all local files, use os.path.getmtime to get the mtime 
        #         (also note round down to int)
        #      c. for new or more up-to-date file, you need to create a socket, 
        #         connect to the peer that contains that file, send the file name, and 
        #         receive the file content from that peer
        #      d. finally, write the file content to disk with the file name, use os.utime
        #         to set the mtime
        try:
            data_dic = json.loads(directory_response_message)
        except ValueError as error:
            print("invalid json: %s" % error)
        for f in data_dic:
            print("Step 3. Parse the directory response message.")
            ip = data_dic[f]['ip']
            port = data_dic[f]['port']
            mtime = data_dic[f]['mtime']
            if os.path.isfile(f):
                if mtime > os.path.getmtime(f):
                    newSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    newSocket.connect((ip,port))
                    newSocket.send(
                        bytes(
                            json.dumps(f), 
                            'utf-8'
                        )
                    )
                    message = ''
                    while True:
                        part = newSocket.recv(self.BUFFER_SIZE)
                        message = message + part.decode('utf-8')
                        print("Sync Message:", message)
                        if len(part) < self.BUFFER_SIZE:
                            break
                    newFile = open(f, 'wb')
                    # newFile.write(message)
                    newFile.write(
                        bytes(
                            json.dumps(message), 
                            'utf-8'
                        )
                    )
                    newFile.close()
                    newSocket.close()
            else:
                newSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                newSocket.connect((ip,port))
                newSocket.send(
                        bytes(
                            json.dumps(f), 
                            'utf-8'
                        )
                    )
                message = ''
                while True:
                    part = newSocket.recv(self.BUFFER_SIZE)
                    message = message + part.decode('utf-8')
                    print("Sync Message:", message)
                    if len(part) < self.BUFFER_SIZE:
                        break
                newFile = open(f, 'wb')
                # newFile.write(message)
                newFile.write(
                    bytes(
                        json.dumps(message), 
                        'utf-8'
                    )
                )
                newFile.close()
                newSocket.close()
                

        #Step 4. construct and send the KeepAlive message
        #Note KeepAlive msg is sent multiple times, the format can be found in Table 1
        #use json.dumps to convert python dict to json string.
        self.msg = {
            'port': self.port
        } 

        #Step 5. start a timer
        t = threading.Timer(5, self.sync)
        t.start()

if __name__ == '__main__':
    #parse command line arguments
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
    #get free port
    synchronizer_port = get_next_available_port(8000)
    synchronizer_thread = FileSynchronizer(tracker_ip,tracker_port,synchronizer_port)
    synchronizer_thread.start()