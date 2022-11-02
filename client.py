import socket
import sys
import os
import struct
from config import *

# Initialise socket stuff

class ClientInterface:
    def __init__(self, ip = TCP_IP, port = TCP_PORT, buffer_size = BUFFER_SIZE, dir = CLIENT_DIR) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ip = ip
        self.port = port
        self.buffer_size = buffer_size
        self.dir = dir

    def communicate(self, data):
        self.socket.send(data.encode('utf-8'))
        
    def connect(self):
        try:
            self.socket.connect((TCP_IP, TCP_PORT))
            print("connected successfully")
        except Exception as ex:
            print("connection unsucessful. Make sure the server is online.")

    def upload(self, file_name):
        # Upload a file
        print(f"Uploading file: {file_name}...")
        try:
            # Check the file exists
            content = open(file_name, "rb")
        except Exception as ex:
            print("Couldn't open file. Make sure the file name was entered correctly: ", ex)
            return
        try:
            # Make upload request
            self.communicate(CMDs['upload'])
        except Exception as ex:
            print("Couldn't make server request. Make sure a connection has bene established: ", ex)
            return
        try:
            # Wait for server acknowledgement then send file details
            # Wait for server ok
            self.socket.recv(self.buffer_size)
            # Send file name size and file name
            self.socket.send(struct.pack("h", sys.getsizeof(file_name)))
            self.communicate(file_name)
            # Wait for server ok then send file size
            self.socket.recv(self.buffer_size)
            self.socket.send(struct.pack("i", os.path.getsize(file_name)))
        except Exception as ex:
            print("Error sending file details: ", ex)
        try:
            # Send the file in chunks defined by self.buffer_size
            # Doing it this way allows for unlimited potential file sizes to be sent
            l = content.read(self.buffer_size)
            print("\nSending...")
            while l:
                self.socket.send(l)
                l = content.read(self.buffer_size)
            content.close()
            # Get upload performance details
            upload_time = struct.unpack("f", self.socket.recv(4))[0]
            upload_size = struct.unpack("i", self.socket.recv(4))[0]
            print(f"Sent file: {file_name}\nTime elapsed: {upload_time}s\nFile size: {upload_size}b")
        except Exception as ex:
            print("Error sending file: ", ex)

    def fetch(self):
        # List the files avaliable on the file server
        # Called list_files(), not list() (as in the format of the others) to avoid the standard python function list()
        print("Requesting files...\n")
        try:
            # Send list request
            self.communicate(CMDs["fetch"])
        except Exception as ex:
            print("Couldn't make server request. Make sure a connection has bene established: ", ex)
            return
        try:
            # First get the number of files in the directory
            number_of_files = struct.unpack("i", self.socket.recv(4))[0]
            print("number: ", number_of_files)
            # Then enter into a loop to recieve details of each, one by one
            for i in range(int(number_of_files)):
                file_name = self.socket.recv(self.buffer_size).decode()
                self.synchronize()
                # Also get the file size for each item in the server
                file_size = struct.unpack("i", self.socket.recv(4))[0]
                print(f"\t{file_name} - {file_size}b")
                # Make sure that the client and server are syncronised
                self.synchronize()
            # Get total size of directory
            total_directory_size = struct.unpack("i", self.socket.recv(4))[0]
            print(f"Total directory size: {total_directory_size}b")
        except Exception as ex:
            print("Couldn't retrieve listing: ", ex)
            return
        try:
            # Final check
            self.communicate("1")
        except Exception as ex:
            print("Couldn't get final server confirmation: ", ex)


    def synchronize(self):
        self.socket.send(b"1")
        
    def download(self, file_name):
        # Download given file
        print(f"Downloading file: {file_name}")
        try:
            # Send server request
            self.communicate(CMDs['download'])
        except Exception as ex:
            print("Couldn't make server request. Make sure a connection has bene established: ", ex)
            return
        try:
            # Wait for server ok, then make sure file exists
            self.socket.recv(self.buffer_size)
            # Send file name length, then name
            self.socket.send(struct.pack("h", sys.getsizeof(file_name)))
            self.communicate(file_name)
            # Get file size (if exists)
            file_size = struct.unpack("i", self.socket.recv(4))[0]
            if file_size == -1:
                # If file size is -1, the file does not exist
                print("File does not exist. Make sure the name was entered correctly")
                return
        except Exception as ex:
            print("Error checking file: ", ex)
        try:
            # Send ok to recieve file content
            self.synchronize()
            # Enter loop to recieve file
            with open(f'{self.dir}/{file_name}', "wb") as output_file:
                bytes_recieved = 0
                print("\n\tDownloading...")
                while bytes_recieved < file_size:
                    # Again, file broken into chunks defined by the self.buffer_size variable
                    l = self.socket.recv(self.buffer_size)
                    output_file.write(l)
                    bytes_recieved += self.buffer_size
            print(f"Successfully downloaded {file_name}")
            # Tell the server that the client is ready to recieve the download performance details
            self.synchronize()
            # Get performance details
            time_elapsed = struct.unpack("f", self.socket.recv(4))[0]
            print("Time elapsed: %.2fs\nFile size: %db" % (time_elapsed, file_size))
        except Exception as ex:
            print("Error downloading file: ", ex)

    def remove(self, file_name):
        # Delete specified file from file server
        print(f"Deleting file: {file_name}...")
        try:
            # Send resquest, then wait for go-ahead
            self.communicate(CMDs['remove'])
            self.socket.recv(self.buffer_size)
        except Exception as ex:
            print("Couldn't connect to server. Make sure a connection has been established: ", ex)
            return
        try:
            # Send file name length, then file name
            self.socket.send(struct.pack("h", sys.getsizeof(file_name)))
            self.communicate(file_name)
        except Exception as ex:
            print("Couldn't send file details: ", ex)
            return
        try:
            # Get conformation that file does/doesn't exist
            file_exists = struct.unpack("i", self.socket.recv(4))[0]
            if file_exists == -1:
                print("The file does not exist on server: ", ex)
                return
        except:
            print("Couldn't determine file existance")
            return
        try:
            # Confirm user wants to delete file
            confirm_delete = input("Are you sure you want to delete {}? (Y/N)\n".format(file_name)).upper()
            # Make sure input is valid
            # Unfortunately python doesn't have a do while style loop, as that would have been better here
            while confirm_delete != "Y" and confirm_delete != "N" and confirm_delete != "YES" and confirm_delete != "NO":
                # If user input is invalid
                print("Command not recognised, try again")
                confirm_delete = input("Are you sure you want to delete {}? (Y/N)\n".format(file_name)).upper()
        except Exception as ex:
            print("Couldn't confirm deletion status: ", ex)
            return
        try:
            # Send conformation
            if confirm_delete == "Y" or confirm_delete == "YES":
                # User wants to delete file
                self.communicate("Y")
                # Wait for conformation file has been deleted
                delete_status = struct.unpack("i", self.socket.recv(4))[0]
                if delete_status == 1:
                    print("File successfully deleted!")
                else:
                    # Client will probably send -1 to get here, but an else is used as more of a catch-all
                    print("File failed to delete!")
            else:
                self.communicate("N")
                print("Delete abandoned by user!: ", ex)
        except Exception as ex:
            print("Couldn't delete file: ", ex)

    def exit(self):
        self.communicate(CMDs['exit'])
        # Wait for server go-ahead
        self.socket.recv(self.buffer_size)
        self.socket.close()
        print("Server connection ended")

    def get_menu(self):
        return '\n\tcommands manual\t\n-----------------------------------------\n%s\t\t: connect to server\n' % CMDs["connect"] + \
            '%s file_path \t: upload file\t\n%s\t\t: fetch files list\n' % (CMDs["upload"], CMDs["fetch"]) + \
            '%s file_path \t: download file\t\n%s file_path \t: delete file\n.x           \t: Exit' % (CMDs["download"], CMDs["remove"])
               

    def process(self, statement):
        try:
            print(statement)
            terms = statement.split()
            for i, term in enumerate(terms):
                if term[0] == '.': # dot is commands start sign
                    lwrterm = term.lower()
                    if lwrterm == CMDs['connect']:
                        self.connect()
                    elif lwrterm == CMDs['upload']:
                        self.upload(terms[i + 1])
                    elif lwrterm == CMDs['fetch']:
                        self.fetch()
                    elif lwrterm == CMDs['download']:
                        self.download(terms[i + 1])
                    elif lwrterm == CMDs['remove']:
                        self.remove(terms[i + 1])
                    elif lwrterm == CMDs['exit']:
                        self.exit()
                        break
                    else:
                        print("command not recognised; please try again")
        except Exception as ex:
            print("command not supported! Please try again: ", ex)

    def standby(self):
        print(self.get_menu())

        # standby:
        while True:
            statement = input("\n--------------command line----------------\n ")
            self.process(statement)

if __name__ == '__main__':
    ClientInterface().standby()