export pocket=`paste -d';' -s pocket_servers.txt`
export num_input=1
export num_partition=1
#export PYWREN_LOGLEVEL=INFO
echo -e "Running with\n\tpocket servers: $redis\n\tnum_input=$num_input\n\tnum_partition=$num_partition"

#echo python sort-generate.py $num_input
#python sort-generate.py $num_input

for i in 1 2 3 4 5; do
  python pywren-part-pocket.py $num_input 5 $num_partition 1 $pocket $num_input
  kill -9 $(jobs -p)

  #mv redis-sort-part-con1.pickle.breakdown.1 redis-sort-part-con1.pickle.breakdown.$i
  #mv redis-sort-sort-con1.pickle.breakdown.1 redis-sort-sort-con1.pickle.breakdown.$i
done
