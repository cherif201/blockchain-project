# @version ^0.3.10
"""
@title Consortium Blockchain Race Contract - Cloud-Enabled Layer
@author Race Event Management System
@notice This contract handles aggregated data storage and cross-organizational sharing
@dev Designed for Ethereum-based consortium blockchain (cloud layer)

This contract implements:
- Federated ledger across multiple Cloud Service Providers (CSPs)
- Identity Provider Extension for cross-layer identity continuity
- Aggregated data upload/retrieval from fog layer
- Proof of Stake & Validation (PoSV) extended consensus
- Stakeholder access control (organizers, sponsors, referees, health teams)
- Selfish CSP detection for network reliability
"""

# ============================================================================
#                           EVENTS (for logging and tracking)
# ============================================================================

# Emitted when a new race is registered in the consortium
event RaceRegistered:
    race_id: indexed(bytes32)            # Race identifier from fog layer
    race_name: String[100]               # Human-readable name
    organizer: indexed(address)          # Primary organizer
    registered_at: uint256               # Timestamp

# Emitted when aggregated data batch is uploaded from fog layer
event DataBatchUploaded:
    race_id: indexed(bytes32)            # Associated race
    batch_id: indexed(uint256)           # Batch identifier
    fog_merkle_root: bytes32             # Merkle root from fog layer
    uploader: indexed(address)           # Who uploaded
    timestamp: uint256                   # Upload timestamp

# Emitted when a CSP validates a batch
event BatchValidated:
    race_id: indexed(bytes32)            # Associated race
    batch_id: indexed(uint256)           # Batch identifier
    validator: indexed(address)          # CSP that validated
    is_valid: bool                       # Validation result

# Emitted when a new stakeholder is added
event StakeholderAdded:
    race_id: indexed(bytes32)            # Associated race
    stakeholder: indexed(address)        # Stakeholder address
    role: uint256                        # Role type
    added_by: address                    # Who added them

# Emitted when a CSP is flagged for suspicious behavior
event CSPFlagged:
    csp: indexed(address)                # CSP address
    reason: uint256                      # Reason code
    reporter: indexed(address)           # Who reported
    flagged_at: uint256                  # Timestamp

# Emitted when final race results are certified
event RaceResultsCertified:
    race_id: indexed(bytes32)            # Race identifier
    results_hash: bytes32                # Hash of final results
    certified_by: address                # Who certified
    certified_at: uint256                # Timestamp

# ============================================================================
#                           DATA STRUCTURES
# ============================================================================

# Role types for stakeholders
# Using constants for clarity (Vyper doesn't have enums)
ROLE_NONE: constant(uint256) = 0
ROLE_ORGANIZER: constant(uint256) = 1      # Administrators - full access
ROLE_REFEREE: constant(uint256) = 2        # Validators - can review disputes
ROLE_SPONSOR: constant(uint256) = 3        # Data Consumers - read access
ROLE_HEALTH_TEAM: constant(uint256) = 4    # Emergency Responders - health alerts
ROLE_BETTING_COMPANY: constant(uint256) = 5  # Analytics Users - verified results
ROLE_CSP: constant(uint256) = 6            # Network Peers - full node operators

# Struct for race information in consortium
struct ConsortiumRace:
    race_id: bytes32                     # Unique identifier (from fog layer)
    race_name: String[100]               # Human-readable name
    fog_contract_address: address        # Address of fog layer contract
    organizer: address                   # Primary organizer
    total_checkpoints: uint256           # Number of checkpoints
    race_status: uint256                 # 0=Pending, 1=Active, 2=Completed
    created_at: uint256                  # Registration timestamp
    completed_at: uint256                # Completion timestamp
    results_hash: bytes32                # Hash of certified results
    total_batches_received: uint256      # Count of uploaded batches

# Struct for aggregated data batches
struct AggregatedBatch:
    batch_id: uint256                    # Unique batch ID in consortium
    fog_batch_id: uint256                # Original batch ID from fog layer
    race_id: bytes32                     # Associated race
    fog_merkle_root: bytes32             # Merkle root from fog layer
    consortium_hash: bytes32             # Additional hash for consortium verification
    uploader: address                    # Who uploaded this batch
    uploaded_at: uint256                 # Upload timestamp
    validation_count: uint256            # Number of CSP validations
    is_finalized: bool                   # Whether validation is complete
    record_count: uint256                # Number of records in batch

