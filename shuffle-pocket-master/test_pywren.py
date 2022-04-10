import pywren
import numpy as np
from multiprocessing.pool import ThreadPool
from multiprocessing import Process, Pipe
def my_function(x):
    def calc(k):
        a = k + 7
    conn1, conn2 = Pipe()
    proc = Process(target=calc, args=(1, ))
    proc.start()
    proc.join()
    return x + 8

wrenexec = pywren.default_executor()
#future = wrenexec.call_async(my_function, 3)
futures = wrenexec.map(my_function, range(10))

ret = pywren.get_all_results(futures)
print(ret)
