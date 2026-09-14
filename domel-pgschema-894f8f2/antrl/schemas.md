# Schemi in PG-Schema

## Casi Base Nodi 
CREATE GRAPH TYPE singleNode STRICT {
  (personType: Person {name STRING, OPTIONAL bday DATE}),
  (athleteType: Athlete OPEN {sport STRING, isOlympic BOOLEAN, medals INT}),
  (customerType: Customer {loyaltyPoints INT, OPTIONAL tier STRING, OPEN})
}

### BASE CASE (AND)
CREATE GRAPH TYPE andBaseCase STRICT {
  (personType: Person {name STRING, OPTIONAL bday DATE, email STRING}),
  (athleteType: Athlete {sport STRING, isOlympic BOOLEAN, medals INT}),
  (customerType: Person & Athlete {loyaltyPoints INT, OPTIONAL tier STRING})
}

### BASE CASE (XOR)
CREATE GRAPH TYPE xorBaseCase STRICT {
  (personType: Person {name STRING, OPTIONAL bday DATE, email STRING}),
  (athleteType: Athlete {sport STRING, isOlympic BOOLEAN, medals INT}),
  (customerType: Person | Athlete {loyaltyPoints INT, OPTIONAL tier STRING})
}

### BASE CASE (?)
CREATE GRAPH TYPE optBaseCase STRICT {
  (personType: Person {name STRING, OPTIONAL bday DATE, email STRING}),
  (athleteType: Athlete {sport STRING, isOlympic BOOLEAN, medals INT}),
  (customerType: Person & Athlete? {loyaltyPoints INT, OPTIONAL tier STRING})
}

### EQUALITY CASE (AND)
CREATE GRAPH TYPE andEqualityCase STRICT {
  (personType: Person {name STRING, OPTIONAL bday DATE, email STRING}),
  (customerType: Person & Customer {name STRING, OPTIONAL since DATE, loyaltyPoints INT})
}

### EQUALITY CASE (XOR)
CREATE GRAPH TYPE xorEqualityCase STRICT {
  (personType: Person {name STRING, OPTIONAL bday DATE, email STRING}),
  (customerType: Person | Customer {name STRING, OPTIONAL since DATE, loyaltyPoints INT})
}

### EQUALITY CASE (?)
CREATE GRAPH TYPE optEqualityCase STRICT {
  (personType: Person {name STRING, OPTIONAL bday DATE, email STRING}),
  (customerType: Person & Customer ? {name STRING, OPTIONAL since DATE, loyaltyPoints INT})
}

### OR CASE (AType: A \/ B) = (AType: A | B | (A&B))
CREATE GRAPH TYPE orCase STRICT {
  (AType: A \/ B)
}

CREATE GRAPH TYPE orCaseReal STRICT {
  (personType: Student \/ Worker {name STRING, age INT})
}

CREATE GRAPH TYPE orCase2 STRICT {
  (NameType: A \/ B)
}

CREATE GRAPH TYPE B2BNetworkGraph STRICT {
  (supplierType: Supplier {rating FLOAT, paymentTerms STRING}),
  (customerType: Customer {discountTier STRING, loyaltyPoints INT}),
  (partnerType: Supplier \/ Customer)
}

CREATE GRAPH TYPE ComplexB2BNetworkGraph STRICT {
  (companyType: Company {vatNumber STRING, name STRING}),
  (supplierType: Supplier {rating FLOAT, paymentTerms STRING}),
  (customerType: Customer {discountTier STRING, loyaltyPoints INT}),
  (partnerType: companyType & (supplierType \/ customerType))
}

### LOOSE GRAPH
CREATE GRAPH TYPE LooseSocialGraph LOOSE {
  (personType: Person {username STRING, age INT}),
  (cityType: City {cityName STRING, zipCode STRING}),
  
  (:personType)-[livesInType: LivesIn {since DATE}]->(:cityType)
}

### IMPORT GRAPH
CREATE GRAPH TYPE TestImportGraph STRICT IMPORTS BaseGraph {
  (userType: User {id INT}),
  (roleType: Role {name STRING}),

  (:userType)-[hasRoleType: HasRole]->(:roleType)
}

