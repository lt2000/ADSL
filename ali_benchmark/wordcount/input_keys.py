import os

input_file = './text_chunks_10000'

filelist = os.listdir(input_file)
with open('./input_keys.txt', 'w') as f:
    for idx in range(len(filelist)):
        f.write('lithops-data/' + filelist[idx] + '\n')    