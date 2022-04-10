export redis=`paste -d';' -s servers.txt`
export num_input=1
export num_partition=1
#export PYWREN_LOGLEVEL=INFO
echo -e "Running with\n\tredis servers: $redis\n\tnum_input=$num_input\n\tnum_partition=$num_partition"

#echo python sort-generate.py $num_input
#python sort-generate.py $num_input

for i in 1 2 3 4 5; do
  ./measure_memory.sh $i &
  echo python pywren-part-redis.py $num_input 1 $num_partition 1 $redis $num_input
  python pywren-part-redis.py $num_input 1 $num_partition 1 $redis $num_input
  echo python pywren-sort-redis.py $num_partition 1 $num_input $redis $num_partition
  python pywren-sort-redis.py $num_partition 1 $num_input $redis $num_partition
  kill -9 $(jobs -p)
  ./clear_memory.sh

  mv redis-sort-part-con1.pickle.breakdown.1 redis-sort-part-con1.pickle.breakdown.$i
  mv redis-sort-sort-con1.pickle.breakdown.1 redis-sort-sort-con1.pickle.breakdown.$i
done
