from __future__ import print_function

import gc
import logging
import struct
import sys
import time
from multiprocessing.pool import ThreadPool

import boto3
from six.moves import cPickle as pickle
import hashlib
import numpy as np
import pocket
import pandas
from base64 import b64encode



def partition_data():
    def run_command(key):
        begin_of_function = time.time()
        logger = logging.getLogger(__name__)
        print("taskId = " + str(key['taskId']))
        print("number of inputs = " + str(key['inputs']))
        print("number of output partitions = " + str(key['parts']))
        # TODO: make the parameters configurable
        taskId = key['taskId']
        # 1T
        #totalInputs = 10000
        totalInputs = key['total_input']
        inputsPerTask = key['inputs']
        taskPerRound = key['taskPerRound']
        rounds = (inputsPerTask + taskPerRound - 1) / taskPerRound
        numPartitions = key['parts']
        bucketName = key['bucket']

        jobid_int = int(key['job_number'])
        pocket_job_name = "job" + str(jobid_int)
        print("Pocket job name " + pocket_job_name)
        #jobid = pocket.register_job(pocket_job_name, capacityGB=1)
        jobid = pocket_job_name
        print("(" + str(taskId) + ")" + "Finish registering job")
        pocket_namenode = pocket.connect("10.1.0.10", 9070)

        print("(" + str(taskId) + ")" + "Connecting namenode job")
        print("See the number of partitions: " + str(numPartitions))
        min_value = struct.unpack(">I", b"\x00\x00\x00\x00")[0]
        max_value = struct.unpack(">I", b"\xff\xff\xff\xff")[0]

        rangePerPart = int((max_value - min_value) / numPartitions)
        print("here 1 " + str(rangePerPart))

        keyType = np.dtype([('key', 'S4')])
        # 4 bytes good enough for partitioning
        recordType = np.dtype([('key', 'S4'), ('value', 'S96')])

        print("here 2")
        boundaries = []
        # (numPartitions-1) boundaries
        for i in range(1, numPartitions):
            # 4 bytes unsigned integers
            b = struct.pack('>I', rangePerPart * i)
            boundaries.append(b)

        client = boto3.client('s3', 'us-west-2')

        print("(" + str(taskId) + ")" + "Connected s3 client")
        [t1, t2, t3] = [time.time()] * 3
        [read_time, work_time, write_time] = [0] * 3
        # a total of 10 threads
        read_pool = ThreadPool(1)
        number_of_clients = 1
        write_pool = ThreadPool(number_of_clients)
        clients = []
        for client_id in range(number_of_clients):
            clients.append(boto3.client('s3', 'us-west-2'))
        write_pool_handler_container = []
        print("(" + str(taskId) + ")" + "rounds" + str(rounds))
        # manager = Manager()
        rounds = int(rounds)
        for roundIdx in range(rounds):
            inputs = []

            def read_work(read_key):
                inputId = read_key['inputId']
                keyname = "input/part-" + str(inputId)
                m = hashlib.md5()
                m.update(keyname.encode('utf-8'))
                randomized_keyname = "input/" + m.hexdigest()[:8] + "-part-" + str(inputId)
                print("(" + str(taskId) + ")" + "fetching " + randomized_keyname)
                obj = client.get_object(Bucket=bucketName, Key=randomized_keyname)
                print("(" + str(taskId) + ")" + "fetching " + randomized_keyname + " done")
                fileobj = obj['Body']
                #data = np.fromstring(fileobj.read(), dtype=recordType)
                data = np.frombuffer(fileobj.read(), dtype=recordType)
                print("(" + str(taskId) + ")" + "conversion " + randomized_keyname + " done")
                print("(" + str(taskId) + ")" + "size " + randomized_keyname + "  " + str(len(data)))
                inputs.append(data)

            startId = taskId * inputsPerTask + roundIdx * taskPerRound
            endId = min(taskId * inputsPerTask + min((roundIdx + 1) * taskPerRound, inputsPerTask), totalInputs)
            inputIds = range(startId, endId)
            if len(inputIds) == 0:
                break

            print("(" + str(taskId) + ")" + "Range for round " + str(roundIdx) + " is (" + str(startId) + "," + str(endId) + ")")

            read_keylist = []
            for i in range(len(inputIds)):
                read_keylist.append({'inputId': inputIds[i],
                                     'i': i})

            # before processing, make sure all data is read
            read_pool.map(read_work, read_keylist)
            print("(" + str(taskId) + ")" + "read call done ")
            print("(" + str(taskId) + ")" + "size of inputs" + str(len(inputs)))

            records = np.concatenate(inputs)
            gc.collect()

            t1 = time.time()
            print("(" + str(taskId) + ")" + 'read time ' + str(t1 - t3))
            read_time = t1 - t3

            if numPartitions == 1:
                ps = [0] * len(records)
            else:
                ps = np.searchsorted(boundaries, records['key'])
            t2 = time.time()
            print("(" + str(taskId) + ")" + 'calculating partitions time: ' + str(t2 - t1))
            # before processing the newly read data, make sure outputs are all written out
            if len(write_pool_handler_container) > 0:
                write_pool_handler = write_pool_handler_container.pop()
                twait_start = time.time()
                write_pool_handler.wait()
                twait_end = time.time()
                if twait_end - twait_start > 0.5:
                    print("(" + str(taskId) + ")" + 'write time = ' + str(twait_end - t3) + " slower than read " + str(t1 - t3))
                else:
                    print("(" + str(taskId) + ")" + 'write time < ' + str(twait_end - t3) + " faster than read " + str(t1 - t3))

            t2 = time.time()
            gc.collect()
            numPartitions = int(numPartitions)
            outputs = [[] for i in range(0, numPartitions)]
            for idx, record in enumerate(records):
                outputs[ps[idx]].append(record)
            t3 = time.time()
            print("(" + str(taskId) + ")" + 'paritioning time: ' + str(t3 - t2))
            work_time = t3 - t1

            def write_work_client(writer_key):
                client_id = writer_key['i']
                mapId = rounds * taskId + writer_key['roundIdx']
                key_per_client = writer_key['key-per-client']

                key_per_client = int(key_per_client)
                client_id = int(client_id)
                numPartitions = int(writer_key['num_partitions'])
                print("(" + str(taskId) + ")" + "range" + str(key_per_client) + " " + str(client_id) +  " " + str(numPartitions))
                for i in range(key_per_client * client_id, min(key_per_client * (client_id + 1), numPartitions)):
                    keyname = "shuffle-part-" + str(mapId) + "-" + str(i)
                    m = hashlib.md5()
                    m.update(keyname.encode('utf-8'))
                    randomized_keyname = "shuffle-" + m.hexdigest()[:8] + "-part-" + str(mapId) + "-" + str(i)
                    print("The name of the key to write is: " + randomized_keyname)
                    bytes_body = np.asarray(outputs[ps[i]]).tobytes()
                    print("Hey top top " + str(len(bytes_body)))
                    datasize = 1700000
                    #print(body)
                    #body = bytes_body.decode('ascii')
                    body = b64encode(bytes_body).decode('utf-8')
                    body = body.ljust(datasize, '=')
                    print("Byte to be written: " + str(len(body)))

                    print("Last ten bits after padding: " + body[-10:])
                    pocket.put_buffer(pocket_namenode, body, len(body), randomized_keyname, jobid)

            writer_keylist = []
            key_per_client = (numPartitions + number_of_clients - 1) / number_of_clients
            number_of_clients = int(number_of_clients)
            for i in range(number_of_clients):
                writer_keylist.append({'roundIdx': roundIdx,
                                       'i': i,
                                       'key-per-client': key_per_client,
                                       'num_partitions': numPartitions})

            for i in range(number_of_clients):
                write_work_client(writer_keylist[i])
            #write_pool_handler = write_pool.map_async(write_work_client, writer_keylist)
            #write_pool_handler_container.append(write_pool_handler)

        #pocket.deregister_job(jobid)
        if len(write_pool_handler_container) > 0:
            write_pool_handler = write_pool_handler_container.pop()
            write_pool_handler.wait()
            twait_end = time.time()
            print("(" + str(taskId) + ")" + 'last write time = ' + str(twait_end - t3))
            write_time = twait_end - t3
        read_pool.close()
        write_pool.close()
        read_pool.join()
        write_pool.join()
        end_of_function = time.time()
        print("(" + str(taskId) + ")" + "Exciting this function")
        return begin_of_function, end_of_function, read_time, work_time, write_time

    numTasks = int(sys.argv[1])
    inputsPerTask = int(sys.argv[2])
    numPartitions = int(sys.argv[3])
    taskPerRound = int(sys.argv[4])
    rate = int(sys.argv[5])
    job_number = int(sys.argv[6])

    keylist = []

    pocket_job_name = "job" + str(job_number)
    print("Pocket job name " + pocket_job_name)
    jobid = pocket.register_job(pocket_job_name, capacityGB=55)

    for i in range(numTasks):
        keylist.append({'taskId': i,
                        'inputs': inputsPerTask,
                        'parts': numPartitions,
                        'taskPerRound': taskPerRound,
                        'bucket': "yupeng-pywren",
                        'job_number': job_number,
                        'total_input':numTasks})

    print("Mapping all the functions")
    for i in range(numTasks):
        run_command(keylist[i])

    #pocket.deregister_job(jobid)

if __name__ == '__main__':
    partition_data()