### DIAMOND GRAPH
CREATE GRAPH TYPE diamondGraph STRICT {
  (xType: A & B {propertyA INT, propertyB INT}),
  (yType: B & C {propertyB INT, propertyC INT}),
  (zType: xType & yType)
}

CREATE GRAPH TYPE TVHotelGraph STRICT {
  (visualType: Visual {resolution STRING, isOled BOOLEAN, OPTIONAL manufactureDate DATE}),
  (electronicType: Electronic {voltage FLOAT}),
  (audioType: Audio {decibels INT, isWireless BOOLEAN, OPEN}),
  (monitorType: Visual & Electronic),
  (speakerType: Electronic & Audio),
  (tvType: monitorType & speakerType),

  (roomType: Room {roomNumber INT, floor INT}),
  (:roomType)-[hasTvType: HasTV]->(:tvType),
  FOR (e: electronicType) MANDATORY e.voltage >= 110.0 AND e.voltage <= 220.0,
  FOR (a: audioType) MANDATORY a.decibels <= 120,
  FOR (r: roomType) SINGLETON rel WITHIN (r)-[rel: hasTvType]->()
}

## Casi Base Relazioni
CREATE GRAPH TYPE fraudGraphType STRICT {
  (personType: Person {name STRING}),
  (customerType: personType & Customer {id INT32}),
  (creditCardType: CreditCard {num STRING}),
  (transactionType: Transaction {num STRING}),
  (accountType: Account {id INT32}),

  (:customerType)-[ownsType: owns]->(:accountType),
  (:customerType)-[usesType: uses]->(:creditCardType),
  (:transactionType)-[chargesType: charges {amount DOUBLE}]->(:creditCardType),
  (:transactionType)-[activityType: deposits|withdraws]->(:accountType)
}

CREATE GRAPH TYPE basicFriendGraph STRICT {
  (personType: Person {name STRING, OPTIONAL bday DATE}),

  (:personType)-[friendType: Knows {OPTIONAL since DATE}]-> (:personType)
}

CREATE GRAPH TYPE friendGraph_v1 STRICT {
  (personType: Person {name STRING, OPTIONAL bday DATE, OPEN}),
  (customerType: Customer),

  (:personType|customerType)-[friendType: Knows & Likes {OPTIONAL since DATE}]-> (:personType|customerType)
}



CREATE GRAPH TYPE friendGraph_v2 STRICT {
  (personType: Person {name STRING, OPTIONAL bday DATE, OPEN}),
  (customerType: Customer & Person),
  
  (:personType|customerType)-[friendType: Knows & Likes {OPTIONAL since DATE}]-> (:personType|customerType)
}

CREATE GRAPH TYPE friendGraph_v3 STRICT {
  (personType: Person {name STRING, id INT}),
  (customerType: Customer {id INT}),

  (:personType)-[friendType: Knows & Likes & Bestie?]->(:personType),
  
  FOR (x:personType) EXCLUSIVE MANDATORY SINGLETON x.id,
  FOR (x:customerType) MANDATORY y.id WITHIN (y:personType) WHERE y.id = x.id,
  FOR (x:personType) SINGLETON y WITHIN (x)-[y: friendType & Bestie]->()
}

CREATE GRAPH TYPE DisjointTest STRICT {
  (personType: Person OPEN {name STRING}),
  (customerType: Person & Customer {name string, OPTIONAL since DATE}),
  (salariedType: Salaried {salary INT}),
  (employeeType: personType & salariedType),

  (:personType)-[friendType: Knows {OPTIONAL since DATE}]-> (:personType),
  (:employeeType)-[buddyType: friendType {since DATE, causal BOOL}]->(:employeeType),

  FOR (x: salariedType) MANDATORY x.salary >= 1000
  FOR (x: customerType) MANDATORY (x: !employeeType)
}

