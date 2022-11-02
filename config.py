import tqdm

TCP_IP = "localhost" # ocal server
TCP_PORT = 4121
BUFFER_SIZE = 1024 # Standard buffer size

CMDs = {'connect': '.$', 'download': '.dl', 'upload': '.+', 'remove': '.-', 'fetch': '...', 'exit': '.x', 'disconnect': '.!'}

(SERVER_DIR, CLIENT_DIR) = ("server", "client")

def short_size(size_byte):
    units = ('eb', 'tb', 'gb', 'mb', 'kb', 'b')
    index = len(units) - 1
    
    while size_byte >= 1024 and index < len(units):
        index -= 1
        size_byte /= 1024
        
    return "%.2f %s" % (size_byte, units[index])


def make_progress(filename, filesize):
    return tqdm.tqdm(range(filesize), f"file: {filename}", unit="B", unit_scale=True, unit_divisor=1024)
