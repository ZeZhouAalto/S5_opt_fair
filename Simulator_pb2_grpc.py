# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

import Simulator_pb2 as Simulator__pb2
import common_pb2 as common__pb2
from google.protobuf import empty_pb2 as google_dot_protobuf_dot_empty__pb2


class SimulatorStub(object):
    """Missing associated documentation comment in .proto file."""

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.travelInfo = channel.unary_unary(
                '/AimsunMOD.Simulator/travelInfo',
                request_serializer=Simulator__pb2.Positions.SerializeToString,
                response_deserializer=common__pb2.TravelInfo.FromString,
                )
        self.travelInfoFleet = channel.unary_unary(
                '/AimsunMOD.Simulator/travelInfoFleet',
                request_serializer=Simulator__pb2.Vehicles.SerializeToString,
                response_deserializer=Simulator__pb2.TravelInfoFleet.FromString,
                )
        self.position = channel.unary_unary(
                '/AimsunMOD.Simulator/position',
                request_serializer=common__pb2.VehicleId.SerializeToString,
                response_deserializer=Simulator__pb2.VehiclePosition.FromString,
                )
        self.positions = channel.unary_unary(
                '/AimsunMOD.Simulator/positions',
                request_serializer=common__pb2.OperatorId.SerializeToString,
                response_deserializer=Simulator__pb2.VehiclePositions.FromString,
                )
        self.getTravelTimeFromOnePointToAnother = channel.unary_unary(
                '/AimsunMOD.Simulator/getTravelTimeFromOnePointToAnother',
                request_serializer=Simulator__pb2.Point2Point.SerializeToString,
                response_deserializer=Simulator__pb2.TravelTime.FromString,
                )
        self.getTravelTimeFromOnePointToManyPoints = channel.unary_unary(
                '/AimsunMOD.Simulator/getTravelTimeFromOnePointToManyPoints',
                request_serializer=Simulator__pb2.Point2ManyPoints.SerializeToString,
                response_deserializer=Simulator__pb2.TravelTimes.FromString,
                )
        self.getTravelTimeFromManyPointToManyPoints = channel.unary_unary(
                '/AimsunMOD.Simulator/getTravelTimeFromManyPointToManyPoints',
                request_serializer=Simulator__pb2.ManyPoints2ManyPoints.SerializeToString,
                response_deserializer=Simulator__pb2.TravelTimesWithPredecessors.FromString,
                )
        self.getTransitPath = channel.unary_unary(
                '/AimsunMOD.Simulator/getTransitPath',
                request_serializer=Simulator__pb2.TransitTargets.SerializeToString,
                response_deserializer=common__pb2.TravelInfo.FromString,
                )
        self.getDRTTransitPath = channel.unary_unary(
                '/AimsunMOD.Simulator/getDRTTransitPath',
                request_serializer=Simulator__pb2.DRTTransitInfo.SerializeToString,
                response_deserializer=common__pb2.TravelInfo.FromString,
                )
        self.getStopsInfo = channel.unary_unary(
                '/AimsunMOD.Simulator/getStopsInfo',
                request_serializer=google_dot_protobuf_dot_empty__pb2.Empty.SerializeToString,
                response_deserializer=Simulator__pb2.StopsInfo.FromString,
                )
        self.assignVehicle = channel.unary_unary(
                '/AimsunMOD.Simulator/assignVehicle',
                request_serializer=Simulator__pb2.VehicleAssignment.SerializeToString,
                response_deserializer=google_dot_protobuf_dot_empty__pb2.Empty.FromString,
                )
        self.reprogramFleet = channel.unary_unary(
                '/AimsunMOD.Simulator/reprogramFleet',
                request_serializer=common__pb2.FleetCommandList.SerializeToString,
                response_deserializer=google_dot_protobuf_dot_empty__pb2.Empty.FromString,
                )
        self.activateVehicle = channel.unary_unary(
                '/AimsunMOD.Simulator/activateVehicle',
                request_serializer=common__pb2.VehicleId.SerializeToString,
                response_deserializer=google_dot_protobuf_dot_empty__pb2.Empty.FromString,
                )
        self.deactivateVehicle = channel.unary_unary(
                '/AimsunMOD.Simulator/deactivateVehicle',
                request_serializer=common__pb2.VehicleId.SerializeToString,
                response_deserializer=google_dot_protobuf_dot_empty__pb2.Empty.FromString,
                )
        self.setPathManagerContext = channel.unary_unary(
                '/AimsunMOD.Simulator/setPathManagerContext',
                request_serializer=Simulator__pb2.Context.SerializeToString,
                response_deserializer=google_dot_protobuf_dot_empty__pb2.Empty.FromString,
                )
        self.executeOffer = channel.unary_unary(
                '/AimsunMOD.Simulator/executeOffer',
                request_serializer=Simulator__pb2.DirectOffer.SerializeToString,
                response_deserializer=google_dot_protobuf_dot_empty__pb2.Empty.FromString,
                )