CREATE GRAPH TYPE birthGraph STRICT {
  (personType: Person {name STRING, OPTIONAL bday DATE, OPEN}),
  (cityType: City {name STRING, zipcode STRING}),

  (:personType)-[placeofbirthType: PlaceOfBirth {OPTIONAL registration STRING}]->(:cityType),

  FOR (x:personType) MANDATORY SINGLETON pob WITHIN (p)-[pob: placeofbirthType]->(c: cityType)
}

CREATE GRAPH TYPE DeepReificationTest STRICT {
  (personType: Person {name STRING}),
  (docType: Document {title STRING}),
  
  (:personType)-[readsType: Reads {time INT}]->(:docType),
  (:personType)-[studiesType: readsType {subject STRING}]->(:docType),
  (:personType)-[memorizesType: studiesType {grade INT}]->(:docType)
}

CREATE GRAPH TYPE UniversityGraph STRICT {
  (studentType: Student {studentID INT, advisorID INT}),
  (professorType: Professor {id INT, name STRING}),

  (:studentType)-[thesisRel: SupervisedBy & EvaluatedBy?]->(:professorType),

  FOR (s: studentType) EXCLUSIVE MANDATORY SINGLETON s.studentID,
  FOR (p: professorType) EXCLUSIVE MANDATORY SINGLETON p.id,
  FOR (s: studentType) MANDATORY p.id WITHIN (p: professorType) WHERE p.id = s.advisorId,
  FOR (s: studentType) SINGLETON r WITHIN (s)-[r: thesisRel]->()
}

CREATE GRAPH TYPE ActiveAccountSystem STRICT {
  (userType: User {userId INT, status STRING}),
  (accountType: Account {accountId INT, balance FLOAT}),

  (:userType)-[ownsType: OWNS]->(:accountType),

  FOR (u: userType) EXCLUSIVE MANDATORY SINGLETON u.userId,
  FOR (u: userType) MANDATORY u.status != "Suspended",
  FOR (a: accountType) MANDATORY a.balance >= 0.0
}

CREATE GRAPH TYPE TranslationNetwork STRICT {
  (translatorType: Translator {certId STRING, level INT}),
  (documentType: Document {docId INT, wordCount INT}),
  (languageType: Language {isoCode STRING}),
  
  (:translatorType)-[translatesType: Translates {pricePerWord FLOAT}]->(:documentType),
  (:documentType)-[writtenInType: Source_Language | Target_Language]->(:languageType),
  
  FOR (t: translatorType) EXCLUSIVE MANDATORY SINGLETON t.certId,
  FOR (d: documentType) MANDATORY d.wordCount > 0
}

CREATE GRAPH TYPE complexFraudGraphType STRICT {
  (personType: Person {name STRING, ssn STRING}),
  (companyType: Company {taxId STRING, name STRING}),
  (customerType: (personType | companyType) & Customer {id INT}),
  
  (creditCardType: CreditCard {num STRING, expDate DATE}),
  (transactionType: Transaction {num STRING, amount FLOAT}),
  (accountType: Account {id INT, balance FLOAT}),
  
  (:customerType)-[ownsType: Owns]->(:accountType),
  (:customerType)-[usesType: Uses]->(:creditCardType),
  (:transactionType)-[chargesType: Charges]->(:creditCardType),
  (:transactionType)-[activityType: Deposits | Withdraws]->(:accountType),
  
  (:transactionType)-[investigationType: Flagged & Audited? {reason STRING}]->(:accountType),

  FOR (c: customerType) EXCLUSIVE MANDATORY SINGLETON c.id,
  FOR (t: transactionType) MANDATORY t.amount > 0.0,
  FOR (t: transactionType) SINGLETON x WITHIN (t)-[x: chargesType]->()
}

