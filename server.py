import socket
import sys
import time
import os
import struct
from random import randrange
import threading
from config import *


class Client:
    objs = {}

    def __init__(self, socket, ip) -> None:
        self.socket = socket
        self.ip = ip
        self.id = f'{ip[0]}{ip[1]}'.replace('.', '')
        self.connection_date = time.ctime()
        while self.id in Client.objs:
            self.id += str(randrange(0, len(Client.objs)))
        Client.objs[self.id] = self
        print(f"{self.ip} [id: {self.id}] has been connected!")

    def disconnect(self):
        if self.socket:
            self.socket.close()
        if self.id in Client.objs:
            del Client.objs[self.id]
        print(f"{self.ip} [id: {self.id}] has been disconnected!")
        
    def disconnect_all(self):
        for each in Client.objs.values():
            each.disconnect()
        Client.objs.clear()
        
    def synchronize(self):
        self.socket.send(b"1")
        
        
class FtpServer:
    def __init__(self, dir = SERVER_DIR, ip = TCP_IP, port = TCP_PORT, buff_size = BUFFER_SIZE) -> None:
        self.port = port
        self.ip = ip
        self.buff_size = buff_size
        self.dir = dir
        
    def standby(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((self.ip, self.port))
        self.server.listen(1)
        print(f"server started listening on {self.ip}:{self.port}; server is now on stand by for new clients...")

        while True:
            client_socket, ip_address = self.server.accept()

            client = Client(socket=client_socket, ip=ip_address)

            # receive the client's username
            thread = threading.Thread(target=self.listen2, args=(client,))
            thread.start()

    def listen2(self, client = None): 
        # listen to a specific client
        if not client:
            return
        try:
            while True: 
                # Enter into a while loop to recieve commands from client
                print("\n\twaiting for instruction")
                data = client.socket.recv(self.buff_size).decode()
                print(f"recieved instruction: {data}")
                # Check the command and respond correctly
                operation = ''
                if data == CMDs['upload']:
                    operation = 'uploading'
                    self.upload(client)
                elif data == CMDs['fetch']:
                    operation = 'fetching'
                    self.fetch(client)
                elif data == CMDs['download']:
                    operation = 'downloading'
                    self.download(client)
                elif data == CMDs['remove']:
                    operation = 'removing'
                    self.remove(client)
                elif data == CMDs['disconnect'] or data == CMDs['exit'] or not data:
                    client.disconnect()
                    
        except Exception as e:
            print(f"something went wrong while {operation} because: ", str(e), "\n\t ... disconnecting...")
            if client:
                client.disconnect()
                                
    def upload(self, client):
        # Send message once server is ready to recieve file details
        client.synchronize()
        # Recieve file name length, then file name
        file_name_size = struct.unpack("h", client.socket.recv(2))[0]
        file_name = client.socket.recv(file_name_size).decode()
        # Send message to let client know server is ready for document content
        client.synchronize()
        # Recieve file size
        file_size = struct.unpack("i", client.socket.recv(4))[0]
        # Initialise and enter loop to recive file content
        start_time = time.time()
        with open(f'./{self.dir}/{file_name}', "wb") as output_file:
            # This keeps track of how many bytes we have recieved, so we know when to stop the loop
            bytes_recieved = 0
            print(f"recieving {file_name}...")
            progress = make_progress(filename=file_name, filesize=file_size)
            while bytes_recieved < file_size:
                l = client.socket.recv(self.buff_size)
                output_file.write(l)
                bytes_recieved += self.buff_size
                progress.update(len(l))
        # Send upload performance details
        client.socket.send(struct.pack("f", time.time() - start_time))
        client.socket.send(struct.pack("i", file_size))


    def fetch(self, client):
        print("fetching files...")
            # Get list of files in directory
        listing = os.listdir(os.getcwd() + f"/{self.dir}")
        # Send over the number of files, so the client knows what to expect (and avoid some errors)
        client.socket.send(struct.pack("i", len(listing)))
        total_directory_size = 0
        # Send over the file names and sizes whilst totaling the directory size
        for x in listing:
            # File name size
            x_path = f"{self.dir}/{x}"
            # File name
            client.socket.send(x.encode())
            client.socket.recv(self.buff_size)
            
            # File content size
            client.socket.send(struct.pack("i", os.path.getsize(x_path)))
            total_directory_size += os.path.getsize(x_path)
            # Make sure that the client and server are syncronised
            client.socket.recv(self.buff_size)
            
        # Sum of file sizes in directory
        client.socket.send(struct.pack("i", total_directory_size))
        #Final check
        client.socket.recv(self.buff_size)
        print("successfully sent files fetch list")

    def download(self, client):
        client.synchronize()
        file_name_length = struct.unpack("h", client.socket.recv(2))[0]
        file_name = client.socket.recv(file_name_length).decode()
        full_relative_path = f'./{self.dir}/{file_name}'
        if os.path.isfile(full_relative_path):
            # Then the file exists, and send file size
            file_size = os.path.getsize(full_relative_path)
            client.socket.send(struct.pack("i", file_size))
            # Wait for ok to send file
            client.socket.recv(self.buff_size)
            # Enter loop to send file
            start_time = time.time()
            print(f"sending file: {file_name}...")
            progress = make_progress(filename=file_name, filesize=file_size)
            with open(full_relative_path, "rb") as content:
                # Again, break into chunks defined by self.buff_size
                l = content.read(self.buff_size)
                while l:
                    progress.update(len(l))
                    client.socket.send(l)
                    l = content.read(self.buff_size)
            # Get client go-ahead, then send download details
            progress.update(len(l))
            client.socket.recv(self.buff_size)
            client.socket.send(struct.pack("f", time.time() - start_time))
        else:
            # Then the file doesn't exist, and send error code
            print("file name not valid")
            client.socket.send(struct.pack("i", -1))

    def remove(self, client):
        # Send go-ahead
        client.synchronize()
        # Get file details
        file_name = client.socket.recv(self.buff_size).decode()
        client.synchronize()
        # Check file exists
        full_path = os.getcwd() + f'/{self.dir}/{file_name}'
        client.socket.recv(self.buff_size)
        if os.path.isfile(full_path):
            client.socket.send(struct.pack("i", 1))
        else:
            # Then the file doesn't exist
            client.socket.send(struct.pack("i", -1))
        # Wait for deletion conformation
        confirm_delete = client.socket.recv(self.buff_size).decode()
        if confirm_delete == "y":
            try:
                # Delete file
                os.remove(full_path)
                client.socket.send(struct.pack("i", 1))
                print(f"file {file_name} successfully removed.")
            except:
                # Something went wrong
                print(f"failed to remove {file_name}; maybe the file is used by another process?")
                client.socket.send(struct.pack("i", -1))
        else:
            # User abandoned deletion
            # The server probably recieved "N", but else used as a safety catch-all
            print("removing canceled!")

    def end(self):
        # Send quit conformation
        Client.disconnect_all()
        self.server.close()
        os.execl(sys.executable, sys.executable, *sys.argv)


if __name__ == '__main__':
    FtpServer(dir = input("enter the relative path of the folder you want to be shared: ") or SERVER_DIR).standby()