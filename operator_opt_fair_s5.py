import os
import grpc
import time
import math
import argparse
import json
import random
import datetime
import common_pb2
import common_pb2_grpc
import Operator_pb2
import Operator_pb2_grpc
import Simulator_pb2
import Simulator_pb2_grpc
import copy
import gurobipy
import pandas as pd
import math
import config
import multiprocessing as mp

from concurrent import futures
from VehSchedule import *
from google.protobuf import empty_pb2


_CPU_NUMBER = mp.cpu_count()
_TEN_SECONDS = 10
_CALL_BACK   = 10
_MAX_COMMAND = 10
drt_discount = 0.95
zeta = 2 # e/req, objective sum divide num of reqs
keepRunning = True
PRICE_PARA = {'base':2.5, 'time':0.2, 'distance': 0.6, 'cost':0.4} # 0.4e/min or e/km
input_file_dir  = 'Input_S3'
output_file_dir = 'Output_S3'

# data save class
class DataSave():

	def __init__(self):
		self.data=pd.DataFrame({'veh_id':[],'time':[],'request_id':[],'state':[], 'fromGarage':[], 'toGarage':[], 'occupancy':[]})
	def get_data(self):
		return self.data.copy()
	def set_data(self,new_data):
		self.data=new_data.copy()
	def update_data(self,veh_ID,time,requst_id,state,ori_g,des_g,occupancy):
		row=pd.DataFrame({'veh_id':[veh_ID],'time':[time],'request_id':[requst_id],'state':[state],'fromGarage':[ori_g], 'toGarage':[des_g], 'occupancy':[occupancy]})
		old_data=self.get_data()
		new_data=pd.concat([old_data,row],ignore_index=True)
		self.set_data(new_data)
	
# helper class to connect to the remote simulator
class SimulatorClient():
	def __init__(self, simulatorAddress ):
		print( "Simulator Client connected to {}".format( simulatorAddress ) )
		self.channel = grpc.insecure_channel( simulatorAddress )
		self.stub = Simulator_pb2_grpc.SimulatorStub( self.channel )

	def etaVehicles( self, veh, destination ):
		origins = Simulator_pb2.Vehicles( destination=destination, vehicles=veh )
		return self.stub.travelInfoFleet( origins )

	def etaVehicle( self, veh, destination ):
		origins = Simulator_pb2.Vehicles( destination=destination, vehicles=[veh] )
		return self.stub.travelInfoFleet( origins )

	def eta( self, origin, destination, mode ):
		pos = Simulator_pb2.Positions( origin=origin, destination=destination, mode=mode )
		return self.stub.travelInfo( pos )
	
	def getVehiclePosition(self, veh):
		vehicle = common_pb2.VehicleId(id = veh)
		return self.stub.position(vehicle)
	
	def getTravelTimeFromAtoB(self, origin, destination, mode):
		input = Simulator_pb2.Point2Point(origin=origin, destination=destination, mode=mode)
		return self.stub.getTravelTimeFromOnePointToAnother(input)

	def getTravelTimeFromAtoMany(self, origin, destinations, mode):
		input = Simulator_pb2.Point2ManyPoints(origin=origin, destination=destinations, mode=mode)
		return self.stub.getTravelTimeFromOnePointToManyPoints(input)

	def changeFleetSchedules(self, command_list):
		# print("got it")
		commandList = common_pb2.FleetCommandList(list=[command_list])
		return self.stub.reprogramFleet(commandList)
	
# Segment travel time
def segmentTravelTime( segment ):
	return segment.inVehicleTime + segment.walkingTime + segment.waitingTime

# extract the in vehicle time
def travelTime( tt ):
	res = 0
	for s in tt.segments:
		res += segmentTravelTime( s )
	return res

# filter only valid responses (if inVehicleTime equal to -1 imples there in no path )
def filterTravelTime( tt ):
	for s in tt.segments:
		if s.inVehicleTime < 0:
			return False
	return True

# user mode choice
def userChoice(tripTime, tripDist, tt, fare):
	privatePara = {"beta_0":0, "beta_t":0.48, "beta_f":3.2, "fix_cost":6, "via_cost":0.9}
	DRTPara = {"beta_0":0, "beta_t":0.48, "beta_f":3.2}
	utilityPrivate = privatePara["beta_0"]-privatePara["beta_t"]*tripTime/60000 - privatePara["beta_f"]*( privatePara["via_cost"]*tripDist*0.001 + privatePara["fix_cost"])
	utilityDRT = DRTPara["beta_0"]- DRTPara["beta_t"]*tt/60000 - DRTPara["beta_f"]*fare
	p_DRT = math.exp(utilityDRT)/(math.exp(utilityPrivate) + math.exp(utilityDRT))
	p_private = math.exp(utilityPrivate)/(math.exp(utilityPrivate) + math.exp(utilityDRT))
	probi = { 'DRT':round(p_DRT,2), 'private':round(p_private,2)}
	return probi

