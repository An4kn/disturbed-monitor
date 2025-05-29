# p2p_node.py
import zmq
import threading
import time
import sys

node_id = "A"
peer_ports = ["5556", "5557"]  # np. ["5556", "5557"]

context = zmq.Context()

# PUB socket - każdy węzeł publikuje na swoim porcie
pub_socket = context.socket(zmq.PUB)
# pub_port = f"555{ord(node_id) - 65}"  # "A" = 5550, "B" = 5551...
pub_port = 5557
pub_socket.bind(f"tcp://*:{pub_port}")

# SUB socket - subskrybuje od innych węzłów
sub_socket = context.socket(zmq.SUB)
# for port in peer_ports:
port = 5556
sub_socket.connect(f"tcp://172.17.0.4:{port}")
sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")

def publish():
    while True:
        pub_socket.send_string(f"{node_id}: Hello at {time.time()}")
        time.sleep(2)

def receive():
    while True:
        time.sleep(5)

        message = sub_socket.recv_string()
        print(f"[{node_id}] Received: {message}")

recv_thread = threading.Thread(target=receive)
recv_thread.start()

pub_thread = threading.Thread(target=publish)
pub_thread.start()

recv_thread.join()
pub_thread.join()
# receive()
# publish()

# while True:
#     time.sleep(1)


