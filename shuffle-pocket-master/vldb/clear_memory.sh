redis_clear_memory() {
  sum=0
  while IFS='' read -r host || [[ -n "$host" ]]; do
    redis-cli -h $host FLUSHALL &
  done < "./servers.txt"
  wait
}

redis_clear_memory
