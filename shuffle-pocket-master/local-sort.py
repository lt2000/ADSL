from __future__ import print_function

import gc
import hashlib
import logging
import sys
import time
from multiprocessing.pool import ThreadPool

import boto3
import numpy as np
import pocket
from six.moves import cPickle as pickle
from base64 import b64decode

def sort_data():
    def run_command(key):
        global concat_time
        begin_of_function = time.time()
        logger = logging.getLogger(__name__)
        print("taskId = " + str(key['taskId']))
        #print("number of works = " + str(key['works']))
        #print("number of input partitions = " + str(key['parts']))

        bucketName = key['bucket']
        taskId = key['taskId']
        rounds = key['works']
        numPartitions = int(key['parts'])

        jobid_int = int(key['job_number'])
        pocket_job_name = "job" + str(jobid_int)
#        jobid = pocket.register_job(pocket_job_name, capacityGB=1)
        jobid = pocket_job_name
        pocket_namenode = pocket.connect("10.1.0.10", 9070)

        # 10 bytes for sorting
        recordType = np.dtype([('key', 'S10'), ('value', 'S90')])

        client = boto3.client('s3', 'us-west-2')
        # rs = []
        # for hostname in key['redis'].split(";"):
        #     r1 = StrictRedis(host=hostname, port=6379, db=0).pipeline()
        #     rs.append(r1)
        # nrs = len(rs)

        [t1, t2, t3] = [time.time()] * 3
        [read_time, work_time, write_time] = [0] * 3
        # a total of 10 threads
        write_pool = ThreadPool(1)
        number_of_clients = 1
        read_pool = ThreadPool(number_of_clients)
        clients = []
        number_of_clients = int(number_of_clients)
        for client_id in range(number_of_clients):
            clients.append(boto3.client('s3', 'us-west-2'))
        write_pool_handler_container = []
        rounds = int(rounds)
        for roundIdx in range(rounds):
            inputs = []

            def read_work(reader_key):
                client_id = reader_key['client_id']
                reduceId = rounds * taskId + reader_key['roundIdx']
                key_per_client = reader_key['key-per-client']
                key_per_client = int(key_per_client)
                client_id = int(client_id)
                objs = []
                for mapId in range(key_per_client * client_id, min(key_per_client * (client_id + 1), numPartitions)):
                    # for mapId in range(1):
                    keyname = "shuffle-part-" + str(mapId) + "-" + str(reduceId)
                    m = hashlib.md5()
                    m.update(keyname.encode('utf-8'))
                    randomized_keyname = "shuffle-" + m.hexdigest()[:8] + "-part-" + str(mapId) + "-" + str(reduceId)
                    print("The name of the key to read is: " + randomized_keyname)
                    try:
                        datasize = 17000000
                        textback = " "*datasize
                        pocket.get_buffer(pocket_namenode, randomized_keyname, textback, datasize, jobid)
                        print("Successfully read")
                        #pos = textback.find('.')
                        #print("Padding position: " + str(pos))
                        original_text = b64decode(textback.encode('utf-8'))
                        print("last ten bytes after padding: " + textback[-10:])

                        objs.append(original_text)
                    except Exception:
                        print("reading error key " + randomized_keyname)
                        raise

                data = [np.fromstring(obj, dtype=recordType) for obj in objs]
                [d.sort(order='key') for d in data]
                inputs.extend(data)


            reader_keylist = []
            key_per_client = (numPartitions + number_of_clients - 1) / number_of_clients
            number_of_clients = int(number_of_clients)
            for client_id in range(number_of_clients):
                reader_keylist.append({'roundIdx': roundIdx,
                                       'client_id': client_id,
                                       'key-per-client': key_per_client})

            for i in range(number_of_clients):
                read_work(reader_keylist[i])

            t1 = time.time()
            print('read time ' + str(t1 - t3))
            read_time = t1 - t3

            if len(write_pool_handler_container) > 0:
                write_pool_handler = write_pool_handler_container.pop()
                twait_start = time.time()
                write_pool_handler.wait()
                twait_end = time.time()
                if twait_end - twait_start > 0.5:
                    print('write time = ' + str(twait_end - t3) + " slower than read " + str(t1 - t3))
                else:
                    print('write time < ' + str(twait_end - t3) + " faster than read " + str(t1 - t3))

            t2 = time.time()
            records = np.concatenate(inputs)
            gc.collect()
            concat_time = len(records)

            records.sort(order='key', kind='mergesort')

            t3 = time.time()
            print('sort time: ' + str(t3 - t2))

            work_time = t3 - t2

            def write_work(reduceId):
                keyname = "output/part-" + str(reduceId)
                m = hashlib.md5()
                m.update(keyname.encode('utf-8'))
                randomized_keyname = "output/" + m.hexdigest()[:8] + "-part-" + str(reduceId)
                body = records.tobytes()
                client.put_object(Bucket=bucketName, Key=randomized_keyname, Body=body)

            write_pool_handler = write_pool.map_async(write_work, [taskId * rounds + roundIdx])
            write_pool_handler_container.append(write_pool_handler)

        if len(write_pool_handler_container) > 0:
            write_pool_handler = write_pool_handler_container.pop()
            write_pool_handler.wait()
            twait_end = time.time()
            print('last write time = ' + str(twait_end - t3))
            write_time = twait_end - t3
        read_pool.close()
        write_pool.close()
        read_pool.join()
        write_pool.join()

        end_of_function = time.time()
        return begin_of_function, end_of_function, read_time, work_time, write_time, concat_time

    numTasks = int(sys.argv[1])
    worksPerTask = int(sys.argv[2])
    numPartitions = int(sys.argv[3])
    redisnode = sys.argv[4]
    rate = int(sys.argv[5])
    job_number = int(sys.argv[6])

    keylist = []

    for i in range(numTasks):
        keylist.append({'taskId': i,
                        'works': worksPerTask,
                        'redis': redisnode,
                        'parts': numPartitions,
                        'bucket': "yupeng-pywren",
                        'job_number': job_number})


    pocket_job_name = "job" + str(job_number)
    for i in range(numTasks):
        run_command(keylist[i])

    print("sort done")
    #pocket.deregister_job(pocket_job_name)


if __name__ == '__main__':
    sort_data()
