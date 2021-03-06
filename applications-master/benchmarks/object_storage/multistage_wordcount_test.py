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

from re import T
from typing import Counter
import time
import pickle
import hashlib
import click
import json
from lithops import FunctionExecutor, Storage




def mapper(backend, storage, bucket_name, intermediate_bucket_name, num_reducers, shuffle_key_prefix, keynames, p, f):

    map_ids = {}
    cur = 0
    for m in keynames:
      map_ids[m] = cur
      cur = cur + 1
    def split_count(key_name, storage):
        output_buckets = {}
        start = p * (map_ids[key_name] // (len(map_ids) // f))
        end = start + p
        for idx in range(start, end):
            output_buckets[idx] = Counter({})

        t1 = time.time()    
        fileobj = storage.get_object(bucket_name, key_name, stream=True)
        data = fileobj.read()
        t2 = time.time()
        
        for line in data.splitlines():
            
            try:
                for word in json.loads(line.decode('utf-8'))['reviewText'].split():
                    digset = hashlib.md5(word.encode('utf-8')).hexdigest()
                    w = int(digset, 16)
                    bucket = (hash(w) % num_reducers) // (num_reducers // p) + start
                    
                    bucket_dict = output_buckets[bucket]
                    bucket_dict[word] += 1
            except Exception as e:
                pass
                
        t3 = time.time()
        my_worker_id = map_ids[key_name]
        shuffle_key_prefix = 'Shuffle-Stage-1/'
        for idx in output_buckets.keys():
            key = shuffle_key_prefix + 'mapper' + str(my_worker_id) + '_' + 'combiner' + str(idx)
            d = pickle.dumps(output_buckets[idx])
            storage.put_object(intermediate_bucket_name, key, d)
        t4 = time.time()
        read_input_time = t2 -t1
        split__time = t3 -t2
        shuffle_time = t4 - t3
        return { map_ids[key_name]: output_buckets}

    fexec = FunctionExecutor(backend=backend, storage=storage, runtime_memory=512)
    fexec.map(split_count, keynames)
    res = fexec.get_result()
    
    return res

def combiner(backend, storage, bucket_name, intermediate_bucket_name, num_mappers, num_reducers, shuffle_key_prefix, p, f):

    def merge_counters(base, other):
        for (k, v) in other.items():
            base[k] += v

    def merge_count(worker_id, storage):
        word_count_dict = Counter({})
        shuffle_time = 0
        merge_time = 0
        start_mapper = (worker_id // p) * (num_mappers // f)
        end_mapper = start_mapper + (num_mappers // f)
        shuffle_key_prefix = 'Shuffle-Stage-1/'
        for idx in range(start_mapper, end_mapper):
            try:
                t1 = time.time()
                key = shuffle_key_prefix + 'mapper' + str(idx) + '_' + 'combiner' + str(worker_id)
                fileobj = storage.get_object(intermediate_bucket_name, key, stream=True)
                t2 = time.time()
                d = pickle.loads(fileobj.read())
                merge_counters(word_count_dict, d)
                t3 = time.time()
            except Exception as e:
                print("except:",e)
            shuffle_time += (t2- t1)
            merge_time += (t3 - t2)
        
        output_buckets = {}
        start = (worker_id % p) * f
        end = start + f
        for idx in range(start, end):
            output_buckets[idx] = Counter({})
        for (word, count) in word_count_dict.items():
                    digset = hashlib.md5(word.encode('utf-8')).hexdigest()
                    w = int(digset, 16)
                    bucket = hash(w) % num_reducers
                    bucket_dict = output_buckets[bucket]
                    bucket_dict[word] = count
        t1 = time.time()
        shuffle_key_prefix = 'Shuffle-Stage-2/'
        for idx in output_buckets.keys():
            key = shuffle_key_prefix + 'combiner' + str(worker_id) + '_' + 'reducer' + str(idx)
            d = pickle.dumps(output_buckets[idx])
            storage.put_object(intermediate_bucket_name, key, d)            
        t2 = time.time()
        write_output_time = t2 -t1
        #return {str(worker_id): word_count_dict}
        return { worker_id: output_buckets}

    fexec = FunctionExecutor(backend=backend, storage=storage, runtime_memory=512)
    fexec.map(merge_count, range(num_reducers))
    res = fexec.get_result()

    return res

def reducer(backend, storage, bucket_name, intermediate_bucket_name, num_mappers, num_reducers, shuffle_key_prefix, p, f):

    def merge_counters(base, other):
        for (k, v) in other.items():
            base[k] += v

    def merge_count(worker_id, storage):
        word_count_dict = Counter({})
        shuffle_time = 0
        merge_time = 0
        start_combiner = worker_id // f
        end_combiner = start_combiner + f*p
        shuffle_key_prefix = 'Shuffle-Stage-2/'
        for idx in range(start_combiner, end_combiner, p):
            try:
                t1 = time.time()
                key = shuffle_key_prefix + 'combiner' + str(idx) + '_' + 'reducer' + str(worker_id)
                fileobj = storage.get_object(intermediate_bucket_name, key, stream=True)
                t2 = time.time()
                d = pickle.loads(fileobj.read())
                merge_counters(word_count_dict, d)
                t3 = time.time()
            except Exception as e:
                print("except:",e)
            shuffle_time += (t2- t1)
            merge_time += (t3 - t2)
        t1 = time.time()
        key = shuffle_key_prefix + '_' + str(worker_id)
        d = pickle.dumps(word_count_dict)
        storage.put_object(bucket_name, key, d)
        t2 = time.time()
        write_output_time = t2 -t1
        #return {str(worker_id): word_count_dict}
        return {worker_id: word_count_dict}

    fexec = FunctionExecutor(backend=backend, storage=storage, runtime_memory=512)
    fexec.map(merge_count, range(num_reducers))
    res = fexec.get_result()

    return res

def delete_temp_data(storage, bucket_name, keynames):
    storage = Storage(backend=storage)
    storage.delete_objects(bucket_name, keynames)
    

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
@click.option('--num_reducers', default=4, help='number of reducers', type=int)
@click.option('--outdir', default='.', help='dir to save results in')
@click.option('--name', '-n', default=None, help='filename to save results in')
@click.option('--partitions', '-p', help=' p is the fraction of partitions each combiner reads', type=int)
@click.option('--files', '-f', help='f is the fraction of files each combiner reads', type=int)
def wordcount(backend, storage, bucket_name, intermediate_bucket_name, input_keys_file, num_reducers, shuffle_key_prefix, outdir, name, partitions, files):
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
                     shuffle_key_prefix, keynames, partitions, files)
    print('map results...')
    print(res_map)
    # with open('map_runtime_breakdown.json', 'w') as f:
    #     for idx in range(len(res_map)):
    #         json_str = json.dumps(res_map[idx])
    #         f.write(json_str + '\n')
    print('Sleeping 5 seconds...')
    time.sleep(5)

    print('Executing Combine Task:')
    res_combine = combiner(backend, storage, bucket_name, intermediate_bucket_name, num_mappers, 
                         num_reducers, shuffle_key_prefix, partitions, files)
    print('combine results...')
    print(res_combine)
    # with open('combine_runtime_breakdown.json', 'w') as f:
    #     for idx in range(len(res_combine)):
    #         json_str = json.dumps(res_combine[idx])
    #         f.write(json_str + '\n')
    print('Sleeping 5 seconds...')
    time.sleep(5)


    print('Executing Reduce Task:')
    res_reduce = reducer(backend, storage, bucket_name, intermediate_bucket_name, num_mappers, 
                         num_reducers, shuffle_key_prefix, partitions, files)
    print('reduce results...')
    print(res_reduce)
    # with open('reduce_runtime_breakdown.json', 'w') as f:
    #     for idx in range(len(res_reduce)):
    #         json_str = json.dumps(res_reduce[idx])
    #         f.write(json_str + '\n')

    # print("Delete Intermediate Data...")       
    # for i in range(num_mappers):
    #     keynames = []
    #     for j in range(num_reducers):
    #         keynames.append('word_count_shuffle_'+ str(i) +'_'+ str(j))
    #     delete_temp_data(storage, intermediate_bucket_name, keynames)   
    # keynames = []
    # print('Delete Output...')
    # for i in range(num_reducers):
    #     keynames.append('word_count_shuffle_'+ str(i))
    # delete_temp_data(storage, bucket_name, keynames)   
       

if __name__ == '__main__':
    cli()
