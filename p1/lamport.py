# p2p_node.py #TODO co to???
import zmq
import time
import json

class DisturbedMonitor:
    def __init__(self, input_device_process_id,input_all_active_processes, input_pub_socket, input_sub_socket,input_time_sleep): #Dane podstawowe
        self.critical_section_queue = []
        self.device_process_id = input_device_process_id
        self.all_active_processes = input_all_active_processes  
        context = zmq.Context()
        self.pub_socket = context.socket(zmq.PUB)
        self.pub_socket.bind(input_pub_socket)
        self.sub_socket = context.socket(zmq.SUB)
   
        for sub_socket in input_sub_socket:
            self.sub_socket.connect(sub_socket)
        
        self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.replay_from_processes_left = self.all_active_processes.copy()
        self.waiting_for_notify = False
        self.condintion_name = ""
        time.sleep(input_time_sleep)

    def get_message(self,shared_data):
        while True:
            response_shared_data = {}

            message = self.sub_socket.recv()
            msg_response = message.decode('utf-8')
            data = json.loads(msg_response)
            print("queue: ", self.critical_section_queue)
            
            if data["msg_type"] == "Replay" and data["process"] == self.device_process_id:
                response_shared_data = self.handle_replay_message(data, shared_data)                  
                             
            elif data["msg_type"] == "Request":
                response_shared_data = self.handle_request_message(data)

            elif data["msg_type"] == "Release":   
                response_shared_data = self.handle_release_message(data, shared_data)
                                            
            elif data["msg_type"] == "ProcessEndWork":
                response_shared_data = self.remove_finished_process(shared_data, data)
            
            if response_shared_data is not None:
                return response_shared_data
            

    def remove_finished_process(self, shared_data, data):
        print("Get process: ",data["From_process"] , " has ended work, no more requests will be sent.")
        self.all_active_processes.discard(data["From_process"])
        self.replay_from_processes_left.discard(data["From_process"])
        processid_want_critical_section = self.critical_section_queue[0]
              
        if processid_want_critical_section[0] == self.device_process_id and not self.replay_from_processes_left:
            self.critical_section_queue.pop(0)
            return shared_data
        
    def handle_replay_message(self, data, shared_data):
        # self.replay_count_needed -= 1
        self.replay_from_processes_left.discard(data["From_process"])
        print("Get Replay from process:", data["From_process"], " counter needed replay from processes: ", self.replay_from_processes_left)

        processid_want_critical_section = self.critical_section_queue[0]

        if processid_want_critical_section[0] == self.device_process_id and not self.replay_from_processes_left:
            self.critical_section_queue.pop(0)
            return shared_data  # Return the buffer and indices after entering critical section
        
    def handle_release_message(self, data, shared_data):
        shared_data = data["shared_data"]
        self.critical_section_queue.pop(0)
        print("Got release message from process:", data["From_process"], "Status: ", data["Status"], " Condition name: ", data["condition_name"], "replay messages left: ", self.replay_from_processes_left)

        if data["Status"] == "wait" and len(self.critical_section_queue) > 0:
            processid_want_critical_section = self.critical_section_queue[0]

            if processid_want_critical_section[0] == self.device_process_id:
                self.critical_section_queue.pop(0)
                return shared_data  # Return the buffer and indices after entering critical section   

        elif data["Status"] == "notify":
            if self.waiting_for_notify and data["condition_name"] == self.condintion_name:        
                self.waiting_for_notify = False                        
                self.send_request_message()

            elif not self.waiting_for_notify and not (len(self.critical_section_queue) == 0):
                processid_want_critical_section = self.critical_section_queue[0]
                if processid_want_critical_section[0] == self.device_process_id and not self.replay_from_processes_left:
                    self.critical_section_queue.pop(0)
                    return shared_data
        
    def handle_request_message(self, data):
        print("Get request message from: ",data["process"]," process")
        self.critical_section_queue.append((data["process"],data["time"])) # collections queue.Queue() #moze dodac
        self.critical_section_queue.sort(key=lambda x: x[1]) #nie wiem w sumie moze to uproscic aby mniejsza zlozonosc obliczeniowa i mnoze zwykle sortowanie bez lambdy jka nie  bedzi edzialac  key=lambda x: x["time"]????
        # self.replay_count_needed = self.other_processes_count #TODO to moze jest wazne
        self.send_replay_message(data["process"])  # Send replay message to the requesting process                    

    def wait(self,shared_data,condition_name): #TODO tutaj bym tabele dodal a teraz zmienne
        self.condintion_name = condition_name
        self.waiting_for_notify = True
        self.send_release_message("wait",shared_data)  # Release message with "no" values_changed
        return self.get_message(shared_data)

    def notify(self,shared_data,condition_name):
        # if self.other_processes_count == 0:
        # if self.replay_from_processes_left == {}: # TODO ????? nie powinno chyba tak to wygladac
        #     return buffer, in_index, out_index
        
        self.condintion_name = condition_name
        self.send_release_message("notify", shared_data)  # Release message with "yes" value
        # return self.get_message(buffer,in_index,out_index)

    def acquire_lock(self,shared_data): #aquirelock
        # if self.other_processes_count == 0:
        if not self.all_active_processes:
            return shared_data
        self.send_request_message()
        return self.get_message(shared_data)

    def send_request_message(self):
        send_time = time.time()
        # self.replay_count_needed = self.other_processes_count#TODO OOOOO
        self.replay_from_processes_left = self.all_active_processes.copy()

        print("Requesting critical section at time:", send_time)

        self.critical_section_queue.append((self.device_process_id ,send_time)) 
        request_data = {"msg_type": "Request" , "process":  self.device_process_id, "time": time.time()}

        message_request = json.dumps(request_data).encode('utf-8') #mozliwe ze nieporzebne
        self.pub_socket.send(message_request) #protocol buffers
    
    def send_replay_message(self,process_id):
        request_data = {"msg_type": "Replay","process":  process_id, "From_process": self.device_process_id}
        message_request = json.dumps(request_data).encode('utf-8') #mozliwe ze nieporzebne
        print("Sending replay message to process:", process_id)

        self.pub_socket.send(message_request) #protocol buffers //TODO rozroznic sockety????

    def send_release_message(self,status,shared_data):        
        if status == "notify":
            request_data = {"msg_type": "Release","Status": "notify", "condition_name": self.condintion_name, "shared_data": shared_data, "From_process": self.device_process_id} #TODO enum  status??
        else:
            request_data = {"msg_type": "Release","Status": "wait", "condition_name": self.condintion_name, "shared_data": shared_data,"From_process": self.device_process_id } #TODO enum  status??

        print("Sending release message with status:", status, "to all processes, condition name:", self.condintion_name)

        message_request = json.dumps(request_data).encode('utf-8')
        self.pub_socket.send(message_request) #protocol buffers //TODO rozroznic sockety????
    
    def join(self):
        request_data = {"msg_type": "ProcessEndWork", "From_process": self.device_process_id} #TODO form proces usunac
        message_request = json.dumps(request_data).encode('utf-8')
        self.pub_socket.send(message_request)
        print("Process has ended work, no more requests will be sent.")
               