# ridesharing worker
def ridesharingWorker(now, requestsList, reqVehInfo, reqCurrentPrice, lookup):
	maxVehicleCapacity = 4
	PRICE_PARA = {'base':2.5, 'time':0.2, 'distance': 0.6, 'cost':0.4} # 0.4e/min or e/km
	minimumFare = 3
	profit_tax = 0.7
	drt_discount = 0.95
	nestedReqVeh = dict()

	if len(requestsList)>0:
		for reqID in requestsList:
			reqTime = config.data.requests[reqID]["time"]
			new_req_wt = config.data.requests[reqID]["reservation_time"]
			new_req_dt = config.data.requests[reqID]["detour_time"]
			# convert str to the Point class to access x,y coordinate
			ori_g = config.data.requests[reqID]["origin"]["object"]
			des_g = config.data.requests[reqID]["destination"]["object"]
			pickupLocation = common_pb2.Point(x=config.data.requests[reqID]["origin"]["x"], y=config.data.requests[reqID]["origin"]["y"])
			dropoffLocation = common_pb2.Point(x=config.data.requests[reqID]["destination"]["x"], y=config.data.requests[reqID]["destination"]["y"])
			try:
				bestSingleDrtIvtt = lookup[ori_g][config.data.garageIndex[des_g]]
				shortestLength = config.data.distance_look_up[ori_g][config.data.garageIndex[des_g]]
			except:
				print( "look up table error from {} to {}".format(ori_g, des_g) )
			# bestSingleDrtWt = requestInfo[reqID]["bestWT"]
			reqDeadline = reqTime + bestSingleDrtIvtt + new_req_wt + new_req_dt

			for veh in reqVehInfo[reqID].keys():
				feasibleSchedules = list()
				try:
					##each veh has a best schedule
					currVehSchedule = reqVehInfo[reqID][veh]["schedule"]
					currVehGarage = reqVehInfo[reqID][veh]["garage"]
					currVehScheduleObject = VehSchedule(veh)
					currVehScheduleObject.schedule = currVehSchedule
					pickUpTime = lookup[currVehGarage][config.data.garageIndex[ori_g]]
					pickUpDist = config.data.distance_look_up[currVehGarage][config.data.garageIndex[ori_g]]
					if not currVehScheduleObject.schedule:
						newPotentialSched, insertionPositions = currVehScheduleObject.createNewPotentialSchedule(
							veh, 
							reqID, 
							currVehScheduleObject.schedule, ["PickUp", "DropOff"], 
							[pickupLocation, dropoffLocation], 
							[0,0]
						)

						vwt = pickUpTime
						ivtt = bestSingleDrtIvtt
						totalTravelTime = vwt + ivtt
						wkt = 0
						dist = shortestLength

						if now + vwt > reqTime + new_req_wt or now + totalTravelTime > reqDeadline:
							continue
						else: 
							feasibleSchedules.append( 
								{
								"vehId": veh, 
								"newSchedule": newPotentialSched, 
								"insertionPositions": insertionPositions, 
								"totalTravelTime": totalTravelTime,
								"additionalTT":totalTravelTime,
								"waitingTime": vwt, 
								"inVehicleTravelTime": ivtt, 
								"walkingTime": wkt, 
								"distance": dist
								} 
							)
					else:
						scheduledCommandDestinations = list()
						commandGarage = list()

						# calculate the total travel time before insertion
						beforeInsertionSchedule = currVehScheduleObject.schedule
						command_garage_before = list()
						for comnd in beforeInsertionSchedule:
							g_name = [ item[1] for item in config.data.garageTupleList if math.isclose(item[3], comnd.destination.x, abs_tol = 0.9) and math.isclose(item[4], comnd.destination.y, abs_tol = 0.9)]
							command_garage_before.append( g_name[0] )
						beforeInsertionTT = 0
						if len(command_garage_before) > 0:
							for m in range(len(command_garage_before)):
								if m == 0:
									legTime = lookup[currVehGarage][config.data.garageIndex[command_garage_before[m]]]
								else:
									legTime = lookup[command_garage_before[m-1]][config.data.garageIndex[command_garage_before[m]]]
								beforeInsertionTT += legTime
						
						for i in range(len(currVehScheduleObject.schedule)+1):
							for j in range(len(currVehScheduleObject.schedule)+1):
								
								if j < i:
									continue
								
								newPotentialSched, insertionPositions = currVehScheduleObject.createNewPotentialSchedule(
									veh, 
									reqID, 
									currVehScheduleObject.schedule, 
									["PickUp", "DropOff"], 
									[pickupLocation, dropoffLocation], 
									[i,j]
								)

								# vehicle occupancy checks first-----------------------------------------------------------
								currentVehOccupancy = reqVehInfo[reqID][veh]["occupancy"]
								predictedOccupancy = currentVehOccupancy
								
								if currentVehOccupancy > maxVehicleCapacity:
									print("Occupancy issue with vehicle {}, current vehicle occupaancy is above capacity. Check occupancy update logic".format(veh))
									break
								
								nonFeasibleInsertion = False
								for command in newPotentialSched:
									if command.operation == common_pb2.Operation.Pickup:
										predictedOccupancy += 1
										if predictedOccupancy > maxVehicleCapacity:
											nonFeasibleInsertion = True
											break
									if command.operation == common_pb2.Operation.Deliver:
										predictedOccupancy -= 1
								
								if nonFeasibleInsertion:
									scheduledCommandDestinations = list()
									commandGarage = list()
									continue
								#-------------------------------------------------------------------------------------------
								for comnd in newPotentialSched:
									scheduledCommandDestinations.append(comnd.destination)
									garage_name = [ item[1] for item in config.data.garageTupleList if math.isclose(item[3], comnd.destination.x, abs_tol = 0.9) and math.isclose(item[4], comnd.destination.y, abs_tol = 0.9)]
									commandGarage.append( garage_name[0] )
								
								# first check potential threshold violations for the new request
								pickUpIndex = insertionPositions[0]
								dropOffIndex = insertionPositions[1]

								# check the waiting time for the new request
								if pickUpIndex == 0:
									vwt = pickUpTime
								else:
									vwt = 0
									previousDestination = None
									preGara = None
									for k in range(0,pickUpIndex+1):
										if k == 0:
											vwt += lookup[currVehGarage][config.data.garageIndex[commandGarage[k]]]
											preGara = commandGarage[k]
										else:
											vwt += lookup[preGara][config.data.garageIndex[commandGarage[k]]]
											preGara = commandGarage[k]
								
								# check the total travel time only for the new request, note the total tt not include other preassigned requests
								ivtt = 0
								dist = 0
								if dropOffIndex == pickUpIndex + 1:
									ivtt = bestSingleDrtIvtt
								else:
									preGara = ori_g
									for k in range(pickUpIndex+1,dropOffIndex+1):
										ivtt += lookup[preGara][config.data.garageIndex[commandGarage[k]]]
										dist += config.data.distance_look_up[preGara][config.data.garageIndex[commandGarage[k]]]
										preGara = commandGarage[k]
								
								totalTravelTime = vwt + ivtt
								wkt = 0
								
								if vwt > new_req_wt or totalTravelTime > reqDeadline:
									scheduledCommandDestinations = list()
									commandGarage = list()
									continue
							
								# now check the rest of the running trips and whether the new insertion violates their thresholds
								# get every req's idx position in the new schedule
								trips_checked = dict()
								for k in range(len(newPotentialSched)):
									if k == pickUpIndex or k == dropOffIndex:
										continue
									else:
										# if newPotentialSched[k].service.request not in modifiedPlannedTripAttributes:
										# 	modifiedPlannedTripAttributes.update( {newPotentialSched[k].service.request: list() })
										
										if newPotentialSched[k].service.request not in trips_checked:
											trips_checked.update({newPotentialSched[k].service.request: {"idxs": [k]}})
										else:
											trips_checked[newPotentialSched[k].service.request]["idxs"].append(k)
								
								nonFeasibleInsertion = False
								for trip_id, info in trips_checked.items():
									if len(info["idxs"]) == 1:
										tempDropoffIdx = info["idxs"][0]
										if tempDropoffIdx < pickUpIndex:
											continue
										
										tempTripCompletionTime = 0
										for k in range(0,tempDropoffIdx+1):
											if k == 0:
												tempTripCompletionTime += lookup[currVehGarage][config.data.garageIndex[commandGarage[k]]]
											else:
												tempTripCompletionTime += lookup[commandGarage[k-1]][config.data.garageIndex[commandGarage[k]]]

										tempTripCompletionTimeClock = now + tempTripCompletionTime
										if tempTripCompletionTimeClock > config.data.reqDeadline[trip_id]:
											nonFeasibleInsertion = True
											break

									else:
										tempPickupIdx = info["idxs"][0]
										tempDropoffIdx = info["idxs"][1]

										if tempPickupIdx < pickUpIndex and tempDropoffIdx < pickUpIndex:
											continue

										tempTripWaitingTime = 0
										tempTripCompletionTime = 0

										# first check how the trip's pickup is affected
										if tempPickupIdx > pickUpIndex:
											for k in range(0,tempPickupIdx+1):
												if k == 0:
													tempTripWaitingTime += lookup[currVehGarage][config.data.garageIndex[commandGarage[k]]]
												else:
													tempTripWaitingTime += lookup[commandGarage[k-1]][config.data.garageIndex[commandGarage[k]]]

										# now check how the trip's dropoff is affected
										previousDestination = scheduledCommandDestinations[tempPickupIdx]
										preGara = commandGarage[tempPickupIdx]
										tempTripInVehicleTime = 0
										for k in range(tempPickupIdx+1,tempDropoffIdx+1):
											tempTripInVehicleTime += lookup[preGara][config.data.garageIndex[commandGarage[k]]]
											preGara = commandGarage[k]
										
										tempTripCompletionTime = tempTripWaitingTime + tempTripInVehicleTime
										tempTripWaitingTimeClock = now + tempTripWaitingTime
										tempTripCompletionTimeClock = now + tempTripCompletionTime
										# computedSchedulePerRequest: initial vehicle schedule with
										if tempTripCompletionTimeClock > config.data.reqDeadline[trip_id] or tempTripWaitingTimeClock - config.data.requests[trip_id]["time"] > config.data.requests[trip_id]["reservation_time"]:
											nonFeasibleInsertion = True
											break
								
								command_garage_after = copy.deepcopy(commandGarage)
								scheduledCommandDestinations = list()
								commandGarage = list()

								if nonFeasibleInsertion:
									continue
								else:
									totalTravelTime = vwt + ivtt

									# calculate the total travel time after insertion
									afterInsertionTT = 0
									if len(command_garage_after) > 0:
										for m in range(len(command_garage_after)):
											if m == 0:
												legTime = lookup[currVehGarage][config.data.garageIndex[command_garage_after[m]]]
											else:
												legTime = lookup[command_garage_after[m-1]][config.data.garageIndex[command_garage_after[m]]]
											afterInsertionTT += legTime
									addedTravelTime = afterInsertionTT - beforeInsertionTT
									additionalTime = addedTravelTime + vwt # add the new request's waiting time

									feasibleSchedules.append( 
										{
											"vehId": veh, 
											"newSchedule": newPotentialSched, 
											"insertionPositions": insertionPositions,
											"totalTravelTime": totalTravelTime,
											"additionalTT": additionalTime,
											"waitingTime": vwt, 
											"inVehicleTravelTime": ivtt, 
											"walkingTime": wkt, 
											"distance": dist
										} 
									)

								scheduledCommandDestinations = list()
								commandGarage = list()
				except Exception as e:
					print("************vehicle route insertion error {} ************".format(e))

				if feasibleSchedules:
					sorted_schedules = sorted(feasibleSchedules, key=lambda i: (i['totalTravelTime'], i['waitingTime'])) 
					bestSchedule = sorted_schedules[0]
					
					# ridesharing price, initialize request price
					totalDisInKm = (shortestLength + pickUpDist)*0.001                                   # convert m to km
					totalTimeInMin = bestSingleDrtIvtt/60000                                             # convert ms to min
					price_solo = PRICE_PARA["base"] + PRICE_PARA["time"]*totalTimeInMin + PRICE_PARA["distance"]*totalDisInKm
					p_0 = max( [minimumFare, round(drt_discount*price_solo,2)] )
					reqCurrentPrice.update( { reqID:p_0 } )

					# modify the schedule, drop off first then pick up
					reqIndex = bestSchedule["insertionPositions"]
					nodesBetween = bestSchedule["newSchedule"][reqIndex[0]:reqIndex[1]]                  # include the new req's origin
					if reqIndex[1] - reqIndex[0] > 1:
						# pu_do stores all pickup and dropoff nodes between the new req OD that equal to the pickupLocation
						pu_do = []
						while nodesBetween[0].destination == pickupLocation:
							pu_do.append(nodesBetween[0])
							nodesBetween.pop(0)
							if len(nodesBetween) == 0:
								break
						sorted_by_value = sorted(pu_do, key=lambda x: x.operation, reverse=True)
						sorted_by_value.extend(nodesBetween)
						bestSchedule["newSchedule"][ reqIndex[0]:reqIndex[1] ] = sorted_by_value

					# check if the new req shares with others
					newReqIndex = [a for a, command in enumerate( bestSchedule["newSchedule"] ) if command.service.request == reqID]
					all_rid = [command.service.request for a, command in enumerate( bestSchedule["newSchedule"]) if command.service.request != reqID]
					all_rid = list(set(all_rid)) # all reqs in the vehicle's schedule except the new req
					sharing_flag = 0
					shared_rid = list()
					onBoardPassengers = list()
					for res_req in all_rid:
						req_index = [ a for a, command in enumerate(bestSchedule["newSchedule"]) if command.service.request == res_req]
						if len(req_index) == 1: # only drop off node left
							onBoardPassengers.append(res_req) # already on board
							if req_index[0] < newReqIndex[0]:
								continue
							else:
								shared_rid.append(res_req)
								sharing_flag = 1
						else:
							if   req_index[1] < newReqIndex[0]: # all in the left
								continue
							elif req_index[0] > newReqIndex[1]: # all in the right
								continue
							else:
								shared_rid.append(res_req)
								sharing_flag = 1

					if sharing_flag == 0:
						serviceCost = PRICE_PARA["cost"]*totalDisInKm
						updatedPrice = { reqID:p_0 }
						profit = round( (p_0 - serviceCost)*profit_tax,2 )
					else:
						try:
							shared_rid.append(reqID) # all ridesharing reqs include the new one
							# calculate the total travel time and path length for each assigned request before insertion
							beforeInsertionTT = 0
							totalTravelDisBefore = 0
							aloneDis  = dict.fromkeys(shared_rid,0)
							beforeInsertionSchedule = currVehScheduleObject.schedule
							ob_p_copy = copy.deepcopy(onBoardPassengers)
							commandGarage_before = list()
							for comnd in beforeInsertionSchedule:
								garage_name = [ item[1] for item in config.data.garageTupleList if math.isclose(item[3], comnd.destination.x, abs_tol = 0.9) and math.isclose(item[4], comnd.destination.y, abs_tol = 0.9)]
								commandGarage_before.append( garage_name[0] )
							# loop over the preceeding schedule, fill in aloneDis
							for idx,cmd in enumerate(beforeInsertionSchedule):
								tripID = cmd.service.request
								if idx == 0:
									beforeInsertionTT += lookup[currVehGarage][config.data.garageIndex[commandGarage_before[0]]]
									totalTravelDisBefore  += config.data.distance_look_up[currVehGarage][config.data.garageIndex[commandGarage_before[0]]]
								else:
									beforeInsertionTT += lookup[commandGarage_before[idx-1]][config.data.garageIndex[commandGarage_before[idx]]]
									totalTravelDisBefore  += config.data.distance_look_up[commandGarage_before[idx-1]][config.data.garageIndex[commandGarage_before[idx]]]
								# update on board passengers
								if cmd.operation == 0:
									ob_p_copy.append(tripID)
								elif cmd.operation == 1:
									if tripID in shared_rid:
										aloneDis[tripID] += totalTravelDisBefore
									ob_p_copy.remove(tripID)
							aloneDis[reqID] = shortestLength + pickUpDist
							# sch_sharing is the new vehicle schedule includes new req OD
							sch_sharing = copy.deepcopy( bestSchedule["newSchedule"] )
							realCost    = dict.fromkeys(shared_rid,0) # shared travel fare
							ifNoShareCost = dict.fromkeys(shared_rid,0)
							aloneFare   = dict.fromkeys(shared_rid,0) # alone means before insertion
							realDis     = dict.fromkeys(shared_rid,0) # real distance after insertion
							for r in shared_rid:
								aloneFare[r]= reqCurrentPrice[r]
							# loop over new schedule
							totalTravelDisAfter = 0
							commandGarage_after = list()
							for comnd in sch_sharing:
								garage_name = [ item[1] for item in config.data.garageTupleList if math.isclose(item[3], comnd.destination.x, abs_tol = 0.9) and math.isclose(item[4], comnd.destination.y, abs_tol = 0.9)]
								commandGarage_after.append( garage_name[0] )
							for idx,cmd in enumerate( sch_sharing ):
								tripID = cmd.service.request
								if idx == 0:
									inVehicleTime = lookup[currVehGarage][config.data.garageIndex[commandGarage_after[idx]]]
									dist = config.data.distance_look_up[currVehGarage][config.data.garageIndex[commandGarage_after[idx]]]
									legFare = PRICE_PARA["time"]*inVehicleTime/60000  + PRICE_PARA["distance"]*dist*0.001
									totalTravelDisAfter += dist
								else:
									ivt = lookup[commandGarage_after[idx-1]][config.data.garageIndex[commandGarage_after[idx]]]
									dist = config.data.distance_look_up[commandGarage_after[idx-1]][config.data.garageIndex[commandGarage_after[idx]]]
									legFare = PRICE_PARA["time"]*ivt/60000  + PRICE_PARA["distance"]*dist*0.001
									totalTravelDisAfter += dist
								if len(onBoardPassengers) !=0 :
									for r in shared_rid:
										if r in onBoardPassengers:
											# realDis[r] += leg.distance
											realCost[r] += legFare/len(onBoardPassengers)
											ifNoShareCost[r] += legFare
								if cmd.operation == 0:
									onBoardPassengers.append(tripID)
								elif cmd.operation == 1:
									if tripID in shared_rid:
										realDis[tripID] += totalTravelDisAfter
									onBoardPassengers.remove(tripID)
							# price after discount
							p = [ round(1-a/b,3) for a,b in zip( list(aloneDis.values()), list(realDis.values()) ) ]
							q = [ 1-a/b for a,b in zip( list(realCost.values()), list(ifNoShareCost.values()) ) ]
							discount = [ 1/math.exp(2*(m+n)/10) for m,n in zip(p,q) ]
							finalFee = [ max([minimumFare, round(a*b,2)]) for a,b in zip( list( aloneFare.values() ), discount ) ]
							updatedPrice = dict( [(m,n) for m,n in zip(shared_rid, finalFee)] )
							delta_p = 0
							for r in shared_rid:
								if r ==reqID:
									delta_p += updatedPrice[reqID]
								else:
									dp = updatedPrice[r] - aloneFare[r]
									delta_p += dp
							# after including the new req, how much the profit increase (maginal profit)
							profit = round(delta_p - (totalTravelDisAfter-totalTravelDisBefore)*PRICE_PARA["cost"]*0.001, 2)
						except Exception as e:
							print("***************ridesharing price error {}************".format(e))
					# store final feasible schedules and profit
					nestedReqVeh.setdefault(reqID, {}).setdefault(veh, {})
					nestedReqVeh[reqID][veh] = {
								"profit": profit,
								"schedule": bestSchedule,
								"updatedPrice": updatedPrice,
								"reqDeadline": reqDeadline
					}
	return nestedReqVeh

