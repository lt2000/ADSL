from lithops import Storage

def delete_temp_data(storage, bucket_name, keynames):
    print('Deleting temp files...')
    storage = Storage(backend=storage)
    storage.delete_object(bucket_name, keynames)
    print('Done!')

if __name__ == '__main__':
    storage = 'aliyun_oss'
    bucket_name = 'data-lithops'
    
    for i in range(10):
        keynames = []
        for j in range(100):
            keynames.append('word_count_shuffle_'+ str(i) +'_'+ str(j))
            delete_temp_data(storage, bucket_name, keynames)