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

from calendar import c
from importlib.metadata import files
import uuid
import numpy as np
import time
import hashlib
import pickle
import click

from lithops import FunctionExecutor, Storage
from plots import create_execution_histogram, create_rates_histogram, create_agg_bdwth_plot


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


def write(backend, storage, bucket_name, mb_per_file, number, files, key_prefix):

    def write_object(key_name, storage):
        bytes_n = mb_per_file * 1024
        d = RandomDataGenerator(bytes_n)
        print(key_name)
        start_time = time.time()
        for idx in range(len(key_name)):
            storage.put_object(bucket_name, key_name[idx], d)
            time.sleep(5)
        end_time = time.time()

        mb_rate = (bytes_n * files) /(end_time-start_time)/1e6
        print('MB Rate: '+str(mb_rate))

        return {'start_time': start_time, 'end_time': end_time, 'mb_rate': mb_rate}

    # create list of random keys
    keynames = []
    for unused in range(number):
        keynames.append([key_prefix + str(uuid.uuid4().hex.upper()) for unused in range(files)])
    print(keynames)

    fexec = FunctionExecutor(backend=backend, storage=storage, runtime_memory=1536)
    start_time = time.time()
    worker_futures = fexec.map(write_object, keynames)
    results = fexec.get_result()
    end_time = time.time()

    worker_stats = [f.stats for f in worker_futures]
    total_time = end_time-start_time

    res = {'start_time': start_time,
           'total_time': total_time,
           'worker_stats': worker_stats,
           'bucket_name': bucket_name,
           'keynames': keynames,
           'results': results}

    return res


def read(backend, storage, bucket_name, number, keylist_raw, read_times):

    blocksize = 1024

    def read_object(key_name, storage):
        m = hashlib.md5()
        bytes_read = 0
        print(key_name)

        start_time = time.time()
        for idx in range(len(key_name)):
            for unused in range(read_times):
                fileobj = storage.get_object(bucket_name, key_name[idx], stream=True)
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

    if number == 0:
        keynames = keylist_raw
    else:
        keynames = [keylist_raw[i % len(keylist_raw)] for i in range(number)]

    fexec = FunctionExecutor(backend=backend, storage=storage, runtime_memory=1536)
    start_time = time.time()
    worker_futures = fexec.map(read_object, keynames)
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
    create_execution_histogram(res_write, res_read, "{}/{}_execution.png".format(outdir, name))
    create_rates_histogram(res_write, res_read, "{}/{}_rates.png".format(outdir, name))
    create_agg_bdwth_plot(res_write, res_read, "{}/{}_agg_bdwth.png".format(outdir, name))


@click.group()
def cli():
    pass


@cli.command('write')
@click.option('--backend', '-b', default='aws_lambda', help='compute backend name', type=str)
@click.option('--storage', '-s', default='aws_s3', help='storage backend name', type=str)
@click.option('--bucket_name', help='bucket to save files in')
@click.option('--mb_per_file', help='MB of each object', type=int)
@click.option('--number', help='number of functions', type=int)
@click.option('--files', default=1, help='write files number of each function', type=int)
@click.option('--key_prefix', default='', help='Object key prefix')
@click.option('--outdir', default='.', help='dir to save results in')
@click.option('--name', default=None, help='filename to save results in')
def write_command(backend, storage, bucket_name, mb_per_file, number, files, key_prefix, outdir, name):
    if name is None:
        name = number
    if bucket_name is None:
        raise ValueError('You must provide a bucket name within --bucket_name parameter')
    res_write = write(backend, storage, bucket_name, mb_per_file, number, files, key_prefix)
    pickle.dump(res_write, open('{}/{}_write.pickle'.format(outdir, name), 'wb'), -1)


@cli.command('read')
@click.option('--backend', '-b', default='aws_lambda', help='compute backend name', type=str)
@click.option('--storage', '-s', default='aws_s3', help='storage backend name', type=str)
@click.option('--key_file', default=None, help="filename generated by write command, which contains the keys to read")
@click.option('--number', help='number of objects to read, 0 for all', type=int, default=0)
@click.option('--outdir', default='.', help='dir to save results in')
@click.option('--name', default=None, help='filename to save results in')
@click.option('--read_times', default=1, help="number of times to read each COS key")
def read_command(backend, storage, key_file, number, outdir, name, read_times):
    if name is None:
        name = number
    if key_file:
        res_write = pickle.load(open(key_file, 'rb'))
    else:
        res_write = pickle.load(open('{}/{}_write.pickle'.format(outdir, name), 'rb'))
    bucket_name = res_write['bucket_name']
    keynames = res_write['keynames']
    res_read = read(backend, storage, bucket_name, number, keynames, read_times)
    pickle.dump(res_read, open('{}/{}_read.pickle'.format(outdir, name), 'wb'), -1)


