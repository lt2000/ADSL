"""
Wordcount example that stores intermediate data in S3

$ python s3_wordcount.py wordcount --input_bucket_name=  --intermediate_bucket_name=shivaram-pywren-test --num_reducers=10

"""

import time
import boto3 
import botocore
import uuid
from io import BytesIO
from gzip import GzipFile
from collections import Counter

import pywren
import subprocess
import logging
import sys
import hashlib
import cPickle as pickle
import click
import exampleutils

from collections import deque

@click.group()
def cli():
    pass


@cli.command()
@click.option('--input_bucket_name', help='bucket to read amazon inputs from')
@click.option('--input_keys_file', help='file containing list of input keys in the bucket')
@click.option('--intermediate_bucket_name', help='bucket to save shuffle data in')
@click.option('--shuffle_key_prefix', help='key prefix for shuffle blocks', default='word_count_shuffle')
@click.option('--output_bucket_name', help='bucket to save output data in')
@click.option('--output_key_prefix', help='key prefix for output blocks', default='word_count_output')
@click.option('--num_reducers', help="Number of reducers", type=int)
@click.option('--region', default='us-west-2', help="AWS Region")
@click.option('--map_outfile', default='s3_wordcount.map.output.pickle', 
              help='filename to save map results in')
@click.option('--red_outfile', default='s3_wordcount.reduce.output.pickle', 
              help='filename to save reduce results in')
@click.option('--bsp/--no-bsp', default=True,
              help='whether we should wait for the mappers to finish before launching reducers')
def wordcount(input_bucket_name, input_keys_file,
        intermediate_bucket_name, shuffle_key_prefix,
        output_bucket_name, output_key_prefix,
        num_reducers, region, map_outfile, red_outfile, bsp):

    print "input_bucket_name =", input_bucket_name
    print "intermediate_bucket_name =", intermediate_bucket_name
    print "num_reducers=", num_reducers

    keys_f = open(input_keys_file, 'r')
    keynames = [x.strip() for x in keys_f.readlines()]
    num_mappers = len(keynames)
    map_ids = {}
    cur = 0
    for m in keynames:
      map_ids[m] = cur
      cur = cur + 1

    def parse(gzip_handle):
      for l in gzip_handle:
        yield eval(l)

    def map_command(keyname):
        client = boto3.client('s3', region)

        bytes_read = exampleutils.key_size(input_bucket_name, keyname)
        print "Reading from ", input_bucket_name, " key ", keyname, " size ", bytes_read 
        sys.stdout.flush()

        # map from reducer_id to map of (word, count) 
        # TODO: To make this more general introduce a `emit(key, value)` primitive.
        output_buckets = {}
        for i in xrange(0, num_reducers):
          output_buckets[i] = Counter({})

        t1 = time.time()
        gz_file = client.get_object(Bucket=input_bucket_name, Key=keyname)
        bytestream = BytesIO(gz_file['Body'].read())
        t_download = time.time()
        print "Download took " + str(t_download - t1)
        sys.stdout.flush()

        docs_handle = GzipFile(None, 'rb', fileobj=bytestream)

        for doc in parse(docs_handle):
            words = doc['reviewText'].split(' ')
            for w in words:
              bucket = hash(w) % num_reducers
              bucket_dict = output_buckets[bucket]
              bucket_dict[w] += 1

        t2 = time.time()

        bytes_written = 0
        my_worker_id = map_ids[keyname]

        for i in xrange(0, num_reducers):
          key = shuffle_key_prefix + '_' + str(my_worker_id) + '_' + str(i)
          d = pickle.dumps(output_buckets[i])
          bytes_written += len(d)
          client.put_object(Bucket=intermediate_bucket_name,
                            Key = key,
                            Body = d)

        t3 = time.time()
        print "Map and bucket took " + str(t2-t1) + " write took " + str(t3-t2)

        return t1, t2, bytes_read, t3, bytes_written, (t_download - t1)


    def merge_counters(base, other):
      for (k, v) in other.iteritems():
        base[k] += v

    def reduce_command(my_worker_id):
        s3 = boto3.resource('s3')
        client = boto3.client('s3', region)

        t1 = time.time()
        blocks_to_read = list(range(num_mappers))
        blocks_to_read = deque(blocks_to_read)

        download_file_name = '/tmp/shufflefile.pickle'
        word_count_dict = Counter({})
        bytes_read = 0
        download_time = 0
        merge_time = 0

        while blocks_to_read:
          block_id = blocks_to_read.pop()
          key = shuffle_key_prefix + '_' + str(block_id) + '_' + str(my_worker_id)
          t_download_start = time.time()

          try:
            intermediate_f = client.get_object(Bucket=intermediate_bucket_name, Key=key)
            intermediate_f_contents = BytesIO(intermediate_f['Body'].read())

            t_download_end = time.time()
            download_time += (t_download_end - t_download_start)
            d = pickle.load(intermediate_f_contents)
            merge_counters(word_count_dict, d)
            t_merge_end = time.time()
            merge_time += (t_merge_end - t_download_end)
          except botocore.exceptions.ClientError as e:
            # print 'Failed to get ', block_id, ' error ', e
            blocks_to_read.append(block_id)

        t2 = time.time()

        d = pickle.dumps(word_count_dict)
        bytes_written = len(d)
        client.put_object(Bucket=output_bucket_name,
                          Key = output_key_prefix + '_' + str(my_worker_id),
                          Body = d)

        t3 = time.time()
        print "Read and merge took " + str(t2-t1) + " write took " + str(t3-t2) + \
              " download " + str(download_time) + " merge " + str(merge_time)
        return t1, t2, bytes_read, t3, bytes_written, download_time, merge_time

    wrenexec = pywren.default_executor()

    map_fut = wrenexec.map(map_command, keynames)

    if bsp:
      map_res = [f.result() for f in map_fut]
      red_fut = wrenexec.map(reduce_command, range(num_reducers))
    else:
      red_fut = wrenexec.map(reduce_command, range(num_reducers))
      map_res = [f.result() for f in map_fut]

    red_res = [f.result() for f in red_fut]
    
    pickle.dump(map_res, open(map_outfile, 'w'))
    pickle.dump(red_res, open(red_outfile, 'w'))

if __name__ == '__main__':
    cli()