# Struct for CSP (Cloud Service Provider) information
struct CSPInfo:
    csp_address: address                 # CSP's address
    name: String[50]                     # Human-readable name
    stake: uint256                       # Staked amount
    is_active: bool                      # Whether currently active
    validations_count: uint256           # Total validations performed
    disputes_count: uint256              # Number of disputes against
    flag_count: uint256                  # Number of times flagged
    joined_at: uint256                   # When they joined
    last_active: uint256                 # Last activity timestamp

# Struct for stakeholder information
struct Stakeholder:
    stakeholder_address: address         # Stakeholder's address
    role: uint256                        # Role type (see constants)
    race_id: bytes32                     # Associated race (or empty for global)
    is_active: bool                      # Whether currently active
    added_at: uint256                    # When added

# Struct for runner results (aggregated from fog layer)
struct RunnerResult:
    runner_id: bytes32                   # Pseudonymous runner ID
    race_id: bytes32                     # Associated race
    finish_time: uint256                 # Total time in seconds
    final_position: uint256              # Finishing position
    checkpoints_passed: uint256          # Number of checkpoints passed
    is_dnf: bool                         # Did Not Finish flag
    is_disqualified: bool                # Disqualification flag
    verified: bool                       # Whether result is verified

# Struct for dispute records
struct Dispute:
    dispute_id: uint256                  # Unique dispute ID
    race_id: bytes32                     # Associated race
    runner_id: bytes32                   # Disputed runner
    filed_by: address                    # Who filed the dispute
    reason: String[200]                  # Reason for dispute
    status: uint256                      # 0=Open, 1=Resolved, 2=Rejected
    resolution: String[200]             # Resolution details
    filed_at: uint256                    # Filing timestamp
    resolved_at: uint256                 # Resolution timestamp
    resolver: address                    # Who resolved

# ============================================================================
#                           STATE VARIABLES
# ============================================================================

# Contract administration
owner: public(address)                   # Contract owner
consortium_name: public(String[100])     # Consortium name

# Race storage
races: public(HashMap[bytes32, ConsortiumRace])  # race_id -> race info
race_ids: public(DynArray[bytes32, 1000])        # List of all race IDs
total_races: public(uint256)                      # Total registered races

# Batch storage
batches: public(HashMap[uint256, AggregatedBatch])  # batch_id -> batch
batch_validations: public(HashMap[uint256, HashMap[address, bool]])  # batch_id -> csp -> validated
total_batches: public(uint256)                       # Total batches received

# CSP storage
csps: public(HashMap[address, CSPInfo])           # csp_address -> info
csp_addresses: public(DynArray[address, 100])     # List of CSP addresses
total_csps: public(uint256)                       # Total registered CSPs
required_validations: public(uint256)             # Required CSP validations for finalization

# Stakeholder storage
stakeholders: public(HashMap[address, HashMap[bytes32, Stakeholder]])  # addr -> race_id -> info
global_stakeholders: public(HashMap[address, Stakeholder])             # Global stakeholders

# Runner results storage
runner_results: public(HashMap[bytes32, HashMap[bytes32, RunnerResult]])  # race_id -> runner_id -> result

# Dispute storage
disputes: public(HashMap[uint256, Dispute])       # dispute_id -> dispute
total_disputes: public(uint256)                   # Total disputes filed

# Configuration
MIN_CSP_STAKE: public(constant(uint256)) = 1000000000000000000  # 1 ETH
VALIDATION_THRESHOLD: public(constant(uint256)) = 2  # Minimum validations needed

# ============================================================================
#                           CONSTRUCTOR
# ============================================================================

@external
def __init__(_consortium_name: String[100], _required_validations: uint256):
    """
    @notice Initialize the consortium blockchain contract
    @dev Sets up the consortium with basic parameters
    @param _consortium_name Name of the consortium (e.g., "Marathon Consortium")
    @param _required_validations Number of CSP validations required for batch finalization
    
    Example: __init__("Global Marathon Consortium", 3)
    """
    assert len(_consortium_name) > 0, "Name cannot be empty"
    assert _required_validations >= 1, "Need at least 1 validation"
    
    self.owner = msg.sender
    self.consortium_name = _consortium_name
    self.required_validations = _required_validations
    
    # Owner is automatically a global organizer
    self.global_stakeholders[msg.sender] = Stakeholder({
        stakeholder_address: msg.sender,
        role: ROLE_ORGANIZER,
        race_id: empty(bytes32),
        is_active: True,
        added_at: block.timestamp
    })

