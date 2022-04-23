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


import uuid
import numpy as np
import time
import hashlib
import pickle
import click

from lithops import FunctionExecutor, Storage
from plots import  create_agg_bdwth_plot


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


def write(backend, storage, bucket_name, kb_per_worker, number, files, key_prefix):

    def write_object(work_id, storage):
        bytes_n = kb_per_worker * 1024
        d = RandomDataGenerator(bytes_n)
        start_time = time.time()
        for idx in range(files):
            key = key_prefix + '_' + str(work_id) + '_' + str(idx)
            storage.put_object(bucket_name, key, d.read(bytes_n//files))
        end_time = time.time()

        mb_rate = bytes_n /(end_time-start_time)/1e6
        print('MB Rate: '+str(mb_rate))

        return {'start_time': start_time, 'end_time': end_time, 'mb_rate': mb_rate}
    

    fexec = FunctionExecutor(backend=backend, storage=storage, runtime_memory=512)
    start_time = time.time()
    worker_futures = fexec.map(write_object, range(number))
    results = fexec.get_result()
    end_time = time.time()

    worker_stats = [f.stats for f in worker_futures]
    total_time = end_time-start_time

    res = {'start_time': start_time,
           'total_time': total_time,
           'worker_stats': worker_stats,
           'bucket_name': bucket_name,
           'results': results}

    return res


def read(backend, storage, bucket_name, number, files, read_times, key_prefix):

    blocksize = 1024

    def read_object(work_id, storage):
        m = hashlib.md5()
        bytes_read = 0

        start_time = time.time()
        for idx in range(files):
            for unused in range(read_times):
                key = key_prefix + '_' + str(work_id) + '_' + str(idx)
                fileobj = storage.get_object(bucket_name, key, stream=True)
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
        mb_rate = bytes_read/(end_time-start_time)/1e6
        print('MB Rate: '+str(mb_rate))

        return {'start_time': start_time, 'end_time': end_time, 'mb_rate': mb_rate, 'bytes_read': bytes_read}

    fexec = FunctionExecutor(backend=backend, storage=storage, runtime_memory=512)
    start_time = time.time()
    worker_futures = fexec.map(read_object, range(number))
    results = fexec.get_result()
    end_time = time.time()

    total_time = end_time-start_time
    worker_stats = [f.stats for f in worker_futures]

    res = {'start_time': start_time,
           'total_time': total_time,
           'worker_stats': worker_stats,
           'results': results}

    return res


def delete_temp_data(storage, bucket_name, keynames):
    print('Deleting temp files...')
    storage = Storage(backend=storage)
    storage.delete_objects(bucket_name, keynames)
    print('Done!')


def create_plots(res_write, res_read, outdir, name):
    create_agg_bdwth_plot(res_write, res_read, "{}/{}_agg_bdwth.png".format(outdir, name))


@click.group()
def cli():
    pass


@cli.command('run')
@click.option('--backend', '-b', default='aliyun_fc', help='compute backend name', type=str)
@click.option('--storage', '-s', default='aliyun_oss', help='storage backend name', type=str)
@click.option('--bucket_name', default='data-lithops', help='bucket to save files in')
@click.option('--kb_per_worker', help='KB of each object', type=int)
@click.option('--number', help='number of functions', type=int)
@click.option('--files', default=1, help='write files number of each function', type=int)
@click.option('--key_prefix', default='bandwidth', help='Object key prefix')
@click.option('--outdir', default='.', help='dir to save results in')
@click.option('--name', '-n', default=None, help='filename to save results in')
@click.option('--read_times', default=1, help="number of times to read each COS key")
def run(backend, storage, bucket_name, kb_per_worker, number, files, key_prefix, outdir, name, read_times):
    if name is None:
        name = number

    if True:
        print('Executing Write Test:')
        if bucket_name is None:
            raise ValueError('You must provide a bucket name within --bucket_name parameter')
        res_write = write(backend, storage, bucket_name, kb_per_worker, number, files, key_prefix)
        pickle.dump(res_write, open('{}/{}_write.pickle'.format(outdir, name), 'wb'), -1)
        print('Sleeping 20 seconds...')
        time.sleep(20)
        print('Executing Read Test:')
        res_read = read(backend, storage, bucket_name, number, files, read_times, key_prefix)
        pickle.dump(res_read, open('{}/{}_read.pickle'.format(outdir, name), 'wb'), -1)

        for i in range(number):
            keynames = []
            for j in range(files):
                keynames.append(key_prefix + '_' + str(i) + '_' + str(j))
            delete_temp_data(storage, bucket_name, keynames)
    else:
        res_write = pickle.load(open('{}/{}_write.pickle'.format(outdir, name), 'rb'))
        res_read = pickle.load(open('{}/{}_read.pickle'.format(outdir, name), 'rb'))
    create_plots(res_write, res_read, outdir, name)


if __name__ == '__main__':
    cli()

