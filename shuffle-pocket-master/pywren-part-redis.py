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
import pywren
from redis import StrictRedis


def partition_data():
    def run_command(key):
        pywren.wrenlogging.default_config('INFO')
        begin_of_function = time.time()
        logger = logging.getLogger(__name__)
        logger.info("taskId = " + str(key['taskId']))
        logger.info("number of inputs = " + str(key['inputs']))
        logger.info("number of output partitions = " + str(key['parts']))
        logger.info("Here 1")

        # TODO: make the parameters configurable
        taskId = key['taskId']
        # 1T
        #totalInputs = 10000
        totalInputs = 5
        inputsPerTask = key['inputs']
        taskPerRound = key['taskPerRound']
        rounds = (inputsPerTask + taskPerRound - 1) / taskPerRound
        numPartitions = key['parts']
        bucketName = key['bucket']
        rs = []
        for hostname in key['redis'].split(";"):
            r1 = StrictRedis(host=hostname, port=6379, db=0).pipeline()
            rs.append(r1)
        nrs = len(rs)

        logger.info("Here 2")
        min_value = struct.unpack(">I", b"\x00\x00\x00\x00")[0]
        max_value = struct.unpack(">I", b"\xff\xff\xff\xff")[0]

        rangePerPart = (max_value - min_value) / numPartitions

        keyType = np.dtype([('key', 'S4')])
        # 4 bytes good enough for partitioning
        recordType = np.dtype([('key', 'S4'), ('value', 'S96')])

        logger.info("Here 3")
        boundaries = []
        # (numPartitions-1) boundaries
        for i in range(1, numPartitions):
            # 4 bytes unsigned integers
            b = struct.pack('>I', rangePerPart * i)
            boundaries.append(b)

        client = boto3.client('s3', 'us-east-2')

        [t1, t2, t3] = [time.time()] * 3
        [read_time, work_time, write_time] = [0] * 3
        # a total of 10 threads
        read_pool = ThreadPool(1)
        number_of_clients = 1
        write_pool = ThreadPool(number_of_clients)
        clients = []
        for client_id in range(number_of_clients):
            clients.append(boto3.client('s3', 'us-east-2'))
        write_pool_handler_container = []
        logger.info("Here 4")
        logger.info("rounds" + str(rounds))
        # manager = Manager()
        rounds = int(rounds)
        for roundIdx in range(rounds):
            inputs = []

            logger.info("Here 5")
            def read_work(read_key):
                inputId = read_key['inputId']
                keyname = "input/part-" + str(inputId)
                m = hashlib.md5()
                m.update(keyname.encode('utf-8'))
                randomized_keyname = "input/" + m.hexdigest()[:8] + "-part-" + str(inputId)
                logger.info("fetching " + randomized_keyname)
                obj = client.get_object(Bucket=bucketName, Key=randomized_keyname)
                logger.info("fetching " + randomized_keyname + " done")
                fileobj = obj['Body']
                #data = np.fromstring(fileobj.read(), dtype=recordType)
                data = np.frombuffer(fileobj.read(), dtype=recordType)
                logger.info("conversion " + randomized_keyname + " done")
                logger.info("size " + randomized_keyname + "  " + str(len(data)))
                inputs.append(data)

            startId = taskId * inputsPerTask + roundIdx * taskPerRound
            logger.info("Here 6")
            endId = min(taskId * inputsPerTask + min((roundIdx + 1) * taskPerRound, inputsPerTask), totalInputs)
            logger.info("Here 7")
            inputIds = range(startId, endId)
            logger.info("Here 8")
            if len(inputIds) == 0:
                break

            logger.info("Range for round " + str(roundIdx) + " is (" + str(startId) + "," + str(endId) + ")")

            read_keylist = []
            for i in range(len(inputIds)):
                read_keylist.append({'inputId': inputIds[i],
                                     'i': i})

            # before processing, make sure all data is read
            read_pool.map(read_work, read_keylist)
            logger.info("read call done ")
            logger.info("size of inputs" + str(len(inputs)))

            records = np.concatenate(inputs)
            gc.collect()

            t1 = time.time()
            logger.info('read time ' + str(t1 - t3))
            read_time = t1 - t3

            if numPartitions == 1:
                ps = [0] * len(records)
            else:
                ps = np.searchsorted(boundaries, records['key'])
            t2 = time.time()
            logger.info('calculating partitions time: ' + str(t2 - t1))
            # before processing the newly read data, make sure outputs are all written out
            if len(write_pool_handler_container) > 0:
                write_pool_handler = write_pool_handler_container.pop()
                twait_start = time.time()
                write_pool_handler.wait()
                twait_end = time.time()
                if twait_end - twait_start > 0.5:
                    logger.info('write time = ' + str(twait_end - t3) + " slower than read " + str(t1 - t3))
                else:
                    logger.info('write time < ' + str(twait_end - t3) + " faster than read " + str(t1 - t3))

            t2 = time.time()
            gc.collect()
            numPartitions = int(numPartitions)
            outputs = [[] for i in range(0, numPartitions)]
            for idx, record in enumerate(records):
                outputs[ps[idx]].append(record)
            t3 = time.time()
            logger.info('paritioning time: ' + str(t3 - t2))
            work_time = t3 - t1

            def write_work_client(writer_key):
                client_id = writer_key['i']
                mapId = rounds * taskId + writer_key['roundIdx']
                key_per_client = writer_key['key-per-client']

                logger.info("Hey 1")
                key_per_client = int(key_per_client)
                client_id = int(client_id)
                numPartitions = int(writer_key['num_partitions'])
                logger.info("range" + str(key_per_client) + " " + str(client_id) +  " " + str(numPartitions))
                for i in range(key_per_client * client_id, min(key_per_client * (client_id + 1), numPartitions)):
                    logger.info("Hey 2")
                    keyname = "shuffle/part-" + str(mapId) + "-" + str(i)
                    m = hashlib.md5()
                    m.update(keyname.encode('utf-8'))
                    logger.info("Hey 3")
                    randomized_keyname = "shuffle/" + m.hexdigest()[:8] + "-part-" + str(mapId) + "-" + str(i)
                    logging.info("The name of the key to write is: " + randomized_keyname)
                    logger.info("Hey 4")
                    body = np.asarray(outputs[ps[i]]).tobytes()
                    ridx = int(m.hexdigest()[:8], 16) % nrs
                    rs[ridx].set(randomized_keyname, body)
                    logger.info("Hey 5")
                for r in rs:
                    r.execute()

            logger.info("Hey 6")
            writer_keylist = []
            key_per_client = (numPartitions + number_of_clients - 1) / number_of_clients
            number_of_clients = int(number_of_clients)
            for i in range(number_of_clients):
                writer_keylist.append({'roundIdx': roundIdx,
                                       'i': i,
                                       'key-per-client': key_per_client,
                                       'num_partitions': numPartitions})

            write_pool_handler = write_pool.map_async(write_work_client, writer_keylist)
            write_pool_handler_container.append(write_pool_handler)
            logger.info("Hey 7")

        logger.info("Here 9")
        if len(write_pool_handler_container) > 0:
            write_pool_handler = write_pool_handler_container.pop()
            write_pool_handler.wait()
            twait_end = time.time()
            logger.info('last write time = ' + str(twait_end - t3))
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
    redisnode = sys.argv[5]
    rate = int(sys.argv[6])

    keylist = []

    for i in range(numTasks):
        keylist.append({'taskId': i,
                        'inputs': inputsPerTask,
                        'parts': numPartitions,
                        'redis': redisnode,
                        'taskPerRound': taskPerRound,
                        'bucket': "yupengtang-pywren-49"})

    wrenexec = pywren.default_executor()
    futures = wrenexec.map(run_command, keylist)

    pywren.wait(futures)
    results = [f.result() for f in futures]
    #print(results)
    print("part done")
    run_statuses = [f.run_status for f in futures]
    invoke_statuses = [f.invoke_status for f in futures]
    res = {'results': results,
           'run_statuses': run_statuses,
           'invoke_statuses': invoke_statuses}
    filename = "redis-sort-part-con" + str(rate) + ".pickle.breakdown." + str(len(redisnode.split(";")))
    pickle.dump(res, open(filename, 'wb'))
    return res


if __name__ == '__main__':
    partition_data()
