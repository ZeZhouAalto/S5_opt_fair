import json
import matplotlib.pyplot as plt

# with open('requestEvents.json', 'r') as fp:
# 	req_event = json.load(fp)

# count = 0
# for k,v in req_event.items():
# 	if len(v)!=3:
# 		count+=1
# print(count)

with open('basic_scenario/1119/no_pv_garage_s1.json', 'r') as fp:
	no_pv_garage = json.load(fp)

output = {}

for item in no_pv_garage:
    if item not in output:
        output[item] = 0
    output[item] += 1

print(output)