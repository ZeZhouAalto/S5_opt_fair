import json
import uuid

# THIS FUNCTION GENERATES THE OPERATOR JSON FILE FOR A DRT-TAXI SERVICE
def gen_drt_operator_input_file(depot_stations_number, fleet_size):
    centroids_indexes = ['516', '517', '151', '523', '568', '217', '546', '440', '119', '66', '28', '385', '154', '518', '529', '54', '15', '490', '170', '130', '145', '531', '431', '615', '65', '564', '159', '215', '289', '403', '538', '24', '133', '553', '277', '124', '108', '418', '484', '368', '204', '148', '394', '310', '216', '367', '135', '114', '4', '191', '274', '37', '429', '112', '382', '577', '601', '45', '284', '402', '64', '409', '180', '27', '407', '160', '537', '52', '563', '416', '565', '421', '322', '554', '597', '526', '198', '22', '425', '40', '29', '245', '486', '308', '282', '48', '540', '337', '547', '539', '392', '291', '465', '432', '187', '150', '34', '72', '536', '123', '544', '556', '347', '457', '111', '395', '369', '91', '84', '137', '3', '442', '552', '598', '175', '422', '370', '299', '21', '562', '341', '157', '181', '413', '120', '448', '76', '493', '603', '511', '524', '50', '235', '162', '339', '445', '278', '109', '36', '426', '125', '397', '58', '311', '411', '471', '177', '155', '458', '31', '579', '102', '296', '317', '462', '433', '244', '482', '476', '233', '330', '513', '158', '307', '192', '494', '377', '75', '279', '497', '545', '190', '242', '86', '364', '503', '127', '90', '464', '460', '110', '92', '14', '2', '588', '165', '228', '412', '472', '570', '316', '399', '351', '83', '261', '223', '80', '247', '106', '141', '96', '360', '525', '98', '567', '356', '572', '334', '355', '46', '443', '97', '81', '501', '275', '176', '260', '122', '209', '586', '79', '306', '480', '384', '391', '436', '272', '166', '146', '304', '548', '25', '269', '262', '463', '152', '283', '372', '475', '366', '254', '473', '101', '179', '302', '469', '573', '444', '182', '239', '264', '257', '259', '599', '414', '361', '338', '376', '89', '82', '352', '63', '335', '276', '268', '188', '612', '467', '346', '453', '423', '51', '406', '288', '139', '195', '237', '555', '200', '305', '398', '374', '1', '468', '530', '250', '218', '510', '241', '118', '303', '266', '100', '401', '246', '285', '142', '332', '117', '49', '270', '232', '587', '549', '437', '69', '325', '134', '527', '26', '35', '478', '474', '604', '73', '485', '329', '39', '607', '68', '578', '318', '492', '522', '189', '202', '461', '608', '327', '606', '584', '580', '326', '199', '435', '499', '309', '600', '400', '500', '427', '345', '434', '331', '609', '550', '455', '569', '56', '115', '602', '78', '428', '219', '446', '591', '430', '226', '143', '373', '515', '521', '596', '38', '528', '44', '8', '313', '298', '30', '574', '466', '222', '388', '328', '229', '208', '343', '243', '438', '354', '13', '498', '171', '378', '533', '281', '104', '212', '320', '183', '470', '420', '43', '353', '205', '348', '344', '451', '379', '454', '128', '57', '105', '575', '380', '559', '419', '258', '479', '410', '333', '136', '103', '59', '210', '535', '358', '163', '507', '415', '456', '543', '93', '520', '405', '595', '74', '505', '532', '168', '10', '447', '576', '61', '301', '67', '362', '295', '77', '236', '144', '16', '560', '393', '164', '213', '491', '129', '512', '113', '156', '396', '506', '23', '121', '290', '294', '265', '178', '60', '88', '488', '417', '551', '349', '169', '365', '558', '196', '201', '449', '613', '424', '561', '439', '207', '340', '252', '315', '557', '459', '300', '324', '240', '271', '42', '203', '495', '336', '221', '312', '357', '263', '55', '585', '293', '267', '581', '197', '19', '594', '234', '383', '172', '481', '592', '404', '230', '314', '614', '487', '161', '319', '321', '359', '280', '18', '611', '11', '220', '256', '389', '206', '20', '450', '381', '342', '387', '363', '138', '6', '583', '185', '140', '225', '610', '107', '251', '616', '147', '116', '323', '508', '566', '519', '589', '32', '390', '590', '7', '287', '582', '53', '477', '95', '441', '386', '131', '193', '184', '593', '483', '12', '238', '70', '255', '47', '541', '214', '286', '87', '9', '211', '605', '149', '514', '153', '542', '273', '167', '186', '62', '292', '253', '126', '496', '94', '534', '99', '502', '375', '224', '408', '17', '350', '571', '71', '194', '297', '85', '174', '173', '231', '33', '41', '489', '5', '504', '509']
    vehicles_per_station = dict()
    for i in range(depot_stations_number):

        #vehicles_per_station.update({ "GARAGE "+str(i+1): int(fleet_size/depot_stations_number) })
        vehicles_per_station.update({ "GARAGE "+str(centroids_indexes[i]): int(fleet_size/depot_stations_number) })

    operator_dict = {"id": str(uuid.uuid4()), "name": "DRT-Taxi Operator", "type": "external", "address": "localhost:45001", 
    "vehicle_type": 2394298, "fleet": []}
    
    for garage, fleet_number in vehicles_per_station.items():
        for i in range(fleet_number):
            veh_dict = {"id": str(uuid.uuid4()), "name": "VEH"+str(i+1), "origin": {"object": garage}}
            operator_dict["fleet"].append(veh_dict)


    with open("operator_definition_ZE.json", "w") as outfile:
        json.dump(operator_dict, outfile, indent=4)
    
    # with open("operator_definition_ZE.json", "w") as outfile:
    #     json.dump(operator_dict, outfile, indent=4)

