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

from concurrent import futures
from VehSchedule import *
from google.protobuf import empty_pb2


_TEN_SECONDS = 10
_CALL_BACK   = 10
_MAX_COMMAND = 10
_CLOSEST_GARAGE = 4
zeta = 1 # e/req
keepRunning = True
PRICE_PARA = {'base':2.5, 'time':0.2, 'distance': 0.6, 'cost':0.4} # 0.4e/min or e/km

# data save class
class DataSave():

	def __init__(self):
		self.data=pd.DataFrame({'veh_id':[],'time':[],'request_id':[],'state':[],'pos_x':[],'pos_y':[]})
	def get_data(self):
		return self.data.copy()
	def set_data(self,new_data):
		self.data=new_data.copy()
	def update_data(self,veh_ID,time,requst_id,state,x,y):
		row=pd.DataFrame({'veh_id':[veh_ID],'time':[time],'request_id':[requst_id],'state':[state],'pos_x':[x],'pos_y':[y]})
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
	privatePara = {"beta_0":0, "beta_t":0.6, "beta_f":3.2, "fix_cost":6, "via_cost":0.6}
	DRTPara = {"beta_0":-0.8, "beta_t":0.6, "beta_f":3.2}
	utilityPrivate = privatePara["beta_0"]-privatePara["beta_t"]*tripTime/60000 - privatePara["beta_f"]*( privatePara["via_cost"]*tripDist*0.001 + privatePara["fix_cost"])
	utilityDRT = DRTPara["beta_0"]- DRTPara["beta_t"]*tt/60000 - DRTPara["beta_f"]*fare
	p_DRT = math.exp(utilityDRT)/(math.exp(utilityPrivate) + math.exp(utilityDRT))
	p_private = math.exp(utilityPrivate)/(math.exp(utilityPrivate) + math.exp(utilityDRT))
	probi = { 'DRT':round(p_DRT,2), 'private':round(p_private,2)}
	return probi