class SimulatorServicer(object):
    """Missing associated documentation comment in .proto file."""

    def travelInfo(self, request, context):
        """! Returns the least generalised cost route from the point Origin to the point Destination using the
        selected Mode (vehicle id only needed for mode DRT)
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def travelInfoFleet(self, request, context):
        """! Returns the travel time from the position of each vehicle defined in the arguments to the destination point
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def position(self, request, context):
        """! Returns the position of a vehicle.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def positions(self, request, context):
        """! Returns the position of all vehicles of an Operator.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def getTravelTimeFromOnePointToAnother(self, request, context):
        """! Returns the travel time from one point to another using the defined mode.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def getTravelTimeFromOnePointToManyPoints(self, request, context):
        """! Returns the travel times from one point to many points using the defined mode.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def getTravelTimeFromManyPointToManyPoints(self, request, context):
        """! Returns the travel times and predecessors from many points to many points using the defined mode.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def getTransitPath(self, request, context):
        """! Returns a transit route from one stop to another taking into account the departure time defined.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def getDRTTransitPath(self, request, context):
        """! Returns a path using the Transit Network taking into account the usage of the operator for the first and last mile path.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def getStopsInfo(self, request, context):
        """! Returns the information of every stop used in the simulation.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def assignVehicle(self, request, context):
        """! Assign a vehicle to an existing request assigned to this operator. Use it for trip plans with DRT segments in where
        the vehicle cannot be assigned as part of the offer.

        The vehicle must be assigned before the DRT segment is executed or the request will be dropped.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def reprogramFleet(self, request, context):
        """! Reprogram vehicles (one, severall, all) in the fleet. callback_time is not use and will be deleted from FleetCommandList
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def activateVehicle(self, request, context):
        """! Activate a vehicle. From this moment the vehicle will generate statistics. An inactive vehicle will automatically activate if it accepts a request.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def deactivateVehicle(self, request, context):
        """! Deactivate a vehicle. Until it is activated again, it will not participate in the statistics.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def setPathManagerContext(self, request, context):
        """! Set the Path Manager Context for one cost mode (Simulation or Historical)
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def executeOffer(self, request, context):
        """! Execute an offer directly from the simulator
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_SimulatorServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'travelInfo': grpc.unary_unary_rpc_method_handler(
                    servicer.travelInfo,
                    request_deserializer=Simulator__pb2.Positions.FromString,
                    response_serializer=common__pb2.TravelInfo.SerializeToString,
            ),
            'travelInfoFleet': grpc.unary_unary_rpc_method_handler(
                    servicer.travelInfoFleet,
                    request_deserializer=Simulator__pb2.Vehicles.FromString,
                    response_serializer=Simulator__pb2.TravelInfoFleet.SerializeToString,
            ),
            'position': grpc.unary_unary_rpc_method_handler(
                    servicer.position,
                    request_deserializer=common__pb2.VehicleId.FromString,
                    response_serializer=Simulator__pb2.VehiclePosition.SerializeToString,
            ),
            'positions': grpc.unary_unary_rpc_method_handler(
                    servicer.positions,
                    request_deserializer=common__pb2.OperatorId.FromString,
                    response_serializer=Simulator__pb2.VehiclePositions.SerializeToString,
            ),
            'getTravelTimeFromOnePointToAnother': grpc.unary_unary_rpc_method_handler(
                    servicer.getTravelTimeFromOnePointToAnother,
                    request_deserializer=Simulator__pb2.Point2Point.FromString,
                    response_serializer=Simulator__pb2.TravelTime.SerializeToString,
            ),
            'getTravelTimeFromOnePointToManyPoints': grpc.unary_unary_rpc_method_handler(
                    servicer.getTravelTimeFromOnePointToManyPoints,
                    request_deserializer=Simulator__pb2.Point2ManyPoints.FromString,
                    response_serializer=Simulator__pb2.TravelTimes.SerializeToString,
            ),
            'getTravelTimeFromManyPointToManyPoints': grpc.unary_unary_rpc_method_handler(
                    servicer.getTravelTimeFromManyPointToManyPoints,
                    request_deserializer=Simulator__pb2.ManyPoints2ManyPoints.FromString,
                    response_serializer=Simulator__pb2.TravelTimesWithPredecessors.SerializeToString,
            ),
            'getTransitPath': grpc.unary_unary_rpc_method_handler(
                    servicer.getTransitPath,
                    request_deserializer=Simulator__pb2.TransitTargets.FromString,
                    response_serializer=common__pb2.TravelInfo.SerializeToString,
            ),
            'getDRTTransitPath': grpc.unary_unary_rpc_method_handler(
                    servicer.getDRTTransitPath,
                    request_deserializer=Simulator__pb2.DRTTransitInfo.FromString,
                    response_serializer=common__pb2.TravelInfo.SerializeToString,
            ),
            'getStopsInfo': grpc.unary_unary_rpc_method_handler(
                    servicer.getStopsInfo,
                    request_deserializer=google_dot_protobuf_dot_empty__pb2.Empty.FromString,
                    response_serializer=Simulator__pb2.StopsInfo.SerializeToString,
            ),
            'assignVehicle': grpc.unary_unary_rpc_method_handler(
                    servicer.assignVehicle,
                    request_deserializer=Simulator__pb2.VehicleAssignment.FromString,
                    response_serializer=google_dot_protobuf_dot_empty__pb2.Empty.SerializeToString,
            ),
            'reprogramFleet': grpc.unary_unary_rpc_method_handler(
                    servicer.reprogramFleet,
                    request_deserializer=common__pb2.FleetCommandList.FromString,
                    response_serializer=google_dot_protobuf_dot_empty__pb2.Empty.SerializeToString,
            ),
            'activateVehicle': grpc.unary_unary_rpc_method_handler(
                    servicer.activateVehicle,
                    request_deserializer=common__pb2.VehicleId.FromString,
                    response_serializer=google_dot_protobuf_dot_empty__pb2.Empty.SerializeToString,
            ),
            'deactivateVehicle': grpc.unary_unary_rpc_method_handler(
                    servicer.deactivateVehicle,
                    request_deserializer=common__pb2.VehicleId.FromString,
                    response_serializer=google_dot_protobuf_dot_empty__pb2.Empty.SerializeToString,
            ),
            'setPathManagerContext': grpc.unary_unary_rpc_method_handler(
                    servicer.setPathManagerContext,
                    request_deserializer=Simulator__pb2.Context.FromString,
                    response_serializer=google_dot_protobuf_dot_empty__pb2.Empty.SerializeToString,
            ),
            'executeOffer': grpc.unary_unary_rpc_method_handler(
                    servicer.executeOffer,
                    request_deserializer=Simulator__pb2.DirectOffer.FromString,
                    response_serializer=google_dot_protobuf_dot_empty__pb2.Empty.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'AimsunMOD.Simulator', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


 # This class is part of an EXPERIMENTAL API.
class Simulator(object):
    """Missing associated documentation comment in .proto file."""

    @staticmethod
    def travelInfo(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/AimsunMOD.Simulator/travelInfo',
            Simulator__pb2.Positions.SerializeToString,
            common__pb2.TravelInfo.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def travelInfoFleet(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/AimsunMOD.Simulator/travelInfoFleet',
            Simulator__pb2.Vehicles.SerializeToString,
            Simulator__pb2.TravelInfoFleet.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def position(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/AimsunMOD.Simulator/position',
            common__pb2.VehicleId.SerializeToString,
            Simulator__pb2.VehiclePosition.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def positions(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/AimsunMOD.Simulator/positions',
            common__pb2.OperatorId.SerializeToString,
            Simulator__pb2.VehiclePositions.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def getTravelTimeFromOnePointToAnother(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/AimsunMOD.Simulator/getTravelTimeFromOnePointToAnother',
            Simulator__pb2.Point2Point.SerializeToString,
            Simulator__pb2.TravelTime.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def getTravelTimeFromOnePointToManyPoints(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/AimsunMOD.Simulator/getTravelTimeFromOnePointToManyPoints',
            Simulator__pb2.Point2ManyPoints.SerializeToString,
            Simulator__pb2.TravelTimes.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def getTravelTimeFromManyPointToManyPoints(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/AimsunMOD.Simulator/getTravelTimeFromManyPointToManyPoints',
            Simulator__pb2.ManyPoints2ManyPoints.SerializeToString,
            Simulator__pb2.TravelTimesWithPredecessors.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def getTransitPath(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/AimsunMOD.Simulator/getTransitPath',
            Simulator__pb2.TransitTargets.SerializeToString,
            common__pb2.TravelInfo.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def getDRTTransitPath(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/AimsunMOD.Simulator/getDRTTransitPath',
            Simulator__pb2.DRTTransitInfo.SerializeToString,
            common__pb2.TravelInfo.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def getStopsInfo(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/AimsunMOD.Simulator/getStopsInfo',
            google_dot_protobuf_dot_empty__pb2.Empty.SerializeToString,
            Simulator__pb2.StopsInfo.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def assignVehicle(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/AimsunMOD.Simulator/assignVehicle',
            Simulator__pb2.VehicleAssignment.SerializeToString,
            google_dot_protobuf_dot_empty__pb2.Empty.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def reprogramFleet(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/AimsunMOD.Simulator/reprogramFleet',
            common__pb2.FleetCommandList.SerializeToString,
            google_dot_protobuf_dot_empty__pb2.Empty.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def activateVehicle(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/AimsunMOD.Simulator/activateVehicle',
            common__pb2.VehicleId.SerializeToString,
            google_dot_protobuf_dot_empty__pb2.Empty.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def deactivateVehicle(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/AimsunMOD.Simulator/deactivateVehicle',
            common__pb2.VehicleId.SerializeToString,
            google_dot_protobuf_dot_empty__pb2.Empty.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def setPathManagerContext(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/AimsunMOD.Simulator/setPathManagerContext',
            Simulator__pb2.Context.SerializeToString,
            google_dot_protobuf_dot_empty__pb2.Empty.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def executeOffer(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/AimsunMOD.Simulator/executeOffer',
            Simulator__pb2.DirectOffer.SerializeToString,
            google_dot_protobuf_dot_empty__pb2.Empty.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)
