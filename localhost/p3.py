from disturbed_monitor import DisturbedMonitor

class ConsumerMonitor(DisturbedMonitor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._shared_state_keys.update(["buffer", "in_index", "out_index", "CAPACITY"])

        self.CAPACITY = 10
        self.buffer = [-1 for _ in range(self.CAPACITY)]
        self.in_index = 0
        self.out_index = 0

    def Consumer(self):
      items_consumed = 0
      while items_consumed < 20:
          self.acquire_lock()

          while self.in_index == self.out_index:
              self.wait("not_empty")

          item = self.buffer[self.out_index]
          self.set_field_updated("buffer")
          
          print("Consumer consumed item:", item)
          self.out_index = (self.out_index + 1) % self.CAPACITY
          self.notify("empty")
          items_consumed += 1


if __name__ == '__main__':         
    input_device_process_id = "P3"
    input_all_active_processes = {"P2", "P1", "P4"}
    input_pub_socket = "tcp://*:5558"
    input_sub_socket = ["tcp://localhost:5556","tcp://localhost:5557","tcp://localhost:5559"]
    input_time_sleep = 10
    Monitor = ConsumerMonitor(input_device_process_id, input_all_active_processes, input_pub_socket, input_sub_socket, input_time_sleep)
    Monitor.Consumer()
    Monitor.join()