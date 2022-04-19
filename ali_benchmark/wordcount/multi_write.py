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


import numpy as np
import click
from lithops import FunctionExecutor


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


def write(backend, storage, bucket_name, mb_per_file, number, key_prefix):

    def write_object(work_id, storage):
        bytes_n = mb_per_file * 1024**2
        for idx in range(number):
            d = RandomDataGenerator(bytes_n)
            key_name = key_prefix + '_' + str(work_id) + '_' + str(idx)
            storage.put_object(bucket_name, key_name, d)
    

        return {'work_id': work_id}


    fexec = FunctionExecutor(backend=backend, storage=storage, runtime_memory=512)
   
    fexec.map(write_object, [1,2])
    results = fexec.get_result()

    return results


@click.group()
def cli():
    pass


@cli.command('write')
@click.option('--backend', '-b', default='aws_lambda', help='compute backend name', type=str)
@click.option('--storage', '-s', default='aws_s3', help='storage backend name', type=str)
@click.option('--bucket_name', help='bucket to save files in')
@click.option('--mb_per_file', help='MB of each object', type=int)
@click.option('--number', help='number of files', type=int)
@click.option('--key_prefix', default='', help='Object key prefix')
def write_command(backend, storage, mb_per_file, bucket_name, number, key_prefix):

    res_write = write(backend, storage, bucket_name, mb_per_file, number, key_prefix)
    print(res_write)


if __name__ == '__main__':
    cli()
