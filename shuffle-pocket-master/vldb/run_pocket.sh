stagger_duration=20
export num_tasks=200
export write_element_size=4096
export process_time=0
export total_time=20

echo python pywren-write-pocket.py $num_tasks 1 $write_element_size $process_time 100 1
python pywren-write-pocket.py $num_tasks 1 $write_element_size $process_time 100 1 &
sleep $stagger_duration

echo python pywren-write-pocket.py $num_tasks 2 $write_element_size $process_time 80 0 
python pywren-write-pocket.py $num_tasks 2 $write_element_size $process_time 80 0 &
sleep $stagger_duration

echo python pywren-write-pocket.py $num_tasks 3 $write_element_size $process_time 60 0 
python pywren-write-pocket.py $num_tasks 3 $write_element_size $process_time 60 0 &
sleep $stagger_duration

echo python pywren-write-pocket.py $num_tasks 4 $write_element_size $process_time 40 0 
python pywren-write-pocket.py $num_tasks 4 $write_element_size $process_time 40 0 &
sleep $stagger_duration

echo python pywren-write-pocket.py $num_tasks 5 $write_element_size $process_time 20 0 
python pywren-write-pocket.py $num_tasks 5 $write_element_size $process_time 20 0 &
sleep $stagger_duration

wait
