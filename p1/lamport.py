# p2p_node.py
import zmq
import threading
import time
import sys
import json

class DisturbedMonitor():
    def __init__(self): #Dane podstawowe
        self.critical_section_queue = []
        self.device_process_id = "P1"
        context = zmq.Context()
        self.pub_socket = context.socket(zmq.PUB)
        pub_port = 5557
        self.pub_socket.bind(f"tcp://*:{pub_port}")
        self.sub_socket = context.socket(zmq.SUB)
        port = 5556
        self.sub_socket.connect(f"tcp://172.17.0.2:5556")
        self.sub_socket.connect(f"tcp://172.17.0.5:5558")
        self.sub_socket.connect(f"tcp://172.17.0.6:5559")
        self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        # self.other_processes_count = 1
        self.all_active_processes = {"P2"}  # List of all processes
        self.replay_from_processes_left = {"P2"}  
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

                # self.replay_count_needed -= 1
                self.replay_from_processes_left.discard(data["From_process"])
                print("Get Replay from process:", data["From_process"], " coutner needed replay from procees: ", self.replay_from_processes_left)

                processid_want_critical_section = self.critical_section_queue[0]
              
                if processid_want_critical_section[0] == self.device_process_id and not self.replay_from_processes_left:
                    self.critical_section_queue.pop(0)
                    return buffer, in_index, out_index  # Return the buffer and indices after entering critical section    
                             
            elif data["msg_type"] == "Request":
                print("Get request message from: ",data["process"]," process")

                self.critical_section_queue.append((data["process"],data["time"])) # collections queue.Queue() #moze dodac
                self.critical_section_queue.sort(key=lambda x: x[1]) #nie wiem w sumie moze to uproscic aby mniejsza zlozonosc obliczeniowa i mnoze zwykle sortowanie bez lambdy jka nie  bedzi edzialac  key=lambda x: x["time"]????
                # self.replay_count_needed = self.other_processes_count #TODO to moze jest wazne
                self.replay_message(data["process"])  # Send replay message to the requesting process

            elif data["msg_type"] == "Release":
                
                buffer = data["buffer"]
                in_index = data["in_index"]
                out_index = data["out_index"]
                self.critical_section_queue.pop(0)
                print("Got release message from process:", data["From_process"], "Status: ", data["Status"], " Condition name: ", data["condition_name"], "replay messagesd left: ", self.replay_from_processes_left)

                if data["Status"] == "wait" and len(self.critical_section_queue) > 0:
                    processid_want_critical_section = self.critical_section_queue[0]

                    if processid_want_critical_section[0] == self.device_process_id:
                        self.critical_section_queue.pop(0) #TODO czmemu to usunalem nie rozumiem
                        return buffer, in_index, out_index  # Return the buffer and indices after entering critical section   
                
                elif data["Status"] == "notify":
                    if self.is_waiting and data["condition_name"] == self.condintion_name:        
                        self.is_waiting = False                        
                        self.request_message()

                    elif not self.is_waiting and not (len(self.critical_section_queue) == 0): #to jeszcze sprawdizc czy tak dziala?
                        if self.replay_from_processes_left == {}:
                            print("Cemu tonie dziala?")
                        
                        processid_want_critical_section = self.critical_section_queue[0]
                        if processid_want_critical_section[0] == self.device_process_id and not self.replay_from_processes_left:
                            print("Cemu tonie dziala?")
                            self.critical_section_queue.pop(0)
                            return buffer, in_index, out_index
                        
            elif data["msg_type"] == "ProcessEndWork":
                print("Get process: ",data["From_process"] , " has ended work, no more requests will be sent.")
                self.all_active_processes.discard(data["From_process"])
                self.replay_from_processes_left.discard(data["From_process"])
                processid_want_critical_section = self.critical_section_queue[0]
              
                if processid_want_critical_section[0] == self.device_process_id and not self.replay_from_processes_left:
                    self.critical_section_queue.pop(0)
                    return buffer, in_index, out_index

    def wait(self,buffer,in_index,out_index,condition_name): #TODO tutaj bym tabele dodal a teraz zmienne
        self.condintion_name = condition_name
        self.is_waiting = True
        self.release_message("wait",buffer,in_index,out_index)  # Release message with "no" values_changed
        return self.get_message(buffer,in_index,out_index)

    def notify(self, buffer,in_index,out_index,condition_name):
        # if self.other_processes_count == 0:
        # if self.replay_from_processes_left == {}: # TODO ????? nie powinno chyba tak to wygladac
        #     return buffer, in_index, out_index
        
        self.condintion_name = condition_name
        self.release_message("notify", buffer,in_index,out_index)  # Release message with "yes" value
        # return self.get_message(buffer,in_index,out_index)

    def enter_crirical_section(self,buffer,in_index,out_index): #aquirelock
        # if self.other_processes_count == 0:
        if self.all_active_processes == {}:
            return buffer, in_index, out_index
        self.request_message()
        return self.get_message(buffer,in_index,out_index)

    def request_message(self):
        send_time = time.time()
        # self.replay_count_needed = self.other_processes_count#TODO OOOOO
        self.replay_from_processes_left = self.all_active_processes.copy()

        print("Requesting critical section at time:", send_time)

        self.critical_section_queue.append((self.device_process_id ,send_time)) 
        request_data = {"msg_type": "Request" , "process":  self.device_process_id, "time": time.time()}

        message_request = json.dumps(request_data).encode('utf-8') #mozliwe ze nieporzebne
        self.pub_socket.send(message_request) #protocol buffers
    
    def replay_message(self,process_id):
        request_data = {"msg_type": "Replay","process":  process_id, "From_process": self.device_process_id}
        message_request = json.dumps(request_data).encode('utf-8') #mozliwe ze nieporzebne
        print("Sending replay message to process:", process_id)

        self.pub_socket.send(message_request) #protocol buffers //TODO rozroznic sockety????

    def release_message(self,status,buffer,in_index,out_index):
        
        if status == "notify":
            request_data = {"msg_type": "Release","Status": "notify", "condition_name": self.condintion_name, "buffer": buffer, "in_index": in_index, "out_index": out_index, "From_process": self.device_process_id} #TODO enum  status??
        else:
            request_data = {"msg_type": "Release","Status": "wait", "condition_name": self.condintion_name, "buffer": buffer, "in_index": in_index, "out_index": out_index,"From_process": self.device_process_id } #TODO enum  status??

        print("Sending release message with status:", status, "to all processes, condition name:", self.condintion_name)

        message_request = json.dumps(request_data).encode('utf-8') #mozliwe ze nieporzebne
        self.pub_socket.send(message_request) #protocol buffers //TODO rozroznic sockety????
    
    def join(self):
        request_data = {"msg_type": "ProcessEndWork", "From_process": self.device_process_id} #TODO form proces usunac
        message_request = json.dumps(request_data).encode('utf-8')
        self.pub_socket.send(message_request) 
        print("Process has ended work, no more requests will be sent.")  
           

