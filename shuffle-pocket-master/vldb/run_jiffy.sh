stagger_duration=20
export num_tasks=200
export write_element_size=4096
export process_time=0
export total_time=20
export directory_server='ec2-52-27-126-237.us-west-2.compute.amazonaws.com'

echo python pywren-write-jiffy.py $num_tasks 1 $write_element_size $process_time 100 $directory_server 
python pywren-write-jiffy.py $num_tasks 1 $write_element_size $process_time 100 $directory_server &
sleep $stagger_duration

echo python pywren-write-jiffy.py $num_tasks 2 $write_element_size $process_time 80 $directory_server 
python pywren-write-jiffy.py $num_tasks 2 $write_element_size $process_time 80 $directory_server &
sleep $stagger_duration

echo python pywren-write-jiffy.py $num_tasks 3 $write_element_size $process_time 60 $directory_server 
python pywren-write-jiffy.py $num_tasks 3 $write_element_size $process_time 60 $directory_server &
sleep $stagger_duration

echo python pywren-write-jiffy.py $num_tasks 4 $write_element_size $process_time 40 $directory_server 
python pywren-write-jiffy.py $num_tasks 4 $write_element_size $process_time 40 $directory_server &
sleep $stagger_duration

echo python pywren-write-jiffy.py $num_tasks 5 $write_element_size $process_time 20 $directory_server 
python pywren-write-jiffy.py $num_tasks 5 $write_element_size $process_time 20 $directory_server &
sleep $stagger_duration

wait
