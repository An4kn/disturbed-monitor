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
        buffer,in_index,out_index = deserialize_shared_data(DisturbedMonitor.acquire_lock(serialize_shared_data(buffer, in_index,out_index))) #TODO to mozna w sumie usunac ale nie trzeba
        while (in_index + 1) % CAPACITY == out_index:
            buffer,in_index,out_index = deserialize_shared_data(DisturbedMonitor.wait(serialize_shared_data(buffer, in_index,out_index),"empty"))  # TODO MA BYC TABLICA ZWYKLA

        counter += 1
        buffer[in_index] = counter
        print("||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||")
        print("Producer produced:", counter)
        print("||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||")

        in_index = (in_index + 1) % CAPACITY
        # time.sleep(0.7)

        DisturbedMonitor.notify(construct_updated_data(buffer,in_index),"not_empty")  # Signal to consumers  #TODO tutaj zmienna not_full i full nie musi byc w pelni transparentne btw

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
Producer(DisturbedMonitor,in_index, buffer, out_index)  # Initialize producer with 0 items produced, empty buffer, and in_index at 0
DisturbedMonitor.join() #to jest taki join()

