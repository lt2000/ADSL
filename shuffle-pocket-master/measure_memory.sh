timestamp() {
  date +%s
}

redis_memory() {
  while IFS='' read -r host || [[ -n "$host" ]]; do
    redis-cli -h $host INFO memory | grep "used_memory_dataset:" | awk -F':' '{print $2 }'
  done < "./servers.txt"
}

if [ -f redis_memory.log ]; then
  ts=`timestamp`
  mv redis_memory.log redis_memory.log.$ts
fi

while true
do
  data_size=`redis_memory | awk '{ sum += $1 } END { print sum }'`
  ts=`timestamp`
  echo "$ts $data_size" >> redis_memory_$1.log
  sleep 1
done
