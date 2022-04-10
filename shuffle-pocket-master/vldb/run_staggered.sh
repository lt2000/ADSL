stagger_duration=20
for i in {1..5}; do
  bash shuffle_50g.sh $i  &
  sleep $stagger_duration
done
wait
