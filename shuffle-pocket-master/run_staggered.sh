stagger_duration=50
for i in {1..2}; do
  bash shuffle_50g.sh $i  &
  sleep $stagger_duration
done
wait
