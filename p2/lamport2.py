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
        self.sub_socket.connect(f"tcp://172.17.0.5:5557")
        self.sub_socket.connect(f"tcp://172.17.0.6:5559")
        self.sub_socket.connect(f"tcp://172.17.0.7:5558")
        self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.other_processes_count = 1
        self.get_replay = False
        self.is_waiting = False
        self.condintion_name = ""
        self.replay_count_needed = 0
        time.sleep(4)  # Allow some time for the subscriber to connect
    
    def get_message(self,buffer,in_index,out_index):  
        while True:
            message = self.sub_socket.recv()
            msg_response = message.decode('utf-8')
            data = json.loads(msg_response)
            print("queue: ", self.critical_section_queue)

            
            if data["msg_type"] == "Replay" and data["process"] == self.device_process_id:
                self.replay_count_needed -= 1

                print("Get Replay from process:", data["From_process"], " coutner needed replay from procees: ", self.replay_count_needed)

                processid_want_critical_section = self.critical_section_queue[0]
               
                if processid_want_critical_section[0] == self.device_process_id and self.replay_count_needed == 0:
                    self.critical_section_queue.pop(0)
                    return buffer, in_index, out_index  # Return the buffer and indices after entering critical section    
                            
            elif data["msg_type"] == "Request":
                print("Get request message from: ",data["process"]," process")
                self.critical_section_queue.append((data["process"],data["time"])) # collections queue.Queue() #moze dodac
                self.critical_section_queue.sort(key=lambda x: x[1]) #nie wiem w sumie moze to uproscic aby mniejsza zlozonosc obliczeniowa i mnoze zwykle sortowanie bez lambdy jka nie  bedzi edzialac  key=lambda x: x["time"]????
                # self.replay_count_needed = self.other_processes_count #TODO Nie wiem czy to potrzebne
                self.send_replay_message(data["process"])  # Send replay message to the requesting process

            elif data["msg_type"] == "Release":
                
                buffer = data["buffer"]
                in_index = data["in_index"]
                out_index = data["out_index"]
                self.critical_section_queue.pop(0)
                print("Got release message from process:", data["From_process"], "Status: ", data["Status"], " Condition name: ", data["condition_name"])


                if data["Status"] == "wait" and len(self.critical_section_queue) > 0:
                    processid_want_critical_section = self.critical_section_queue[0]

                    if processid_want_critical_section[0] == self.device_process_id:

                        self.critical_section_queue.pop(0)
                        return buffer, in_index, out_index  # Return the buffer and indices after entering critical section   
                
                elif data["Status"] == "notify":
                    if self.is_waiting and data["condition_name"] == self.condintion_name:     #TODOCondition_nmame_waiting?????   
                        self.is_waiting = False
                        self.send_request_message()
                    elif not self.is_waiting and len(self.critical_section_queue) > 0:
                        processid_want_critical_section = self.critical_section_queue[0]

                        if processid_want_critical_section[0] == self.device_process_id and self.replay_count_needed == 0:
                            self.critical_section_queue.pop(0)
                            return buffer, in_index, out_index

            elif data["msg_type"] == "ProcessEndWork":
                print("Get process: ",data["From_process"] , " has ended work, no more requests will be sent.")

                self.other_processes_count -= 1

    def wait(self,buffer,in_index,out_index,condition_name): #TODO tutaj bym tabele dodal a teraz zmienne
        self.condintion_name = condition_name
        self.is_waiting = False
        self.send_release_message("wait",buffer,in_index,out_index)  # Release message with "no" values_changed
        return self.get_message(buffer,in_index,out_index)

    def notify(self, buffer,in_index,out_index,condition_name):
        if self.other_processes_count == 0:
            return buffer, in_index, out_index
         
        self.condintion_name = condition_name
        self.send_release_message("notify", buffer,in_index,out_index)  # Release message with "yes" value
        # return self.get_message(buffer,in_index,out_index) # TODO nie wiem to moze byc niebezpieczne ale chyba nie

    def enter_crirical_section(self,buffer,in_index,out_index):
        if self.other_processes_count == 0:
            return buffer, in_index, out_index
        
        self.send_request_message()
        return self.get_message(buffer,in_index,out_index)

    def send_request_message(self):
        send_time = time.time()
        self.replay_count_needed = self.other_processes_count
        print("Requesting critical section at time:", send_time)
        self.critical_section_queue.append((self.device_process_id ,send_time))  # Append the process ID and current time to the queue
        request_data = {"msg_type": "Request" , "process":  self.device_process_id, "time": time.time()}
        message_request = json.dumps(request_data).encode('utf-8') #mozliwe ze nieporzebne
        self.pub_socket.send(message_request) #protocol buffers
    
    def send_replay_message(self,process_id):
        request_data = {"msg_type": "Replay","process":  process_id,"From_process": self.device_process_id} #do debuggingu usunac na koniecśś
        message_request = json.dumps(request_data).encode('utf-8') #mozliwe ze nieporzebne
        print("Sending replay message to process:", process_id)

        self.pub_socket.send(message_request) #protocol buffers //TODO rozroznic sockety???? TODO chyba to zrobione

    def send_release_message(self,status,buffer,in_index,out_index):
        
        if status == "notify":
            request_data = {"msg_type": "Release","Status": "notify", "condition_name": self.condintion_name, "buffer": buffer, "in_index": in_index, "out_index": out_index,"From_process": self.device_process_id}
        else:
            request_data = {"msg_type": "Release","Status": "wait", "condition_name": self.condintion_name, "buffer": buffer, "in_index": in_index, "out_index": out_index,"From_process": self.device_process_id } #TODO enum  status??

        message_request = json.dumps(request_data).encode('utf-8') #mozliwe ze nieporzebne
        print("Sending release message with status: ", status, " to all processes, condition name: ", self.condintion_name)
        self.pub_socket.send(message_request) #protocol buffers //TODO rozroznic sockety????
    
    def send_end_of_the_work_message(self):
        request_data = {"msg_type": "ProcessEndWork","From_process": self.device_process_id}
        message_request = json.dumps(request_data).encode('utf-8')
        self.pub_socket.send(message_request) 
        print("Process has ended work, no more requests will be sent.")
       

