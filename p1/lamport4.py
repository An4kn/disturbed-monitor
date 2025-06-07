# p2p_node.py (wersja poprawiona z Enum)
import zmq
import time
import json
from enum import Enum

class DisturbedMonitor:
    def __init__(self, input_device_process_id,input_all_active_processes, input_pub_socket, input_sub_socket,input_time_sleep):
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
            response_shared_data = None
            message = self.sub_socket.recv()
            msg_response = message.decode('utf-8')
            data = json.loads(msg_response)
            print("queue: ", self.critical_section_queue)

            # --- POPRAWKA: Jawna konwersja string -> Enum ---
            
            msg_type = MessageType(data["msg_type"])
            

            if msg_type == MessageType.REPLAY and data["process"] == self.device_process_id:
                response_shared_data = self.handle_replay_message(data, shared_data)
            elif msg_type == MessageType.REQUEST:
                response_shared_data = self.handle_request_message(data)
            elif msg_type == MessageType.RELEASE:
                response_shared_data = self.handle_release_message(data, shared_data)
            elif msg_type == MessageType.SHUTDOWN:
                response_shared_data = self.remove_finished_process(shared_data, data)

            if response_shared_data is not None:
                return response_shared_data

    def remove_finished_process(self, shared_data, data):
        print("Get process: ",data["From_process"] , " has ended work, no more requests will be sent.")
        self.all_active_processes.discard(data["From_process"])
        self.replay_from_processes_left.discard(data["From_process"])
        
        if not self.critical_section_queue:
            return None

        processid_want_critical_section = self.critical_section_queue[0]
        if processid_want_critical_section[0] == self.device_process_id and not self.replay_from_processes_left:
            self.critical_section_queue.pop(0)
            return shared_data
        return None

    def handle_replay_message(self, data, shared_data):
        self.replay_from_processes_left.discard(data["From_process"])
        print("Get Replay from process:", data["From_process"], " counter needed replay from processes: ", self.replay_from_processes_left)

        if not self.critical_section_queue:
            return None

        processid_want_critical_section = self.critical_section_queue[0]
        if processid_want_critical_section[0] == self.device_process_id and not self.replay_from_processes_left:
            self.critical_section_queue.pop(0)
            return shared_data
        return None

    def handle_release_message(self, data, shared_data):
        shared_data.update(data["shared_data"]) # Aktualizujemy stan, ale nie podmieniamy referencji
                
        self.critical_section_queue.pop(0)
        
        status = ReleaseStatus(data["Status"])
       

        print("Got release message from process:", data["From_process"], "Status: ", status, " Condition name: ", data["condition_name"], "replay messages left: ", self.replay_from_processes_left)

        if status == ReleaseStatus.NOTIFY:
            if self.waiting_for_notify and data["condition_name"] == self.condintion_name:
                self.waiting_for_notify = False
                self.send_request_message()
                return None # Po wysłaniu prośby wracamy do nasłuchiwania

        if self.critical_section_queue:
            processid_want_critical_section = self.critical_section_queue[0]
            if processid_want_critical_section[0] == self.device_process_id and not self.replay_from_processes_left:
                self.critical_section_queue.pop(0)
                return shared_data
        
        return None

    def handle_request_message(self, data):
        print("Get request message from: ",data["process"]," process")
        self.critical_section_queue.append((data["process"],data["time"]))
        self.critical_section_queue.sort(key=lambda x: x[1])
        self.send_replay_message(data["process"])
        return None

    def wait(self,shared_data,condition_name):
        self.condintion_name = condition_name
        self.waiting_for_notify = True
        self.send_release_message(ReleaseStatus.WAIT,shared_data)
        return self.get_message(shared_data)

    def notify(self,shared_data,condition_name):
        self.condintion_name = condition_name
        self.send_release_message(ReleaseStatus.NOTIFY, shared_data)
    
    def acquire_lock(self,shared_data):
        if not self.all_active_processes:
            return shared_data
        self.send_request_message()
        return self.get_message(shared_data)

    def send_request_message(self):
        send_time = time.time()
        self.replay_from_processes_left = self.all_active_processes.copy()
        print("Requesting critical section at time:", send_time)
        self.critical_section_queue.append((self.device_process_id ,send_time))
        request_data = {"msg_type": MessageType.REQUEST.value, "process":  self.device_process_id, "time": time.time()}
        message_request = json.dumps(request_data).encode('utf-8')
        self.pub_socket.send(message_request)

    def send_replay_message(self,replay_process_id):
        request_data = {"msg_type": MessageType.REPLAY.value,"process":  replay_process_id, "From_process": self.device_process_id}
        message_request = json.dumps(request_data).encode('utf-8')
        print("Sending replay message to process:", replay_process_id)
        self.pub_socket.send(message_request)

    def send_release_message(self,status,shared_data):
        request_data = {
            "msg_type": MessageType.RELEASE.value,
            "Status": status.value,
            "condition_name": self.condintion_name,
            "shared_data": shared_data,
            "From_process": self.device_process_id
        }
        print("Sending release message with status:", status, "to all processes, condition name:", self.condintion_name)
        message_request = json.dumps(request_data).encode('utf-8')
        self.pub_socket.send(message_request)

    def join(self):
        request_data = {"msg_type": MessageType.SHUTDOWN.value, "From_process": self.device_process_id}
        message_request = json.dumps(request_data).encode('utf-8')
        self.pub_socket.send(message_request)
        print("Process has ended work, no more requests will be sent.")

class MessageType(str, Enum):
    REQUEST = "Request"
    REPLAY = "Replay"
    RELEASE = "Release"
    SHUTDOWN = "Shutdown"

class ReleaseStatus(str, Enum):
    WAIT = "wait"
    NOTIFY = "notify"

def serialize_shared_data(buffer, in_index,out_index):
  return { "buffer": buffer, "in_index": in_index, "out_index": out_index }

def deserialize_shared_data(data):
  buffer = data.get('buffer')
  in_index = data.get('in_index')
  out_index = data.get('out_index')
  return buffer, in_index, out_index

def Consumer(disturbed_monitor, in_index, buffer, out_index):
    global CAPACITY
    items_consumed = 0
    while items_consumed < 20:
        shared_data = disturbed_monitor.acquire_lock(serialize_shared_data(buffer, in_index,out_index))
        buffer, in_index, out_index = deserialize_shared_data(shared_data)

        while in_index == out_index:
            shared_data = disturbed_monitor.wait(serialize_shared_data(buffer, in_index,out_index),"not_empty")
            buffer, in_index, out_index = deserialize_shared_data(shared_data)

        item = buffer[out_index]
        print("||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||")
        print("Consumer consumed item:", item)
        print("||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||")
        out_index = (out_index + 1) % CAPACITY
        disturbed_monitor.notify(serialize_shared_data(buffer, in_index,out_index),"empty")
        items_consumed += 1

# --- Reszta kodu bez zmian ---
CAPACITY = 10
buffer = [-1 for _ in range(CAPACITY)]
in_index = 0
out_index = 0
input_device_process_id = "P1"
input_all_active_processes = {"P2"}
input_pub_socket = "tcp://*:5557"
input_sub_socket = ["tcp://172.17.0.2:5556","tcp://172.17.0.5:5558","tcp://172.17.0.6:5559"]
input_time_sleep = 4

DisturbedMonitor_instance = DisturbedMonitor(input_device_process_id, input_all_active_processes, input_pub_socket, input_sub_socket, input_time_sleep)
Consumer(DisturbedMonitor_instance,in_index, buffer, out_index)
DisturbedMonitor_instance.join()