# ============================================================================
#                           MODIFIERS (Access Control)
# ============================================================================

@internal
def _only_owner():
    """@dev Ensures only the contract owner can call"""
    assert msg.sender == self.owner, "Only owner allowed"

@internal
def _only_organizer(race_id: bytes32):
    """@dev Ensures caller is an organizer for the race or globally"""
    is_global: bool = self.global_stakeholders[msg.sender].role == ROLE_ORGANIZER
    is_race_org: bool = self.stakeholders[msg.sender][race_id].role == ROLE_ORGANIZER
    assert is_global or is_race_org, "Only organizers allowed"

@internal
def _only_csp():
    """@dev Ensures caller is an active CSP"""
    assert self.csps[msg.sender].is_active, "Only active CSPs allowed"

@internal
def _only_referee(race_id: bytes32):
    """@dev Ensures caller is a referee for the race or globally"""
    is_global_ref: bool = self.global_stakeholders[msg.sender].role == ROLE_REFEREE
    is_race_ref: bool = self.stakeholders[msg.sender][race_id].role == ROLE_REFEREE
    is_organizer: bool = self.global_stakeholders[msg.sender].role == ROLE_ORGANIZER
    assert is_global_ref or is_race_ref or is_organizer, "Only referees allowed"

@internal
def _race_exists(race_id: bytes32):
    """@dev Ensures the race exists"""
    assert self.races[race_id].race_id == race_id, "Race not found"

# ============================================================================
#                           CSP MANAGEMENT
# ============================================================================

@external
@payable
def register_csp(name: String[50]):
    """
    @notice Register as a Cloud Service Provider (CSP)
    @dev Requires minimum stake for participation in consensus
    @param name Human-readable name for the CSP
    
    CSPs are network peers that:
    - Host blockchain nodes
    - Participate in PoSV consensus
    - Validate data batches from fog layer
    - Provide scalability and fault tolerance
    """
    assert msg.value >= MIN_CSP_STAKE, "Insufficient stake"
    assert not self.csps[msg.sender].is_active, "Already registered"
    assert len(name) > 0, "Name cannot be empty"
    
    self.csps[msg.sender] = CSPInfo({
        csp_address: msg.sender,
        name: name,
        stake: msg.value,
        is_active: True,
        validations_count: 0,
        disputes_count: 0,
        flag_count: 0,
        joined_at: block.timestamp,
        last_active: block.timestamp
    })
    
    self.csp_addresses.append(msg.sender)
    self.total_csps += 1

@external
def deactivate_csp(csp_address: address):
    """
    @notice Deactivate a CSP (owner only)
    @dev Used for removing malicious or inactive CSPs
    @param csp_address The CSP to deactivate
    """
    self._only_owner()
    assert self.csps[csp_address].is_active, "CSP not active"
    
    self.csps[csp_address].is_active = False

@external
def withdraw_csp_stake():
    """
    @notice Allow inactive CSP to withdraw their stake
    @dev Only after deactivation
    """
    csp: CSPInfo = self.csps[msg.sender]
    assert csp.csp_address == msg.sender, "Not a CSP"
    assert not csp.is_active, "Must be deactivated first"
    assert csp.stake > 0, "No stake to withdraw"
    
    stake_amount: uint256 = csp.stake
    self.csps[msg.sender].stake = 0
    
    send(msg.sender, stake_amount)

@external
def flag_csp(csp_address: address, reason: uint256):
    """
    @notice Flag a CSP for suspicious behavior (selfish CSP detection)
    @dev Any active CSP can flag another CSP
    @param csp_address The CSP to flag
    @param reason Reason code (1=data alteration, 2=non-responsive, 3=invalid validations)
    
    This implements the "Identity Selfish CSP Detection" from the architecture.
    """
    self._only_csp()
    assert self.csps[csp_address].is_active, "Target CSP not active"
    assert csp_address != msg.sender, "Cannot flag yourself"
    
    self.csps[csp_address].flag_count += 1
    
    log CSPFlagged(csp_address, reason, msg.sender, block.timestamp)
    
    # Auto-deactivate if flagged too many times
    if self.csps[csp_address].flag_count >= 3:
        self.csps[csp_address].is_active = False