CAPACITY = 10
buffer = [-1 for _ in range(CAPACITY)]
in_index = 0
out_index = 0

def Consumer(DisturbedMonitor,in_index, buffer, out_index):
    global CAPACITY
    items_produced = 0
    items_consumed = 0

    while items_consumed < 20:
        buffer,in_index,out_index = DisturbedMonitor.enter_crirical_section(buffer,in_index,out_index) #TODO to mozna w sumie usunac ale nie trzeba
        while in_index == out_index:
            buffer,in_index,out_index = DisturbedMonitor.wait(buffer,in_index,out_index,"not_empty")  # TODO MA BYC TABLICA ZWYKLA

        item = buffer[out_index]
        print("||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||")
        print("Consumer consumed item:", item)
        print("||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||")

        out_index = (out_index + 1) % CAPACITY
        # time.sleep(0.7) 

        DisturbedMonitor.notify(buffer,in_index,out_index,"empty")  # Signal to consumers  #TODO tutaj zmienna not_full i full nie musi byc w pelni transparentne btw
        items_consumed += 1

    # DisturbedMonitor.end_of_the_work()

CAPACITY = 10
buffer = [-1 for _ in range(CAPACITY)]
in_index = 0

DisturbedMonitor = DisturbedMonitor()
Consumer(DisturbedMonitor,in_index, buffer, out_index)  # Initialize producer with 0 items produced, empty buffer, and in_index at 0
DisturbedMonitor.join()