CREATE GRAPH TYPE FinancialTransactions STRICT {
  (accountType: Account {accId INT, balance FLOAT, typology STRING}),
  (transactionType: Transaction {txId INT, amount FLOAT, fee FLOAT}),
  (userType: User {userId INT, fiscalCode STRING}),
  
  (:userType)-[ownsType: Owns]->(:accountType),
  (:accountType)-[sendsType: Sends]->(:transactionType),
  (:transactionType)-[receivesType: Receives]->(:accountType),

  FOR (u: userType) EXCLUSIVE MANDATORY SINGLETON u.userId,
  FOR (u: userType) EXCLUSIVE u.fiscalCode,
  FOR (a: accountType) MANDATORY a.balance >= 0.0,
  FOR (t: transactionType) MANDATORY t.amount > 0.0 AND t.fee >= 0.0,
  FOR (t: transactionType) MANDATORY SINGLETON s WITHIN (t)-[s: receivesType]->(),
  FOR (u: userType) MANDATORY o WITHIN (u)-[o: ownsType]->()
}

CREATE GRAPH TYPE CorporateStructure STRICT {
  (personType: Person {name STRING, taxId STRING}),
  (companyType: Company {name STRING, vatNumber STRING}),
  (employeeType: personType & Employee {salary INT, department STRING}),
  (managerType: employeeType & Manager {budget INT, hasStockOptions BOOLEAN}),
  (executiveType: managerType & Executive {boardMember BOOLEAN}),
  (:employeeType)-[worksForType: WorksFor {startDate DATE}]->(:companyType),
  (:employeeType)-[reportsToType: ReportsTo]->(:managerType),
  (:executiveType)-[ownsSharesType: OwnsShares {percentage FLOAT}]->(:companyType),
  
  FOR (x: employeeType) MANDATORY x.salary >= 30000,
  FOR (x: managerType) MANDATORY x.budget >= 100000,
  FOR (x: ownsSharesType) MANDATORY x.percentage > 0.0
}

CREATE GRAPH TYPE CorporateHierarchy STRICT {
  (employeeType: Employee {empId INT, email STRING, age INT}),
  (managerType: employeeType & Manager {departmentId INT}),
  (internType: employeeType & Intern {mentorId INT}),
  (departmentType: Department {deptId INT, name STRING}),
  (:employeeType)-[worksInType: WorksIn]->(:departmentType),
  (:internType)-[mentoredByType: MentoredBy]->(:managerType),

  FOR (e: employeeType) EXCLUSIVE MANDATORY SINGLETON e.empId,
  FOR (e: employeeType) EXCLUSIVE e.email,
  FOR (e: employeeType) MANDATORY e.age >= 18 AND e.age <= 65,
  FOR (m: managerType) MANDATORY (m: !internType),
  FOR (e: employeeType) MANDATORY SINGLETON r WITHIN (e)-[r: worksInType]->(),
  FOR (m: managerType) MANDATORY d.deptId WITHIN (d: departmentType) WHERE d.deptId = m.departmentId
}

CREATE GRAPH TYPE GitVersionControl STRICT {
  (userType: User {email STRING}),
  (commitType: Commit {hash STRING, authorEmail STRING}),
  (fileType: File {path STRING}),
  (:userType)-[authorsType: Authors]->(:commitType),
  (:commitType)-[actionType: Adds | Modifies | Deletes {lines INT}]->(:fileType),
  
  FOR (c: commitType) EXCLUSIVE MANDATORY SINGLETON c.hash,
  FOR (u: userType) EXCLUSIVE u.email,
  FOR (c: commitType) MANDATORY u.email WITHIN (u: userType) WHERE u.email = c.authorEmail
}

CREATE GRAPH TYPE SmartHomeNetwork STRICT {
  (deviceType: Device {mac STRING}),
  (sensorType: Sensor {metric STRING}),
  (actuatorType: Actuator {action STRING}),
  (smartNodeType: sensorType \/ actuatorType),
  
  (:deviceType)-[connectsType: Connects {bandwidth INT}]->(:deviceType),
  (:deviceType)-[wirelessType: connectsType {protocol STRING}]->(:deviceType),
  (:deviceType)-[bluetoothType: wirelessType {version FLOAT}]->(:deviceType),
  
  FOR (d: deviceType) EXCLUSIVE MANDATORY SINGLETON d.mac
}

