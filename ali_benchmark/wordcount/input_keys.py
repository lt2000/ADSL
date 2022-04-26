import os

input_file = './input'

filelist = os.listdir(input_file)
with open('./input_keys.txt', 'w') as f:
    for idx in range(len(filelist)):
        f.write('lithops-data/' + filelist[idx] + '\n')    