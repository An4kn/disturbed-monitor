import zmq
import time
import json
from enum import Enum

class DisturbedMonitor:
    def __init__(self, input_device_process_id, input_all_active_processes, input_pub_socket, input_sub_socket, input_time_sleep):
        self._shared_state_keys = set()
        self._updated_fields = set()
        self._critical_section_queue = []
        self.device_process_id = input_device_process_id
        self._all_active_processes = input_all_active_processes
        
        context = zmq.Context()
        self.pub_socket = context.socket(zmq.PUB)
        self.pub_socket.bind(input_pub_socket)
        
        self.sub_socket = context.socket(zmq.SUB)
        for sub_socket_addr in input_sub_socket:
            self.sub_socket.connect(sub_socket_addr)

        self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self._replay_from_processes_left = self._all_active_processes.copy()
        self._waiting_for_notify = False
        self._condition_name = ""
        
        time.sleep(input_time_sleep)
        self._updated_fields.clear()

    def get_message(self):
        while True:
            should_return = False
            message = self.sub_socket.recv()
            msg_response = message.decode('utf-8')
            data = json.loads(msg_response)
            
            msg_type = MessageType(data["msg_type"])
            
            if msg_type == MessageType.REPLAY and data["process"] == self.device_process_id:
                should_return = self.handle_replay_message(data)
            elif msg_type == MessageType.REQUEST:
                self.handle_request_message(data)
            elif msg_type == MessageType.RELEASE:
                should_return = self.handle_release_message(data)
            elif msg_type == MessageType.SHUTDOWN:
                should_return = self.remove_finished_process(data)

            if should_return:
                return

    def remove_finished_process(self, data):
        finished_proc = data["from_process"]
        self._all_active_processes.discard(finished_proc)
        self._replay_from_processes_left.discard(finished_proc)
        
        if self._critical_section_queue and self._critical_section_queue[0][0] == self.device_process_id and not self._replay_from_processes_left:
            self._critical_section_queue.pop(0)
            return True
        return False

    def handle_replay_message(self, data):
        self._replay_from_processes_left.discard(data["from_process"])

        if self._critical_section_queue and self._critical_section_queue[0][0] == self.device_process_id and not self._replay_from_processes_left:
            self._critical_section_queue.pop(0)
            return True
        return False

    def handle_release_message(self, data):
        self.deserialize_and_update_state(data["shared_data"])
        if self._critical_section_queue:
            self._critical_section_queue.pop(0)
        
        status = ReleaseStatus(data["Status"])
        if status == ReleaseStatus.NOTIFY:
            condition_name = data.get("condition_name")
            if self._waiting_for_notify and condition_name == self._condition_name:
                self._waiting_for_notify = False
                self.send_request_message()

        if self._critical_section_queue and self._critical_section_queue[0][0] == self.device_process_id and not self._replay_from_processes_left:
            self._critical_section_queue.pop(0)
            return True
        return False

    def handle_request_message(self, data):
        self._critical_section_queue.append((data["process"], data["time"]))
        self._critical_section_queue.sort(key=lambda x: (x[1], x[0]))
        self.send_replay_message(data["process"])

    def wait(self, condition_name):
        self._condition_name = condition_name
        self._waiting_for_notify = True
        self.send_release_message(ReleaseStatus.WAIT)
        self.get_message()

    def notify(self, condition_name):
        self._condition_name = condition_name
        self.send_release_message(ReleaseStatus.NOTIFY)
    
    def acquire_lock(self):
        if not self._all_active_processes:
            return
        self.send_request_message()
        self.get_message()

    def send_request_message(self):
        send_time = time.time()
        self._replay_from_processes_left = self._all_active_processes.copy()
        self._critical_section_queue.append((self.device_process_id, send_time))
        self._critical_section_queue.sort(key=lambda x: (x[1], x[0]))
        
        request_data = {"msg_type": MessageType.REQUEST.value, "process": self.device_process_id, "time": send_time}
        self.pub_socket.send_json(request_data)

    def send_replay_message(self, replay_process_id):
        request_data = {"msg_type": MessageType.REPLAY.value, "process": replay_process_id, "from_process": self.device_process_id}
        self.pub_socket.send_json(request_data)

    def send_release_message(self, status):
        fields_to_send = list(self._updated_fields)
        
        request_data = {
            "msg_type": MessageType.RELEASE.value,
            "Status": status.value,
            "condition_name": self._condition_name,
            "shared_data": self.serialize_state(fields=fields_to_send),
            "from_process": self.device_process_id
        }
        self.pub_socket.send_json(request_data)
        self._updated_fields.clear()

    def join(self):
        request_data = {"msg_type": MessageType.SHUTDOWN.value, "from_process": self.device_process_id}
        self.pub_socket.send_json(request_data)
        time.sleep(2)

    def serialize_state(self, fields=None):
        state = {}
        keys_to_serialize = fields if fields is not None else self._shared_state_keys
        for key in keys_to_serialize:
            if hasattr(self, key):
                state[key] = getattr(self, key)
        return state

    def deserialize_and_update_state(self, state_data_dict):
        if not state_data_dict: return
        for key, value in state_data_dict.items():
            super().__setattr__(key, value)
            
    def set_field_updated(self, field_name):
        if field_name in self._shared_state_keys:
            self._updated_fields.add(field_name)

    def __setattr__(self, key, value):
        if hasattr(self, '_shared_state_keys') and key in self._shared_state_keys:
            self._updated_fields.add(key)
        super().__setattr__(key, value)

class MessageType(str, Enum):
    REQUEST = "Request"
    REPLAY = "Replay"
    RELEASE = "Release"
    SHUTDOWN = "Shutdown"

class ReleaseStatus(str, Enum):
    WAIT = "wait"
    NOTIFY = "notify"