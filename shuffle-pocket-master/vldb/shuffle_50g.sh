export num_input=200
export num_partition=200


echo python pywren-part-pocket.py $num_input 1 $num_partition 1  $num_input $1
python pywren-part-pocket.py $num_input 1 $num_partition 1 $num_input $1
echo python pywren-sort-pocket.py $num_partition 1 $num_input 1 $num_input $1
python pywren-sort-pocket.py $num_partition 1 $num_input 1 $num_input $1