CAPACITY = 10
buffer = [-1 for _ in range(CAPACITY)]
in_index = 0
out_index = 0

def Producer(DisturbedMonitor,in_index, buffer, out_index):
    global CAPACITY
    items_produced = 0
    counter = 0

    while items_produced < 20:
        buffer,in_index,out_index = DisturbedMonitor.enter_crirical_section(buffer,in_index,out_index) #TODO to mozna w sumie usunac ale nie trzeba nazwa aquire lock
        while (in_index + 1) % CAPACITY == out_index:
            buffer,in_index,out_index = DisturbedMonitor.wait(buffer,in_index,out_index,"empty")  # TODO MA BYC TABLICA ZWYKLA

        counter += 1
        buffer[in_index] = counter
        print("||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||")
        print("Producer produced:", counter)
        print("||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||")

        in_index = (in_index + 1) % CAPACITY
        # time.sleep(1)

        DisturbedMonitor.notify(buffer,in_index,out_index,"not_empty")  # Signal to consumers  #TODO tutaj zmienna not_full i full nie musi byc w pelni transparentne btw

        items_produced += 1
    DisturbedMonitor.send_end_of_the_work_message() #to jest taki join()

CAPACITY = 10
buffer = [-1 for _ in range(CAPACITY)]
in_index = 0

DisturbedMonitor = DisturbedMonitor()
Producer(DisturbedMonitor,in_index, buffer, out_index)  # Initialize producer with 0 items produced, empty buffer, and in_index at 0

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