CREATE GRAPH TYPE AcademicPeerReview STRICT {
  (researcherType: Researcher {orcid STRING, affiliation STRING}),
  (paperType: Paper {doi STRING, status STRING}),
  
  (:researcherType)-[reviewActionType: Assigned & Reviewed & Approved? {score FLOAT, OPTIONAL comment STRING}]->(:paperType),
  
  FOR (r: researcherType) EXCLUSIVE MANDATORY SINGLETON r.orcid,
  FOR (r: reviewActionType) MANDATORY r.score >= 0.0 AND r.score <= 10.0
}

CREATE GRAPH TYPE RealEstateLeasing STRICT {
  (personType: Person {ssn STRING, name STRING}),
  (businessType: Business {vat STRING, companyName STRING}),
  
  (propertyType: Property {propId INT, address STRING, value FLOAT}),
  
  (:personType | businessType)-[leasesType: Leases {monthlyRent FLOAT, startDate DATE}]->(:propertyType),
  
  FOR (p: personType) EXCLUSIVE MANDATORY SINGLETON p.ssn,
  FOR (b: businessType) EXCLUSIVE MANDATORY SINGLETON b.vat,
  FOR (prop: propertyType) EXCLUSIVE MANDATORY SINGLETON prop.propId,
  FOR (prop: propertyType) MANDATORY prop.value > 0.0
}

CREATE GRAPH TYPE FreelanceEcosystem STRICT {
  (userType: User OPEN {userId INT}),
  (clientType: userType & Client {company STRING}),
  (freelancerType: userType & Freelancer {hourlyRate FLOAT}),
  (projectType: Project {projId INT, budget FLOAT, OPTIONAL deadline DATE, OPEN}),
  
  (:clientType)-[postsType: Posts]->(:projectType),
  (:freelancerType)-[engagementType: Bids | WorksOn | Completes {hours INT, OPTIONAL rating FLOAT}]->(:projectType),
  
  FOR (u: userType) EXCLUSIVE MANDATORY SINGLETON u.userId,
  FOR (c: clientType) MANDATORY (c: !freelancerType),
  FOR (p: projectType) MANDATORY p.budget >= 100.0
}

CREATE GRAPH TYPE DigitalMarketplace STRICT {
  (vendorType: Vendor {taxId STRING}),
  (buyerType: Buyer {email STRING}),
  (userType: Vendor \/ Buyer {rating FLOAT}),
  (itemType: Item {sku STRING, price FLOAT}),
  
  (:userType)-[interactsType: Views | Cart | Purchases {qty INT}]->(:itemType),
  
  FOR (i: itemType) MANDATORY i.price >= 0.0,
  FOR (u: userType) MANDATORY u.rating >= 1.0 AND u.rating <= 5.0
}

CREATE GRAPH TYPE CloudInfrastructure STRICT {
  (resourceType: Resource OPEN {id STRING, region STRING}),
  (computeType: resourceType & Compute {cores INT, ram FLOAT}),
  (storageType: resourceType & Storage {capacity INT, OPTIONAL encrypted BOOLEAN}),

  (:computeType)-[mountsType: Mounts {mode STRING}]->(:storageType),
  
  FOR (r: resourceType) EXCLUSIVE MANDATORY SINGLETON r.id,
  FOR (c: computeType) MANDATORY (c: !storageType),
  FOR (c: computeType) MANDATORY c.cores >= 1
}

CREATE GRAPH TYPE SoftwareArchitecture STRICT {
  (serviceType: Service {name STRING}),
  (frontendType: serviceType & Frontend {framework STRING}),
  (backendType: serviceType & Backend {language STRING}),
  (fullstackType: frontendType & backendType {isMonolith BOOLEAN}),
  (databaseType: Database {engine STRING}),

  (:fullstackType)-[queriesType: Queries {poolSize INT}]->(:databaseType),
  
  FOR (s: serviceType) EXCLUSIVE MANDATORY SINGLETON s.name,
  FOR (f: fullstackType) SINGLETON q WITHIN (f)-[q: queriesType]->()
}

