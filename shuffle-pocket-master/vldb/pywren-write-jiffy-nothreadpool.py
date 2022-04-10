from __future__ import print_function

import sys
import time
import logging

import hashlib
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
        begin_of_function = time.time()
        logger = logging.getLogger(__name__)
        print("taskId = " + str(key['taskId']))
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

        time.sleep(process_time)


        print("Process finish here: " + str(time.time()))

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
            table = em.open_or_create_hash_table(data_path,"local://tmp", 1,1)
            throughput_step = 1
            throughput_count = 1
            throughput_total = 0
            throughput_nops = 0
            ret = []
            while time.time() < start_time + total_time:
                count = count + 1
                keyname = str(jobID) + "-" + str(taskID) + "-" + str(count)
                m = hashlib.md5()
                m.update(keyname.encode('utf-8'))
                randomized_keyname = str(jobID) + "-" + str(taskID) + '-' + m.hexdigest()[:8] + '-' + str(count)
                #print("(" + str(taskId) + ")" + "The name of the key to write is: " + randomized_keyname)
                start = time.time()
                print("[HONEYCOMB] [" + str(jobID) + "] " + str(time.time()) + " " + str(taskID) + " " + str(len(body)) + " write " + "S")
                table.put(randomized_keyname, body)
                end = time.time()
                print("[HONEYCOMB] [" + str(jobID) + "] " + str(time.time()) + " " + str(taskID) + " " + str(len(body)) + " write " + "E")
                throughput_total += end - start
                throughput_nops += 1
                if end - start_time >= throughput_count:
                    throughput = throughput_nops / throughput_total
                    ret.append((end, throughput))
                    throughput_nops = 0
                    throughput_count += throughput_step
                    throughput_total = 0

            print("Write finish here: " + str(time.time()))
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
        ret = write_work_client(writer_keylist[0])

        print("Write task launched")

        print(ret)
        twait_end = time.time()
        write_time = twait_end - start_time
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

    run_command(keylist[0])


if __name__ == '__main__':
    print("Start time: " + str(time.time()))
    write_data()
    print("End time: " + str(time.time()))