# THIS FUNCTION GENERATES THE OPERATOR JSON FILE FOR A CARSHARING SERVICE
##def gen_carsharing_operator_input_file(stations_number, station_occupancy):
##
##    vehicles_per_station = dict()
##    for i in range(stations_number):
##        vehicles_per_station.update({ "css_"+str(i+1): station_occupancy })
##
##    operator_dict = {"id": str(uuid.uuid4()), "name": "Carsharing Operator (station-to-station)", "type": "external", 
##    "address": "localhost:45002", "vehicle_type": 2394298, "frequencySecondsRebalancing": 0, "rebalancing": 0, 
##    "rebalancingType": "UsingFleet", "fleet": [], "veh_stations": []}
##    
##    for station, capacity in vehicles_per_station.items():
##        for i in range(capacity-5):
##            veh_dict = {"id": str(uuid.uuid4()), "name": "Car No: "+str(i+1)+"_Initial Station: "+station, "origin": {"object": station}, 
##            "supportCluster": 0}
##            operator_dict["fleet"].append(veh_dict)
##        
##        station_dict = {"id": str(uuid.uuid4()), "name": station, "nickName": station, "capacity": capacity, 
##        "idCluster": 0, "depot": 0, "position": { "object": station}, "predictedDemand": [0]}
##        operator_dict["veh_stations"].append(station_dict)
##
##
##    with open("carsharing_operator/operator_definition_carsharing.json", "w") as outfile:
##        json.dump(operator_dict, outfile, indent=4)
##    
##    with open("operator_definition_carsharing.json", "w") as outfile:
##        json.dump(operator_dict, outfile, indent=4)
##
##
### THIS FUNCTION GENERATES THE OPERATOR JSON FILE FOR A BIKESHARING SERVICE
##def gen_bikesharing_operator_input_file(stations_number, station_occupancy):
##
##    vehicles_per_station = dict()
##    for i in range(stations_number):
##        vehicles_per_station.update({ "bss_"+str(i): station_occupancy })
##
##    operator_dict = {"id": str(uuid.uuid4()), "name": "Bikesharing Operator (station-to-station)", "type": "external", 
##    "address": "localhost:45003", "vehicle_type": 152, "frequencySecondsRebalancing": 0, "rebalancing": 0, 
##    "rebalancingType": "UsingFleet", "fleet": [], "veh_stations": []}
##    
##    for station, capacity in vehicles_per_station.items():
##        for i in range(capacity-5):
##            veh_dict = {"id": str(uuid.uuid4()), "name": "Car No: "+str(i)+"_Initial Station: "+station, "origin": {"object": station}, 
##            "supportCluster": 0}
##            operator_dict["fleet"].append(veh_dict)
##        
##        station_dict = {"id": str(uuid.uuid4()), "name": station, "nickName": station, "capacity": capacity, 
##        "idCluster": 0, "depot": 0, "position": { "object": station}, "predictedDemand": [0]}
##        operator_dict["veh_stations"].append(station_dict)
##
##
##    with open("bikesharing_operator/operator_definition_bikesharing.json", "w") as outfile:
##        json.dump(operator_dict, outfile, indent=4)
##    
##    with open("operator_definition_bikesharing.json", "w") as outfile:
##        json.dump(operator_dict, outfile, indent=4)



if __name__ == '__main__':
    #############################--------------------DRT---------------------------############################

    # number of stations where the DRT fleet will be loaded into the simulation (initial position of fleet vehicles)
    # NOTE: in that case, it's a hardcoded fixed number based on manually created objects created for the 
    # virtual city ang file (however a shapefile can be also loaded) - DO NOT CHANGE VALUE
    _depot_stations_number = 610

    # nummber of vehicles in the DRT fleet
    # NOTE: This value is freely configurable!
    fleet_size = 3000

    gen_drt_operator_input_file(_depot_stations_number, fleet_size)
    
    
    
    #############################----------------CARSHARING--------------------############################

    # number of stations where the Carsharing fleet will be parked
    # NOTE: in that case, it's a hardcoded fixed number based on manually created objects created for the 
    # virtual city ang file (however a shapefile can be also loaded) - DO NOT CHANGE VALUE
    stations_number = 8

    # nummber of vehicles that can be parked in each station
    # NOTE: This value is freely configurable!
    station_occupancy = 15

    #NOTE: The final fleet size is not stations_number*station_occupancy since we need to make sure that there more parking
    #spots than the actual fleet; therefore each station is assumed to have 5 vehicles less than occupancy. Meaning that the
    #total fleet size is assumed to be fleet_size = stations_number*station_occupancy - (stations_number*5)
    #this value convention is hardcoded within the below fuction!!
    
##    gen_carsharing_operator_input_file(stations_number, station_occupancy)


    #############################---------------BIKESHARING---------------------############################

    # number of stations where the Bikesharing fleet will be parked
    # NOTE: in that case, it's a hardcoded fixed number based on manually created objects created for the 
    # virtual city ang file (however a shapefile can be also loaded) - DO NOT CHANGE VALUE
    stations_number = 18

    # nummber of vehicles that can be parked in each station
    # NOTE: This value is freely configurable!
    station_occupancy = 20

    #NOTE: The final fleet size is not stations_number*station_occupancy since we need to make sure that there more parking
    #spots than the actual fleet; therefore each station is assumed to have 5 vehicles less than occupancy. Meaning that the
    #total fleet size is assumed to be fleet_size = stations_number*station_occupancy - (stations_number*5)
    #this value convention is hardcoded within the below fuction!!

##    gen_bikesharing_operator_input_file(stations_number, station_occupancy)