@cli.command('delete')
@click.option('--key_file', default=None, help="filename generated by write command, which contains the keys to read")
@click.option('--outdir', default='.', help='dir to save results in')
@click.option('--name', default='os_benchmark', help='filename to save results in')
def delete_command(key_file, outdir, name):
    if key_file:
        res_write = pickle.load(open(key_file, 'rb'))
    else:
        res_write = pickle.load(open('{}/{}_write.pickle'.format(outdir, name), 'rb'))
    bucket_name = res_write['bucket_name']
    keynames = res_write['keynames']
    delete_temp_data(bucket_name, keynames)


@cli.command('run')
@click.option('--backend', '-b', default='aws_lambda', help='compute backend name', type=str)
@click.option('--storage', '-s', default='aws_s3', help='storage backend name', type=str)
@click.option('--bucket_name', help='bucket to save files in')
@click.option('--mb_per_file', help='MB of each object', type=int)
@click.option('--number', help='number of files', type=int)
@click.option('--files', default=1, help='write files number of each function', type=int)
@click.option('--key_prefix', default='', help='Object key prefix')
@click.option('--outdir', default='.', help='dir to save results in')
@click.option('--name', '-n', default=None, help='filename to save results in')
@click.option('--read_times', default=1, help="number of times to read each COS key")
def run(backend, storage, bucket_name, mb_per_file, number, files, key_prefix, outdir, name, read_times):
    if name is None:
        name = number

    if True:
        print('Executing Write Test:')
        if bucket_name is None:
            raise ValueError('You must provide a bucket name within --bucket_name parameter')
        res_write = write(backend, storage, bucket_name, mb_per_file, number, files, key_prefix)
        pickle.dump(res_write, open('{}/{}_write.pickle'.format(outdir, name), 'wb'), -1)
        print('Sleeping 20 seconds...')
        time.sleep(20)
        print('Executing Read Test:')
        bucket_name = res_write['bucket_name']
        keynames = res_write['keynames']
        res_read = read(backend, storage, bucket_name, number, keynames, read_times)
        pickle.dump(res_read, open('{}/{}_read.pickle'.format(outdir, name), 'wb'), -1)

        for idx in range(len(keynames)):
            delete_temp_data(storage, bucket_name, keynames[idx])
    else:
        res_write = pickle.load(open('{}/{}_write.pickle'.format(outdir, name), 'rb'))
        res_read = pickle.load(open('{}/{}_read.pickle'.format(outdir, name), 'rb'))
    create_plots(res_write, res_read, outdir, name)


if __name__ == '__main__':
    cli()

