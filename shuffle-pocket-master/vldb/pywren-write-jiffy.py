from __future__ import print_function

import sys
import time
import logging
from multiprocessing.pool import ThreadPool

from six.moves import cPickle as pickle
import hashlib
import pywren
from jiffy import JiffyClient


def write_data():
    def run_command(key):
        """
        keylist.append({'taskId': i,
                        'job_number': job_number,
                        'total_input': numTasks,
                        'write_element_size': write_element_size,
                        'process_time': process_time,
                        'total_time': total_time,
                        'em': em})
        """
        pywren.wrenlogging.default_config('INFO')
        begin_of_function = time.time()
        logger = logging.getLogger(__name__)
        logger.info("taskId = " + str(key['taskId']))
        taskId = key['taskId']
        jobid_int = int(key['job_number'])
        write_element_size = int(key['write_element_size'])
        process_time = int(key['process_time'])
        total_time = int(key['total_time'])
        em = JiffyClient(host=key['em'])

        [read_time, work_time, write_time] = [0] * 3
        start_time = time.time()

        # a total of 10 threads
        number_of_clients = 1
        write_pool = ThreadPool(number_of_clients)

        time.sleep(process_time)


        logger.info("Process finish here: " + str(time.time()))

        def write_work_client(writer_key):
            start_time = time.time()
            client_id = int(writer_key['client_id'])
            taskID = writer_key['taskId']
            jobID = writer_key['jobid']
            datasize = writer_key['write_element_size']
                #datasize = 1310720
            total_time = writer_key['total_time']
            body = b'a' * datasize
            client_id = int(client_id)
            count = 0
            data_path = "/job" + str(jobID)
            open_start = time.time()
            table = em.open_or_create_hash_table(data_path,"local://tmp", 1,1)
            open_end = time.time()
            throughput_step = 1
            throughput_count = 1
            throughput_total = 0
            throughput_nops = 0
            ret = []
            ret.append((open_start, open_end - open_start))
            first_flag = False
            while time.time() < start_time + total_time:
                count = count + 1
                keyname = str(jobID) + "-" + str(taskID) + "-" + str(count)
                m = hashlib.md5()
                m.update(keyname.encode('utf-8'))
                randomized_keyname = str(jobID) + "-" + str(taskID) + '-' + m.hexdigest()[:8] + '-' + str(count)
                #logger.info("(" + str(taskId) + ")" + "The name of the key to write is: " + randomized_keyname)
                start = time.time()
                #logger.info("[HONEYCOMB] [" + str(jobID) + "] " + str(time.time_ns()) + " " + str(taskID) + " " + str(len(body)) + " write " + "S")
                table.put(randomized_keyname, body)
                end = time.time()
                if first_flag is False:
                    first_flag = True
                    ret.append((start, end))
                if end - start > 1:
                    ret.append((start, 1111111111111))
                #logger.info("[HONEYCOMB] [" + str(jobID) + "] " + str(time.time_ns()) + " " + str(taskID) + " " + str(len(body)) + " write " + "E")
                throughput_total += end - start
                throughput_nops += 1
                if end - start_time >= throughput_count:
                    throughput = throughput_nops / throughput_total
                    ret.append((end, throughput))
                    throughput_nops = 0
                    throughput_count += throughput_step
                    throughput_total = 0

            logger.info("Write finish here: " + str(time.time()))
            return ret

        writer_keylist = []
        number_of_clients = int(number_of_clients)
        for i in range(number_of_clients):
            writer_keylist.append({'client_id': i,
                                   'taskId': taskId,
                                   'jobid': jobid_int,
                                   'write_element_size': write_element_size,
                                   'total_time': total_time})

        start_time = time.time()
        write_pool_handler_container = []
        write_pool_handler = write_pool.map_async(write_work_client, writer_keylist)
        write_pool_handler_container.append(write_pool_handler)

        if len(write_pool_handler_container) > 0:
            write_pool_handler = write_pool_handler_container.pop()
            ret = write_pool_handler.get()
            twait_end = time.time()
            write_time = twait_end - start_time
        write_pool.close()
        write_pool.join()
        end_of_function = time.time()
        return begin_of_function, end_of_function, write_time, ret

    numTasks = int(sys.argv[1])
    job_number = int(sys.argv[2])
    write_element_size = int(sys.argv[3])
    process_time = int(sys.argv[4]) # microseconds
    total_time = int(sys.argv[5])
    em = sys.argv[6]

    keylist = []

    for i in range(numTasks):
        keylist.append({'taskId': i,
                        'job_number': job_number,
                        'total_input': numTasks,
                        'write_element_size': write_element_size,
                        'process_time': process_time,
                        'total_time': total_time,
                        'em': em})

    wrenexec = pywren.default_executor()
    futures = wrenexec.map(run_command, keylist)
    pywren.wait(futures)
    results = [f.result() for f in futures]

    print("Write " + str(job_number))
    run_statuses = [f.run_status for f in futures]
    invoke_statuses = [f.invoke_status for f in futures]
    res = {'results': results,
           'run_statuses': run_statuses,
           'invoke_statuses': invoke_statuses}
    filename = "jiffy-write-" + str(job_number) + ".pickle.breakdown"
    pickle.dump(res, open(filename, 'wb'))
    return res


if __name__ == '__main__':
    print("Start time: " + str(time.time()))
    write_data()
    print("End time: " + str(time.time()))
