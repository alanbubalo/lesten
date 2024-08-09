import socket
import random
import warnings
import os
from datetime import datetime
from configs import CFG, Config
from segment import UDPSegment
config = Config.from_json(CFG)

# global variables
used_ports = []


def set_socket(port: int) -> socket.socket:
    '''
    This function creates a new UDP socket

    :param port: port number
    :return: A socket object with an unused port number
    '''
    sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('localhost', port))
    used_ports.append(port)

    return sock


def free_socket(sock: socket.socket):
    '''
    This function free a socket to be able to be used by others

    :param sock: socket
    :return:
    '''
    used_ports.remove(sock.getsockname()[1])
    sock.close()


def generate_random_port() -> int:
    '''
    This function generates a new(unused) random port number

    :return: a random integer in range of [1024, 65535]
    '''
    available_ports = config.constants.AVAILABLE_PORTS_RANGE
    rand_port = random.randint(available_ports[0], available_ports[1])
    while rand_port in used_ports:
        rand_port = random.randint(available_ports[0], available_ports[1])

    return rand_port


def parse_command(command: str):
    '''
    This function parses the input command

    :param command: A string which is the input command.
    :return: Command parts (mode, filename)
    '''
    parts = command.split(' ')
    try:
        if len(parts) >= 2:
            mode = parts[0]
            filename = parts[1:]
            filename = " ".join(filename)
            return mode, filename
        elif len(parts) == 1:
            mode = parts[0]
            filename = ""
            if mode == 'send' or mode == 'download':
                raise ValueError
            return mode, filename
    except IndexError:
        warnings.warn("INVALID COMMAND ENTERED. TRY ANOTHER!")
        return
    except ValueError:
        warnings.warn("INVALID USE OF COMMAND. TRY ANOTHER!")
        return


def log(content: str, is_tracker=False, node_id: int = 0) -> None:
    '''
    This function is used for logging

    :param node_id: Since each node has an individual log file to be written in
    :param content: content to be written
    :return:
    '''
    if not os.path.exists(config.directory.logs_dir):
        os.makedirs(config.directory.logs_dir)

    # time
    current_time = datetime.now().strftime("%H:%M:%S")

    content = f"[{current_time}]  {content}\n"
    print(content)

    log_filename = '_tracker.log' if is_tracker else 'node{}.log'.format(node_id)
    node_logs_filename = config.directory.logs_dir + log_filename

    log_mode = 'w' if not os.path.exists(node_logs_filename) else 'a'
    with open(node_logs_filename, log_mode) as f:
        f.write(content)
        f.close()


def send_segment(sock: socket.socket, data: bytes, addr: tuple):
    ip, dest_port = addr
    segment = UDPSegment(src_port=sock.getsockname()[1],
                         dest_port=dest_port,
                         data=data)
    encrypted_data = segment.data
    sock.sendto(encrypted_data, addr)