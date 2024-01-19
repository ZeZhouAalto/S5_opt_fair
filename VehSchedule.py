
import common_pb2
import common_pb2_grpc
import copy


class VehSchedule:
	def __init__(self, idVeh):
		self.idVeh = idVeh
		self.schedule = list()

	def createNewPotentialSchedule( self, idVeh, requestID, currentVehicleSchedule, commandTypes, commandDestinations, commandOrders):
		newSchedule = copy.deepcopy(currentVehicleSchedule)
		commandInsertionPositions = list()
		
		j = 0
		for i in range(len(commandTypes)):
			if commandTypes[i] == "PickUp":
				command = common_pb2.Command(
							operation = common_pb2.Operation.Pickup,
							operationTime = 10,
							service=common_pb2.ServiceInfo(
								vehicle = idVeh,
								request =  requestID
							),
							destination= commandDestinations[i]
				)
			elif commandTypes[i] == "DropOff":
				command = common_pb2.Command(
							operation = common_pb2.Operation.Deliver,
							operationTime = 10,
							service=common_pb2.ServiceInfo(
								vehicle = idVeh,
								request =  requestID
							),
							destination=commandDestinations[i]
				)
			
			insertionPosition = commandOrders[i] + j
			newSchedule.insert(insertionPosition, command)
			# final_insertion_position = newSchedule.index(command)
			commandInsertionPositions.append(insertionPosition)
			j += 1

		return newSchedule, commandInsertionPositions

	def updateCurrentSchedule(self, newSchedule):
		self.schedule = newSchedule

	def removeCommandFromSchedule(self):
		self.schedule.pop(0)
	
	def getSchedule(self):
		return self.schedule