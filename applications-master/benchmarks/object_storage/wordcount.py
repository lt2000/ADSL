#
# Copyright Cloudlab URV 2020
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from asyncio import streams
from typing import Counter
import time
import pickle
import hashlib
from io import BytesIO
import click

from lithops import FunctionExecutor




def mapper(backend, storage, bucket_name, intermediate_bucket_name, num_reducers, shuffle_key_prefix, keynames):

    map_ids = {}
    cur = 0
    for m in keynames:
      map_ids[m] = cur
      cur = cur + 1
    def split_count(key_name, storage):
        output_buckets = {}
        for idx in range(0, num_reducers):
            output_buckets[idx] = Counter({})

        t1 = time.time()    
        fileobj = storage.get_object(bucket_name, key_name, stream=True)
        data = fileobj.read()
        t2 = time.time()
        wlist=[]
        blist=[]
        for line in data.splitlines():
            for word in line.decode('utf-8').split():
                wlist.append(word)
                digset = hashlib.md5(word.encode('utf-8')).hexdigest()
                w = int(digset, 16)
                bucket = hash(w) % num_reducers
                blist.append(bucket)
                bucket_dict = output_buckets[bucket]
                bucket_dict[word] += 1

        t3 = time.time()
        my_worker_id = map_ids[key_name]
        for idx in range(0, num_reducers):
            key = shuffle_key_prefix + '_' + str(my_worker_id) + '_' + str(idx)
            d = pickle.dumps(output_buckets[idx])
            storage.put_object(intermediate_bucket_name, key, d)
        t4 = time.time()

        return [{str(my_worker_id): [wlist,blist]}, output_buckets]

    fexec = FunctionExecutor(backend=backend, storage=storage, runtime_memory=512)
    fexec.map(split_count, keynames)
    res = fexec.get_result()
    
    return res


def reducer(backend, storage, bucket_name, intermediate_bucket_name, num_mappers, num_reducers, shuffle_key_prefix):

    def merge_counters(base, other):
        for (k, v) in other.items():
            base[k] += v

    def merge_count(worker_id, storage):
        word_count_dict = Counter({})
        dlist=[]
        elist=[]
        for idx in range(0, num_mappers):
            try:
                key = shuffle_key_prefix + '_' + str(idx) + '_' + str(worker_id)
                fileobj = storage.get_object(intermediate_bucket_name, key, stream=True)
                d = pickle.loads(fileobj.read())
                dlist.append(d)
                merge_counters(word_count_dict, d)
            except Exception as e:
                print("except:",e)
                elist.append(e)
        
        key = shuffle_key_prefix + '_' + str(worker_id)
        d = pickle.dumps(word_count_dict)
        storage.put_object(bucket_name, key, d)

        return {str(worker_id): [dlist,elist]}, word_count_dict
    
    fexec = FunctionExecutor(backend=backend, storage=storage, runtime_memory=512)
    fexec.map(merge_count, range(num_reducers))
    res = fexec.get_result()

    return res


@click.group()
def cli():
    pass

@cli.command('wordcount')
@click.option('--backend', '-b', default='aliyun_fc', help='compute backend name', type=str)
@click.option('--storage', '-s', default='aliyun_oss', help='storage backend name', type=str)
@click.option('--bucket_name', default='lithops-data-little', help='bucket to read inputs from and write outputs to', type=str)
@click.option('--input_keys_file', default='./input_keys.txt', help='file containing list of input keys in the bucket', type=str)
@click.option('--intermediate_bucket_name', default='data-lithops', help='bucket to save files in')
@click.option('--shuffle_key_prefix', help='key prefix for shuffle blocks', default='word_count_shuffle')
@click.option('--num_reducers', default=3, help='number of reducers', type=int)
@click.option('--outdir', default='.', help='dir to save results in')
@click.option('--name', '-n', default=None, help='filename to save results in')
def wordcount(backend, storage, bucket_name, intermediate_bucket_name, input_keys_file, num_reducers, shuffle_key_prefix, outdir, name):
    print("input_bucket_name =", bucket_name)
    print("intermediate_bucket_name =", intermediate_bucket_name)
    print("num_reducers=", num_reducers)

    if name is None:
        name = num_reducers

    keys_f = open(input_keys_file, 'r')
    keynames = [x.strip() for x in keys_f.readlines()]
    num_mappers = len(keynames)
    print('Executing Map Task...:')
    if bucket_name is None:
        raise ValueError('You must provide a bucket name within --bucket_name parameter')
    res_map = mapper(backend, storage, bucket_name, intermediate_bucket_name, num_reducers, 
                     shuffle_key_prefix, keynames)
    # print('intermediate results...')
    # print(res_map)

    print('Sleeping 5 seconds...')
    time.sleep(5)
    print('Executing Reduce Task:')
    res_reduce = reducer(backend, storage, bucket_name, intermediate_bucket_name, num_mappers, 
                         num_reducers, shuffle_key_prefix)
    print('wordcount results...')
    print(res_reduce)

if __name__ == '__main__':
    cli()
