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

from unittest import result
import uuid
import numpy as np
import time
import hashlib
import pickle
import click

from lithops import FunctionExecutor, Storage



class RandomDataGenerator(object):
    """
    A file-like object which generates random data.
    1. Never actually keeps all the data in memory so
    can be used to generate huge files.
    2. Actually generates random data to eliminate
    false metrics based on compression.

    It does this by generating data in 1MB blocks
    from np.random where each block is seeded with
    the block number.
    """

    def __init__(self, bytes_total):
        self.bytes_total = bytes_total
        self.pos = 0
        self.current_block_id = None
        self.current_block_data = ""
        self.BLOCK_SIZE_BYTES = 1024*1024
        self.block_random = np.random.randint(0, 256, dtype=np.uint8,
                                              size=self.BLOCK_SIZE_BYTES)

    def __len__(self):
        return self.bytes_total

    @property
    def len(self):
        return self.bytes_total 

    def tell(self):
        return self.pos

    def seek(self, pos, whence=0):
        if whence == 0:
            self.pos = pos
        elif whence == 1:
            self.pos += pos
        elif whence == 2:
            self.pos = self.bytes_total - pos

    def get_block(self, block_id):
        if block_id == self.current_block_id:
            return self.current_block_data

        self.current_block_id = block_id
        self.current_block_data = (block_id + self.block_random).tostring()
        return self.current_block_data

    def get_block_coords(self, abs_pos):
        block_id = abs_pos // self.BLOCK_SIZE_BYTES
        within_block_pos = abs_pos - block_id * self.BLOCK_SIZE_BYTES
        return block_id, within_block_pos

    def read(self, bytes_requested):
        remaining_bytes = self.bytes_total - self.pos
        if remaining_bytes == 0:
            return b''

        bytes_out = min(remaining_bytes, bytes_requested)
        start_pos = self.pos

        byte_data = b''
        byte_pos = 0
        while byte_pos < bytes_out:
            abs_pos = start_pos + byte_pos
            bytes_remaining = bytes_out - byte_pos

            block_id, within_block_pos = self.get_block_coords(abs_pos)
            block = self.get_block(block_id)
            # how many bytes can we copy?
            chunk = block[within_block_pos:within_block_pos + bytes_remaining]

            byte_data += chunk

            byte_pos += len(chunk)

        self.pos += bytes_out

        return byte_data


runtime_bins = np.linspace(0, 50, 50)


def write(backend, storage, bucket_name, kb_per_file, number, key_prefix):

    def write_object(key_name, storage):
        bytes_n = kb_per_file * 1024
        d = RandomDataGenerator(bytes_n)
        print(key_name)
        start_time = time.time()
        storage.put_object(bucket_name, key_name, d)
        end_time = time.time()

        return str(end_time - start_time)

    # create list of random keys
    keynames = [key_prefix + str(uuid.uuid4().hex.upper()) for unused in range(number)]

    fexec = FunctionExecutor(backend=backend, storage=storage, runtime_memory=1536)
    
    worker_futures = fexec.map(write_object, keynames)
    results = fexec.get_result()
    

    worker_stats = [f.stats for f in worker_futures]


    res = {'worker_stats': worker_stats,
           'bucket_name': bucket_name,
           'keynames': keynames,
           'results': results}

    return res


def read(backend, storage, bucket_name, number, keylist_raw, read_times):

    blocksize = 1024

    def read_object(key_name, storage):
        m = hashlib.md5()
        bytes_read = 0
    
        start_time = time.time()
        for unused in range(read_times):
            fileobj = storage.get_object(bucket_name, key_name, stream=True)
            try:
                buf = fileobj.read(blocksize)
                while len(buf) > 0:
                    bytes_read += len(buf)
                    m.update(buf)
                    buf = fileobj.read(blocksize)
            except Exception as e:
                print(e)
                pass
        end_time = time.time()

        return {'read_latency': end_time - start_time}

    if number == 0:
        keynames = keylist_raw
    else:
        keynames = [keylist_raw[i % len(keylist_raw)] for i in range(number)]

    fexec = FunctionExecutor(backend=backend, storage=storage, runtime_memory=1536)
    
    worker_futures = fexec.map(read_object, keynames)
    results = fexec.get_result()
    

    
    worker_stats = [f.stats for f in worker_futures]

    res = {'worker_stats': worker_stats,
           'results': results}

    return res


def delete_temp_data(storage, bucket_name, keynames):
    print('Deleting temp files...')
    storage = Storage(backend=storage)
    storage.delete_objects(bucket_name, keynames)
    print('Done!')


@click.group()
def cli():
    pass

@cli.command('run')
@click.option('--backend', '-b', default='aws_lambda', help='compute backend name', type=str)
@click.option('--storage', '-s', default='aws_s3', help='storage backend name', type=str)
@click.option('--bucket_name', help='bucket to save files in')
@click.option('--kb_per_file', help='MB of each object', type=int)
@click.option('--number', default=1, help='number of files', type=int)
@click.option('--key_prefix', default='', help='Object key prefix')
@click.option('--outdir', default='.', help='dir to save results in')
@click.option('--name', '-n', default=None, help='filename to save results in')
@click.option('--read_times', default=1, help="number of times to read each COS key")
def run(backend, storage, bucket_name, kb_per_file, number, key_prefix, outdir, name, read_times):
    if name is None:
        name = number
    
    print('Executing Write Test:')
    if bucket_name is None:
        raise ValueError('You must provide a bucket name within --bucket_name parameter')
    res_write = write(backend, storage, bucket_name, kb_per_file, number, key_prefix)
    print('write latency...')
    print(res_write['results'])
    with open('{}/{}kb_write_latency.txt'.format(outdir, name), 'a+') as f:
        f.write(res_write['results'])
    print('Sleeping 20 seconds...')
    time.sleep(20)
    print('Executing Read Test:')
    bucket_name = res_write['bucket_name']
    keynames = res_write['keynames']
    res_read = read(backend, storage, bucket_name, number, keynames, read_times)
    print('read latency...')
    with open('{}/{}kb_read_latency.txt'.format(outdir, name), 'a+') as f:
        f.write(str(res_read['results']['read_latency']))

    delete_temp_data(storage, bucket_name, keynames)    
   

if __name__ == '__main__':
    cli()
