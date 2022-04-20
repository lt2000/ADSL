import pickle
import json
from tkinter import W
import os
# input_keys_file = './input_keys.txt'
# keys_f = open(input_keys_file, 'r')
# keynames = [x.strip() for x in keys_f.readlines()]
# print(keynames)

# res = pickle.load(open('./word_count_shuffle_0_0', 'rb'))
# print(res)

input_file = './text_chunks'


# data = open(input_file, 'r')
# for line in data:
#     new_dict = json.loads(line)
#     for word in new_dict['reviewText'].split():
#         print(word)

filelist = os.listdir(input_file)
with open('./input_keys_file.txt', 'w') as f:
    for idx in range(len(filelist)):
        f.write('lithops-data-little' + filelist[idx] + '\n')    