# built-in libraries
from utils import *
from threading import Thread, Timer
from operator import itemgetter
import datetime
import time
from itertools import groupby
import mmap
import warnings
warnings.filterwarnings("ignore")

# implemented classes
from configs import CFG, Config
config = Config.from_json(CFG)
from messages.message import Message
from messages.node2tracker import Node2Tracker
from messages.node2node import Node2Node
from messages.chunk_sharing import ChunkSharing

next_call = time.time()

class Node:
    def __init__(self, node_id: int = int(time.time()), rcv_port: int = generate_random_port(), send_port: int = generate_random_port()):
        self.node_id = node_id
        self.rcv_socket = set_socket(rcv_port)
        self.send_socket = set_socket(send_port)
        self.files = self.fetch_owned_files()
        self.is_in_send_mode = False
        self.downloaded_files = {}

    def split_file_to_chunks(self, file_path: str, rng: tuple) -> list:
        with open(file_path, "r+b") as f:
            mm = mmap.mmap(f.fileno(), 0)[rng[0]: rng[1]]

            piece_size = config.constants.CHUNK_PIECES_SIZE
            return [mm[p: p + piece_size] for p in range(0, rng[1] - rng[0], piece_size)]

    def reassemble_file(self, chunks: list, file_path: str):
        with open(file_path, "bw+") as f:
            for ch in chunks:
                f.write(ch)
            f.flush()
            f.close()

    def send_chunk(self, filename: str, rng: tuple, dest_node_id: int, dest_port: int):
        file_path = f"{config.directory.node_files_dir}node{self.node_id}/{filename}"
        chunk_pieces = self.split_file_to_chunks(file_path=file_path, rng=rng)
        temp_port = generate_random_port()
        temp_sock = set_socket(temp_port)
        for idx, p in enumerate(chunk_pieces):
            msg = ChunkSharing(src_node_id=self.node_id,
                               dest_node_id=dest_node_id,
                               filename=filename,
                               range=rng,
                               idx=idx,
                               chunk=p)
            log_content = f"The {idx}/{len(chunk_pieces)} has been sent!"
            log(node_id=self.node_id, content=log_content)
            send_segment(sock=temp_sock,
                              data=Message.encode(msg),
                              addr=("localhost", dest_port))

        msg = ChunkSharing(src_node_id=self.node_id,
                           dest_node_id=dest_node_id,
                           filename=filename,
                           range=rng)
        send_segment(sock=temp_sock,
                          data=Message.encode(msg),
                          addr=("localhost", dest_port))

        log_content = "The process of sending a chunk to node{} of file {} has finished!".format(dest_node_id, filename)
        log(node_id=self.node_id, content=log_content)

        msg = Node2Tracker(node_id=self.node_id,
                           mode=config.tracker_requests_mode.UPDATE,
                           filename=filename)

        send_segment(sock=temp_sock,
                          data=Message.encode(msg),
                          addr=tuple(config.constants.TRACKER_ADDR))

        free_socket(temp_sock)

    def handle_requests(self, msg: dict, addr: tuple):
        # 1. asks the node about a file size
        if "size" in msg.keys() and msg["size"] == -1:
            self.tell_file_size(msg=msg, addr=addr)
        # 2. Wants a chunk of a file
        elif "range" in msg.keys() and msg["chunk"] is None:
            self.send_chunk(filename=msg["filename"],
                            rng=msg["range"],
                            dest_node_id=msg["src_node_id"],
                            dest_port=addr[1])


    def listen(self):
        while True:
            data, addr = self.send_socket.recvfrom(config.constants.BUFFER_SIZE)
            msg = Message.decode(data)
            self.handle_requests(msg=msg, addr=addr)

    def send(self, filename: str):
        if filename not in self.fetch_owned_files():
            log(node_id=self.node_id,
                content=f"You don't have {filename}")
            return

        if not filename.endswith(".mp3") and not filename.endswith(".wav"):
            log(node_id=self.node_id,
                content=f"You can only send .mp3 and .wav files!")
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
            t = Thread(target=self.listen, args=())
            t.setDaemon(True)
            t.start()

    def ask_file_size(self, filename: str, file_owner: tuple) -> int:
        temp_port = generate_random_port()
        temp_sock = set_socket(temp_port)
        dest_node = file_owner[0]

        msg = Node2Node(src_node_id=self.node_id,
                        dest_node_id=dest_node["node_id"],
                        filename=filename)
        send_segment(sock=temp_sock,
                          data=msg.encode(),
                          addr=tuple(dest_node["addr"]))
        while True:
            data, addr = temp_sock.recvfrom(config.constants.BUFFER_SIZE)
            dest_node_response = Message.decode(data)
            size = dest_node_response["size"]
            free_socket(temp_sock)

            return size

    def tell_file_size(self, msg: dict, addr: tuple):
        filename = msg["filename"]
        file_path = f"{config.directory.node_files_dir}node{self.node_id}/{filename}"
        file_size = os.stat(file_path).st_size
        response_msg = Node2Node(src_node_id=self.node_id,
                        dest_node_id=msg["src_node_id"],
                        filename=filename,
                        size=file_size)
        temp_port = generate_random_port()
        temp_sock = set_socket(temp_port)
        send_segment(sock=temp_sock,
                          data=response_msg.encode(),
                          addr=addr)

        free_socket(temp_sock)

    def receive_chunk(self, filename: str, range: tuple, file_owner: tuple):
        dest_node = file_owner[0]
        # we set idx of ChunkSharing to -1, because we want to tell it that we
        # need the chunk from it
        msg = ChunkSharing(src_node_id=self.node_id,
                           dest_node_id=dest_node["node_id"],
                           filename=filename,
                           range=range)
        temp_port = generate_random_port()
        temp_sock = set_socket(temp_port)
        send_segment(sock=temp_sock,
                          data=msg.encode(),
                          addr=tuple(dest_node["addr"]))
        log_content = "I sent a request for a chunk of {0} for node{1}".format(filename, dest_node["node_id"])
        log(node_id=self.node_id, content=log_content)

        while True:
            data, _ = temp_sock.recvfrom(config.constants.BUFFER_SIZE)
            msg = Message.decode(data)
            if msg["idx"] == -1:
                free_socket(temp_sock)
                return

            self.downloaded_files[filename].append(msg)

    def sort_downloaded_chunks(self, filename: str) -> list:
        sort_result_by_range = sorted(self.downloaded_files[filename],
                                      key=itemgetter("range"))
        group_by_range = groupby(sort_result_by_range,
                                 key=lambda i: i["range"])
        sorted_downloaded_chunks = []
        for _, value in group_by_range:
            value_sorted_by_idx = sorted(list(value),
                                         key=itemgetter("idx"))
            sorted_downloaded_chunks.append(value_sorted_by_idx)

        return sorted_downloaded_chunks

    def split_file_owners(self, file_owners: list, filename: str):
        owners = []
        for owner in file_owners:
            if owner[0]['node_id'] != self.node_id:
                owners.append(owner)
        if len(owners) == 0:
            log_content = f"No one has {filename}"
            log(node_id=self.node_id, content=log_content)
            return

        owners = sorted(owners, key=lambda x: x[1], reverse=True)

        to_be_used_owners = owners[:config.constants.MAX_SPLITTNES_RATE]

        # 1. first ask the size of the file from peers
        log_content = f"You are going to download {filename} from Node(s) {[o[0]['node_id'] for o in to_be_used_owners]}"
        log(node_id=self.node_id, content=log_content)
        file_size = self.ask_file_size(filename=filename, file_owner=to_be_used_owners[0])
        log_content = f"The file {filename} which you are about to download, has size of {file_size} bytes"
        log(node_id=self.node_id, content=log_content)

        # 2. Now, we know the size, let's split it equally among peers to download chunks of it from them
        step = file_size / len(to_be_used_owners)
        chunks_ranges = [(round(step*i), round(step*(i+1))) for i in range(len(to_be_used_owners))]

        # 3. Create a thread for each neighbor peer to get a chunk from it
        self.downloaded_files[filename] = []
        neighboring_peers_threads = []
        for idx, obj in enumerate(to_be_used_owners):
            t = Thread(target=self.receive_chunk, args=(filename, chunks_ranges[idx], obj))
            t.setDaemon(True)
            t.start()
            neighboring_peers_threads.append(t)
        for t in neighboring_peers_threads:
            t.join()

        log_content = "All the chunks of {} has downloaded from neighboring peers. But they must be reassembled!".format(filename)
        log(node_id=self.node_id, content=log_content)

        # 4. Now we have downloaded all the chunks of the file. It's time to sort them.
        sorted_chunks = self.sort_downloaded_chunks(filename=filename)
        log_content = f"All the pieces of the {filename} is now sorted and ready to be reassembled."
        log(node_id=self.node_id, content=log_content)

        # 5. Finally, we assemble the chunks to re-build the file
        total_file = []
        file_path = f"{config.directory.node_files_dir}node{self.node_id}/{filename}"
        for chunk in sorted_chunks:
            for piece in chunk:
                total_file.append(piece["chunk"])
        self.reassemble_file(chunks=total_file,
                             file_path=file_path)
        log_content = f"{filename} has successfully downloaded and saved in my files directory."
        log(node_id=self.node_id, content=log_content)
        self.files.append(filename)

    def set_download_mode(self, filename: str):
        file_path = f"{config.directory.node_files_dir}node{self.node_id}/{filename}"
        if os.path.isfile(file_path):
            log_content = f"You already have this file!"
            log(node_id=self.node_id, content=log_content)
            return
        else:
            log_content = f"You just started to download {filename}. Let's search it in torrent!"
            log(node_id=self.node_id, content=log_content)
            tracker_response = self.search_torrent(filename=filename)
            file_owners = tracker_response['search_result']
            self.split_file_owners(file_owners=file_owners, filename=filename)

    def search_torrent(self, filename: str) -> dict:
        msg = Node2Tracker(node_id=self.node_id,
                           mode=config.tracker_requests_mode.NEED,
                           filename=filename)
        temp_port = generate_random_port()
        search_sock = set_socket(temp_port)
        send_segment(sock=search_sock,
                          data=msg.encode(),
                          addr=tuple(config.constants.TRACKER_ADDR))

        while True:
            data, _ = search_sock.recvfrom(config.constants.BUFFER_SIZE)
            tracker_msg = Message.decode(data)
            return tracker_msg

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

    def download(self, filename: str):
        t = Thread(target=self.set_download_mode, args=(filename,))
        t.setDaemon(True)
        t.start()

    def check_files(self, files: list):
        log(node_id=self.node_id, content=f"Displaying available songs...\n")

        for idx, song in enumerate(files):
            print(f"[{idx + 1}] Track: {song}")
            print("-----------------------------")

    def check(self):
        msg = Node2Tracker(node_id=self.node_id,
                           mode=config.tracker_requests_mode.CHECK,
                           filename="")
        send_segment(sock=self.rcv_socket,
                          data=Message.encode(msg),
                          addr=tuple(config.constants.TRACKER_ADDR))

        while True:
            data, _ = self.rcv_socket.recvfrom(config.constants.BUFFER_SIZE)
            tracker_msg = Message.decode(data)

            self.check_files(files=tracker_msg["search_result"])
            return

    def setup(self):
        log_content = f"***************** Node program started just right now! *****************"
        log(node_id=self.node_id, content=log_content)
        self.enter_torrent()

        timer_thread = Thread(target=self.inform_tracker_periodically, args=(config.constants.NODE_TIME_INTERVAL,))
        timer_thread.setDaemon(True)
        timer_thread.start()

def run():
    node = Node()
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
                  f"download <filename> : downloads a file from nodes\n"
                  f"check : checks available files\n"
                  f"exit : exits the torrent\n"
                  f"help : shows this help menu\n")
            continue
        #################### send mode ####################
        if mode == 'send':
            node.send(filename=filename)
        #################### download mode ####################
        elif mode == 'download':
            node.download(filename=filename)
        #################### what can i download mode ####################
        elif mode == 'check':
            node.check()
        #################### exit mode ####################
        elif mode == 'exit':
            node.exit()
            exit(0)


if __name__ == '__main__':
    # run the node
    run()
