import multiprocessing
import logging
import logging.handlers
import sys
import os

class LoggerSingleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LoggerSingleton, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.queue = multiprocessing.Queue(-1)
        self.listener = None

    def listener_configurer(self):
        root = logging.getLogger()
        h = logging.FileHandler(os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), 'project.log'))
        f = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        h.setFormatter(f)
        root.addHandler(h)

    def listener_process(self, queue):
        self.listener_configurer()
        while True:
            try:
                record = queue.get()
                if record is None:  # Sentinel to shut down
                    break
                logger = logging.getLogger(os.path.join(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH"), 'project.log'))
                logger.log(logging.INFO, record)
            except Exception:
                import traceback
                print('Error in log listener:', file=sys.stderr)
                traceback.print_exc(file=sys.stderr)

    def start_listener(self):
        pass
        # if self.listener is None:
        #     self.listener = multiprocessing.Process(target=self.listener_process, args=(self.queue,))
        #     self.listener.start()

    def stop_listener(self):
        if self.listener is not None:
            self.queue.put_nowait(None)
            self.listener.join()

    def log(self, msg: str):
        # self.queue.put(msg)
        pass

    def error(self, msg: str):
        # self.queue.put('ERROR: ' + msg)
        pass

if __name__ == '__main__':
    LoggerSingleton().start_listener()
