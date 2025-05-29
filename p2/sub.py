# p2p_node.py
import zmq
import threading
import time
import sys

node_id = "B"
peer_ports = ["5556", "5557"]  # np. ["5556", "5557"]

context = zmq.Context()

# # PUB socket - każdy węzeł publikuje na swoim porcie
# pub_socket = context.socket(zmq.PUB)
# pub_port = 5556
# # f"555{ord(no
# # portde_id) - 65}"  # "A" = 5550, "B" = 5551...
# pub_socket.bind(f"tcp://*:{pub_port}")

# SUB socket - subskrybuje od innych węzłów
sub_socket = context.socket(zmq.SUB)
# for port in peer_ports:
port = 5657
sub_socket.connect("tcp://172.17.0.2:5555")
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")

def publish():
    # time.sleep(4)  # Ensure the subscriber is ready before publishing
    while True:
        # pub_socket.send_string(f"{node_id}: Hello at {time.time()}")
        time.sleep(2)

def receive():
    while True:
        message = sub_socket.recv_string()
        
        print(f"[{node_id}] Received: {message}")

receive()