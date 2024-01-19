import csv
import json
import random
import datetime
import pandas as pd

# with open('input_test/less_requests_half_hour.json') as f:
#     # result is a dict
#     requests = json.load(f)

df = pd.read_csv( "private_trip_data.csv" )
reqs = df["requst id"].to_list()
req = set(reqs)
print(len(req))
# df.columns = ["Garage", "X", "Y"]

# timeOffset = 0
# reqTime = []
# invalidReq = []
# for r in requests:
#     # r["time"] += timeOffset
#     # if r["time"] > 27000000: # 9:30 am
#     #     r["time"] = random.randint(21600000, 27000000)
#     ori_garage = r["origin"]["object"]
#     des_garage = r["destination"]["object"]
#     if ori_garage == des_garage:
#         invalidReq.append(r["id"])
#         continue
#     elif ori_garage == "GARAGE 610" or des_garage == "GARAGE 610":
#         invalidReq.append(r["id"])
#         continue
#     try:
#         coor_x = df[(df['Garage'] == ori_garage)]['X'].item()
#         coor_y = df[(df['Garage'] == ori_garage)]['Y'].item()

#         coor_x_d = df[(df['Garage'] == des_garage)]['X'].item()
#         coor_y_d = df[(df['Garage'] == des_garage)]['Y'].item()
#         r["origin"] = { "object": ori_garage, "x":round(coor_x,3), "y":round(coor_y,3)}
#         r["destination"] = { "object": des_garage, "x":round(coor_x_d,3), "y":round(coor_y_d,3)}
#     except:
#         invalidReq.append(r["id"])
#         continue
#     reqTime.append(r["time"])

# reqTime = []
# for r in requests:
#     r["reservation_time"] = 300000
#     r["detour_time"] = 300000
#     reqTime.append(r["time"])
# # new_reqs = [r for r in requests if r["id"] not in invalidReq and r["time"] < 23400000]
# # new_reqs = [r for i, r in enumerate(new_reqs) if i%5 == 0]
# # new_reqs = [r for r in requests if r["id"] not in invalidReq]

# minT = datetime.datetime.fromtimestamp( min(reqTime)/1000 ).strftime('%Y-%m-%d %H:%M:%S.%f')
# maxT = datetime.datetime.fromtimestamp( max(reqTime)/1000 ).strftime('%Y-%m-%d %H:%M:%S.%f')
# print( minT )
# print( maxT )
# print( "Number of requests {}".format( len(requests) ) )
# # print( "Number of invalid requests {}".format( len(invalidReq) ) )
# # print( "Number of requests difference {}".format(len(requests)-len(new_reqs)) )
# with open("less_reqs_with_waiting.json", "w") as outfile:
#     json.dump(requests, outfile, indent=4)