# Our operator
class OperatorServicer(Operator_pb2_grpc.OperatorServicer):

	def __init__(self, simulator, operatorFile, requestFile):
		self.stepLen = 30              # unit s
		self.simHorizon = 8100         # unit s, including 15 mins cool down process
		self.ttUpdate = 300            # s
		self.pvAssign = 120            # s
		self.intialTime = 21600000     # ms, simulation init_time, from 8 to 9.30 am Helsinki time
		self.timeOffset = 0            # milliseconds, request time needs to add this value, minus one hour
		self.avaNum = 15               # number of available vehicles
		self.maxReqs= 300              # max allowed number of reqs
		self.privateSearchNum = 4
		self.maxVehicleCapacity = 4    # TODO: hardcoded; need to change
		self.minimumFare = 3
		self.profit_tax = 0.7
		self.infeasibility = 0
		self.closestGaraNum = 300
		
		self.unfair = list()
		self.lookup = dict()
		self.distance_look_up = dict()
		self.requests = list()
		self.demandInfo = dict()
		self.reqCurrentPrice = dict()
		self.requestsInterval = dict()
		# self.executor = executor
		self.executor = futures.ProcessPoolExecutor(max_workers=_CPU_NUMBER)
		self.simulator = simulator
		self.simulation_data = DataSave()
		self.private_trip_data = DataSave()
		self.privateVeh = list()
		self.priVehDestination = dict()
		self.garagePrivateCar = dict()

		self.vehicles = list()
		self.reposition = dict()
		self.vehIdle = list()
		self.vehicleGarage = dict()
		self.garageIndex = dict()
		self.garageTupleList = list()
		self.garageNearBy = dict()
		self.vehicleSchedules = dict()
		self.vehicleOccupancy = dict()
		self.vehOccuRecord = dict()
		self.offersPerRequest = dict()
		self.requestEventTime = dict()
		self.computedSchedulePerRequest = dict()  # record requests inital schedule, fatest travel time, and price
		self.requestsFailedServing = list()       # all reqs finally leave the system
		self.reqWaitingPool = list()
		self.simulationInfo = dict()
		self.noPrivateCarGarage = list()          # record unserved requests that cannot find a private car either
		self.restoreOperator( operatorFile )
		self.readRequests( requestFile )

	# Read the vehicles in our fleet 
	def restoreOperator( self, operatorFile ):
		with open( operatorFile ) as data_file:
			data = json.load(data_file)
		
		print( "Operator Name: {}".format( data["name"] ) )
		for v in data["fleet"]:
			print( "Vehicle: {} {}".format( v["id"], v["name"] ) )
			if v["origin"]["object"] == "GARAGE 610":                          # vehicle at garage 610 not include in self.vehicles, simulator cannot get it position
				continue
			if v["name"].startswith("P_"):                                     # filter dummy private car, and store private cars in a dic where the key is the "object"
				self.privateVeh.append(v["id"])
				if v["origin"]["object"] not in self.garagePrivateCar:
					self.garagePrivateCar.update( {v["origin"]["object"]:[v["id"]]} )
				else:
					self.garagePrivateCar[v["origin"]["object"]].append(v["id"])
				continue
			self.vehicles.append(v["id"] )                                     # only store DRT taxi car to self.vehicles dict
			self.vehIdle.append(v["id"])
			self.vehicleGarage.update( {v["id"]: v["origin"]["object"]} )      # 609 garages, record every vehicle's initial garage, not include dummy private car
			self.vehicleOccupancy.update( {v["id"]: 0} )
			self.vehOccuRecord.update({v["id"]: [0 for _ in range(240)]})
			self.vehicleSchedules[v["id"]] = VehSchedule(v["id"])

	# Read all the requests
	def readRequests( self, requestFile ):
		with open( requestFile  ) as data_file:
			data = json.load(data_file)
		
		print( "Request name: {}".format( data[0]["name"] ) )
		remainder = self.simHorizon % self.stepLen
		timeStep = self.simHorizon // self.stepLen
		if remainder > 0:
			timeStep += 1
		self.requestsInterval = {key:[] for key in range(timeStep)}
		for r in data:
			print( "Request: {} ".format( r["name"] ) )
			r["time"] += self.timeOffset                                       # change the request time manually
			not_interested = ["destination_time","name","person_type","req_purpose","people","extra_value"]
			dict_cleaned = {key: value for key, value in r.items() if key not in not_interested}
			self.demandInfo.update({r["id"]: dict_cleaned})
			# self.demandInfo.update({r["id"]: r})
			self.requests.append(r["id"] )
			stepCount = int((r["time"] - self.intialTime)*0.001) // self.stepLen
			self.requestsInterval[stepCount].append(r["id"])
		print( "---------------total time steps {}------------".format(timeStep) )

	# return non error as we are ready
	def ok( self, request, context ):
		print( "ok" )
		return empty_pb2.Empty()

	# initialize
	def init(self, request, context): 
		now = request.init_time
		print( "init" )
		self.garageIndex = config.data.garageIndex
		# only 609 garages
		garage_added = list()
		for v,garage in self.vehicleGarage.items():
			if garage not in garage_added:
				garage_added.append(garage)
				index = self.garageIndex[garage]
				vehCurrentPos = self.simulator.getVehiclePosition(v).position
				self.garageTupleList.append( ( index, garage, vehCurrentPos, round(vehCurrentPos.x,2), round(vehCurrentPos.y,2) ) )
		print("length of self garageTupleList {} before adding garage".format(len(self.garageTupleList)))
		# manually add garage 610
		if "GARAGE 610" not in garage_added:
			garage_added.append("GARAGE 610")
			index = self.garageIndex["GARAGE 610"]
			point = common_pb2.Point(x=381651.66, y=6589852.35)
			self.garageTupleList.append( ( index, "GARAGE 610", point, 381651.66, 6589852.35 ) )
		print("length of self garageTupleList after {}".format(len(self.garageTupleList)))
		self.garageTupleList = sorted(self.garageTupleList, key=lambda x: x[0])
		# load look up table
		with open(os.path.join(input_file_dir, "time_look_up.json"), 'r') as fp:
			self.lookup = json.load(fp)
		self.distance_look_up = config.data.distance_look_up
		global sim_start_time
		sim_start_time = time.time()
		return common_pb2.CallbackTime(when = now + _CALL_BACK*1000)

	def updateVehOccupancy(self, timeStep):
		if timeStep < 240:
			for veh in self.vehicles:
				self.vehOccuRecord[veh][timeStep] = self.vehicleOccupancy[veh]

	def rebalancing(self,currentTime):
		# rebalancing veh
		if len(self.reqWaitingPool)>50 and len(self.vehIdle)>50:
			print("-----start rebalancing-----")
			r_v_cost = dict()
			allAvaVeh = list()
			validRebalanceReq = list()
			for unassigned_r in self.reqWaitingPool:
				try:
					ori_g = self.demandInfo[unassigned_r]["origin"]['object']
					des_g = self.demandInfo[unassigned_r]["destination"]['object']
					# speed up available veh search, finding veh from nearby garages
					vehRank = dict()
					for veh in self.vehIdle:
						if self.vehicleGarage[veh] in self.garageNearBy[ori_g]:
							if self.vehicleGarage[veh] not in vehRank:
								vehRank[self.vehicleGarage[veh]] = []
							vehRank[self.vehicleGarage[veh]].append(veh)
					avaVehs = list()
					# from the closest garage to the farthest
					for nearGarage in self.garageNearBy[ori_g]:
						if nearGarage in vehRank:
							avaVehs += vehRank[nearGarage]
						if len(avaVehs) > self.avaNum:
							break
					if len( avaVehs ) > self.avaNum:
						avaVehs = avaVehs[:self.avaNum]
					for veh in avaVehs:
						r_v_cost.setdefault(unassigned_r, {}).setdefault(veh, {})
						currVehGarage = self.vehicleGarage[veh]
						pickUpTime = self.lookup[currVehGarage][self.garageIndex[ori_g]]
						r_v_cost[unassigned_r][veh] = pickUpTime
						if veh not in allAvaVeh:
							allAvaVeh.append(veh)
				except Exception as e:
					print("***********rebalancing error {}***********".format(e))

			for req in self.reqWaitingPool:
				for veh in allAvaVeh:
					try:
						test = r_v_cost[req][veh]
					except:
						r_v_cost.setdefault(req, {}).setdefault(veh, {})
						r_v_cost[req][veh] = 3600000
			
			# start optimization
			model2 = gurobipy.Model("vehicle rebalancing")
			x = model2.addVars(self.reqWaitingPool, allAvaVeh, vtype=gurobipy.GRB.BINARY)
			model2.update()
			model2.setObjective(
								gurobipy.quicksum(r_v_cost[req][veh]*x[req,veh] for req in self.reqWaitingPool for veh in allAvaVeh), 
								sense=gurobipy.GRB.MINIMIZE
							)
			model2.addConstr(gurobipy.quicksum(x[req, veh] for req in self.reqWaitingPool for veh in allAvaVeh) == min([len(self.reqWaitingPool), len(allAvaVeh)]))
			model2.addConstrs(gurobipy.quicksum(x[req,veh] for req in self.reqWaitingPool) <= 1 for veh in allAvaVeh)
			model2.addConstrs(gurobipy.quicksum(x[req,veh] for veh in allAvaVeh) <= 1 for req in self.reqWaitingPool)
			model2.optimize()
			if model2.status == gurobipy.GRB.Status.OPTIMAL:
				m2_solution = [k for k, v in model2.getAttr('x', x).items() if v == 1]
				for s in m2_solution:
					r = s[0]
					v = s[1]
					pu_time = r_v_cost[r][v]
					pickupLocation = common_pb2.Point(x=self.demandInfo[r]["origin"]['x'], y=self.demandInfo[r]["origin"]['y'])
					dropoffLocation = common_pb2.Point(x=self.demandInfo[r]["destination"]['x'], y=self.demandInfo[r]["destination"]['y'])
					currVehGarage = self.vehicleGarage[v]
					ori_g = self.demandInfo[r]["origin"]['object']
					des_g = self.demandInfo[r]["destination"]['object']
					bestSingleDrtIvtt = self.lookup[ori_g][self.garageIndex[des_g]]
					shortestLength = self.distance_look_up[ori_g][self.garageIndex[des_g]]
					pickUpDist = self.distance_look_up[currVehGarage][self.garageIndex[ori_g]]
					# price, initialize request price
					totalDisInKm = (shortestLength + pickUpDist)*0.001               # convert m to km
					totalTimeInMin = bestSingleDrtIvtt/60000                         # convert ms to min
					price_solo = PRICE_PARA["base"] + PRICE_PARA["time"]*totalTimeInMin + PRICE_PARA["distance"]*totalDisInKm
					p_0 = max( [self.minimumFare, round(drt_discount*price_solo,2)] )

					probi = userChoice ( bestSingleDrtIvtt, shortestLength, bestSingleDrtIvtt + pu_time, p_0)
					mode = max(probi, key=probi.get)
					if mode == "DRT" and currentTime + pu_time < self.demandInfo[r]["time"] + self.demandInfo[r]["reservation_time"]:
						currVehScheduleObject = copy.deepcopy(self.vehicleSchedules[v])
						if not currVehScheduleObject.schedule:
							newPotentialSched, insertionPositions = currVehScheduleObject.createNewPotentialSchedule(
								v,
								r, 
								currVehScheduleObject.schedule, ["PickUp", "DropOff"], 
								[pickupLocation, dropoffLocation], 
								[0,0]
							)

							self.computedSchedulePerRequest[r].update( 
								{
									"schedule": newPotentialSched,
									"reqDeadline": config.data.reqDeadline[r],
									"initialPrice": p_0
								}
							)
							self.vehicleSchedules[v].updateCurrentSchedule(newPotentialSched)
							command_list = common_pb2.CommandList( list = newPotentialSched )
							self.simulator.changeFleetSchedules(command_list)
							self.reqCurrentPrice.update( { r:p_0 } )
							validRebalanceReq.append(r)
						else:
							print("**************veh schedule is not empty but idle, check**************")
					else:
						self.reposition[v] = ori_g
						reposition_command = common_pb2.Command(
							operation = common_pb2.Operation.Reposition,
							operationTime = 0,
							service=common_pb2.ServiceInfo(
								vehicle = v,
								request = r
							),
							destination= pickupLocation
						)
						command_list_p = common_pb2.CommandList( list = [reposition_command] )
						self.simulator.changeFleetSchedules(command_list_p)
					if v in self.vehIdle:
						self.vehIdle.remove(v)
			self.reqWaitingPool = [r for r in self.reqWaitingPool if r not in validRebalanceReq]

	def callback(self, request, context):
		# request is the time when the simulator calls back
		callBackTime = request.when
		# callback time every 10s, but the requests are grouped every 30s
		timeElapsed = (callBackTime-self.intialTime)*0.001 #in secs
		if timeElapsed % self.ttUpdate == 0 or timeElapsed == _CALL_BACK:
			# update vehicle position and between garage travel time every 5 mins
			print("-----------start updating travel time--------------")
			garage_points = [item[2] for item in self.garageTupleList]
			print("-----------number of garage points {}--------------".format(len(garage_points)))
			garage_updated = list()
			self.lookup = dict()
			tt_updating = time.time()
			for veh in self.vehicles:
				try:
					vehCurrentPos = self.simulator.getVehiclePosition(veh).position
				except:
					print( "vehicle garage before updating {}".format(self.vehicleGarage[veh]) )
					print("*****cannot get the vehicle's current position when updating travel time look up table*****")
				vehToAllGarage = self.simulator.getTravelTimeFromAtoMany(vehCurrentPos, garage_points, common_pb2.DRT)
				vehTravelTime = list(vehToAllGarage.travelTimes)
				index = vehTravelTime.index(min(vehTravelTime))
				veh_nearest_garage = self.garageTupleList[index][1]
				self.vehicleGarage.update( {veh:veh_nearest_garage} )
				# update point to point (OD) travel time, store in a dict
				if veh_nearest_garage not in garage_updated:
					garage_updated.append(veh_nearest_garage)
					self.lookup.update( {veh_nearest_garage:vehTravelTime} )
					closestThreeGarageIndex = sorted(range(len(vehTravelTime)), key=lambda k: vehTravelTime[k])[:self.closestGaraNum]
					closestGarageName = [self.garageTupleList[idx][1] for idx in closestThreeGarageIndex] 
					self.garageNearBy.update( {veh_nearest_garage:closestGarageName} )
			remain_garage = [ g for g in list(self.garageIndex.keys()) if g not in garage_updated]
			for remain_g in remain_garage:
				point_class = self.garageTupleList[self.garageIndex[remain_g]][2]
				oneToAllGarage = self.simulator.getTravelTimeFromAtoMany(point_class, garage_points, common_pb2.DRT)
				traveTime_list = list(oneToAllGarage.travelTimes)
				self.lookup.update( {remain_g:traveTime_list} )
				# update near by garages
				closestThreeGarageIndex = sorted(range(len(traveTime_list)), key=lambda k: traveTime_list[k])[:self.closestGaraNum]
				closestGarageName = [self.garageTupleList[idx][1] for idx in closestThreeGarageIndex] 
				self.garageNearBy.update( {remain_g:closestGarageName} )
			print("vehicle position and travel time updating time {}".format(round(time.time()-tt_updating,2)))
		if timeElapsed % self.stepLen != 0:
			return common_pb2.CallbackTime(when = callBackTime + _CALL_BACK*1000)
		timeStep = int( timeElapsed//self.stepLen ) -1
		if timeStep >= len(self.requestsInterval):
			return common_pb2.CallbackTime()
		print("--------------Got a callback at time {}--------------time step {}--------------".format( datetime.datetime.fromtimestamp(callBackTime/1000).strftime('%Y-%m-%d %H:%M:%S.%f'), timeStep))
		
		#----------------------------------------------------------------------------------------------------------------------------------------------------
		reqsCurrent = copy.deepcopy(self.requestsInterval[timeStep]) #requests id list at the current batch
		allAvaVeh = list() # for all the requests
		sameODReq = list()
		# add reqs in the waiting pool to the current req batch
		if len(reqsCurrent) < self.maxReqs:
			diff = self.maxReqs - len(reqsCurrent)
			if len(self.reqWaitingPool) < diff:
				reqsCurrent += self.reqWaitingPool
				self.reqWaitingPool = list()
			else:
				reqsCurrent += self.reqWaitingPool[:diff]
				self.reqWaitingPool = self.reqWaitingPool[diff:]
		actual_num_reqs = len(reqsCurrent)

		one_time_step_start = time.time()
		if len(reqsCurrent)>0:
			# requestInfo = dict()
			reqVehInfo = dict()
			for reqID in reqsCurrent:
				try:
					# convert str to the Point class to access x,y coordinate
					ori_g = self.demandInfo[reqID]["origin"]['object']
					des_g = self.demandInfo[reqID]["destination"]['object']
					# pickupLocation = common_pb2.Point(x=self.demandInfo[reqID]["origin"]['x'], y=self.demandInfo[reqID]["origin"]['y'])
					# dropoffLocation = common_pb2.Point(x=self.demandInfo[reqID]["destination"]['x'], y=self.demandInfo[reqID]["destination"]['y']) 
					if ori_g == des_g:
						sameODReq.append(reqID)
						continue
					self.computedSchedulePerRequest[reqID] = dict()
					vehNotFull = [veh for veh in self.vehicles if self.vehicleOccupancy[veh] < self.maxVehicleCapacity and len(self.vehicleSchedules[veh].schedule) < _MAX_COMMAND]
					# speed up available veh search, finding veh from nearby garages
					vehRank = dict()
					for veh in vehNotFull:
						if self.vehicleGarage[veh] in self.garageNearBy[ori_g]:
							if self.vehicleGarage[veh] not in vehRank:
								vehRank[self.vehicleGarage[veh]] = []
							vehRank[self.vehicleGarage[veh]].append(veh)
					avaVehs = list()
					# from the closest garage to the farthest
					for nearGarage in self.garageNearBy[ori_g]:
						if nearGarage in vehRank:
							avaVehs += vehRank[nearGarage]
						if len(avaVehs) > self.avaNum:
							break
					if len( avaVehs ) > self.avaNum:
						avaVehs = avaVehs[:self.avaNum-5]
					# adding idle vehicles
					nearest_idle_veh = list()
					for nearGarage in self.garageNearBy[ori_g]:
						if nearGarage in vehRank:
							idle_v = [v for v in vehRank[nearGarage] if v in self.vehIdle]
							nearest_idle_veh += idle_v
						if len(nearest_idle_veh)> self.avaNum:
							break
					for idle_v in nearest_idle_veh:
						if idle_v not in avaVehs:
							avaVehs.append(idle_v)
						if len(avaVehs) >= self.avaNum:
							break
					reqCurrentPrice = self.reqCurrentPrice
					vehicleInfo = dict()
					for veh in avaVehs:
						# convert vehSchedule class object to a dict
						# currVehSchedule = self.vehicleSchedules[veh].schedule
						vehicleInfo.update( {veh: {"garage":self.vehicleGarage[veh],"schedule":self.vehicleSchedules[veh].schedule, "occupancy": self.vehicleOccupancy[veh] } } )
						if veh not in allAvaVeh:
							allAvaVeh.append(veh)
					reqVehInfo.update( {reqID: vehicleInfo} )
				except Exception as e:
					print("******* finding ava vehicles error {} *******".format(e))
					continue
			print( "-----finding available vehicles takes {} secs".format( round(time.time() - one_time_step_start, 2) ) )
			# ------------------------------------------------------parallize the computation----------------------------------------------------------------
			lookUpTable = self.lookup
			chunksize = math.ceil(len(reqsCurrent)/_CPU_NUMBER)
			chunks = [reqsCurrent[x:x+chunksize] for x in range(0, len(reqsCurrent), chunksize)]
			future_list = list()
			# nestedReqVeh_test = list()
			for reqIDGroup in chunks:
				# req_chunk = {k:v for k,v in requestInfo.items() if k in reqIDGroup}
				veh_chunk = {k:v for k,v in reqVehInfo.items() if k in reqIDGroup }
				# res = ridesharingWorker(callBackTime, reqIDGroup, reqVehInfo, reqCurrentPrice, lookUpTable)
				# nestedReqVeh_test.update(res)
				future_list.append( self.executor.submit(ridesharingWorker, callBackTime, reqIDGroup, veh_chunk, 
									reqCurrentPrice, lookUpTable) )
			ridesharing_start_time = time.time()
			nestedReqVeh = dict()
			index_error = list()
			for idx,f in enumerate( future_list ):
				try:
					nestedReqVeh.update( f.result() )
				except Exception as e:
					index_error.append(idx)
					print( "-----future list Error, multiprocessing----- {}".format( e ) )
			print( "-----finish all requests loop time {}".format( round(time.time() - ridesharing_start_time, 2) ) )
			# ----------------------------------------------------------------------------------------------------------------------------------------------------
			# loop over all req-veh pair and add a penalty cost to these invalid pairs, profit times probability
			# note that some requests could not be served by all vehicles, waiting or leaving
			loop_all_req_veh = time.time()
			unmatchedReq = list()                       # 0. unmatched reqs at the current batch
			for req in reqsCurrent:
				noAvaVehFlag = True
				numChoosePrivate = 0
				for veh in allAvaVeh:
					try:
						profit = nestedReqVeh[req][veh]["profit"]
						pickup_g = self.demandInfo[req]["origin"]["object"]
						dropoff_g = self.demandInfo[req]["destination"]["object"] 
						tripTime = self.lookup[pickup_g][self.garageIndex[dropoff_g]]
						tripDist = self.distance_look_up[pickup_g][self.garageIndex[dropoff_g]]
						probi = userChoice ( tripTime, tripDist, nestedReqVeh[req][veh]["schedule"]["totalTravelTime"], 
											nestedReqVeh[req][veh]["updatedPrice"][req] )
						if probi["DRT"] < 0.5:
							probi["DRT"] = 0
							numChoosePrivate += 1
						nestedReqVeh[req][veh]["profit"] = profit*probi["DRT"]
						# additional travel time times probability
						# nestedReqVeh[req][veh]["schedule"]["additionalTT"] = nestedReqVeh[req][veh]["schedule"]["additionalTT"]*(1-probi["DRT"])
						nestedReqVeh[req][veh].update ( {"probability":probi} )
						noAvaVehFlag = False
					except:
						nestedReqVeh.setdefault(req, {}).setdefault(veh, {})
						nestedReqVeh[req][veh] = { "profit": -10000 }
						# nestedReqVeh[req][veh] = { "schedule": {"additionalTT":10000000} }
				# assign a private car to serve unmatched request
				if noAvaVehFlag or numChoosePrivate == self.avaNum:
					unmatchedReq.append(req)
			unmatchedReq = unmatchedReq + sameODReq     # 1. unmatched reqs due to no avalibale vehs or choose private cars
			reqsCurrent = [ r for r in reqsCurrent if r not in unmatchedReq]
			print( "loop over all req veh pair {}".format( round(time.time() - loop_all_req_veh, 2) ) )
			# start optimization
			opt_start = time.time()
			model = gurobipy.Model("request to vehicle assignment")
			x = model.addVars(reqsCurrent, allAvaVeh, vtype=gurobipy.GRB.BINARY)
			model.update()
			model.setObjective(
								gurobipy.quicksum(nestedReqVeh[req][veh]["profit"]*x[req,veh] for req in reqsCurrent for veh in allAvaVeh) 
								- zeta*( len(reqsCurrent) - gurobipy.quicksum(x[req,veh] for req in reqsCurrent for veh in allAvaVeh) ), 
								sense=gurobipy.GRB.MAXIMIZE
							)
			model.addConstrs(gurobipy.quicksum(x[req,veh] for req in reqsCurrent) <= 1 for veh in allAvaVeh)
			model.addConstrs(gurobipy.quicksum(x[req,veh] for veh in allAvaVeh) <= 1 for req in reqsCurrent)
			model.optimize()
			# deliver the assignment result to the fleetManagement module, call reprogramFleet to create vehicle commands, where each veh needs to go
			if model.status == gurobipy.GRB.Status.OPTIMAL:
				solution = [k for k, v in model.getAttr('x', x).items() if v == 1]
				# mysterious missing requests
				print("--------num of optimization reqs {}--------".format(len(reqsCurrent)))
				print("--------num of solution {}--------".format( len(solution) ))
				if len(solution) != len(reqsCurrent):
					print("***********optimization solution length {} not equal to requests number {}***********".format(len(solution), len(reqsCurrent)))
				reqsInSolution = [item[0] for item in solution]
				reqsLeftByOpt  = [r for r in reqsCurrent if r not in reqsInSolution]
				for s in solution:
					requestID = s[0]
					idVeh = s[1]
					try:
						# let the user choose
						probi = nestedReqVeh[requestID][idVeh]["probability"]
						mode = max(probi, key=probi.get)
						if mode == "DRT":
							finalPrice = nestedReqVeh[requestID][idVeh]["updatedPrice"]
							newProfit = nestedReqVeh[requestID][idVeh]["profit"]
							hp_flag = 0
							for r, v in finalPrice.items():
								if r in self.reqCurrentPrice:
									if v > self.reqCurrentPrice[r]:
										hp_flag = 1
							# if newProfit < 0:
							# 	print("************no profit for serving this request************")
							# change the vehicle schedule and update the price
							if not hp_flag and newProfit > 0:
								self.computedSchedulePerRequest[requestID].update( 
									{
										"schedule": nestedReqVeh[requestID][idVeh]["schedule"],
										"reqDeadline": nestedReqVeh[requestID][idVeh]["reqDeadline"],
										"initialPrice": nestedReqVeh[requestID][idVeh]["updatedPrice"][requestID]
									}
								)
								resultSchedule = nestedReqVeh[requestID][idVeh]["schedule"]["newSchedule"]
								self.vehicleSchedules[idVeh].updateCurrentSchedule(resultSchedule)
								command_list = common_pb2.CommandList( list = resultSchedule )
								self.simulator.changeFleetSchedules(command_list)
								if idVeh in self.vehIdle:
									self.vehIdle.remove(idVeh)
								self.reqCurrentPrice.update( finalPrice )
							else:
								self.unfair.append(requestID)
						else:
							unmatchedReq.append(requestID)  # 2. unmatched reqs due to actively choose private cars
					except Exception as e:
						print( "-----fake solution error {}; profit{}-----".format(e, round(nestedReqVeh[requestID][idVeh]["profit"], 2)) )
						unmatchedReq.append(requestID)  # fake solution, in solution but not valid
				print("--------num of idle vehicles after optimization {}--------".format( len(self.vehIdle) ))
				unmatchedReq += reqsLeftByOpt           # 3. reqs in the reqsCurrent but not in the optimization results
			else:
				print("***************The optimization model is infeasible*******************")
				self.infeasibility += 1 
				unmatchedReq += reqsCurrent             # 4. unmatched reqs due to infeasibility

			for r in unmatchedReq:
				if r not in self.reqWaitingPool and r not in self.unfair:
					self.reqWaitingPool.append(r)
			print( "--------------optimization and fleet reprogram {}--------------".format( round(time.time() - opt_start, 2) ) )
		
		# rebalancing and assign expired requests to private cars every certain minutes
		if timeElapsed % self.pvAssign == 0:
			self.rebalancing(callBackTime)
			failed_reqs = [ r for r in self.reqWaitingPool if self.demandInfo[r]["time"] + self.demandInfo[r]["reservation_time"] <= callBackTime]
			self.reqWaitingPool = [r for r in self.reqWaitingPool if r not in failed_reqs]  # remove failed reqs from waiting pool
			failed_reqs += self.unfair
			self.unfair = list()
			self.requestsFailedServing += failed_reqs
			for req in failed_reqs:
				pickupLocation = common_pb2.Point(x=self.demandInfo[req]["origin"]['x'], y=self.demandInfo[req]["origin"]['y'])
				dropoffLocation = common_pb2.Point(x=self.demandInfo[req]["destination"]['x'], y=self.demandInfo[req]["destination"]['y'])
				originG = self.demandInfo[req]["origin"]['object']
				try:
					if len(self.garagePrivateCar[originG]) == 0:
						nearByGarage = copy.deepcopy(self.garageNearBy[originG])
						if len(nearByGarage)> self.privateSearchNum:
							nearByGarage = nearByGarage[:self.privateSearchNum]
						# [index, number of private vehs]
						previousLen = [None, 0]
						for idx, nbg in enumerate(nearByGarage):
							if len(self.garagePrivateCar[nbg])>previousLen[1]:
								previousLen = [idx, len(self.garagePrivateCar[nbg])]
						if previousLen[0] == None:
							self.noPrivateCarGarage.append( originG )
							continue
						garage_with_most_veh = nearByGarage[previousLen[0]]
						pv = random.choice(self.garagePrivateCar[garage_with_most_veh])
						self.garagePrivateCar[garage_with_most_veh].remove(pv)
					else:
						pv = random.choice(self.garagePrivateCar[originG])
						self.garagePrivateCar[originG].remove(pv)
					self.priVehDestination.update( { pv:[req, self.demandInfo[req]["destination"]["object"]] } )
					pu_command = common_pb2.Command(
						operation = common_pb2.Operation.Pickup,
						operationTime = 10,
						service=common_pb2.ServiceInfo(
							vehicle = pv,
							request = req
						),
						destination= pickupLocation
					)
					do_command = common_pb2.Command(
						operation = common_pb2.Operation.Deliver,
						operationTime = 10,
						service=common_pb2.ServiceInfo(
							vehicle = pv,
							request = req
						),
						destination=dropoffLocation
					)
					command_list_p = common_pb2.CommandList( list = [pu_command, do_command] )
					self.simulator.changeFleetSchedules(command_list_p)
				except Exception as e:
					# print( "*******************No private car for req = {}, error {}**************************".format(req, e) )
					self.noPrivateCarGarage.append(req)
		num_initial_requests = len(self.requestsInterval[timeStep])
		one_step_computation_time = round(time.time()-one_time_step_start,2)
		print( "--------------one step with {} initial reqs, {} real reqs, takes {} s, average {} req/s--------------".format( num_initial_requests, actual_num_reqs, one_step_computation_time, round(actual_num_reqs/one_step_computation_time,2)) )
		print([num_initial_requests, actual_num_reqs, len(reqsCurrent), len(solution), len(self.vehIdle), one_step_computation_time])
		# if (actual_num_reqs - len(solution))/actual_num_reqs > 0.15 and len(self.vehIdle)>300:
		# 	self.closestGaraNum = 100
		self.simulationInfo.update( 
			{timeStep:[num_initial_requests, actual_num_reqs, len(reqsCurrent), len(solution), len(self.vehIdle), one_step_computation_time]}
		)
		next_time = callBackTime + _CALL_BACK*1000 # you can ofc make this configurable from the update_interval attribute of the simulation experiment class (like Simon did)
		return common_pb2.CallbackTime(when=next_time)

	def startService( self, request, context ):
		print( "startService  request = {}".format(request) )
		return empty_pb2.Empty()

	def endService( self, request, context ):
		print( "endService" )
		return empty_pb2.Empty()

	def rejected( self, request, context ):
		print( "rejected" )
		return empty_pb2.Empty()

	def dropService( self, request, context ):
		print( "dropService" )
		return empty_pb2.Empty()

	def segmentStarted( self, request, context ):
		print( "segmentStarted = {}".format(request))
		return empty_pb2.Empty()

	def segmentCompleted( self, request, context ):
		print( "segmentCompleted = {}".format(request))
		return empty_pb2.Empty()

	def reprogramFleet(self, request, context):
		return common_pb2.FleetCommandList()
	
	def state( self, request, context ):
		# print( "***")
		# print("New state for vehicle {} state {} at time {}  {}".format( request.service.vehicle, request.state, request.when, datetime.datetime.fromtimestamp(request.when/1000).strftime('%Y-%m-%d %H:%M:%S.%f') ) )
		# print( "   ............. New state - VehicleState = {}".format( request ) )
		## Get the State
		state_options={0:'Idle',  1:"Travelling to origin", 2:'At pickup', 3:'Travelling to destination',4:'At delivery',
		5: 'Repositioning', 6: 'At reposition point',7:'Active',8:'Inactive',9:'PickupDone', 10:'DeliveryDone'}
		state=request.state
		state=state_options[state]
		interested_states = [0, 5, 6, 1, 2, 3, 4, 9, 10]

		## Get Time
		time=datetime.datetime.fromtimestamp(request.when/1000)
		time=time.strftime('%H:%M:%S')
		# initialize
		from_garage = 0
		to_garage = 0
		occupancy = 0

		if request.state in interested_states:
			# idRequest = request.service.request[1:-1]
			vehId = request.service.vehicle[1:-1]
			# vehId = self.computedSchedulePerRequest[idRequest]["vehId"]
			if vehId in self.privateVeh:
				no_update_flag = 0
				try:
					req_id = self.priVehDestination[vehId][0]
					if request.state == Operator_pb2.DeliveryDone:
						do_g = self.priVehDestination[vehId][1]
						self.garagePrivateCar[do_g].append(vehId)
						self.priVehDestination.pop(vehId, None)	
				except Exception as e:
					# when vehicle state is idle there is no previous veh destination
					no_update_flag = 1
					# print( "**************private car state updating error {}, veh state{}*****************".format(e,request.state) )
			else:
				from_garage = self.vehicleGarage[vehId]
				try:
					reqId = copy.deepcopy(self.vehicleSchedules[vehId].schedule[0].service.request)
				except Exception as e:
					reqId = 0
				if request.state == Operator_pb2.AtPickup:
					self.requestEventTime.update( {reqId:[request.when]} )
					self.vehicleSchedules[vehId].removeCommandFromSchedule()
					self.vehicleOccupancy[vehId] += 1
					self.vehicleGarage[vehId] = self.demandInfo[reqId]["origin"]["object"]
					# print(self.vehicleOccupancy[vehId])
				elif request.state == Operator_pb2.AtDelivery:
					# record request drop off time
					# reqId = self.vehicleSchedules[vehId].schedule[0].service.request
					self.requestEventTime[reqId].append(request.when)
					self.vehicleSchedules[vehId].removeCommandFromSchedule()
					self.vehicleOccupancy[vehId] -= 1
					self.vehicleGarage[vehId] = self.demandInfo[reqId]["destination"]["object"]
				elif request.state == Operator_pb2.Idle:
					if vehId not in self.vehIdle and len(self.vehicleSchedules[vehId].schedule)==0:
						self.vehIdle.append(vehId)
				elif request.state == Operator_pb2.Repositioning:
					to_garage = self.reposition[vehId]
				elif request.state == Operator_pb2.AtRepositionPoint:
					self.reposition.pop(vehId, None)
					if vehId not in self.vehIdle and len(self.vehicleSchedules[vehId].schedule)==0:
						self.vehIdle.append(vehId)

			## position 
			# point=self.simulator.getVehiclePosition(vehId).position
			# x=round(point.x,2)
			# y=round(point.y,2)

			if vehId in self.privateVeh:
				if not no_update_flag:
					self.private_trip_data.update_data(vehId,time,req_id,state,from_garage,to_garage,occupancy)
			else:
				occupancy = self.vehicleOccupancy[vehId]
				self.simulation_data.update_data(vehId,time,reqId,state,from_garage,to_garage,occupancy)
		return empty_pb2.Empty()

	def finish( self, request, context ):
		final_data=self.simulation_data.get_data()
		final_data.to_csv(os.path.join(output_file_dir, "final_data.csv"))
		print('DRT Data Saved!')
		
		final_data=self.private_trip_data.get_data()
		final_data.to_csv(os.path.join(output_file_dir, "private_trip_data.csv"))
		print('Private Data Saved!')

		print( "finish" )
		print("---running time: %s hours ---" % ( round( (time.time() - sim_start_time)/3600,2) ) )
		# store request event time and price to json files
		with open(os.path.join(output_file_dir, 'requestEvents.json'), 'w') as f:
			for k,value in self.demandInfo.items():
				if k in self.requestEventTime:
					self.requestEventTime[k].insert(0, self.demandInfo[k]["time"])
			json.dump(self.requestEventTime, f, indent=4)
		with open(os.path.join(output_file_dir, 'requestPrice.json'), 'w') as f:
			requestsPrice = {}
			for k,value in self.reqCurrentPrice.items():
				try:
					init_price = self.computedSchedulePerRequest[k]["initialPrice"]
					requestsPrice.update( {k : [init_price, value]} )
				except Exception as e:
					# print("store the final price error {}".format(e)) # no initialPrice, reqs not choose DRT
					pass
			print( "length of requestsPrice --- {}".format( len(requestsPrice) ) )
			json.dump(requestsPrice, f, indent=4)
		with open(os.path.join(output_file_dir, "no_pv_garage.json"),"w") as f:
			json.dump(self.noPrivateCarGarage, f, indent=4)
		with open(os.path.join(output_file_dir, "simulation_info.json"),"w") as f:
			json.dump(self.simulationInfo, f, indent=4)
		with open("vehicle_occupancy.json","w") as f:
			json.dump(self.vehOccuRecord, f, indent=4)
		print( "Number of infeasiblity {}".format(self.infeasibility) )
		print( "Number of Unserved requests --- {}".format( len(self.requestsFailedServing) ) )
		print( "Number of Unserved requests cannot find pv --- {}".format( len(self.noPrivateCarGarage) ) )
		# stop this app
		global keepRunning
		keepRunning = False
		return empty_pb2.Empty()

def serve( args ):
	# executor = futures.ProcessPoolExecutor(max_workers=_CPU_NUMBER)
	# the connection to Aimsun Next simulator
	simulator = SimulatorClient( args.simulatorAddress )
	# our gRPC server
	server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
	# Operator_pb2_grpc.add_OperatorServicer_to_server( OperatorServicer( simulator, executor, args.operatorFile, args.requestFile), server)
	Operator_pb2_grpc.add_OperatorServicer_to_server( OperatorServicer( simulator, args.operatorFile, args.requestFile), server)
	server.add_insecure_port( "[::]:{}".format( args.operatorPort ) )
	server.start()
	print("waiting for simulator to start")
	try:
		# stop after finishing the simulation or when the user stops this python app
		while keepRunning:
			time.sleep(_TEN_SECONDS)
	except KeyboardInterrupt:
		server.stop(0)

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument("--simulator-address", dest="simulatorAddress",
				help="TCP/IP <Address and port>. By default localhost:45000.", default="localhost:45000")
	parser.add_argument("--operator-port", dest="operatorPort",
				help="TCP/IP <port>. By default localhost:45001.", default="45001" )
	parser.add_argument("--operator", dest="operatorFile",
				help="Path to an operator definition <file>.", metavar="INFILE")
	parser.add_argument("--demand", dest="requestFile",
				help="Path to a request definition <file>.", metavar="INFILE")
	args = parser.parse_args()

	if args.operatorFile:
		serve( args )
	else:
		parser.print_help()
