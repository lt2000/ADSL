import cPickle as pickle
import sys
res = pickle.load(open(sys.argv[1]))
for r in res['results']:
    print '\t'.join([str(e) for e in r[:5]])
