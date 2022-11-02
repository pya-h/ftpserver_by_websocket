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
        file_size = os.path.getsize(file_name)
        try:
            # Wait for server acknowledgement then send file details
            # Wait for server ok
            self.socket.recv(self.buffer_size)
            # Send file name size and file name
            self.socket.send(struct.pack("h", sys.getsizeof(file_name)))
            self.communicate(file_name)
            # Wait for server ok then send file size
            self.socket.recv(self.buffer_size)
            self.socket.send(struct.pack("i", file_size))
        except Exception as ex:
            print("Error sending file details: ", ex)
        try:
            # Send the file in chunks defined by self.buffer_size
            # Doing it this way allows for unlimited potential file sizes to be sent
            upload_progress = make_progress(filename=file_name, filesize=file_size)
            l = content.read(self.buffer_size)

            while l:
                upload_progress.update(len(l))
                self.socket.send(l)
                l = content.read(self.buffer_size)

            upload_progress.update(len(l))
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
        print("requesting files...\n")
        try:
            # Send list request
            self.communicate(CMDs["fetch"])
        except Exception as ex:
            print("couldn't make server request. Make sure a connection has bene established: ", ex)
            return
        try:
            # First get the number of files in the directory
            number_of_files = struct.unpack("i", self.socket.recv(4))[0]
            # Then enter into a loop to recieve details of each, one by one
            print(f"\tfile size \t \t \t file name")
            print(f"  -----------------------|----------------------------------------------------------------")
            
            for i in range(int(number_of_files)):
                file_name = self.socket.recv(self.buffer_size).decode()
                self.synchronize()
                # Also get the file size for each item in the server
                file_size = struct.unpack("i", self.socket.recv(4))[0]
                print(f"\t{short_size(file_size)} \t | \t {file_name}")
                # Make sure that the client and server are syncronised
                self.synchronize()
            # Get total size of directory
            print(f"total files: {number_of_files}")
            total_directory_size = struct.unpack("i", self.socket.recv(4))[0]
            print(f"total directory size: {short_size(total_directory_size)}")
        except Exception as ex:
            print("couldn't retrieve listing: ", ex)
            return
        try:
            # Final check
            self.communicate("1")
        except Exception as ex:
            print("couldn't get final server confirmation: ", ex)


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
                print("file does not exist. Make sure the name was entered correctly")
                return
        except Exception as ex:
            print("error checking file: ", ex)
        try:
            # Send ok to recieve file content
            self.synchronize()
            # Enter loop to recieve file
            download_progress = make_progress(filename=file_name, filesize=file_size)
            with open(f'{self.dir}/{file_name}', "wb") as output_file:
                bytes_recieved = 0
                while bytes_recieved < file_size:
                    # Again, file broken into chunks defined by the self.buffer_size variable
                    l = self.socket.recv(self.buffer_size)
                    download_progress.update(len(l))
                    output_file.write(l)
                    bytes_recieved += self.buffer_size
            # Tell the server that the client is ready to recieve the download performance details
            self.synchronize()
            # Get performance details
            time_elapsed = struct.unpack("f", self.socket.recv(4))[0]
            print("time elapsed: %.2fs\nFile size: %s" % (time_elapsed, short_size(file_size)))
        except Exception as ex:
            print("error downloading file: ", ex)

    def remove(self, file_name):
        # Delete specified file from file server
        print(f"removing file: {file_name}...")
        try:
            # Send resquest, then wait for go-ahead
            self.communicate(CMDs['remove'])
            self.socket.recv(self.buffer_size)
        except Exception as ex:
            print("couldn't connect to server. Make sure a connection has been established: ", ex)
            return
        try:
            # Send file name length, then file name
            self.communicate(file_name)
            self.socket.recv(self.buffer_size)
            self.synchronize()
        except Exception as ex:
            print("couldn't send file details: ", ex)
            return
        try:
            # Get conformation that file does/doesn't exist
            file_exists = struct.unpack("i", self.socket.recv(4))[0]
            if file_exists == -1:
                print("the file does not exist on server: ")
                return
        except Exception as ex:
            print(f"failure while checking file existence: {ex}!")
            return
        
        confirm_delete = '0'
        try:
            # Confirm user wants to delete file
            # Make sure input is valid
            # Unfortunately python doesn't have a do while style loop, as that would have been better here
            while confirm_delete != "y" and confirm_delete != "n" and confirm_delete != "yes" and confirm_delete != "no":
                # If user input is invalid
                confirm_delete = input(f"r u sure to remove {file_name}? y [yes] \t n [no]: ").lower()

        except Exception as ex:
            print("couldn't confirm deletion status: ", ex)
            return
        try:
            # Send conformation
            if confirm_delete[0] == 'y':
                print(confirm_delete)
                # User wants to delete file
                self.communicate("y")
                # Wait for conformation file has been deleted
                delete_status = struct.unpack("i", self.socket.recv(4))[0]
                if delete_status == 1:
                    print(f"file: {file_name} successfully deleted!")
                else:
                    # Client will probably send -1 to get here, but an else is used as more of a catch-all
                    print(f"file: {file_name} failed to delete!")
            else:
                self.communicate("n")
                print("removing cancelled by u!")
        except Exception as ex:
            print(f"couldn't delete file because: {ex}!")


    def get_menu(self):
        return '\n\tcommands manual\t\n-----------------------------------------------------------------------\n%s\t\t: connect to server\n' % CMDs["connect"] + \
            '%s file_path \t: upload a file\t\n%s\t\t: fetch files list\n' % (CMDs["upload"], CMDs["fetch"]) + \
            '%s file_path \t: download a file\t\n%s file_path \t: remove a file\n%s           \t: disconnect\n' % (CMDs["download"], CMDs["remove"], CMDs['disconnect']) + \
            '%s           \t: exit' % (CMDs['exit'])   

    def disconnect(self):
        try:
            if self.socket:
                self.communicate(CMDs['disconnect'])
                # Wait for server go-ahead
                self.socket.recv(self.buffer_size)
                self.socket.close()
        except:
            pass
        finally:
            print("you are now disconnected!")

    def exit(self):
        self.disconnect()
        print("bye bye!")
        exit(0)
        
    def process(self, statement):
        try:
            print(statement)
            terms = statement.split()
            for i, term in enumerate(terms):
                if term[0] == '.': # dot is commands start sign
                    lwrterm = term.lower()
                    if lwrterm == CMDs['connect']:
                        print("\n----------------------------connection---------------------------------\n ")
                        self.connect()
                    elif lwrterm == CMDs['upload']:
                        print("\n-------------------------------upload----------------------------------\n ")
                        self.upload(terms[i + 1])
                    elif lwrterm == CMDs['fetch']:
                        print("\n----------------------------fetch files--------------------------------\n ")
                        self.fetch()
                    elif lwrterm == CMDs['download']:
                        print("\n-----------------------------download----------------------------------\n ")
                        self.download(terms[i + 1])
                    elif lwrterm == CMDs['remove']:
                        print("\n------------------------------remove-----------------------------------\n ")
                        self.remove(terms[i + 1])
                        
                    elif lwrterm == CMDs['disconnect']:
                        print("\n----------------------------disconnect---------------------------------\n ")
                        self.disconnect()
                        break
                                            
                    elif lwrterm == CMDs['exit']:
                        self.exit()
                    else:
                        print("command not recognised; please try again")
        except Exception as ex:
            print("command not supported! Please try again: ", ex)

    def standby(self):
        print(self.get_menu())

        # standby:
        while True:
            statement = input("\n----------------------------command line--------------------------------\n ")
            self.process(statement)

        
if __name__ == '__main__':
    ClientInterface().standby()