def serialize_shared_data(buffer, in_index,out_index):
  return {
      "buffer": buffer,
      "in_index": in_index,
      "out_index": out_index
  }

def deserialize_shared_data(data):
  buffer = data.get('buffer')
  in_index = data.get('in_index') #TODOChange this
  out_index = data.get('out_index')
  return buffer, in_index, out_index

def Consumer(DisturbedMonitor,in_index, buffer, out_index):
    global CAPACITY
    items_produced = 0
    items_consumed = 0
    dict_data = {}

    while items_consumed < 20:
        buffer,in_index,out_index = deserialize_shared_data(DisturbedMonitor.acquire_lock(serialize_shared_data(buffer, in_index,out_index))) #TODO to mozna w sumie usunac ale nie trzeba
        
        while in_index == out_index:
            buffer,in_index,out_index = deserialize_shared_data(DisturbedMonitor.wait(serialize_shared_data(buffer, in_index,out_index),"not_empty"))
  
        item = buffer[out_index]
        print("||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||")
        print("Consumer consumed item:", item)
        print("||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||")

        out_index = (out_index + 1) % CAPACITY

        DisturbedMonitor.notify(serialize_shared_data(buffer, in_index,out_index),"empty")  # Signal to consumers  #TODO tutaj zmienna not_full i full nie musi byc w pelni transparentne btw
        items_consumed += 1 

CAPACITY = 10
buffer = [-1 for _ in range(CAPACITY)]
in_index = 0
out_index = 0
input_device_process_id = "P1"
input_all_active_processes = {"P2"}
input_pub_socket = "tcp://*:5557"
input_sub_socket = ["tcp://172.17.0.2:5556","tcp://172.17.0.5:5558","tcp://172.17.0.6:5559"]
input_time_sleep = 4

DisturbedMonitor = DisturbedMonitor(input_device_process_id, input_all_active_processes, input_pub_socket, input_sub_socket, input_time_sleep)  # Initialize DisturbedMonitor with given parameters
Consumer(DisturbedMonitor,in_index, buffer, out_index)  # Initialize producer with 0 items produced, empty buffer, and in_index at 0
DisturbedMonitor.join()