['18754FA3643849199AB944665C04C31E', '430B2B2DE45A488C9E502309013572BB', '193D992F848345C5B8908321C19468D7', '5CDAA85046CA471EAE79E4A8447FC237', '71C923442C5E4531B1EC4F9CF70FF541', '0D410A0B2447437A8EC595AE0E2C86B5', '0EE2A899F5E149E68DB6068139B4D688', 'FE429D5E80844D33A4B4473A414D46A2', 'C564962D76F943B1BE306227F534274F', '28FF7AB2CE4F470FB63210A766E7999D']
['8F35449664AB4637B2D743480F2B61DB', 'A19340C11BD24258A0AEB8684568EE7D', 'FBC8C422BE1A4C5B9A519F3E4C7E0457', '6515E1A7B6B6460D8F1B0C6DC11EA304', '2AEDFCE7E5A94910B75472ADF945BDEB', 'F7E2AF1E80654AA68B20889FDD29BBE9', '5012644568304D5A847B0FE389FB8A12', '2E11A65CF8CB43B29DAF2C047B9B1DFC', '8BCDA5888C5845FDA207D141D98C8C09', '0ED629EADFA44D94A3F3A6053967C42F']
['9E3A9DCE90C1422888C7E429F0A39B00', '2E48DD1CD11B493DBF862FCAD15E641C', 'F7D71F0D03B6438897E82D6B3609E1A4', '236E39A4EA5F4237BBBDDD5628332A22', 'E9051C91215C4E59B1045CEC26F87632', '1081972EFB3F47F2BB6748BAEA97178A', 'AFB5F7235E6642D292CE02DC727EF802', '2D0F660A5DDF453CBB151394F4F37D44', 'D5DCE29D5CEE4DAB8DAC63A3E517B18D', '962FC99FA05E4BC988EEE910DE871D46']
['96BFED9915634E26A767D19C0C5DF08E', '238BFEB40ADC462AAE216D28A5CFE6EA', '060244A5101F42EB86E753168C9244F4', '77FF8035FFAA46B7B0D583D0122DE131', '53B9E69F6EB944ED99E15CD2833ED832', '1890306CB35F44B7814504F2CB430CE9', 'AA181CBFED5744FBBF8D9D101FFD3EB1', '3523DC9D5C254603ACA31C7964A0EF44', 'EFB3010EAE354E89A2595CB248D0CFE7', 'F4D70FB2969C43B8BCF6D1418E0359C5']
['7B24AE546D56473497E278569DDBE68A', '47D150CCAC934156BC0610B0B51D3360', '5301D133054C4CD9A259CCE6677E898D', '35F81005FEC04370B36BC86BF4782C58', '8211B34501D5456DB7E4144AA28E1E57', 'CC271A1ADAE442FEA0A719736C2728E8', 'CEAFCC4A2D56454EB3BFE148510224F6', '8C8C91DDA24A475F81DB7689141BC207', '297B24C8BC154DC3A9453C97C524F422', 'A1A627A1BA0D43E88018285975A62E55']
['C5C6E3CEAECF4A6490ABFD3E1367640C', '10A54AC91B474CCD9D587DFAC1C099AE', '036AC4F1C07C420EBDEA250FF45DB057', '904FD8D9913B4858B7B522C3A67523D1', 'CEA8E4A67F304FCB9F0FD86E3E440479', 'F87CD753E94540E8B396CA2ED0E22DB7', '434DCB8702F04409A64DA900DDF79D0B', '6235504D439D454CA408568A6CBD9BDA', 'B14275674C614032A6DA310262BC8EB2', '6C9BCB6701784B9887A16912CBE768BF']
['513773C7F97444ECAE70456A034A85BB', '78B8AD33BED643B9BBC35F56D952BE54', 'DA5EF7D6C3574027ADE5961E6EF34D6E', '353C8A6C113443FD850EDC0517DD00D2', '4F6B0655A9414D7AA339FFEB960F903F', 'C16FD875A2F74682B3E932BC8FDCDFF9', '72B6D8BF19714ADC8742F31E4EB41100', '5C6BCB07BEDF4DC0AB6F048C31A28CA7', '630677D7B3FE473E8E97A9D00CA87B6E', 'C3E23CE0ABF946C4BA67521655811528']
['9AEA4F82D4A04984A174998D6E614475', 'A5A6BB4143F84F21977EDAA68B097030', '42740309501D4FA7A56B7C70AE94269E', '09E4872AF37C470FAE5B12D8A9C35653', '604FA7BAC8E64696A3DB819ABE74384D', '0D6FBE824F5A44B7815907AA87C65171', '00C2FD7472964A078BF18C5F50F4A8D6', 'C159F2EAD8F748669B47C3A38D8F7182', 'AFA128D9E51040B99DE5DEBD424E0D4E', '3F5755309C6F4C15A669BD1C7C42CA72']
['A4D57C0605424A369AE1BCED935A0A89', '6A62406714E941B78D0D98263D874AA4', '41A36BC144D34B55AAE380A9F8250E3D', 'ABBC45B6943043C7B2587D2E9CB5FC64', '029F9A7062A7404E97FB9B2BF529BA70', 'F732C0161F664FE0AEBCDC5E39B91A53', 'D71AA77CA4664EC69B8766F90F795C4C', '684A72878282487A8A112F03B8BEB69B', '2492F05E59114A1BBA2691E5210EAC70', '32D9BF93683D4FB18FF3A1529C77A7D2']
['5B4586CBAED24FB8A495B2CB7BD5A63B', '698E23B8658D4BA2AB81B07A3DF984A3', '5B64060850A54CF79C8C299E7D471048', '83097951384C42C98B6D784B6B0D02F8', 'CE393F70D7154F01A7ACBA5D3073EFB2', '335FE879922E40F9934E38A3441C249F', 'F40C7E6544CC4640AA6C28DDED17AB7A', 'C53DAE50A9C748349B7AABE27C8D46F0', '784AE25C33124D819840ED6DBC9D032D', '95C5846D483D4B1591EE61BC9F8D178A']
