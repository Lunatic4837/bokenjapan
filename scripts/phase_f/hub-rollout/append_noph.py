import csv,sys,shutil,os
NP='/workspace/p1/photos-5pref/no-photo-found.csv'
if not os.path.exists(NP+'.bak-rollout'): shutil.copy(NP,NP+'.bak-rollout')
have={(r[0],r[4]) for r in csv.reader(open(NP)) if len(r)>4}
new=[r for r in csv.reader(open(sys.argv[1])) if (r[0],r[4]) not in have]
with open(NP,'a',newline='') as f: csv.writer(f).writerows(new)
print('appended',len(new))
