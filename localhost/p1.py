from disturbed_monitor import DisturbedMonitor

def serialize_shared_data(buffer, in_index,out_index):
  return { "buffer": buffer, "in_index": in_index, "out_index": out_index }

def deserialize_shared_data(data):
  return data['buffer'], data['in_index'], data['out_index']

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