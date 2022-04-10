from __future__ import print_function

import gc
import struct
import sys
import time
import logging
from multiprocessing.pool import ThreadPool

import boto3
from six.moves import cPickle as pickle
import hashlib
import numpy as np
import pywren
import pocket
from base64 import b64encode
import time


def partition_data():
    def run_command(key):
        pywren.wrenlogging.default_config('INFO')
        begin_of_function = time.time()
        logger = logging.getLogger(__name__)
        logger.info("taskId = " + str(key['taskId']))
        #logger.info("number of inputs = " + str(key['inputs']))
        #logger.info("number of output partitions = " + str(key['parts']))
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
        jobid = pocket_job_name
        pocket_namenode = pocket.connect("10.1.0.10", 9070)

        #logger.info("(" + str(taskId) + ")" + "Connecting namenode job")
        #logger.info("See the number of partitions: " + str(numPartitions))
        min_value = struct.unpack(">I", b"\x00\x00\x00\x00")[0]
        max_value = struct.unpack(">I", b"\xff\xff\xff\xff")[0]

        rangePerPart = int((max_value - min_value) / numPartitions)
        #logger.info("here 1 " + str(rangePerPart))

        keyType = np.dtype([('key', 'S4')])
        # 4 bytes good enough for partitioning
        recordType = np.dtype([('key', 'S4'), ('value', 'S96')])

        #logger.info("here 2")
        boundaries = []
        # (numPartitions-1) boundaries
        for i in range(1, numPartitions):
            # 4 bytes unsigned integers
            b = struct.pack('>I', rangePerPart * i)
            boundaries.append(b)

        client = boto3.client('s3', 'us-west-2')

        #logger.info("(" + str(taskId) + ")" + "Connected s3 client")
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
        #logger.info("(" + str(taskId) + ")" + "rounds" + str(rounds))
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
        #        logger.info("(" + str(taskId) + ")" + "fetching " + randomized_keyname)
                obj = client.get_object(Bucket=bucketName, Key=randomized_keyname)
                #logger.info("(" + str(taskId) + ")" + "fetching " + randomized_keyname + " done")
                fileobj = obj['Body']
                #data = np.fromstring(fileobj.read(), dtype=recordType)
                data = np.frombuffer(fileobj.read(), dtype=recordType)
        #        logger.info("(" + str(taskId) + ")" + "conversion " + randomized_keyname + " done")
        #        logger.info("(" + str(taskId) + ")" + "size " + randomized_keyname + "  " + str(len(data)))
                inputs.append(data)

            startId = taskId * inputsPerTask + roundIdx * taskPerRound
            endId = min(taskId * inputsPerTask + min((roundIdx + 1) * taskPerRound, inputsPerTask), totalInputs)
            inputIds = range(startId, endId)
            if len(inputIds) == 0:
                break

        #    logger.info("(" + str(taskId) + ")" + "Range for round " + str(roundIdx) + " is (" + str(startId) + "," + str(endId) + ")")

            read_keylist = []
            for i in range(len(inputIds)):
                read_keylist.append({'inputId': inputIds[i],
                                     'i': i})

            # before processing, make sure all data is read
            read_pool.map(read_work, read_keylist)
            #logger.info("(" + str(taskId) + ")" + "read call done ")
        #    logger.info("(" + str(taskId) + ")" + "size of inputs" + str(len(inputs)))

            records = np.concatenate(inputs)
            gc.collect()

            t1 = time.time()
            #logger.info("(" + str(taskId) + ")" + 'read time ' + str(t1 - t3))
            read_time = t1 - t3

            if numPartitions == 1:
                ps = [0] * len(records)
            else:
                ps = np.searchsorted(boundaries, records['key'])
            t2 = time.time()
            #logger.info("(" + str(taskId) + ")" + 'calculating partitions time: ' + str(t2 - t1))
            # before processing the newly read data, make sure outputs are all written out
            if len(write_pool_handler_container) > 0:
                write_pool_handler = write_pool_handler_container.pop()
                twait_start = time.time()
                write_pool_handler.wait()
                twait_end = time.time()
                if twait_end - twait_start > 0.5:
                    logger.info("(" + str(taskId) + ")" + 'write time = ' + str(twait_end - t3) + " slower than read " + str(t1 - t3))
                else:
                    logger.info("(" + str(taskId) + ")" + 'write time < ' + str(twait_end - t3) + " faster than read " + str(t1 - t3))

            t2 = time.time()
            gc.collect()
            numPartitions = int(numPartitions)
            outputs = [[] for i in range(0, numPartitions)]
            for idx, record in enumerate(records):
                outputs[ps[idx]].append(record)
            t3 = time.time()
            #logger.info("(" + str(taskId) + ")" + 'paritioning time: ' + str(t3 - t2))
            work_time = t3 - t1
            logger.info("Process finish here: " + str(time.time()))

            def write_work_client(writer_key):
                client_id = writer_key['i']
                mapId = rounds * taskId + writer_key['roundIdx']
                key_per_client = writer_key['key-per-client']
                taskID = writer_key['taskId']
                jobID = writer_key['jobid']
                key_per_client = int(key_per_client)
                client_id = int(client_id)
                numPartitions = int(writer_key['num_partitions'])
        #        logger.info("(" + str(taskId) + ")" + "range" + str(key_per_client) + " " + str(client_id) +  " " + str(numPartitions))
                #datasize = 1024 * 1024 * 2
                #body = "a"*datasize
                for i in range(key_per_client * client_id, min(key_per_client * (client_id + 1), numPartitions)):
                    keyname = "shuffle-part-" + str(mapId) + "-" + str(i)
                    m = hashlib.md5()
                    m.update(keyname.encode('utf-8'))
                    randomized_keyname = "shuffle-" + m.hexdigest()[:8] + "-part-" + str(mapId) + "-" + str(i)
                    #logger.info("(" + str(taskId) + ")" + "The name of the key to write is: " + randomized_keyname)
                    body = np.asarray(outputs[ps[i]]).tobytes()
                    #logger.info("(" + str(taskId) + ")" + "Original size: " + str(len(bytes_body)))
                    #body = b64encode(bytes_body).decode('utf-8')
                    #logger.info("(" + str(taskId) + ")" + "B64 encode size: " + str(len(body)))
                    # FIXME data size jobid time stamp read/write
                    # client.put_object(Bucket=bucketName, Key=randomized_keyname, Body=body)
                    #datasize = 1300 * 1000
                    datasize = 1310720
                    #while len(body) < datasize:
                    #    body = body + "="
                    body = body.ljust(datasize, b'=')
                    #logger.info("(" + str(taskId) + ")" + "Byte to be written: " + str(len(body)))
                    #logger.info("(" + str(taskId) + ")" + "Last ten bits after padding: " + body[-10:])
                    logger.info("[POCKET] [" + str(jobID) + "] " + str(time.time_ns()) + " " + str(taskID) + " " + str(len(body)) + " write " + "S")
                    r = pocket.put_buffer_bytes(pocket_namenode, body, len(body), randomized_keyname, jobid)
                    logger.info("[POCKET] [" + str(jobID) + "] " + str(time.time_ns()) + " " + str(taskID) + " " + str(len(body)) + " write " + "E " + str(r) )
                    #logger.info("(" + str(taskId) + ")" + "Successful put buffer")

                #logger.info("Write finish here: " + str(time.time()))

            writer_keylist = []
            key_per_client = (numPartitions + number_of_clients - 1) / number_of_clients
            number_of_clients = int(number_of_clients)
            for i in range(number_of_clients):
                writer_keylist.append({'roundIdx': roundIdx,
                                       'i': i,
                                       'key-per-client': key_per_client,
                                       'num_partitions': numPartitions,
                                       'taskId': taskId,
                                       'jobid': jobid_int})

            write_pool_handler = write_pool.map_async(write_work_client, writer_keylist)
            write_pool_handler_container.append(write_pool_handler)

        if len(write_pool_handler_container) > 0:
            write_pool_handler = write_pool_handler_container.pop()
            write_pool_handler.wait()
            twait_end = time.time()
            #logger.info("(" + str(taskId) + ")" + 'last write time = ' + str(twait_end - t3))
            write_time = twait_end - t3
        read_pool.close()
        write_pool.close()
        read_pool.join()
        write_pool.join()
        end_of_function = time.time()
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
    jobid = pocket.register_job(pocket_job_name, capacityGB=53, peakMbps=40000)

    for i in range(numTasks):
        keylist.append({'taskId': i,
                        'inputs': inputsPerTask,
                        'parts': numPartitions,
                        'taskPerRound': taskPerRound,
                        'bucket': "yupeng-pywren-" + str(job_number),
                        'job_number': job_number,
                        'total_input': numTasks})
    wrenexec = pywren.default_executor()
    futures = wrenexec.map(run_command, keylist)
    print("Mapping all the functions")

    pywren.wait(futures)
    print("Waiting for futures")
    results = [f.result() for f in futures]
    #print(results)
    print("part done " + str(job_number))
    run_statuses = [f.run_status for f in futures]
    invoke_statuses = [f.invoke_status for f in futures]
    res = {'results': results,
           'run_statuses': run_statuses,
           'invoke_statuses': invoke_statuses}
    filename = "pocket-part-con" + str(rate) + ".pickle.breakdown"
    pickle.dump(res, open(filename, 'wb'))
    return res


if __name__ == '__main__':
    print(time.time())
    partition_data()
    print(time.time())
