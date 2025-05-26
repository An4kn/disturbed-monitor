# p2p_node.py
import zmq
import threading
import time
import sys
import json

class DisturbedMonitor():
    def __init__(self):
        self.critical_section_queue = []
        self.device_process_id = "P2"
        context = zmq.Context()
        self.pub_socket = context.socket(zmq.PUB)
        pub_port = 5556
        self.pub_socket.bind(f"tcp://*:{pub_port}")
        self.sub_socket = context.socket(zmq.SUB)
        port = 5557
        self.sub_socket.connect(f"tcp://172.17.0.2:{port}")
        self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.other_processes_count = 2
        time.sleep(4)  # Allow some time for the subscriber to connect

    
    def get_message(self,buffer,in_index,out_index):
        message = self.sub_socket.recv()
        msg_response = message.decode('utf-8')
        data = json.loads(msg_response)
        
        if data["msg_type"] == "Replay" and data["process"] == self.device_process_id:
            processid_want_critical_section = self.critical_section_queue[0]
            if processid_want_critical_section[0] == self.device_process_id:
                # EnterCriticalSection(self.device_process_id, critical_section_queue, 10, [], 0)
                self.critical_section_queue.pop(0)

        elif data["msg_type"] == "Request":
            self.critical_section_queue.append(data["process"],data["time"]) # collections queue.Queue() #moze dodac
            self.critical_section_queue.sort() #nie wiem w sumie moze to uproscic aby mniejsza zlozonosc obliczeniowa i mnoze zwykle sortowanie bez lambdy jka nie  bedzi edzialac  key=lambda x: x["time"]????
            
        elif data["msg_type"] == "Release":
            pass

        elif data["msg_type"] == "ProcessEndWork":
            pass

    def wait(self,buffer,in_index,out_index): #TODO tutaj bym tabele dodal a teraz zmienne
        #TODO releasemessage
        return self.get_message(buffer,in_index,out_index)
        # while True:
        #     self.get_message()
    def notify(self, message):
        #TODO release_message
        self.pub_socket.send_string(message)

    def CriticalSectionAllowed(self,buffer,in_index,out_index):
        self.Request_message()
        self.get_message(buffer,in_index,out_index)
    
    def Release_message(self):
        pass

    def Request_message(self):
        Process = "P2"
        request_data = {"msg_type": "Request" , "process":  Process, "time": time.time()}
        message_request = json.dumps(request_data).encode('utf-8') #mozliwe ze nieporzebne
        self.pub_socket.send(message_request) #protocol buffers
    
    def Replay_message(self,process_id):
        if process_id == "P2":
            request_data = {"msg_type": "Replay","Process":  process_id}
            message_request = json.dumps(request_data).encode('utf-8') #mozliwe ze nieporzebne
            self.pub_socket.send(message_request) #protocol buffers //TODO rozroznic sockety????
            
CAPACITY = 10
buffer = [-1 for _ in range(CAPACITY)]
in_index = 0
out_index = 0

def Producer(DisturbedMonitor):
    global CAPACITY, buffer, in_index
    items_produced = 0
    counter = 0

    while items_produced < 20:
        buffer,in_index,out_index = DisturbedMonitor.CriticalSectionAllowed(buffer,in_index,out_index) #TODO to mozna w sumie usunac ale nie trzeba
        while (in_index + 1) % CAPACITY == out_index:
            buffer,in_index,out_index = DisturbedMonitor.wait(buffer,in_index,out_index)  # TODO MA BYC TABLICA ZWYKLA

        counter += 1
        buffer[in_index] = counter
        print("Producer produced:", counter)
        in_index = (in_index + 1) % CAPACITY

        DisturbedMonitor.notify(buffer,in_index)  # Signal to consumers



CAPACITY = 10
buffer = [-1 for _ in range(CAPACITY)]
in_index = 0

DisturbedMonitor = DisturbedMonitor()
Producer(DisturbedMonitor,0, [], 0)  # Initialize producer with 0 items produced, empty buffer, and in_index at 0

# node_id = "B"
# peer_ports = ["5556", "5557"]  # np. ["5556", "5557"]
# critical_section_queue = []
# context = zmq.Context()

# pub_socket = context.socket(zmq.PUB)
# pub_port = 5556
# pub_socket.bind(f"tcp://*:{pub_port}")
# sub_socket = context.socket(zmq.SUB)
# port = 5557
# sub_socket.connect(f"tcp://172.17.0.2:{port}")
# sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")

# time.sleep(4)  # Allow some time for the subscriber to connect

# Process = "P2"
# request_data = {"msg_type": "Request" , "process": Process, "time": time.time()}
# message_request = json.dumps(request_data).encode('utf-8') #mozliwe ze nieporzebne
# pub_socket.send(message_request) #protocol buffers


# def get_message(sub_socket,pub_socket,device_processid,critical_section_queue):
#     message = sub_socket.recv()
#     msg_response = message.decode('utf-8')
#     data = json.loads(msg_response)
    
#     if data["msg_type"] == "Replay":
#         processid_want_critical_section = critical_section_queue[0]
#         if processid_want_critical_section[0] == device_processid:
#             Producer(device_processid, critical_section_queue, 10, [], 0)
#             critical_section_queue.pop(0)

#     elif data["msg_type"] == "Request":
#         critical_section_queue.append(data["process"],data["time"]) # collections queue.Queue() #moze dodac
#         critical_section_queue.sort() #nie wiem w sumie moze to uproscic aby mniejsza zlozonosc obliczeniowa i mnoze zwykle sortowanie bez lambdy jka nie  bedzi edzialac  key=lambda x: x["time"]????
        
#     elif data["msg_type"] == "Release":
#         pass

#     elif data["msg_type"] == "ProcessEndWork":
#         pass