CREATE GRAPH TYPE HospitalPathology STRICT {
  (patientType: Patient {ssn STRING, name STRING}),
  (doctorType: Doctor {licenseId STRING}),
  (labType: Lab {labId STRING}),
  (testType: Test {testId STRING, typology STRING}),
  (reportType: Report {reportId STRING, outcome STRING, accuracy FLOAT}),

  (:doctorType)-[prescribesType: Prescribes {date DATE}]->(:testType),
  (:patientType)-[undergoesType: Undergoes]->(:testType),
  (:labType)-[analyzesType: Analyzes {date DATE}]->(:testType),
  (:testType)-[generatesType: Generates]->(:reportType),
  
  FOR (p: patientType) EXCLUSIVE MANDATORY SINGLETON p.ssn,
  FOR (r: reportType) EXCLUSIVE MANDATORY SINGLETON r.reportId,
  FOR (r: reportType) MANDATORY r.accuracy >= 90.0 AND r.accuracy <= 100.0,
  FOR (t: testType) SINGLETON res WITHIN (t)-[res: generatesType]->()
}

CREATE GRAPH TYPE FleetManagement STRICT {
  (vehicleType: Vehicle {vin STRING, plate STRING, mileage INT}),
  (driverType: Driver {licenseId STRING, name STRING, assignedVin STRING}),
  (maintenanceType: Maintenance {ticketId INT, cost FLOAT}),
  (:driverType)-[drivesType: Drives]->(:vehicleType),
  (:vehicleType)-[requiresType: Requires]->(:maintenanceType),

  FOR (v: vehicleType) EXCLUSIVE MANDATORY SINGLETON v.vin,
  FOR (v: vehicleType) EXCLUSIVE v.plate,
  FOR (d: driverType) EXCLUSIVE MANDATORY SINGLETON d.licenseId,
  FOR (v: vehicleType) MANDATORY v.mileage >= 0,
  FOR (d: driverType) MANDATORY v.vin WITHIN (v: vehicleType) WHERE v.vin = d.assignedVin,
  FOR (d: driverType) SINGLETON r WITHIN (d)-[r: drivesType]->()
}

CREATE GRAPH TYPE PublicTransport STRICT {
  (stationType: Station {stationId INT, name STRING}),
  (hubType: stationType & Hub {terminals INT}),
  (routeType: Route {routeId INT, color STRING}),
  (vehicleType: Vehicle {vehicleId INT, capacity INT}),
  (busType: vehicleType & Bus {wheelchairAccess BOOLEAN}),
  (trainType: vehicleType & Train {wagons INT}),
  (:routeType)-[stopsAtType: StopsAt {order INT}]->(:stationType),
  (:vehicleType)-[assignedToType: AssignedTo]->(:routeType),

  FOR (v: vehicleType) EXCLUSIVE MANDATORY SINGLETON v.vehicleId,
  FOR (s: stationType) EXCLUSIVE MANDATORY SINGLETON s.stationId,
  FOR (b: busType) MANDATORY (b: !trainType)
}

CREATE GRAPH TYPE PaymentGateway STRICT {
  (creditCardType: CreditCard {cardNumber STRING, expiry DATE}),
  (bankaccountType: BankAccount {iban STRING, swift STRING}),
  (paymentSourceType: CreditCard | BankAccount {sourceId INT, active BOOLEAN, OPEN}),
  (userType: User {userId INT, email STRING}),
  (transactionType: Transaction {txId STRING, amount FLOAT}),
  (:userType)-[registersType: Registers {verified BOOLEAN}]->(:paymentSourceType),
  (:transactionType)-[chargedToType: ChargedTo {fee FLOAT}]->(:paymentSourceType),
  
  FOR (p: paymentSourceType) EXCLUSIVE MANDATORY SINGLETON p.sourceId,
  FOR (u: userType) EXCLUSIVE MANDATORY SINGLETON u.userId,
  FOR (u: userType) EXCLUSIVE u.email,
  FOR (t: transactionType) MANDATORY t.amount > 0.0,
  FOR (t: transactionType) SINGLETON c WITHIN (t)-[c: chargedToType]->()
}

