# lesten

Lesten is a distributed music file sharing platform that uses the BitTorrent protocol for peer-to-peer (P2P) exchange. Through a decentralized P2P system, users can safely, quickly and efficiently share, download and stream music directly from each other.

## How to use

### Tracker

    python3 tracker.py

### Node

    python3 node.py

## Commands

The following commands are available for each node:

### send

    send <file_name>

Send a file to another user. When a user wants to share a music file, he:

- Registers the file with the tracker, notifying it that the file is available for download.
- Enters a waiting state until other peers request that file.

### download

    download <file_name>

Download a file from another user. When a user wants to download a file:

- It first informs the tracker about the required file.
- Tracker searches the torrent and sorts the peers according to their upload frequency (the more a peer has sent, the more chances it has to be selected).
- Tracker then selects a fixed number of peers that own the file and suggests them to the user.
- The user establishes a UDP connection to the selected peers and starts downloading parts of the file.

Suppose we send a download request to N peering nodes to obtain a file of size S. Each peering node sends S/N bytes of that file to the original peer in parallel. After collecting all parts of the file, they must be reassembled and saved in the local directory of that node.

### check

    check

When a user wants to see which files are available for download:

- First, it informs the tracker about the list of available files and waits for its response.
- Tracker collects from the database a list of files that all users in the torrent can send.
- Tracker then sends a notification to the user about the list of files available for download.

### exit

exit

Exit the torrent and close the program.

### help

    help

Display a list of commands.
