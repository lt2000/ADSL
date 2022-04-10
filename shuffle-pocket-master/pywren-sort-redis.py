from __future__ import print_function

import gc
import hashlib
import logging
import sys
import time
from multiprocessing.pool import ThreadPool

import boto3
import numpy as np
import pywren
from redis import StrictRedis
from six.moves import cPickle as pickle


def sort_data():
    def run_command(key):
        global concat_time
        pywren.wrenlogging.default_config('INFO')
        begin_of_function = time.time()
        logger = logging.getLogger(__name__)
        logger.info("taskId = " + str(key['taskId']))
        logger.info("number of works = " + str(key['works']))
        logger.info("number of input partitions = " + str(key['parts']))

        bucketName = key['bucket']
        taskId = key['taskId']
        rounds = key['works']
        numPartitions = int(key['parts'])

        # 10 bytes for sorting
        recordType = np.dtype([('key', 'S10'), ('value', 'S90')])

        client = boto3.client('s3', 'us-east-2')
        rs = []
        for hostname in key['redis'].split(";"):
            r1 = StrictRedis(host=hostname, port=6379, db=0).pipeline()
            rs.append(r1)
        nrs = len(rs)

        [t1, t2, t3] = [time.time()] * 3
        [read_time, work_time, write_time] = [0] * 3
        # a total of 10 threads
        write_pool = ThreadPool(1)
        number_of_clients = 1
        read_pool = ThreadPool(number_of_clients)
        clients = []
        number_of_clients = int(number_of_clients)
        for client_id in range(number_of_clients):
            clients.append(boto3.client('s3', 'us-east-2'))
        write_pool_handler_container = []
        rounds = int(rounds)
        logger.info("number of rounds here here here" + str(rounds))
        for roundIdx in range(rounds):
            logger.info("HHHHHHH 1")
            inputs = []

            def read_work(reader_key):
                client_id = reader_key['client_id']
                reduceId = rounds * taskId + reader_key['roundIdx']
                key_per_client = reader_key['key-per-client']
                logger.info("HHHHHHH 4")
                key_per_client = int(key_per_client)
                client_id = int(client_id)
                for mapId in range(key_per_client * client_id, min(key_per_client * (client_id + 1), numPartitions)):
                    # for mapId in range(1):
                    keyname = "shuffle/part-" + str(mapId) + "-" + str(reduceId)
                    m = hashlib.md5()
                    m.update(keyname.encode('utf-8'))
                    randomized_keyname = "shuffle/" + m.hexdigest()[:8] + "-part-" + str(mapId) + "-" + str(reduceId)
                    logging.info("The name of the key to read is: " + randomized_keyname)
                    logger.info("HHHHHHH 5")
                    try:
                        ridx = int(m.hexdigest()[:8], 16) % nrs
                        rs[ridx].get(randomized_keyname)
                    except Exception:
                        logger.info("reading error key " + randomized_keyname)
                        raise
                logger.info("HHHHHHH 6")
                for r in rs:
                    logger.info("HHHHHHH 7")
                    objs = r.execute()
                    logger.info("HHHHHHH 8")
                    data = [np.fromstring(obj, dtype=recordType) for obj in objs]
                    logger.info("HHHHHHH 9")
                    [d.sort(order='key') for d in data]
                    logger.info("HHHHHHH 10")
                    inputs.extend(data)


            reader_keylist = []
            key_per_client = (numPartitions + number_of_clients - 1) / number_of_clients
            number_of_clients = int(number_of_clients)
            logger.info("HHHHHHH 2")
            for client_id in range(number_of_clients):
                reader_keylist.append({'roundIdx': roundIdx,
                                       'client_id': client_id,
                                       'key-per-client': key_per_client})

            logger.info("HHHHHHH 3")
            read_pool.map(read_work, reader_keylist)
            logger.info("HHHHHHH 11")
            t1 = time.time()
            logger.info('read time ' + str(t1 - t3))
            read_time = t1 - t3

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
            records = np.concatenate(inputs)
            gc.collect()
            concat_time = len(records)

            records.sort(order='key', kind='mergesort')

            t3 = time.time()
            logger.info('sort time: ' + str(t3 - t2))

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
            logger.info('last write time = ' + str(twait_end - t3))
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

    keylist = []

    for i in range(numTasks):
        keylist.append({'taskId': i,
                        'works': worksPerTask,
                        'redis': redisnode,
                        'parts': numPartitions,
                        'bucket': "yupengtang-pywren-49"})

    wrenexec = pywren.default_executor()
    futures = wrenexec.map(run_command, keylist)

    pywren.wait(futures)
    results = [f.result() for f in futures]
    #print(results)
    print("sort done")
    run_statuses = [f.run_status for f in futures]
    invoke_statuses = [f.invoke_status for f in futures]
    res = {'results': results,
           'run_statuses': run_statuses,
           'invoke_statuses': invoke_statuses}
    filename = "redis-sort-sort-con" + str(rate) + ".pickle.breakdown." + str(len(redisnode.split(";")))
    pickle.dump(res, open(filename, 'wb'))
    return res


if __name__ == '__main__':
    sort_data()