# ============================================================================
#                           RACE MANAGEMENT
# ============================================================================

@external
def register_race(
    race_id: bytes32,
    race_name: String[100],
    fog_contract_address: address,
    total_checkpoints: uint256
):
    """
    @notice Register a new race in the consortium
    @dev Called by fog layer or organizers to link fog and consortium layers
    @param race_id Unique race identifier (from fog layer)
    @param race_name Human-readable race name
    @param fog_contract_address Address of the fog layer contract
    @param total_checkpoints Number of checkpoints in the race
    
    Example: register_race(0x123..., "City Marathon 2025", 0xabc..., 5)
    """
    # Only global organizers can register races
    assert self.global_stakeholders[msg.sender].role == ROLE_ORGANIZER, "Only global organizers"
    assert self.races[race_id].race_id == empty(bytes32), "Race already registered"
    assert len(race_name) > 0, "Name cannot be empty"
    assert total_checkpoints >= 2, "Need at least 2 checkpoints"
    
    self.races[race_id] = ConsortiumRace({
        race_id: race_id,
        race_name: race_name,
        fog_contract_address: fog_contract_address,
        organizer: msg.sender,
        total_checkpoints: total_checkpoints,
        race_status: 0,  # Pending
        created_at: block.timestamp,
        completed_at: 0,
        results_hash: empty(bytes32),
        total_batches_received: 0
    })
    
    self.race_ids.append(race_id)
    self.total_races += 1
    
    # Add creator as race organizer
    self.stakeholders[msg.sender][race_id] = Stakeholder({
        stakeholder_address: msg.sender,
        role: ROLE_ORGANIZER,
        race_id: race_id,
        is_active: True,
        added_at: block.timestamp
    })
    
    log RaceRegistered(race_id, race_name, msg.sender, block.timestamp)

@external
def activate_race(race_id: bytes32):
    """
    @notice Activate a race (move from Pending to Active)
    @param race_id The race to activate
    """
    self._only_organizer(race_id)
    self._race_exists(race_id)
    assert self.races[race_id].race_status == 0, "Race not pending"
    
    self.races[race_id].race_status = 1  # Active

@external
def complete_race(race_id: bytes32):
    """
    @notice Mark a race as completed
    @param race_id The race to complete
    """
    self._only_organizer(race_id)
    self._race_exists(race_id)
    assert self.races[race_id].race_status == 1, "Race not active"
    
    self.races[race_id].race_status = 2  # Completed
    self.races[race_id].completed_at = block.timestamp

# ============================================================================
#                           STAKEHOLDER MANAGEMENT
# ============================================================================

@external
def add_stakeholder(
    stakeholder_address: address,
    role: uint256,
    race_id: bytes32
):
    """
    @notice Add a stakeholder to a race
    @dev Organizers can add different stakeholder types
    @param stakeholder_address Address of the stakeholder
    @param role Role type (1-6, see ROLE constants)
    @param race_id Associated race (or empty for global)
    
    Role types:
    1 = Organizer (administrators)
    2 = Referee (validators)
    3 = Sponsor (data consumers)
    4 = Health Team (emergency responders)
    5 = Betting Company (analytics users)
    6 = CSP (handled separately)
    """
    # Check authorization
    if race_id == empty(bytes32):
        self._only_owner()  # Only owner can add global stakeholders
    else:
        self._only_organizer(race_id)
        self._race_exists(race_id)
    
    assert role >= 1 and role <= 5, "Invalid role"
    assert stakeholder_address != empty(address), "Invalid address"
    
    stakeholder: Stakeholder = Stakeholder({
        stakeholder_address: stakeholder_address,
        role: role,
        race_id: race_id,
        is_active: True,
        added_at: block.timestamp
    })
    
    if race_id == empty(bytes32):
        self.global_stakeholders[stakeholder_address] = stakeholder
    else:
        self.stakeholders[stakeholder_address][race_id] = stakeholder
    
    log StakeholderAdded(race_id, stakeholder_address, role, msg.sender)