CREATE GRAPH TYPE BioprocessExperimentGraph STRICT {
  (objectiveType: Objective),
  (personType: Person),
  (feedingConfigType: FeedingConfig),
  (inductionConfigType: InductionConfig),
  (experimentType: Experiment {run_id INT, start_time DATE, horizon FLOAT, OPEN}),
  (bioreactorType: Bioreactor),
  (strainType: Strain),
  (plasmidType: Plasmid),
  (computationalMethodType: ComputationalMethod),
  (computationalEnvironmentType: ComputationalEnvironment),
  (workflowNodeType: WorkflowNode),
  (feedingSetpointType: FeedingSetpoint),
  (modelStateType: ModelState),
  (measurementType: Measurement),
  (deviceType: Device),
  (protocolTaskType: ProtocolTask),
  (modelParameterType: ModelParameter),
  (modelType: Model),

  (:experimentType)-[designedForType: DESIGNED_FOR]->(:objectiveType),
  (:experimentType)-[responsibleType: RESPONSIBLE {rol STRING}]->(:personType),
  
  (:experimentType)-[includesType: INCLUDES]->(:bioreactorType),
  (:experimentType)-[hasComputationalWorkflowType: HAS_COMPUTATIONAL_WORKFLOW]->(:workflowNodeType),

  (:experimentType)-[hasType: HAS]->(:feedingConfigType | inductionConfigType),
  
  (:bioreactorType)-[usesType: USES]->(:strainType | plasmidType),
  
  (:modelStateType | modelParameterType)-[partOfType: PART_OF]->(:modelType),

  (:workflowNodeType)-[dependencyType: DEPENDENCY]->(:workflowNodeType),
  
  (:workflowNodeType)-[executesType: EXECUTES]->(:computationalMethodType),
  (:workflowNodeType)-[executedInType: EXECUTED_IN]->(:computationalEnvironmentType),
  (:workflowNodeType)-[calculatesType: CALCULATES]->(:feedingSetpointType),
  (:workflowNodeType)-[predictsType: PREDICTS]->(:modelStateType),
  (:workflowNodeType)-[getsType: GETS]->(:measurementType),
  (:workflowNodeType)-[estimatesType: ESTIMATES]->(:modelParameterType),

  (:feedingSetpointType)-[feedsType: FEEDS]->(:bioreactorType),
  (:modelStateType)-[predictionForType: PREDICTION_FOR]->(:bioreactorType),

  (:measurementType)-[sampleFromType: SAMPLE_FROM]->(:bioreactorType),
  (:measurementType)-[takenFromType: TAKEN_FROM]->(:deviceType),
  (:measurementType)-[takenFollowingType: TAKEN_FOLLOWING]->(:protocolTaskType),

  FOR (e:experimentType) SINGLETON MANDATORY EXCLUSIVE e.run_id,
  FOR (e:experimentType) MANDATORY r WITHIN (e)-[r: responsibleType]-> (:personType),
  FOR (e:experimentType) MANDATORY wn.task_id = "start" WITHIN (e)-[:hasComputationalWorkflowType]-> (wn:workflowNodeType)
}




<!--esempio in standby-->
CREATE GRAPH TYPE IndustrialGraph STRICT {
  (machineType: Machine {macAddress STRING, model STRING}),
  (sensorType: Sensor {sensorId STRING, isActive BOOLEAN}),
  
  (thermalType: sensorType & Thermal {temperature FLOAT}),
  (pressureType: sensorType & Pressure {psi FLOAT}),

  (:machineType)-[monitoredByType: MonitoredBy {installDate DATE}]->(:sensorType),

  FOR (m: machineType) EXCLUSIVE MANDATORY SINGLETON m.macAddress,
  FOR (s: sensorType) EXCLUSIVE MANDATORY SINGLETON s.sensorId,

  FOR (t: thermalType) MANDATORY t.temperature < -20.0 OR t.temperature > 150.0,
  FOR (p: pressureType) MANDATORY p.psi < 10.0 OR p.psi > 500.0,
  
  FOR (m: machineType) MANDATORY s WITHIN (m)-[s: monitoredByType]->()
}