import pickle
# input_keys_file = './input_keys.txt'
# keys_f = open(input_keys_file, 'r')
# keynames = [x.strip() for x in keys_f.readlines()]
# print(keynames)

res = pickle.load(open('./word_count_shuffle_0_0', 'rb'))
print(res)