@external
def remove_stakeholder(stakeholder_address: address, race_id: bytes32):
    """
    @notice Remove a stakeholder's access
    @param stakeholder_address Address to remove
    @param race_id Associated race (or empty for global)
    """
    if race_id == empty(bytes32):
        self._only_owner()
        self.global_stakeholders[stakeholder_address].is_active = False
    else:
        self._only_organizer(race_id)
        self.stakeholders[stakeholder_address][race_id].is_active = False

# ============================================================================
#                           DATA BATCH UPLOAD & VALIDATION
# ============================================================================

@external
def upload_batch(
    race_id: bytes32,
    fog_batch_id: uint256,
    fog_merkle_root: bytes32,
    record_count: uint256
) -> uint256:
    """
    @notice Upload aggregated data batch from fog layer
    @dev Called periodically to sync fog data to consortium
    @param race_id Associated race
    @param fog_batch_id Original batch ID from fog layer
    @param fog_merkle_root Merkle root from fog layer for verification
    @param record_count Number of checkpoint records in batch
    @return The consortium batch ID
    
    This implements the "Aggregated Data Upload" component:
    - Handles batched uploads from fog layer
    - Supports scalable querying
    - Provides real-time dashboards
    """
    self._only_organizer(race_id)
    self._race_exists(race_id)
    assert self.races[race_id].race_status == 1, "Race not active"
    
    # Generate consortium hash for additional verification
    consortium_hash: bytes32 = keccak256(concat(
        fog_merkle_root,
        convert(block.timestamp, bytes32),
        convert(msg.sender, bytes32)
    ))
    
    # Create batch record
    batch_id: uint256 = self.total_batches
    self.batches[batch_id] = AggregatedBatch({
        batch_id: batch_id,
        fog_batch_id: fog_batch_id,
        race_id: race_id,
        fog_merkle_root: fog_merkle_root,
        consortium_hash: consortium_hash,
        uploader: msg.sender,
        uploaded_at: block.timestamp,
        validation_count: 0,
        is_finalized: False,
        record_count: record_count
    })
    
    self.total_batches += 1
    self.races[race_id].total_batches_received += 1
    
    log DataBatchUploaded(race_id, batch_id, fog_merkle_root, msg.sender, block.timestamp)
    
    return batch_id

@external
def validate_batch(batch_id: uint256, is_valid: bool):
    """
    @notice CSP validates a data batch (part of PoSV consensus)
    @dev Multiple CSPs must validate for finalization
    @param batch_id The batch to validate
    @param is_valid Whether the CSP considers the batch valid
    
    This implements extended PoSV consensus:
    - CSPs verify data integrity
    - Multiple validations required
    - Maintains integrity during data aggregation
    """
    self._only_csp()
    assert batch_id < self.total_batches, "Invalid batch ID"
    assert not self.batches[batch_id].is_finalized, "Already finalized"
    assert not self.batch_validations[batch_id][msg.sender], "Already validated"
    
    batch: AggregatedBatch = self.batches[batch_id]
    
    # Record validation
    self.batch_validations[batch_id][msg.sender] = True
    self.csps[msg.sender].validations_count += 1
    self.csps[msg.sender].last_active = block.timestamp
    
    # Only count positive validations
    if is_valid:
        self.batches[batch_id].validation_count += 1
    
    log BatchValidated(batch.race_id, batch_id, msg.sender, is_valid)
    
    # Check if enough validations for finalization
    if self.batches[batch_id].validation_count >= self.required_validations:
        self.batches[batch_id].is_finalized = True

# ============================================================================
#                           RUNNER RESULTS MANAGEMENT
# ============================================================================

@external
def submit_runner_result(
    race_id: bytes32,
    runner_id: bytes32,
    finish_time: uint256,
    final_position: uint256,
    checkpoints_passed: uint256,
    is_dnf: bool,
    is_disqualified: bool
):
    """
    @notice Submit final result for a runner
    @dev Called after race completion to record official results
    @param race_id Associated race
    @param runner_id Pseudonymous runner ID
    @param finish_time Total race time in seconds
    @param final_position Finishing position (1st, 2nd, etc.)
    @param checkpoints_passed Number of checkpoints passed
    @param is_dnf Did Not Finish flag
    @param is_disqualified Disqualification flag
    """
    self._only_organizer(race_id)
    self._race_exists(race_id)
    
    self.runner_results[race_id][runner_id] = RunnerResult({
        runner_id: runner_id,
        race_id: race_id,
        finish_time: finish_time,
        final_position: final_position,
        checkpoints_passed: checkpoints_passed,
        is_dnf: is_dnf,
        is_disqualified: is_disqualified,
        verified: False
    })

