from __future__ import print_function

import random
import sys

import boto3
import hashlib
import pywren

if __name__ == "__main__":
    import logging
    import subprocess
    import gc
    import time


    def run_command(key):
        print("Initially the key is: " + str(key))
        pywren.wrenlogging.default_config()
        logger = logging.getLogger(__name__)

        logging.info("Inserting this function")
        m = hashlib.md5()
        genpart = str(random.choice(range(50)))
        m.update(genpart.encode('utf-8'))
        #genfile = m.hexdigest()[:8] + "-gensort-" + genpart
        genfile="gensort"
        client = boto3.client('s3', 'us-west-2')
        client.download_file('yupeng-pywren', genfile, '/tmp/gensort')
        logging.info("Downloaded the file")
        subprocess.check_output(["chmod", "a+x", "/tmp/gensort"])

        for i in range(0, 5):
            number_of_records = 1250 * 1000
            begin = key * number_of_records
            data = subprocess.check_output(["/tmp/gensort",
                                            "-b" + str(begin),
                                            str(number_of_records),
                                            "/dev/stdout"])
            keyname = "input/part-" + str(key)
            m = hashlib.md5()
            m.update(keyname.encode('utf-8'))
            logging.info("Here is the key! " + str(key))
            randomized_keyname = "input/" + m.hexdigest()[:8] + "-part-" + str(key)
            put_start = time.time()
            client.put_object(Body=data, Bucket="yupeng-pywren-0", Key=randomized_keyname)
            put_end = time.time()
            logger.info(str(key) + " th object uploaded using " + str(put_end - put_start) + " seconds.")
            gc.collect()
            key = key + 1


    wrenexec = pywren.default_executor()
    num_of_files = int(sys.argv[1])
    print("Generating " + str(62.5 * int(num_of_files)) + " Mb input dataset.")
    passed_tasks = range(0, num_of_files, 5)

    fut = wrenexec.map(run_command, passed_tasks)

    pywren.wait(fut)
    res = [f.result() for f in fut]
    print(res)
