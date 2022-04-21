import pickle
import json
from tkinter import W
import os

from pip import main

input_file = './text_chunks'

'''
读取input_keys
'''
# input_keys_file = './input_keys.txt'
# keys_f = open(input_keys_file, 'r')
# keynames = [x.strip() for x in keys_f.readlines()]
# print(keynames)


'''
 一个文件包含多个json文件的读取
'''
# data = open(input_file, 'r')
# for line in data:
#     new_dict = json.loads(line)
#     for word in new_dict['reviewText'].split():
#         print(word)

'''
获取文件夹所有文件名
'''
def gen_path(input_file):
    filelist = os.listdir(input_file)
    with open('./input_keys_file.txt', 'w') as f:
        for idx in range(len(filelist)):
            f.write('lithops-data-little' + filelist[idx] + '\n')    

'''
计算wordcount运行时间breakdown
'''
def breakdown(map_file, reduce_file):
    read_time = 0
    map_shuffle_time = 0
    split_time = 0
    reduce_shuffle_time = 0
    merge_time = 0
    write_time = 0
    with open(map_file, 'r') as data:
        count = 0
        for line in data:
            res = json.loads(line)
            count +=1
            read_time += res['Read Input Time']
            map_shuffle_time += res['Shuffle Time']
            split_time += res['Split Time']
        read_time /= count
        map_shuffle_time /= count
        split_time /= count

    with open(reduce_file, 'r') as data:
        count = 0
        for line in data:
            res = json.loads(line)
            count +=1
            write_time += res['Write Output Time']
            reduce_shuffle_time += res['Shuffle Time']
            merge_time += res['Merge Time']
        write_time /= count
        reduce_shuffle_time /= count
        merge_time /= count
    
    object_io_time = read_time + write_time
    shuffle_time = map_shuffle_time + reduce_shuffle_time
    computing_time = split_time + merge_time

    with open('./breakdown.txt', 'w') as f:
        f.write('Read Time: ' + str(read_time) + '\n')
        f.write('Write Time: ' + str(write_time) + '\n')
        
        f.write('Split Time: ' + str(split_time) + '\n')
        f.write('Merge Time: ' + str(merge_time) + '\n')

        f.write('Map Shuffle Time: ' + str(map_shuffle_time) + '\n')
        f.write('Reduce Shuffle Time: ' + str(reduce_shuffle_time) + '\n')

        f.write('Object IO Time: ' + str(object_io_time) + '\n')
        f.write('Computing Time: ' + str(computing_time) + '\n')
        f.write('Shuffle Time: ' + str(shuffle_time) + '\n')

if __name__ == 'main':
    map_file = './map_runtime_breakdown.json'
    reduce_file = './reduce_runtime_breakdown.json'
    breakdown(map_file, reduce_file)

