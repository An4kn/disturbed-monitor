from disturbed_monitor import DisturbedMonitor

def serialize_shared_data(buffer, in_index,out_index):
  return { "buffer": buffer, "in_index": in_index, "out_index": out_index }

def construct_updated_data(buffer, in_index):
    return { 'buffer': buffer, 'in_index': in_index }

def deserialize_shared_data(data):
  return data['buffer'], data['in_index'], data['out_index']

def Producer(DisturbedMonitor,in_index, buffer, out_index):
    global CAPACITY
    items_produced = 20
    counter = 20

    while items_produced < 40:
        shared_data = DisturbedMonitor.acquire_lock(serialize_shared_data(buffer, in_index,out_index))
        buffer,in_index,out_index = deserialize_shared_data(shared_data)
        while (in_index + 1) % CAPACITY == out_index:
            shared_data = DisturbedMonitor.wait(serialize_shared_data(buffer, in_index,out_index),{},"empty")
            buffer,in_index,out_index = deserialize_shared_data(shared_data)
        
        counter += 1
        buffer[in_index] = counter
        print("Producer produced:", counter)
        in_index = (in_index + 1) % CAPACITY

        DisturbedMonitor.notify(construct_updated_data(buffer,in_index),"not_empty")

        items_produced += 1

CAPACITY = 10
buffer = [-1 for _ in range(CAPACITY)]
in_index = 0
out_index = 0
input_device_process_id = "P4"
input_all_active_processes = {"P1", "P2", "P3"}
input_pub_socket = "tcp://*:5559"
input_sub_socket = ["tcp://localhost:5557","tcp://localhost:5556","tcp://localhost:5558"]
input_time_sleep = 10

DisturbedMonitor = DisturbedMonitor(input_device_process_id, input_all_active_processes, input_pub_socket, input_sub_socket, input_time_sleep)
Producer(DisturbedMonitor,in_index, buffer, out_index)
DisturbedMonitor.join()

