import zmq
import time
import json

class DisturbedMonitor:
    def __init__(self, input_device_process_id, input_all_active_processes, input_pub_socket, input_sub_socket, input_time_sleep):
        # ... (kod konstruktora pozostaje bez zmian) ...
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


    def get_message(self, shared_data):
        while True:
            # Ta zmienna będzie przechowywać wartość zwrotną z funkcji obsługi.
            # Jest przypisywana tylko wtedy, gdy proces uzyska dostęp do sekcji krytycznej.
            response_shared_data = None

            message = self.sub_socket.recv()
            msg_response = message.decode('utf-8')
            data = json.loads(msg_response)
            print("queue: ", self.critical_section_queue)

            if data["msg_type"] == "Replay" and data["process"] == self.device_process_id:
                response_shared_data = self.handle_replay_message(data, shared_data)

            elif data["msg_type"] == "Request":
                # Ten handler nie powinien zwracać wartości, ponieważ nie przyznaje dostępu do sekcji krytycznej.
                self.handle_request_message(data)

            elif data["msg_type"] == "Release":
                response_shared_data = self.handle_release_message(data, shared_data)

            elif data["msg_type"] == "ProcessEndWork":
                response_shared_data = self.remove_finished_process(shared_data, data)

            # Zwróć wartość tylko wtedy, gdy handler potwierdzi dostęp do sekcji krytycznej
            # i zwróci odpowiednie dane shared_data.
            if response_shared_data is not None:
                return response_shared_data

    def remove_finished_process(self, shared_data, data):
        print("Get process: ", data["From_process"], " has ended work, no more requests will be sent.")
        self.all_active_processes.discard(data["From_process"])
        self.replay_from_processes_left.discard(data["From_process"])

        if self.critical_section_queue:
            processid_want_critical_section = self.critical_section_queue[0]
            if processid_want_critical_section[0] == self.device_process_id and not self.replay_from_processes_left:
                self.critical_section_queue.pop(0)
                return shared_data
        # Zwróć None, jeśli ta wiadomość nie przyznaje dostępu temu procesowi
        return None


    def handle_replay_message(self, data, shared_data):
        self.replay_from_processes_left.discard(data["From_process"])
        print("Get Replay from process:", data["From_process"], " counter needed replay from processes: ", self.replay_from_processes_left)

        if self.critical_section_queue:
            processid_want_critical_section = self.critical_section_queue[0]
            if processid_want_critical_section[0] == self.device_process_id and not self.replay_from_processes_left:
                self.critical_section_queue.pop(0)
                return shared_data
        return None

    def handle_release_message(self, data, shared_data):
        # Należy użyć przychodzących danych shared_data z wiadomości o zwolnieniu.
        new_shared_data = data["shared_data"]
        # Bezpieczniej jest używać pop po sprawdzeniu, czy kolejka nie jest pusta
        if self.critical_section_queue:
            self.critical_section_queue.pop(0)

        print("Got release message from process:", data["From_process"], "Status: ", data["Status"], " Condition name: ", data["condition_name"])

        if data["Status"] == "wait" and self.critical_section_queue:
            processid_want_critical_section = self.critical_section_queue[0]
            if processid_want_critical_section[0] == self.device_process_id:
                 # Sprawdź odpowiedzi przed wejściem
                if not self.replay_from_processes_left:
                    self.critical_section_queue.pop(0)
                    return new_shared_data

        elif data["Status"] == "notify":
            if self.waiting_for_notify and data["condition_name"] == self.condintion_name:
                self.waiting_for_notify = False
                self.send_request_message()
            elif not self.waiting_for_notify and self.critical_section_queue:
                 processid_want_critical_section = self.critical_section_queue[0]
                 if processid_want_critical_section[0] == self.device_process_id and not self.replay_from_processes_left:
                     self.critical_section_queue.pop(0)
                     return new_shared_data
        return None


    def handle_request_message(self, data):
        print("Get request message from: ", data["process"], " process")
        self.critical_section_queue.append((data["process"], data["time"]))
        self.critical_section_queue.sort(key=lambda x: x[1])
        self.send_replay_message(data["process"])
        # Ta funkcja nie powinna niczego zwracać, ponieważ główna pętla w get_message będzie kontynuowana.

    def wait(self, shared_data, condition_name):
        self.condintion_name = condition_name
        self.waiting_for_notify = True
        self.send_release_message("wait", shared_data)
        return self.get_message(shared_data)

    def notify(self, shared_data, condition_name):
        self.condintion_name = condition_name
        self.send_release_message("notify", shared_data)
        # Notify nie czeka na odpowiedź, więc nie powinno wywoływać get_message.

    def acquire_lock(self, shared_data):
        if not self.all_active_processes:
            return shared_data
        self.send_request_message()
        return self.get_message(shared_data)

    # ... (Reszta metod send_* oraz join pozostaje bez zmian) ...
    def send_request_message(self):
        send_time = time.time()
        self.replay_from_processes_left = self.all_active_processes.copy()

        print("Requesting critical section at time:", send_time)

        self.critical_section_queue.append((self.device_process_id ,send_time))
        request_data = {"msg_type": "Request" , "process":  self.device_process_id, "time": time.time()}

        message_request = json.dumps(request_data).encode('utf-8')
        self.pub_socket.send(message_request)

    def send_replay_message(self,process_id):
        request_data = {"msg_type": "Replay","process":  process_id, "From_process": self.device_process_id}
        message_request = json.dumps(request_data).encode('utf-8')
        print("Sending replay message to process:", process_id)
        self.pub_socket.send(message_request)

    def send_release_message(self,status,shared_data):
        if status == "notify":
            request_data = {"msg_type": "Release","Status": "notify", "condition_name": self.condintion_name, "shared_data": shared_data, "From_process": self.device_process_id}
        else:
            request_data = {"msg_type": "Release","Status": "wait", "condition_name": self.condintion_name, "shared_data": shared_data,"From_process": self.device_process_id }

        print("Sending release message with status:", status, "to all processes, condition name:", self.condintion_name)
        message_request = json.dumps(request_data).encode('utf-8')
        self.pub_socket.send(message_request)

    def join(self):
        request_data = {"msg_type": "ProcessEndWork", "From_process": self.device_process_id}
        message_request = json.dumps(request_data).encode('utf-8')
        self.pub_socket.send(message_request)
        print("Process has ended work, no more requests will be sent.")