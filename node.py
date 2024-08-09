# built-in libraries
from utils import *
import argparse
from threading import Thread, Timer
import datetime
import time
import warnings
warnings.filterwarnings("ignore")

# implemented classes
from configs import CFG, Config
config = Config.from_json(CFG)
from messages.message import Message
from messages.node2tracker import Node2Tracker

next_call = time.time()

class Node:
    def __init__(self, node_id: int, rcv_port: int = generate_random_port(), send_port: int = generate_random_port()):
        self.node_id = node_id
        self.rcv_socket = set_socket(rcv_port)
        self.send_socket = set_socket(send_port)
        self.files = self.fetch_owned_files()
        self.is_in_send_mode = False

    def send(self, filename: str):
        if filename not in self.fetch_owned_files():
            log(node_id=self.node_id,
                content=f"You don't have {filename}")
            return
        message = Node2Tracker(node_id=self.node_id,
                               mode=config.tracker_requests_mode.OWN,
                               filename=filename)

        send_segment(sock=self.send_socket,
                          data=message.encode(),
                          addr=tuple(config.constants.TRACKER_ADDR))

        if self.is_in_send_mode:
            log_content = f"Some other node also requested a file from you! But you are already in SEND(upload) mode!"
            log(node_id=self.node_id, content=log_content)
            return
        else:
            self.is_in_send_mode = True
            log_content = f"You are free now! You are waiting for other nodes' requests!"
            log(node_id=self.node_id, content=log_content)

    def fetch_owned_files(self) -> list:
        files = []
        node_files_dir = config.directory.node_files_dir + 'node' + str(self.node_id)
        if os.path.isdir(node_files_dir):
            _, _, files = next(os.walk(node_files_dir))
        else:
            os.makedirs(node_files_dir)

        return files

    def exit(self):
        msg = Node2Tracker(node_id=self.node_id,
                           mode=config.tracker_requests_mode.EXIT,
                           filename="")
        send_segment(sock=self.send_socket,
                          data=Message.encode(msg),
                          addr=tuple(config.constants.TRACKER_ADDR))
        free_socket(self.send_socket)
        free_socket(self.rcv_socket)

        log_content = f"You exited the torrent!"
        log(node_id=self.node_id, content=log_content)

    def enter_torrent(self):
        msg = Node2Tracker(node_id=self.node_id,
                           mode=config.tracker_requests_mode.REGISTER,
                           filename="")

        send_segment(sock=self.send_socket,
                          data=Message.encode(msg),
                          addr=tuple(config.constants.TRACKER_ADDR))

        log_content = f"You entered Torrent."
        log(node_id=self.node_id, content=log_content)

    def inform_tracker_periodically(self, interval: int):
        global next_call
        log_content = f"I informed the tracker that I'm still alive in the torrent!"
        log(node_id=self.node_id, content=log_content)

        msg = Node2Tracker(node_id=self.node_id,
                           mode=config.tracker_requests_mode.REGISTER,
                           filename="")

        send_segment(sock=self.send_socket,
                          data=msg.encode(),
                          addr=tuple(config.constants.TRACKER_ADDR))

        datetime.datetime.now()
        next_call = next_call + interval
        Timer(next_call - time.time(), self.inform_tracker_periodically, args=(interval,)).start()


    def setup(self):
        log_content = f"***************** Node program started just right now! *****************"
        log(node_id=self.node_id, content=log_content)
        self.enter_torrent()

        timer_thread = Thread(target=self.inform_tracker_periodically, args=(config.constants.NODE_TIME_INTERVAL,))
        timer_thread.setDaemon(True)
        timer_thread.start()

def run(node_id: int):
    node = Node(node_id=node_id)
    node.setup()

    print("ENTER YOUR COMMAND!")
    while True:
        command = input()

        parsed_command = parse_command(command)
        if parsed_command is None:
            continue

        mode, filename = parsed_command

        if mode == 'help':
            print(f"HELP MENU:\n"
                  f"send <filename> : sends a file to the tracker and register itself\n"
                  f"exit : exits the torrent\n"
                  f"help : shows this help menu\n")
            continue
        #################### send mode ####################
        if mode == 'send':
            node.send(filename=filename)
        #################### exit mode ####################
        elif mode == 'exit':
            node.exit()
            exit(0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-node_id', type=int,  help='id of the node you want to create')
    node_args = parser.parse_args()

    # run the node
    run(node_id=node_args.node_id)