@external
def verify_runner_result(race_id: bytes32, runner_id: bytes32):
    """
    @notice Verify a runner's result (referee validation)
    @param race_id Associated race
    @param runner_id Runner to verify
    """
    self._only_referee(race_id)
    self._race_exists(race_id)
    assert self.runner_results[race_id][runner_id].runner_id == runner_id, "Result not found"
    
    self.runner_results[race_id][runner_id].verified = True

@external
def certify_race_results(race_id: bytes32, results_hash: bytes32):
    """
    @notice Certify final race results
    @dev Creates immutable record of official results
    @param race_id Associated race
    @param results_hash Hash of all final results data
    
    This creates the immutable audit trail mentioned in the architecture.
    """
    self._only_organizer(race_id)
    self._race_exists(race_id)
    assert self.races[race_id].race_status == 2, "Race not completed"
    assert self.races[race_id].results_hash == empty(bytes32), "Already certified"
    
    self.races[race_id].results_hash = results_hash
    
    log RaceResultsCertified(race_id, results_hash, msg.sender, block.timestamp)

# ============================================================================
#                           DISPUTE MANAGEMENT
# ============================================================================

@external
def file_dispute(
    race_id: bytes32,
    runner_id: bytes32,
    reason: String[200]
) -> uint256:
    """
    @notice File a dispute about a runner's result
    @dev Any stakeholder with access can file disputes
    @param race_id Associated race
    @param runner_id Runner being disputed
    @param reason Reason for the dispute
    @return Dispute ID
    
    This supports the referee role for:
    - Reviewing aggregated data for disputes
    - Ensuring rule compliance via consortium access
    """
    self._race_exists(race_id)
    
    # Check stakeholder has some role in this race
    has_access: bool = (
        self.global_stakeholders[msg.sender].is_active or
        self.stakeholders[msg.sender][race_id].is_active
    )
    assert has_access, "No access to this race"
    assert len(reason) > 0, "Reason required"
    
    dispute_id: uint256 = self.total_disputes
    self.disputes[dispute_id] = Dispute({
        dispute_id: dispute_id,
        race_id: race_id,
        runner_id: runner_id,
        filed_by: msg.sender,
        reason: reason,
        status: 0,  # Open
        resolution: "",
        filed_at: block.timestamp,
        resolved_at: 0,
        resolver: empty(address)
    })
    
    self.total_disputes += 1
    
    return dispute_id

@external
def resolve_dispute(
    dispute_id: uint256,
    resolution: String[200],
    accepted: bool
):
    """
    @notice Resolve a dispute
    @dev Only referees can resolve disputes
    @param dispute_id The dispute to resolve
    @param resolution Resolution details
    @param accepted Whether the dispute was accepted (True) or rejected (False)
    """
    assert dispute_id < self.total_disputes, "Invalid dispute ID"
    dispute: Dispute = self.disputes[dispute_id]
    assert dispute.status == 0, "Already resolved"
    
    self._only_referee(dispute.race_id)
    
    self.disputes[dispute_id].status = 1 if accepted else 2
    self.disputes[dispute_id].resolution = resolution
    self.disputes[dispute_id].resolved_at = block.timestamp
    self.disputes[dispute_id].resolver = msg.sender

# ============================================================================
#                           VIEW FUNCTIONS (Read-only queries)
# ============================================================================

@external
@view
def get_race_info(race_id: bytes32) -> (String[100], address, uint256, uint256, uint256):
    """
    @notice Get basic race information
    @param race_id Race to query
    @return Tuple of (name, organizer, status, total_checkpoints, batches_received)
    """
    race: ConsortiumRace = self.races[race_id]
    return (race.race_name, race.organizer, race.race_status, race.total_checkpoints, race.total_batches_received)

@external
@view
def get_runner_result(race_id: bytes32, runner_id: bytes32) -> (uint256, uint256, uint256, bool, bool, bool):
    """
    @notice Get a runner's result
    @param race_id Associated race
    @param runner_id Runner to query
    @return Tuple of (finish_time, position, checkpoints, is_dnf, is_disqualified, verified)
    """
    result: RunnerResult = self.runner_results[race_id][runner_id]
    return (result.finish_time, result.final_position, result.checkpoints_passed, 
            result.is_dnf, result.is_disqualified, result.verified)