# Our operator
class OperatorServicer(Operator_pb2_grpc.OperatorServicer):

	def __init__(self, simulator, operatorFile, requestFile):
		self.stepLen = 30              # unit s
		self.simHorizon = 8100         # unit s, including 15 mins cool down process
		self.ttUpdate = 300            # s
		self.pvAssign = 120            # s
		self.intialTime = 21600000     # ms, simulation init_time, from 8 to 9.30 am Helsinki time
		self.timeOffset = 0            # milliseconds, request time needs to add this value, minus one hour
		self.avaNum = 10               # number of available vehicles
		self.maxReqs= 300              # max allowed number of reqs
		# self.maxWtThreshold = 0.5
		# self.maxTttThreshold = 0.5
		self.maxVehicleCapacity = 4    # TODO: hardcoded; need to change
		self.minimumFare = 4
		self.profit_tax = 0.7

		self.lookup = dict()
		self.distance_look_up = dict()
		self.requests = list()
		self.demandInfo = dict()
		self.reqCurrentPrice = dict()
		self.requestsInterval = dict()
		self.simulator = simulator
		self.simulation_data = DataSave()
		self.private_trip_data = DataSave()
		self.privateVeh = list()
		self.priVehDestination = dict()
		self.garagePrivateCar = dict()
		self.vehicles = list()
		self.vehicleGarage = dict()
		self.garageIndex = dict()
		self.garageTupleList = list()
		self.garageNearBy = dict()
		self.vehicleSchedules = dict()
		self.vehicleOccupancy = dict()
		self.offersPerRequest = dict()
		self.requestEventTime = dict()
		self.computedSchedulePerRequest = dict()  # record requests inital schedule, fatest travel time, and price
		self.requestsFailedServing = list()       # all reqs finally leave the system
		self.reqWaitingPool = list()
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
			self.vehicleGarage.update( {v["id"]: v["origin"]["object"]} )      # 609 garages, record every vehicle's initial garage, not include dummy private car
			self.vehicleOccupancy.update( {v["id"]: 0} )
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
		# establish a connection between garage and its coordinate point object
		garages = ['GARAGE 516', 'GARAGE 517', 'GARAGE 151', 'GARAGE 523', 'GARAGE 568', 'GARAGE 217', 'GARAGE 546', 'GARAGE 440', 'GARAGE 119', 'GARAGE 66', 'GARAGE 28', 'GARAGE 385', 'GARAGE 154', 'GARAGE 518', 'GARAGE 529', 'GARAGE 54', 'GARAGE 15', 'GARAGE 490', 'GARAGE 170', 'GARAGE 130', 'GARAGE 145', 'GARAGE 531', 'GARAGE 431', 'GARAGE 615', 'GARAGE 65', 'GARAGE 564', 'GARAGE 159', 'GARAGE 215', 'GARAGE 289', 'GARAGE 403', 'GARAGE 538', 'GARAGE 24', 'GARAGE 133', 'GARAGE 553', 'GARAGE 277', 'GARAGE 124', 'GARAGE 108', 'GARAGE 418', 'GARAGE 484', 'GARAGE 368', 'GARAGE 204', 'GARAGE 148', 'GARAGE 394', 'GARAGE 310', 'GARAGE 216', 'GARAGE 367', 'GARAGE 135', 'GARAGE 114', 'GARAGE 4', 'GARAGE 191', 'GARAGE 274', 'GARAGE 37', 'GARAGE 429', 'GARAGE 112', 'GARAGE 382', 'GARAGE 577', 'GARAGE 601', 'GARAGE 45', 'GARAGE 284', 'GARAGE 402', 'GARAGE 64', 'GARAGE 409', 'GARAGE 180', 'GARAGE 27', 'GARAGE 407', 'GARAGE 160', 'GARAGE 537', 'GARAGE 52', 'GARAGE 563', 'GARAGE 416', 'GARAGE 565', 'GARAGE 421', 'GARAGE 322', 'GARAGE 554', 'GARAGE 597', 'GARAGE 526', 'GARAGE 198', 'GARAGE 22', 'GARAGE 425', 'GARAGE 40', 'GARAGE 29', 'GARAGE 245', 'GARAGE 486', 'GARAGE 308', 'GARAGE 282', 'GARAGE 48', 'GARAGE 540', 'GARAGE 337', 'GARAGE 547', 'GARAGE 539', 'GARAGE 392', 'GARAGE 291', 'GARAGE 465', 'GARAGE 432', 'GARAGE 187', 'GARAGE 150', 'GARAGE 34', 'GARAGE 72', 'GARAGE 536', 'GARAGE 123', 'GARAGE 544', 'GARAGE 556', 'GARAGE 347', 'GARAGE 457', 'GARAGE 111', 'GARAGE 395', 'GARAGE 369', 'GARAGE 91', 'GARAGE 84', 'GARAGE 137', 'GARAGE 3', 'GARAGE 442', 'GARAGE 552', 'GARAGE 598', 'GARAGE 175', 'GARAGE 422', 'GARAGE 370', 'GARAGE 299', 'GARAGE 21', 'GARAGE 562', 'GARAGE 341', 'GARAGE 157', 'GARAGE 181', 'GARAGE 413', 'GARAGE 120', 'GARAGE 448', 'GARAGE 76', 'GARAGE 493', 'GARAGE 603', 'GARAGE 511', 'GARAGE 524', 'GARAGE 50', 'GARAGE 235', 'GARAGE 162', 'GARAGE 339', 'GARAGE 445', 'GARAGE 278', 'GARAGE 109', 'GARAGE 36', 'GARAGE 426', 'GARAGE 125', 'GARAGE 397', 'GARAGE 58', 'GARAGE 311', 'GARAGE 411', 'GARAGE 471', 'GARAGE 177', 'GARAGE 155', 'GARAGE 458', 'GARAGE 31', 'GARAGE 579', 'GARAGE 102', 'GARAGE 296', 'GARAGE 317', 'GARAGE 462', 'GARAGE 433', 'GARAGE 244', 'GARAGE 482', 'GARAGE 476', 'GARAGE 233', 'GARAGE 330', 'GARAGE 513', 'GARAGE 158', 'GARAGE 307', 'GARAGE 192', 'GARAGE 494', 'GARAGE 377', 'GARAGE 75', 'GARAGE 279', 'GARAGE 497', 'GARAGE 545', 'GARAGE 190', 'GARAGE 242', 'GARAGE 86', 'GARAGE 364', 'GARAGE 503', 'GARAGE 127', 'GARAGE 90', 'GARAGE 464', 'GARAGE 460', 'GARAGE 110', 'GARAGE 92', 'GARAGE 14', 'GARAGE 2', 'GARAGE 588', 'GARAGE 165', 'GARAGE 228', 'GARAGE 412', 'GARAGE 472', 'GARAGE 570', 'GARAGE 316', 'GARAGE 399', 'GARAGE 351', 'GARAGE 83', 'GARAGE 261', 'GARAGE 223', 'GARAGE 80', 'GARAGE 247', 'GARAGE 106', 'GARAGE 141', 'GARAGE 96', 'GARAGE 360', 'GARAGE 525', 'GARAGE 98', 'GARAGE 567', 'GARAGE 356', 'GARAGE 572', 'GARAGE 334', 'GARAGE 355', 'GARAGE 46', 'GARAGE 443', 'GARAGE 97', 'GARAGE 81', 'GARAGE 501', 'GARAGE 275', 'GARAGE 176', 'GARAGE 260', 'GARAGE 122', 'GARAGE 209', 'GARAGE 586', 'GARAGE 79', 'GARAGE 306', 'GARAGE 480', 'GARAGE 384', 'GARAGE 391', 'GARAGE 436', 'GARAGE 272', 'GARAGE 166', 'GARAGE 146', 'GARAGE 304', 'GARAGE 548', 'GARAGE 25', 'GARAGE 269', 'GARAGE 262', 'GARAGE 463', 'GARAGE 152', 'GARAGE 283', 'GARAGE 372', 'GARAGE 475', 'GARAGE 366', 'GARAGE 254', 'GARAGE 473', 'GARAGE 101', 'GARAGE 179', 'GARAGE 302', 'GARAGE 469', 'GARAGE 573', 'GARAGE 444', 'GARAGE 182', 'GARAGE 239', 'GARAGE 264', 'GARAGE 257', 'GARAGE 259', 'GARAGE 599', 'GARAGE 414', 'GARAGE 361', 'GARAGE 338', 'GARAGE 376', 'GARAGE 89', 'GARAGE 82', 'GARAGE 352', 'GARAGE 63', 'GARAGE 335', 'GARAGE 276', 'GARAGE 268', 'GARAGE 188', 'GARAGE 612', 'GARAGE 467', 'GARAGE 346', 'GARAGE 453', 'GARAGE 423', 'GARAGE 51', 'GARAGE 406', 'GARAGE 288', 'GARAGE 139', 'GARAGE 195', 'GARAGE 237', 'GARAGE 555', 'GARAGE 200', 'GARAGE 305', 'GARAGE 398', 'GARAGE 374', 'GARAGE 1', 'GARAGE 468', 'GARAGE 530', 'GARAGE 250', 'GARAGE 218', 'GARAGE 510', 'GARAGE 241', 'GARAGE 118', 'GARAGE 303', 'GARAGE 266', 'GARAGE 100', 'GARAGE 401', 'GARAGE 246', 'GARAGE 285', 'GARAGE 142', 'GARAGE 332', 'GARAGE 117', 'GARAGE 49', 'GARAGE 270', 'GARAGE 232', 'GARAGE 587', 'GARAGE 549', 'GARAGE 437', 'GARAGE 69', 'GARAGE 325', 'GARAGE 134', 'GARAGE 527', 'GARAGE 26', 'GARAGE 35', 'GARAGE 478', 'GARAGE 474', 'GARAGE 604', 'GARAGE 73', 'GARAGE 485', 'GARAGE 329', 'GARAGE 39', 'GARAGE 607', 'GARAGE 68', 'GARAGE 578', 'GARAGE 318', 'GARAGE 492', 'GARAGE 522', 'GARAGE 189', 'GARAGE 202', 'GARAGE 461', 'GARAGE 608', 'GARAGE 327', 'GARAGE 606', 'GARAGE 584', 'GARAGE 580', 'GARAGE 326', 'GARAGE 199', 'GARAGE 435', 'GARAGE 499', 'GARAGE 309', 'GARAGE 600', 'GARAGE 400', 'GARAGE 500', 'GARAGE 427', 'GARAGE 345', 'GARAGE 434', 'GARAGE 331', 'GARAGE 609', 'GARAGE 550', 'GARAGE 455', 'GARAGE 569', 'GARAGE 56', 'GARAGE 115', 'GARAGE 602', 'GARAGE 78', 'GARAGE 428', 'GARAGE 219', 'GARAGE 446', 'GARAGE 591', 'GARAGE 430', 'GARAGE 226', 'GARAGE 143', 'GARAGE 373', 'GARAGE 515', 'GARAGE 521', 'GARAGE 596', 'GARAGE 38', 'GARAGE 528', 'GARAGE 44', 'GARAGE 8', 'GARAGE 313', 'GARAGE 298', 'GARAGE 30', 'GARAGE 574', 'GARAGE 466', 'GARAGE 222', 'GARAGE 388', 'GARAGE 328', 'GARAGE 229', 'GARAGE 208', 'GARAGE 343', 'GARAGE 243', 'GARAGE 438', 'GARAGE 354', 'GARAGE 13', 'GARAGE 498', 'GARAGE 171', 'GARAGE 378', 'GARAGE 533', 'GARAGE 281', 'GARAGE 104', 'GARAGE 212', 'GARAGE 320', 'GARAGE 183', 'GARAGE 470', 'GARAGE 420', 'GARAGE 43', 'GARAGE 353', 'GARAGE 205', 'GARAGE 348', 'GARAGE 344', 'GARAGE 451', 'GARAGE 379', 'GARAGE 454', 'GARAGE 128', 'GARAGE 57', 'GARAGE 105', 'GARAGE 575', 'GARAGE 380', 'GARAGE 559', 'GARAGE 419', 'GARAGE 258', 'GARAGE 479', 'GARAGE 410', 'GARAGE 333', 'GARAGE 136', 'GARAGE 103', 'GARAGE 59', 'GARAGE 210', 'GARAGE 535', 'GARAGE 358', 'GARAGE 163', 'GARAGE 507', 'GARAGE 415', 'GARAGE 456', 'GARAGE 543', 'GARAGE 93', 'GARAGE 520', 'GARAGE 405', 'GARAGE 595', 'GARAGE 74', 'GARAGE 505', 'GARAGE 532', 'GARAGE 168', 'GARAGE 10', 'GARAGE 447', 'GARAGE 576', 'GARAGE 61', 'GARAGE 301', 'GARAGE 67', 'GARAGE 362', 'GARAGE 295', 'GARAGE 77', 'GARAGE 236', 'GARAGE 144', 'GARAGE 16', 'GARAGE 560', 'GARAGE 393', 'GARAGE 164', 'GARAGE 213', 'GARAGE 491', 'GARAGE 129', 'GARAGE 512', 'GARAGE 113', 'GARAGE 156', 'GARAGE 396', 'GARAGE 506', 'GARAGE 23', 'GARAGE 121', 'GARAGE 290', 'GARAGE 294', 'GARAGE 265', 'GARAGE 178', 'GARAGE 60', 'GARAGE 88', 'GARAGE 488', 'GARAGE 417', 'GARAGE 551', 'GARAGE 349', 'GARAGE 169', 'GARAGE 365', 'GARAGE 558', 'GARAGE 196', 'GARAGE 201', 'GARAGE 449', 'GARAGE 613', 'GARAGE 424', 'GARAGE 561', 'GARAGE 439', 'GARAGE 207', 'GARAGE 340', 'GARAGE 252', 'GARAGE 315', 'GARAGE 557', 'GARAGE 459', 'GARAGE 300', 'GARAGE 324', 'GARAGE 240', 'GARAGE 271', 'GARAGE 42', 'GARAGE 203', 'GARAGE 495', 'GARAGE 336', 'GARAGE 221', 'GARAGE 312', 'GARAGE 357', 'GARAGE 263', 'GARAGE 55', 'GARAGE 585', 'GARAGE 293', 'GARAGE 267', 'GARAGE 581', 'GARAGE 197', 'GARAGE 19', 'GARAGE 594', 'GARAGE 234', 'GARAGE 383', 'GARAGE 172', 'GARAGE 481', 'GARAGE 592', 'GARAGE 404', 'GARAGE 230', 'GARAGE 314', 'GARAGE 614', 'GARAGE 487', 'GARAGE 161', 'GARAGE 319', 'GARAGE 321', 'GARAGE 359', 'GARAGE 280', 'GARAGE 18', 'GARAGE 611', 'GARAGE 11', 'GARAGE 220', 'GARAGE 256', 'GARAGE 389', 'GARAGE 206', 'GARAGE 20', 'GARAGE 450', 'GARAGE 381', 'GARAGE 342', 'GARAGE 387', 'GARAGE 363', 'GARAGE 138', 'GARAGE 6', 'GARAGE 583', 'GARAGE 185', 'GARAGE 140', 'GARAGE 225', 'GARAGE 610', 'GARAGE 107', 'GARAGE 251', 'GARAGE 616', 'GARAGE 147', 'GARAGE 116', 'GARAGE 323', 'GARAGE 508', 'GARAGE 566', 'GARAGE 519', 'GARAGE 589', 'GARAGE 32', 'GARAGE 390', 'GARAGE 590', 'GARAGE 7', 'GARAGE 287', 'GARAGE 582', 'GARAGE 53', 'GARAGE 477', 'GARAGE 95', 'GARAGE 441', 'GARAGE 386', 'GARAGE 131', 'GARAGE 193', 'GARAGE 184', 'GARAGE 593', 'GARAGE 483', 'GARAGE 12', 'GARAGE 238', 'GARAGE 70', 'GARAGE 255', 'GARAGE 47', 'GARAGE 541', 'GARAGE 214', 'GARAGE 286', 'GARAGE 87', 'GARAGE 9', 'GARAGE 211', 'GARAGE 605', 'GARAGE 149', 'GARAGE 514', 'GARAGE 153', 'GARAGE 542', 'GARAGE 273', 'GARAGE 167', 'GARAGE 186', 'GARAGE 62', 'GARAGE 292', 'GARAGE 253', 'GARAGE 126', 'GARAGE 496', 'GARAGE 94', 'GARAGE 534', 'GARAGE 99', 'GARAGE 502', 'GARAGE 375', 'GARAGE 224', 'GARAGE 408', 'GARAGE 17', 'GARAGE 350', 'GARAGE 571', 'GARAGE 71', 'GARAGE 194', 'GARAGE 297', 'GARAGE 85', 'GARAGE 174', 'GARAGE 173', 'GARAGE 231', 'GARAGE 33', 'GARAGE 41', 'GARAGE 489', 'GARAGE 5', 'GARAGE 504', 'GARAGE 509']
		garages.sort(key= lambda x: float(x.strip('GARAGE ')))
		for index, garage_name in enumerate(garages):
			self.garageIndex.update( {garage_name:index} )
		
		garage_added = list()
		# only 609 garages
		for v,garage in self.vehicleGarage.items():
			if garage not in garage_added:
				garage_added.append(garage)
				index = garages.index(garage)
				vehCurrentPos = self.simulator.getVehiclePosition(v).position
				self.garageTupleList.append( ( index, garage, vehCurrentPos, round(vehCurrentPos.x,2), round(vehCurrentPos.y,2) ) )
		print("length of self garageTupleList {} before adding garage".format(len(self.garageTupleList)))

		# manually add garage 610
		if "GARAGE 610" not in garage_added:
			garage_added.append("GARAGE 610")
			index = garages.index("GARAGE 610")
			point = common_pb2.Point(x=381651.66, y=6589852.35)
			self.garageTupleList.append( ( index, "GARAGE 610", point, 381651.66, 6589852.35 ) )
		print("length of self garageTupleList after {}".format(len(self.garageTupleList)))

		self.garageTupleList = sorted(self.garageTupleList, key=lambda x: x[0])
		# with open("garageTupleList.json","w") as f:
		# 	json.dump(self.garageTupleList, f, indent=4)

		# save distance look up
		distance_look_up = {}
		for i,row in enumerate(self.garageTupleList):
			distance_list = list()
			for j,column in enumerate(self.garageTupleList):
				dis = self.simulator.eta( self.garageTupleList[i][2], self.garageTupleList[j][2], common_pb2.DRT ).segments[0].distance
				distance_list.append(dis)
			distance_look_up.update({self.garageTupleList[i][1]:distance_list})
		with open("distance_look_up.json","w") as f:
			json.dump(distance_look_up, f, indent=4)
		print("distance look up saved!")

		
		# load look up table
		with open('generate/time_look_up.json', 'r') as fp:
			self.lookup = json.load(fp)
		with open('generate/distance_look_up.json', 'r') as fp:
			self.distance_look_up = json.load(fp)
		global sim_start_time
		sim_start_time = time.time()
		return common_pb2.CallbackTime(when = now + _CALL_BACK*1000)

	def callback(self, request, context):
		# request is the time when the simulator calls back
		callBackTime = request.when
		# callback time every 10s, but the requests are grouped every 30s
		timeElapsed = (callBackTime-self.intialTime)*0.001 #in secs
		if timeElapsed % self.stepLen != 0:
			return common_pb2.CallbackTime(when = callBackTime + _CALL_BACK*1000)
		elif timeElapsed % self.ttUpdate == 0:
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
					closestThreeGarageIndex = sorted(range(len(vehTravelTime)), key=lambda k: vehTravelTime[k])[:_CLOSEST_GARAGE]
					closestGarageName = [self.garageTupleList[idx][1] for idx in closestThreeGarageIndex] 
					self.garageNearBy.update( {veh_nearest_garage:closestGarageName} )
			remain_garage = [ g for g in list(self.garageIndex.keys()) if g not in garage_updated]
			for remain_g in remain_garage:
				point_class = self.garageTupleList[self.garageIndex[remain_g]][2]
				oneToAllGarage = self.simulator.getTravelTimeFromAtoMany(point_class, garage_points, common_pb2.DRT)
				traveTime_list = list(oneToAllGarage.travelTimes)
				self.lookup.update( {remain_g:traveTime_list} )
				# update near by garages
				closestThreeGarageIndex = sorted(range(len(traveTime_list)), key=lambda k: traveTime_list[k])[:_CLOSEST_GARAGE]
				closestGarageName = [self.garageTupleList[idx][1] for idx in closestThreeGarageIndex] 
				self.garageNearBy.update( {remain_g:closestGarageName} )
			print("vehicle position and travel time updating time {}".format(round(time.time()-tt_updating,2)))
			with open("nearby_garages.json","w") as f:
				json.dump(self.garageNearBy, f, indent=4)
		timeStep = int( timeElapsed//self.stepLen ) -1
		# simulation end, check the ang file
		if timeStep >= len(self.requestsInterval):
			return common_pb2.CallbackTime()
		print("--------------Got a callback at time {}--------------time step {}--------------".format( datetime.datetime.fromtimestamp(callBackTime/1000).strftime('%Y-%m-%d %H:%M:%S.%f'), timeStep))
		
		#----------------------------------------------------------------------------------------------------------------------------------------------------
		reqsCurrent = copy.deepcopy(self.requestsInterval[timeStep]) #requests id list at the current batch
		allAvaVeh = list() # for all the requests
		sameODReq = list() # reqs have been cleaned, no reqs with same OD
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
			nestedReqVeh = dict()
			ridesharing_start_time = time.time()
			for reqID in reqsCurrent:
				now = callBackTime
				new_req_wt = self.demandInfo[reqID]["reservation_time"]
				new_req_dt = self.demandInfo[reqID]["detour_time"]
				# convert str to the Point class to access x,y coordinate
				ori_g = self.demandInfo[reqID]["origin"]['object']
				des_g = self.demandInfo[reqID]["destination"]['object']
				pickupLocation = common_pb2.Point(x=self.demandInfo[reqID]["origin"]['x'], y=self.demandInfo[reqID]["origin"]['y'])
				dropoffLocation = common_pb2.Point(x=self.demandInfo[reqID]["destination"]['x'], y=self.demandInfo[reqID]["destination"]['y']) 
				if ori_g == des_g:
					sameODReq.append(reqID)
					continue
				self.computedSchedulePerRequest[reqID] = dict()

				# finding first the optimal times if a DRT single service was used - to be used as lower bounds for the DRT-Pool performance ensurance (check violation critria below)
				# set waiting time lower bound to a constant
				vehNotFull = [veh for veh in self.vehicles if self.vehicleOccupancy[veh] < self.maxVehicleCapacity and len(self.vehicleSchedules[veh].schedule) < _MAX_COMMAND]
				response = self.simulator.etaVehicles( vehNotFull, pickupLocation )
				validVehs = sorted( list(filter( filterTravelTime, response.travelInfo )), key=travelTime )
				shortestLength = self.distance_look_up[ori_g][self.garageIndex[des_g]]
				# shortestLength = self.simulator.eta( pickupLocation, dropoffLocation, common_pb2.DRT ).segments[0].distance
				# test_length = self.distanceLookUp[ori_g][garage_index[des_g]]
				if len( validVehs ) > 0:
					# bestSingleDrtIvtt = self.simulator.eta( pickupLocation, dropoffLocation, common_pb2.DRT ).segments[0].inVehicleTime
					bestSingleDrtIvtt = self.lookup[ori_g][self.garageIndex[des_g]]
					bestSingleDrtWt = travelTime( validVehs[0] )
					#check the waiting time bound
					# if bestSingleDrtWt  < self.wtBound[0]:
					# 	bestSingleDrtWt = self.wtBound[0]
					# elif bestSingleDrtWt > self.wtBound[1]:
					# 	bestSingleDrtWt  = self.wtBound[1]
				# bestSingleDrtTtt = bestSingleDrtIvtt + bestSingleDrtWt
				# new req deadline
				bestSingleDrtTtt = bestSingleDrtIvtt + new_req_wt + new_req_dt
				if len( validVehs ) > self.avaNum:
					validVehs = validVehs[:self.avaNum]
				avaVehs = [item.segments[0].vehicle for item in validVehs]

				for veh in avaVehs:
					try:
						##each veh has a best schedule
						feasibleSchedules = list()
						try:
							currVehScheduleObject = copy.deepcopy(self.vehicleSchedules[veh])
						except KeyError:
							print("Vehile {} not in vehicle schedules dictionary. Check operator initialization".format(veh))
						currVehGarage = self.vehicleGarage[veh]
						pickUpTime = self.lookup[currVehGarage][self.garageIndex[ori_g]]
						pickUpDist = self.distance_look_up[currVehGarage][self.garageIndex[ori_g]]
						# if vehicle's schedule is empty (no commands) and it's idle, it's added directly to the list of possible alternatives
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

							if vwt > new_req_wt or totalTravelTime > bestSingleDrtTtt:
								continue
							else: 
								feasibleSchedules.append( 
									{
									"vehId": veh, 
									"newSchedule": newPotentialSched, 
									"insertionPositions": insertionPositions, 
									"totalTravelTime": totalTravelTime, 
									"waitingTime": vwt, 
									"inVehicleTravelTime": ivtt, 
									"walkingTime": wkt, 
									"distance": dist
									} 
								)
						else:
							scheduledCommandDestinations = list()
							commandGarage = list()
							
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
									currentVehOccupancy = self.vehicleOccupancy[veh]
									predictedOccupancy = currentVehOccupancy
									
									if currentVehOccupancy > self.maxVehicleCapacity:
										print("Occupancy issue with vehicle {}, current vehicle occupaancy is above capacity. Check occupancy update logic".format(veh))
										break
									
									nonFeasibleInsertion = False
									for command in newPotentialSched:
										if command.operation == common_pb2.Operation.Pickup:
											predictedOccupancy += 1
											if predictedOccupancy > self.maxVehicleCapacity:
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
										garage_name = [ item[1] for item in self.garageTupleList if math.isclose(item[3], comnd.destination.x, abs_tol = 0.9) and math.isclose(item[4], comnd.destination.y, abs_tol = 0.9)]
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
												vwt += self.lookup[currVehGarage][self.garageIndex[commandGarage[k]]]
												preGara = commandGarage[k]
											else:
												vwt += self.lookup[preGara][self.garageIndex[commandGarage[k]]]
												preGara = commandGarage[k]
									
									# check the total travel time only for the new request, note the total tt not include other preassigned requests
									ivtt = 0
									dist = 0
									if dropOffIndex == pickUpIndex + 1:
										ivtt = bestSingleDrtIvtt
									else:
										preGara = ori_g
										for k in range(pickUpIndex+1,dropOffIndex+1):
											ivtt += self.lookup[preGara][self.garageIndex[commandGarage[k]]]
											dist += self.distance_look_up[preGara][self.garageIndex[commandGarage[k]]]
											preGara = commandGarage[k]
									
									totalTravelTime = vwt + ivtt
									wkt = 0
									
									if vwt > new_req_wt or totalTravelTime > bestSingleDrtTtt:
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
													tempTripCompletionTime += self.lookup[currVehGarage][self.garageIndex[commandGarage[k]]]
												else:
													tempTripCompletionTime += self.lookup[commandGarage[k-1]][self.garageIndex[commandGarage[k]]]

											tempTripCompletionTimeClock = now + tempTripCompletionTime
											if tempTripCompletionTimeClock - self.demandInfo[trip_id]["time"] > self.computedSchedulePerRequest[trip_id]["fastestIdealTotalTravelTime"]:
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
														tempTripWaitingTime += self.lookup[currVehGarage][self.garageIndex[commandGarage[k]]]
													else:
														tempTripWaitingTime += self.lookup[commandGarage[k-1]][self.garageIndex[commandGarage[k]]]

											# now check how the trip's dropoff is affected
											previousDestination = scheduledCommandDestinations[tempPickupIdx]
											preGara = commandGarage[tempPickupIdx]
											tempTripInVehicleTime = 0
											for k in range(tempPickupIdx+1,tempDropoffIdx+1):
												tempTripInVehicleTime += self.lookup[preGara][self.garageIndex[commandGarage[k]]]
												preGara = commandGarage[k]
											
											tempTripCompletionTime = tempTripWaitingTime + tempTripInVehicleTime
											tempTripWaitingTimeClock = now + tempTripWaitingTime
											tempTripCompletionTimeClock = now + tempTripCompletionTime
											# computedSchedulePerRequest: initial vehicle schedule with
											if tempTripCompletionTimeClock - self.demandInfo[trip_id]["time"] > self.computedSchedulePerRequest[trip_id]["fastestIdealTotalTravelTime"] or tempTripWaitingTimeClock - self.demandInfo[trip_id]["time"] > self.demandInfo[trip_id]["reservation_time"]:
												nonFeasibleInsertion = True
												break
									
									scheduledCommandDestinations = list()
									commandGarage = list()

									if nonFeasibleInsertion:
										continue
									else:
										totalTravelTime = vwt + ivtt
										feasibleSchedules.append( 
											{
												"vehId": veh, 
												"newSchedule": newPotentialSched, 
												"insertionPositions": insertionPositions,
												"totalTravelTime": totalTravelTime,
												"waitingTime": vwt, 
												"inVehicleTravelTime": ivtt, 
												"walkingTime": wkt, 
												"distance": dist
											} 
										)

									scheduledCommandDestinations = list()
									commandGarage = list()

						if feasibleSchedules:
							sorted_schedules = sorted(feasibleSchedules, key=lambda i: (i['totalTravelTime'], i['waitingTime'])) 
							bestSchedule = sorted_schedules[0]
							# bestSingleDrtTtt = bestSingleDrtIvtt + bestSchedule['waitingTime']
							
							# ridesharing price, initialize request price
							totalDisInKm = (shortestLength + pickUpDist)*0.001                                   # convert m to km
							totalTimeInMin = (bestSingleDrtIvtt + pickUpTime)/60000                              # convert ms to min
							price_solo = PRICE_PARA["base"] + PRICE_PARA["time"]*totalTimeInMin + PRICE_PARA["distance"]*totalDisInKm
							p_0 = max( [self.minimumFare, round(price_solo,2)] )
							self.reqCurrentPrice.update( { reqID:p_0 } )

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
								profit = round(p_0 - serviceCost,2)*self.profit_tax
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
										garage_name = [ item[1] for item in self.garageTupleList if math.isclose(item[3], comnd.destination.x, abs_tol = 0.9) and math.isclose(item[4], comnd.destination.y, abs_tol = 0.9)]
										commandGarage_before.append( garage_name[0] )
									# loop over the preceeding schedule, fill in aloneDis
									for idx,cmd in enumerate(beforeInsertionSchedule):
										tripID = cmd.service.request
										if idx == 0:
											beforeInsertionTT += self.lookup[currVehGarage][self.garageIndex[commandGarage_before[0]]]
											totalTravelDisBefore  += self.distance_look_up[currVehGarage][self.garageIndex[commandGarage_before[0]]]
										else:
											beforeInsertionTT += self.lookup[commandGarage_before[idx-1]][self.garageIndex[commandGarage_before[idx]]]
											totalTravelDisBefore  += self.distance_look_up[commandGarage_before[idx-1]][self.garageIndex[commandGarage_before[idx]]]
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
										aloneFare[r]= self.reqCurrentPrice[r]
									# loop over new schedule
									totalTravelDisAfter = 0
									commandGarage_after = list()
									for comnd in sch_sharing:
										garage_name = [ item[1] for item in self.garageTupleList if math.isclose(item[3], comnd.destination.x, abs_tol = 0.9) and math.isclose(item[4], comnd.destination.y, abs_tol = 0.9)]
										commandGarage_after.append( garage_name[0] )
									for idx,cmd in enumerate( sch_sharing ):
										tripID = cmd.service.request
										if idx == 0:
											inVehicleTime = self.lookup[currVehGarage][self.garageIndex[commandGarage_after[idx]]]
											dist = self.distance_look_up[currVehGarage][self.garageIndex[commandGarage_after[idx]]]
											legFare = PRICE_PARA["time"]*inVehicleTime/60000  + PRICE_PARA["distance"]*dist*0.001
											totalTravelDisAfter += dist
										else:
											ivt = self.lookup[commandGarage_after[idx-1]][self.garageIndex[commandGarage_after[idx]]]
											dist = self.distance_look_up[commandGarage_after[idx-1]][self.garageIndex[commandGarage_after[idx]]]
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
									finalFee = [ max([self.minimumFare, round(a*b,2)]) for a,b in zip( list( aloneFare.values() ), discount ) ]
									updatedPrice = dict( [(m,n) for m,n in zip(shared_rid, finalFee)] )
									delta_p = 0
									for r in shared_rid:
										if r ==reqID:
											delta_p += updatedPrice[reqID]
										else:
											dp = updatedPrice[r] - aloneFare[r]
											delta_p += dp
									# after including the new req, how much the profit increase (maginal profit)
									profit = round(delta_p - (totalTravelDisAfter-totalTravelDisBefore)*PRICE_PARA["cost"]*0.001,2)
								except Exception as e:
									print("***************ridesharing price error {}************".format(e))
							# store final feasible schedules and profit
							nestedReqVeh.setdefault(reqID, {}).setdefault(veh, {})
							nestedReqVeh[reqID][veh] = {
										"profit": profit,
										"schedule": bestSchedule,
										"updatedPrice": updatedPrice,
										"fastestIdealTotalTravelTime": bestSingleDrtTtt,
										"fastestIdealWaitingTime": bestSingleDrtWt,
							}
							if veh not in allAvaVeh:
								allAvaVeh.append(veh)
					except Exception as e:
						print( "******************************error within vehicle for loop {}***********************************".format( e ) )
						continue
			print( "--------------finish all requests loop time {}--------------".format( round(time.time() - ridesharing_start_time, 2) ) )

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
						nestedReqVeh[req][veh].update ( {"probability":probi} )
						noAvaVehFlag = False
					except:
						nestedReqVeh.setdefault(req, {}).setdefault(veh, {})
						nestedReqVeh[req][veh] = { "profit": -10000 }
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
			# model.addConstr(gurobipy.quicksum(x[req, veh] for req in reqsCurrent for veh in allAvaVeh) == min([len(reqsCurrent), len(allAvaVeh)]))
			model.addConstrs(gurobipy.quicksum(x[req,veh] for req in reqsCurrent) <= 1 for veh in allAvaVeh)
			model.addConstrs(gurobipy.quicksum(x[req,veh] for veh in allAvaVeh) <= 1 for req in reqsCurrent)
			model.optimize()
			# deliver the assignment result to the fleetManagement module, call reprogramFleet to create vehicle commands, where each veh needs to go
			if model.status == gurobipy.GRB.Status.OPTIMAL:
				solution = [k for k, v in model.getAttr('x', x).items() if v == 1]
				# mysterious missing requests
				if len(solution) != len(reqsCurrent):
					print("***********optimization solution length {} not equal to requests number {}***********".format(len(solution), len(reqsCurrent)))
				reqsInSolution = [item[0] for item in solution]
				reqsLeftByOpt  = [r for r in reqsCurrent if r not in reqsInSolution]
				for s in solution:
					requestID = s[0]
					idVeh = s[1]
					# let the user choose
					probi = nestedReqVeh[requestID][idVeh]["probability"]
					mode = max(probi, key=probi.get)
					if mode == "DRT":
						# change the vehicle schedule and update the price
						self.computedSchedulePerRequest[requestID].update( 
							{
								"schedule": nestedReqVeh[requestID][idVeh]["schedule"],
								"fastestIdealTotalTravelTime": nestedReqVeh[requestID][idVeh]["fastestIdealTotalTravelTime"],
								"fastestIdealWaitingTime": nestedReqVeh[requestID][idVeh]["fastestIdealWaitingTime"],
								"initialPrice": nestedReqVeh[requestID][idVeh]["updatedPrice"][requestID]
							}
						)
						resultSchedule = nestedReqVeh[requestID][idVeh]["schedule"]["newSchedule"]
						self.vehicleSchedules[idVeh].updateCurrentSchedule(resultSchedule)
						command_list = common_pb2.CommandList( list = resultSchedule )
						self.simulator.changeFleetSchedules(command_list)
						finalPrice = nestedReqVeh[requestID][idVeh]["updatedPrice"]
						self.reqCurrentPrice.update( finalPrice )
					else:
						unmatchedReq.append(requestID)  # 2. unmatched reqs due to actively choose private cars
				unmatchedReq += reqsLeftByOpt           # 3. reqs in the reqsCurrent but not in the optimization results
			else:
				print("The optimization model is infeasible")
				# self.reqWaitingPool += [ r for r in reqsCurrent if r not in self.reqWaitingPool]
				unmatchedReq += reqsCurrent             # 4. unmatched reqs due to infeasibility

			for r in unmatchedReq:
				if r not in self.reqWaitingPool:
					self.reqWaitingPool.append(r)
			print( "--------------optimization and fleet reprogram {}--------------".format( round(time.time() - opt_start, 2) ) )
			
		# assign expired requests to private cars every certain minutes
		if timeElapsed % self.pvAssign == 0:
			failed_reqs = [ r for r in self.reqWaitingPool if self.demandInfo[r]["time"] + self.demandInfo[r]["reservation_time"] <= callBackTime]
			self.reqWaitingPool = [r for r in self.reqWaitingPool if r not in failed_reqs]  # remove failed reqs from waiting pool
			self.requestsFailedServing += failed_reqs
			# half = int(len(unmatchedReq)/2)
			# halfReqs = unmatchedReq[0:half]
			for req in failed_reqs:
				pickupLocation = common_pb2.Point(x=self.demandInfo[req]["origin"]['x'], y=self.demandInfo[req]["origin"]['y'])
				dropoffLocation = common_pb2.Point(x=self.demandInfo[req]["destination"]['x'], y=self.demandInfo[req]["destination"]['y'])
				originG = self.demandInfo[req]["origin"]['object']
				try:
					if len(self.garagePrivateCar[originG]) == 0:
						nearByGarage = self.garageNearBy[originG]
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
		next_time = callBackTime + _CALL_BACK*1000 # you can ofc make this configurable from the update_interval attribute of the simulation experiment class (like Simon did)
		return common_pb2.CallbackTime(when=next_time)
	

	# make an offer using the best vehicle
	def offerAccepted( self, request, context ):
		print( "OfferAccepted request = {}".format(request) )

		vehId = self.computedSchedulePerRequest[request.id]["schedule"]["vehId"]
		resultSchedule = self.computedSchedulePerRequest[request.id]["schedule"]["newSchedule"]

		self.vehicleSchedules[vehId].updateCurrentSchedule(resultSchedule)
		
		result = common_pb2.CommandList( list=resultSchedule)

		return result

	def startService( self, request, context ):
		print( "startService  request = {}".format(request) )
		return empty_pb2.Empty()

	def endService( self, request, context ):
		print( "endService" )
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

	def rejected( self, request, context ):
		print( "rejected" )
		return empty_pb2.Empty()

	def finish( self, request, context ):
		final_data=self.simulation_data.get_data()
		final_data.to_csv(r"final_data.csv")
		print('DRT Data Saved!')
		
		final_data=self.private_trip_data.get_data()
		final_data.to_csv(r"private_trip_data.csv")
		print('Private Data Saved!')

		print( "finish" )
		print("---running time: %s hours ---" % ( round( (time.time() - sim_start_time)/3600,2) ) )
		# store request event time and price to json files
		with open('requestEvents.json', 'w') as f:
			for k,value in self.demandInfo.items():
				if k in self.requestEventTime:
					self.requestEventTime[k].insert(0, self.demandInfo[k]["time"])
			json.dump(self.requestEventTime, f, indent=4)
		with open('requestPrice.json', 'w') as f:
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
		with open("no_pv_garage.json","w") as f:
			json.dump(self.noPrivateCarGarage, f, indent=4)
		print( "Number of Unserved requests --- {}".format( len(self.requestsFailedServing) ) )
		print( "Number of Unserved requests cannot find pv --- {}".format( len(self.noPrivateCarGarage) ) )
		# stop this app
		global keepRunning
		keepRunning = False
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
		interested_states = [1,2,3,4,9,10]

		if request.state in interested_states:
			# idRequest = request.service.request[1:-1]
			vehId = request.service.vehicle[1:-1]
			# vehId = self.computedSchedulePerRequest[idRequest]["vehId"]
			if vehId in self.privateVeh:
				try:
					req_id = self.priVehDestination[vehId][0]
					if request.state == Operator_pb2.DeliveryDone:
						do_g = self.priVehDestination[vehId][1]
						self.garagePrivateCar[do_g].append(vehId)
						self.priVehDestination.pop(vehId, None)	
				except Exception as e:
					print( "**************private car state updating error {}, veh state{}*****************".format(e,request.state) )
			else:
				reqId = self.vehicleSchedules[vehId].schedule[0].service.request
				if request.state == Operator_pb2.AtPickup:
					# record request pick up time
					# reqId = self.vehicleSchedules[vehId].schedule[0].service.request
					self.requestEventTime.update( {reqId:[request.when]} )
					self.vehicleSchedules[vehId].removeCommandFromSchedule()
					self.vehicleOccupancy[vehId] += 1
					# print(self.vehicleOccupancy[vehId])
				elif request.state == Operator_pb2.AtDelivery:
					# record request drop off time
					# reqId = self.vehicleSchedules[vehId].schedule[0].service.request
					self.requestEventTime[reqId].append(request.when)
					self.vehicleSchedules[vehId].removeCommandFromSchedule()
					self.vehicleOccupancy[vehId] -= 1

			## Get Time
			time=datetime.datetime.fromtimestamp(request.when/1000)
			time=time.strftime('%H:%M:%S')

			## position 
			point=self.simulator.getVehiclePosition(vehId).position
			x=round(point.x,2)
			y=round(point.y,2)

			if vehId in self.privateVeh:
				self.private_trip_data.update_data(vehId,time,req_id,state,x,y)
			else:
				self.simulation_data.update_data(vehId,time,reqId,state,x,y)
		return empty_pb2.Empty()


def serve( args ):
	# the connection to Aimsun Next simulator
	simulator = SimulatorClient( args.simulatorAddress )
	# our gRPC server
	server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
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
