import json
import random
import datetime
import matplotlib.pyplot as plt

with open('C:/Users/zhouz2/third_paper_code/Scenario3/Output_S3/s5_1208/requestEvents.json') as f:
    # result is a dict
    requests_events = json.load(f)

# with open('C:/Users/zhouz2/third_paper_code/Scenario2/Output_S2/1207_new_results_record/requestPrice.json') as f:
#     requests_price = json.load(f)

with open('C:/Users/zhouz2/third_paper_code/Scenario3/Input_S3/req_8_10_min_wait.json') as f:
    # result is a dict
    requests = json.load(f)

count = 0
waiting_list = []
travel_time = []
shortest_tt = []
# print(len(requests_price))
print(len(requests_events))
for r in requests:
    if r["id"] in requests_events:
        time_list = requests_events[r["id"]]
        if len(time_list)!=3:
            count+=1
        else:
            req_submit_time = r["time"]
            waiting_list.append((time_list[1]-req_submit_time)/60000)
            travel_time.append((time_list[2]-time_list[1])/60000)

print(len(waiting_list))
wait_avg = sum(waiting_list)/len(waiting_list)
print("average waiting time {} in mins".format(wait_avg))
travel_time_avg = sum(travel_time)/len(travel_time)
print(len(travel_time))
print("average travel time {} in mins".format(travel_time_avg))



# n, bins, patches = plt.hist(waiting_list)
# plt.hist(travel_time)
# plt.show()
# print("test") 


# timeOffset = 0
# timeOffset = -3600000
# reqTime = []
# for r in requests:
#     r["time"] += timeOffset
#     # if r["time"] > 27000000: # 9:30 am
#     #     r["time"] = random.randint(21600000, 27000000)
#     reqTime.append(r["time"])

# minT = datetime.datetime.fromtimestamp( min(reqTime)/1000 ).strftime('%Y-%m-%d %H:%M:%S.%f')
# maxT = datetime.datetime.fromtimestamp( max(reqTime)/1000 ).strftime('%Y-%m-%d %H:%M:%S.%f')
# print( minT )
# print( maxT )
# print( "number of requests {}".format(len(reqTime)))
# with open("reqs_from_8_10.json", "w") as outfile:
#     json.dump(requests, outfile, indent=4)