@external
@view
def get_batch_info(batch_id: uint256) -> (bytes32, bytes32, uint256, uint256, bool):
    """
    @notice Get batch information
    @param batch_id Batch to query
    @return Tuple of (race_id, merkle_root, record_count, validation_count, is_finalized)
    """
    batch: AggregatedBatch = self.batches[batch_id]
    return (batch.race_id, batch.fog_merkle_root, batch.record_count, 
            batch.validation_count, batch.is_finalized)

@external
@view
def get_csp_info(csp_address: address) -> (String[50], uint256, bool, uint256, uint256):
    """
    @notice Get CSP information
    @param csp_address CSP to query
    @return Tuple of (name, stake, is_active, validations_count, flag_count)
    """
    csp: CSPInfo = self.csps[csp_address]
    return (csp.name, csp.stake, csp.is_active, csp.validations_count, csp.flag_count)

@external
@view
def get_stakeholder_role(stakeholder: address, race_id: bytes32) -> uint256:
    """
    @notice Check a stakeholder's role for a race
    @param stakeholder Address to check
    @param race_id Race to check (empty for global)
    @return Role type (0 if none)
    """
    if race_id == empty(bytes32):
        if self.global_stakeholders[stakeholder].is_active:
            return self.global_stakeholders[stakeholder].role
    else:
        if self.stakeholders[stakeholder][race_id].is_active:
            return self.stakeholders[stakeholder][race_id].role
    
    # Check global role if no race-specific role
    if self.global_stakeholders[stakeholder].is_active:
        return self.global_stakeholders[stakeholder].role
    
    return ROLE_NONE

@external
@view
def get_dispute_info(dispute_id: uint256) -> (bytes32, bytes32, address, uint256, uint256):
    """
    @notice Get dispute information
    @param dispute_id Dispute to query
    @return Tuple of (race_id, runner_id, filed_by, status, filed_at)
    """
    dispute: Dispute = self.disputes[dispute_id]
    return (dispute.race_id, dispute.runner_id, dispute.filed_by, dispute.status, dispute.filed_at)

@external
@view
def has_batch_access(viewer: address, batch_id: uint256) -> bool:
    """
    @notice Check if an address has access to view batch data
    @param viewer Address to check
    @param batch_id Batch to check
    @return True if has access
    
    Access control for different stakeholder types:
    - Organizers: Full access
    - Referees: Full access for dispute resolution
    - Sponsors: Access to verified results
    - Health Teams: Access for monitoring
    - Betting Companies: Access to verified results
    """
    if batch_id >= self.total_batches:
        return False
    
    batch: AggregatedBatch = self.batches[batch_id]
    race_id: bytes32 = batch.race_id
    
    # Check global access
    global_role: uint256 = self.global_stakeholders[viewer].role
    if global_role == ROLE_ORGANIZER or global_role == ROLE_REFEREE:
        return True
    
    # Check race-specific access
    race_role: uint256 = self.stakeholders[viewer][race_id].role
    if not self.stakeholders[viewer][race_id].is_active:
        race_role = ROLE_NONE
    
    # All legitimate stakeholders have read access
    return race_role != ROLE_NONE

# ============================================================================
#                           HEALTH TEAM SPECIFIC FUNCTIONS
# ============================================================================

@external
@view
def check_runner_anomaly(race_id: bytes32, runner_id: bytes32, expected_time: uint256) -> bool:
    """
    @notice Check if a runner's time is anomalous (for health monitoring)
    @dev Health teams can use this to detect potential medical issues
    @param race_id Associated race
    @param runner_id Runner to check
    @param expected_time Expected checkpoint time
    @return True if runner's time significantly deviates from expected
    
    This supports the Health Team role for:
    - Monitoring runner data for health alerts
    - Detecting anomalies in timings
    """
    result: RunnerResult = self.runner_results[race_id][runner_id]
    
    if result.runner_id == empty(bytes32):
        return False
    
    # Check if finish time deviates more than 50% from expected
    if result.finish_time > expected_time * 3 / 2:
        return True  # Much slower than expected
    
    return False
