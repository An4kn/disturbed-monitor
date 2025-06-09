from disturbed_monitor import DisturbedMonitor 

class ProducerMonitor(DisturbedMonitor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._shared_state_keys.update(["buffer", "in_index", "out_index", "CAPACITY"])

        self.CAPACITY = 10
        self.buffer = [-1 for _ in range(self.CAPACITY)]
        self.in_index = 0
        self.out_index = 0

    def produce(self):
        items_produced = 20
        items_to_produce = 40
        counter = 20
        while items_produced < items_to_produce:
          self.acquire_lock()

          while (self.in_index + 1) % self.CAPACITY == self.out_index:
              self.wait("empty")

          counter += 1
          self.buffer[self.in_index] = counter
          self.set_field_updated("buffer")
    
          print(f"Producer ({self.device_process_id}) produced: {counter}")
          self.in_index = (self.in_index + 1) % self.CAPACITY
          self.notify("not_empty")  
          items_produced += 1


if __name__ == '__main__':
    input_device_process_id = "P4"
    input_all_active_processes = {"P1", "P2", "P3"}
    input_pub_socket = "tcp://*:5559"
    input_sub_socket = ["tcp://localhost:5557","tcp://localhost:5556","tcp://localhost:5558"]
    input_time_sleep = 10

    monitor = ProducerMonitor(
        input_device_process_id, 
        input_all_active_processes, 
        input_pub_socket, 
        input_sub_socket, 
        input_time_sleep
    )
    
    monitor.produce()
    monitor.join()
