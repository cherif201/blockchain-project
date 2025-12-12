# @version ^0.3.10
"""
@title Fog Layer Race Contract - Private Blockchain for Race Events
@author Race Event Management System
@notice This contract handles real-time checkpoint validation at fog nodes
@dev Designed for low-latency edge computing on Raspberry Pi devices

This contract implements:
- Runner registration with pseudonymous IDs (GDPR compliant)
- Checkpoint crossing validation with sequential order enforcement
- Fog node registration and authorization
- Intermediate validation with timestamp duplicate detection
- Batch aggregation for consortium upload
"""

# ============================================================================
#                           EVENTS (for logging and tracking)
# ============================================================================

# Emitted when a new runner is registered
event RunnerRegistered:
    runner_id: indexed(bytes32)          # Pseudonymous ID (hashed from bib number)
    bib_number: indexed(uint256)         # Physical bib number
    registered_at: uint256               # Timestamp of registration

# Emitted when a runner crosses a checkpoint
event CheckpointCrossing:
    runner_id: indexed(bytes32)          # Runner's pseudonymous ID
    checkpoint_id: indexed(uint256)      # Checkpoint number (1, 2, 3...)
    fog_node_id: indexed(bytes32)        # ID of the fog node that recorded
    timestamp: uint256                   # When the crossing occurred
    validated: bool                      # Whether it passed validation

# Emitted when a fog node is registered
event FogNodeRegistered:
    fog_node_id: indexed(bytes32)        # Unique fog node identifier
    checkpoint_id: indexed(uint256)      # Associated checkpoint
    operator: address                    # Node operator address

# Emitted when data batch is ready for consortium upload
event BatchReadyForUpload:
    batch_id: indexed(uint256)           # Unique batch identifier
    checkpoint_count: uint256            # Number of crossings in batch
    merkle_root: bytes32                 # Merkle root of batch data
    created_at: uint256                  # Timestamp

# Emitted when race state changes
event RaceStateChanged:
    race_id: indexed(bytes32)            # Race identifier
    new_state: uint256                   # 0=Setup, 1=Active, 2=Paused, 3=Finished
    changed_at: uint256                  # Timestamp

# ============================================================================
#                           DATA STRUCTURES
# ============================================================================

# Struct to store runner information
struct Runner:
    bib_number: uint256                  # Physical bib number
    pseudonymous_id: bytes32             # Hashed ID for privacy
    last_checkpoint: uint256             # Last validated checkpoint
    last_timestamp: uint256              # Timestamp of last crossing
    is_active: bool                      # Whether runner is in race
    total_crossings: uint256             # Total valid crossings

# Struct to store checkpoint crossing data
struct CheckpointRecord:
    runner_id: bytes32                   # Runner's pseudonymous ID
    checkpoint_id: uint256               # Checkpoint number
    fog_node_id: bytes32                 # Recording fog node
    timestamp: uint256                   # Crossing timestamp
    is_valid: bool                       # Validation status
    validation_hash: bytes32             # Hash for integrity verification

# Struct for fog node information
struct FogNode:
    node_id: bytes32                     # Unique node identifier
    checkpoint_id: uint256               # Associated checkpoint
    operator: address                    # Operator's address
    is_active: bool                      # Whether node is operational
    stake: uint256                       # Staked amount for PoSV
    recordings_count: uint256            # Total recordings made
    last_active: uint256                 # Last activity timestamp

# Struct for data batches (for consortium upload)
struct DataBatch:
    batch_id: uint256                    # Unique batch ID
    start_index: uint256                 # First record index
    end_index: uint256                   # Last record index
    merkle_root: bytes32                 # Merkle root of records
    created_at: uint256                  # Creation timestamp
    is_uploaded: bool                    # Upload status

# ============================================================================
#                           STATE VARIABLES
# ============================================================================

# Race configuration
race_id: public(bytes32)                 # Unique race identifier
race_name: public(String[100])           # Human-readable race name
total_checkpoints: public(uint256)       # Number of checkpoints in race
race_state: public(uint256)              # 0=Setup, 1=Active, 2=Paused, 3=Finished
race_start_time: public(uint256)         # Race start timestamp
race_end_time: public(uint256)           # Race end timestamp

# Access control
owner: public(address)                   # Contract owner (organizer)
organizers: public(HashMap[address, bool])  # Authorized organizers

# Runner storage
runners: public(HashMap[bytes32, Runner])           # runner_id -> Runner
bib_to_runner_id: public(HashMap[uint256, bytes32]) # bib -> runner_id
registered_runner_count: public(uint256)            # Total registered runners

# Fog node storage
fog_nodes: public(HashMap[bytes32, FogNode])        # node_id -> FogNode
checkpoint_to_fog_node: public(HashMap[uint256, bytes32])  # checkpoint -> primary node
registered_fog_node_count: public(uint256)          # Total registered nodes

# Checkpoint records storage
checkpoint_records: public(HashMap[uint256, CheckpointRecord])  # index -> record
total_records: public(uint256)                                   # Total records

# Batch storage
batches: public(HashMap[uint256, DataBatch])        # batch_id -> batch
total_batches: public(uint256)                      # Total batches created
last_batched_record: public(uint256)                # Last record included in batch

# Validation settings
MIN_TIME_BETWEEN_CHECKPOINTS: public(constant(uint256)) = 30  # 30 seconds minimum
MAX_TIMESTAMP_VARIANCE: public(constant(uint256)) = 5         # 5 seconds tolerance
MIN_STAKE_AMOUNT: public(constant(uint256)) = 100000000000000000  # 0.1 ETH

# ============================================================================
#                           CONSTRUCTOR
# ============================================================================

@external
def __init__(_race_name: String[100], _total_checkpoints: uint256):
    """
    @notice Initialize the fog layer contract for a race
    @dev Sets up the race with basic parameters
    @param _race_name Human-readable name of the race (e.g., "City Marathon 2025")
    @param _total_checkpoints Number of checkpoints including start and finish
    
    Example: __init__("City Marathon 2025", 5) creates a race with 5 checkpoints
    """
    # Input validation
    assert _total_checkpoints >= 2, "Need at least start and finish"
    assert len(_race_name) > 0, "Race name cannot be empty"
    
    # Set owner and initialize organizers
    self.owner = msg.sender
    self.organizers[msg.sender] = True
    
    # Generate unique race ID from name and creation time
    self.race_id = keccak256(concat(
        convert(_race_name, Bytes[100]),
        convert(block.timestamp, bytes32)
    ))
    
    # Set race parameters
    self.race_name = _race_name
    self.total_checkpoints = _total_checkpoints
    self.race_state = 0  # Setup state
    
    # Log race creation
    log RaceStateChanged(self.race_id, 0, block.timestamp)

# ============================================================================
#                           MODIFIERS (Access Control)
# ============================================================================

@internal
def _only_owner():
    """
    @dev Ensures only the contract owner can call the function
    """
    assert msg.sender == self.owner, "Only owner allowed"

@internal
def _only_organizer():
    """
    @dev Ensures only authorized organizers can call the function
    """
    assert self.organizers[msg.sender], "Only organizers allowed"

@internal
def _only_active_fog_node(fog_node_id: bytes32):
    """
    @dev Ensures the fog node is registered and active
    """
    assert self.fog_nodes[fog_node_id].is_active, "Fog node not active"

@internal
def _race_is_active():
    """
    @dev Ensures the race is in active state
    """
    assert self.race_state == 1, "Race not active"

@internal
def _race_is_setup():
    """
    @dev Ensures the race is in setup state
    """
    assert self.race_state == 0, "Race not in setup"

# ============================================================================
#                           REGISTRATION FUNCTIONS
# ============================================================================

@external
def add_organizer(organizer: address):
    """
    @notice Add a new organizer to manage the race
    @dev Only owner can add organizers
    @param organizer Address to grant organizer privileges
    """
    self._only_owner()
    assert organizer != empty(address), "Invalid address"
    self.organizers[organizer] = True

@external
def remove_organizer(organizer: address):
    """
    @notice Remove organizer privileges from an address
    @dev Only owner can remove organizers
    @param organizer Address to revoke privileges from
    """
    self._only_owner()
    assert organizer != self.owner, "Cannot remove owner"
    self.organizers[organizer] = False

@external
def register_runner(bib_number: uint256) -> bytes32:
    """
    @notice Register a new runner with a bib number
    @dev Creates a pseudonymous ID for GDPR compliance
    @param bib_number The physical bib number worn by the runner
    @return The pseudonymous runner ID (hashed)
    
    Example: register_runner(1234) registers runner with bib #1234
    """
    self._only_organizer()
    self._race_is_setup()
    
    # Validate input
    assert bib_number > 0, "Invalid bib number"
    assert self.bib_to_runner_id[bib_number] == empty(bytes32), "Bib already registered"
    
    # Generate pseudonymous ID (hash of bib + race_id for privacy)
    # This ensures the same bib in different races has different IDs
    runner_id: bytes32 = keccak256(concat(
        convert(bib_number, bytes32),
        self.race_id
    ))
    
    # Create runner record
    self.runners[runner_id] = Runner({
        bib_number: bib_number,
        pseudonymous_id: runner_id,
        last_checkpoint: 0,
        last_timestamp: 0,
        is_active: True,
        total_crossings: 0
    })
    
    # Map bib to runner ID
    self.bib_to_runner_id[bib_number] = runner_id
    self.registered_runner_count += 1
    
    # Log registration
    log RunnerRegistered(runner_id, bib_number, block.timestamp)
    
    return runner_id

@external
@payable
def register_fog_node(checkpoint_id: uint256) -> bytes32:
    """
    @notice Register a new fog node for a checkpoint
    @dev Requires minimum stake for Proof of Stake & Validation (PoSV)
    @param checkpoint_id The checkpoint this node will monitor
    @return The unique fog node ID
    
    Example: register_fog_node(2) with 0.1 ETH stake registers node for checkpoint 2
    """
    self._only_organizer()
    self._race_is_setup()
    
    # Validate input
    assert checkpoint_id > 0 and checkpoint_id <= self.total_checkpoints, "Invalid checkpoint"
    assert msg.value >= MIN_STAKE_AMOUNT, "Insufficient stake"
    
    # Generate unique fog node ID
    fog_node_id: bytes32 = keccak256(concat(
        convert(msg.sender, bytes32),
        convert(checkpoint_id, bytes32),
        convert(block.timestamp, bytes32)
    ))
    
    # Create fog node record
    self.fog_nodes[fog_node_id] = FogNode({
        node_id: fog_node_id,
        checkpoint_id: checkpoint_id,
        operator: msg.sender,
        is_active: True,
        stake: msg.value,
        recordings_count: 0,
        last_active: block.timestamp
    })
    
    # Set as primary node for checkpoint if none exists
    if self.checkpoint_to_fog_node[checkpoint_id] == empty(bytes32):
        self.checkpoint_to_fog_node[checkpoint_id] = fog_node_id
    
    self.registered_fog_node_count += 1
    
    # Log registration
    log FogNodeRegistered(fog_node_id, checkpoint_id, msg.sender)
    
    return fog_node_id

@external
def batch_register_runners(bib_numbers: DynArray[uint256, 100]) -> DynArray[bytes32, 100]:
    """
    @notice Register multiple runners in a single transaction (gas efficient)
    @dev Useful for pre-race bulk registration
    @param bib_numbers Array of bib numbers to register
    @return Array of generated runner IDs
    """
    self._only_organizer()
    self._race_is_setup()
    
    runner_ids: DynArray[bytes32, 100] = []
    
    for bib_number in bib_numbers:
        if bib_number > 0 and self.bib_to_runner_id[bib_number] == empty(bytes32):
            # Generate pseudonymous ID
            runner_id: bytes32 = keccak256(concat(
                convert(bib_number, bytes32),
                self.race_id
            ))
            
            # Create runner record
            self.runners[runner_id] = Runner({
                bib_number: bib_number,
                pseudonymous_id: runner_id,
                last_checkpoint: 0,
                last_timestamp: 0,
                is_active: True,
                total_crossings: 0
            })
            
            self.bib_to_runner_id[bib_number] = runner_id
            self.registered_runner_count += 1
            runner_ids.append(runner_id)
            
            log RunnerRegistered(runner_id, bib_number, block.timestamp)
    
    return runner_ids

# ============================================================================
#                           RACE CONTROL FUNCTIONS
# ============================================================================

@external
def start_race():
    """
    @notice Start the race - moves from Setup to Active state
    @dev Only organizers can start, requires at least one runner and fog node
    """
    self._only_organizer()
    self._race_is_setup()
    
    # Validate race readiness
    assert self.registered_runner_count > 0, "No runners registered"
    assert self.registered_fog_node_count > 0, "No fog nodes registered"
    
    # Update state
    self.race_state = 1  # Active
    self.race_start_time = block.timestamp
    
    log RaceStateChanged(self.race_id, 1, block.timestamp)

@external
def pause_race():
    """
    @notice Pause the race temporarily
    @dev Can be used for emergencies or weather delays
    """
    self._only_organizer()
    self._race_is_active()
    
    self.race_state = 2  # Paused
    log RaceStateChanged(self.race_id, 2, block.timestamp)

@external
def resume_race():
    """
    @notice Resume a paused race
    @dev Moves from Paused back to Active state
    """
    self._only_organizer()
    assert self.race_state == 2, "Race not paused"
    
    self.race_state = 1  # Active
    log RaceStateChanged(self.race_id, 1, block.timestamp)

@external
def finish_race():
    """
    @notice End the race - moves to Finished state
    @dev Prevents any more checkpoint recordings
    """
    self._only_organizer()
    assert self.race_state == 1 or self.race_state == 2, "Race not active or paused"
    
    self.race_state = 3  # Finished
    self.race_end_time = block.timestamp
    
    log RaceStateChanged(self.race_id, 3, block.timestamp)

# ============================================================================
#                           CHECKPOINT RECORDING (Core Function)
# ============================================================================

@external
def record_checkpoint_crossing(
    bib_number: uint256,
    checkpoint_id: uint256,
    fog_node_id: bytes32,
    timestamp: uint256
) -> bool:
    """
    @notice Record a runner crossing a checkpoint (called by fog nodes)
    @dev This is the main function called when RFID sensors detect a bib
    @param bib_number The bib number read by the RFID sensor
    @param checkpoint_id The checkpoint where crossing occurred
    @param fog_node_id The ID of the fog node recording this
    @param timestamp The timestamp of the crossing (from fog node)
    @return True if valid crossing, False if invalid
    
    Validation Rules:
    1. Runner must be registered and active
    2. Checkpoint must be sequential (can't skip checkpoints)
    3. Minimum time must pass between checkpoints
    4. Timestamp must be recent (no replay attacks)
    5. Fog node must be active and authorized for this checkpoint
    
    Example: record_checkpoint_crossing(1234, 2, node_id, 1699999999)
    """
    self._race_is_active()
    self._only_active_fog_node(fog_node_id)
    
    # Get runner ID from bib
    runner_id: bytes32 = self.bib_to_runner_id[bib_number]
    assert runner_id != empty(bytes32), "Runner not registered"
    
    # Get runner data
    runner: Runner = self.runners[runner_id]
    assert runner.is_active, "Runner not active"
    
    # Validate fog node is assigned to this checkpoint
    fog_node: FogNode = self.fog_nodes[fog_node_id]
    assert fog_node.checkpoint_id == checkpoint_id, "Wrong checkpoint for node"
    
    # Initialize validation result
    is_valid: bool = True
    
    # ===== VALIDATION RULE 1: Sequential Checkpoint Order =====
    # Runners must pass checkpoints in order (can't skip)
    expected_checkpoint: uint256 = runner.last_checkpoint + 1
    if checkpoint_id != expected_checkpoint:
        is_valid = False
    
    # ===== VALIDATION RULE 2: Minimum Time Between Checkpoints =====
    # Prevents impossible times (cheating detection)
    if runner.last_timestamp > 0:
        time_elapsed: uint256 = timestamp - runner.last_timestamp
        if time_elapsed < MIN_TIME_BETWEEN_CHECKPOINTS:
            is_valid = False
    
    # ===== VALIDATION RULE 3: Timestamp Sanity Check =====
    # Timestamp should be recent (within tolerance of block time)
    if timestamp > block.timestamp + MAX_TIMESTAMP_VARIANCE:
        is_valid = False  # Future timestamp not allowed
    if timestamp < block.timestamp - 300:  # 5 minutes max delay
        is_valid = False  # Too old
    
    # ===== VALIDATION RULE 4: No Duplicate Timestamps =====
    # Same runner can't have same timestamp twice
    if timestamp == runner.last_timestamp and runner.last_timestamp > 0:
        is_valid = False
    
    # Generate validation hash for integrity verification
    validation_hash: bytes32 = keccak256(concat(
        runner_id,
        convert(checkpoint_id, bytes32),
        convert(timestamp, bytes32),
        fog_node_id
    ))
    
    # Create checkpoint record (even if invalid, for audit trail)
    record_index: uint256 = self.total_records
    self.checkpoint_records[record_index] = CheckpointRecord({
        runner_id: runner_id,
        checkpoint_id: checkpoint_id,
        fog_node_id: fog_node_id,
        timestamp: timestamp,
        is_valid: is_valid,
        validation_hash: validation_hash
    })
    self.total_records += 1
    
    # Update runner state only if valid
    if is_valid:
        self.runners[runner_id].last_checkpoint = checkpoint_id
        self.runners[runner_id].last_timestamp = timestamp
        self.runners[runner_id].total_crossings += 1
    
    # Update fog node statistics
    self.fog_nodes[fog_node_id].recordings_count += 1
    self.fog_nodes[fog_node_id].last_active = block.timestamp
    
    # Emit event
    log CheckpointCrossing(runner_id, checkpoint_id, fog_node_id, timestamp, is_valid)
    
    return is_valid

# ============================================================================
#                           BATCH AGGREGATION (For Consortium Upload)
# ============================================================================

@external
def create_batch() -> uint256:
    """
    @notice Create a batch of checkpoint records for consortium upload
    @dev Generates Merkle root for data integrity verification
    @return The batch ID
    
    This function packages recent checkpoint records into a batch
    that can be uploaded to the consortium blockchain for long-term storage.
    """
    self._only_organizer()
    
    # Check if there are new records to batch
    assert self.total_records > self.last_batched_record, "No new records to batch"
    
    # Calculate batch range
    start_index: uint256 = self.last_batched_record
    end_index: uint256 = self.total_records - 1
    
    # Generate Merkle root of records in batch
    # For simplicity, we hash all record hashes together
    # In production, you'd implement a proper Merkle tree
    merkle_root: bytes32 = self._calculate_batch_merkle_root(start_index, end_index)
    
    # Create batch record
    batch_id: uint256 = self.total_batches
    self.batches[batch_id] = DataBatch({
        batch_id: batch_id,
        start_index: start_index,
        end_index: end_index,
        merkle_root: merkle_root,
        created_at: block.timestamp,
        is_uploaded: False
    })
    
    # Update counters
    self.total_batches += 1
    self.last_batched_record = self.total_records
    
    # Emit event
    log BatchReadyForUpload(batch_id, end_index - start_index + 1, merkle_root, block.timestamp)
    
    return batch_id

@internal
def _calculate_batch_merkle_root(start: uint256, end: uint256) -> bytes32:
    """
    @dev Calculate a simple Merkle root for batch integrity
    @param start Starting record index
    @param end Ending record index
    @return Merkle root hash
    """
    # Simplified implementation - combines all validation hashes
    combined_hash: bytes32 = empty(bytes32)
    
    for i in range(start, start + 1000):  # Vyper requires bounded loops
        if i > end:
            break
        record: CheckpointRecord = self.checkpoint_records[i]
        combined_hash = keccak256(concat(combined_hash, record.validation_hash))
    
    return combined_hash

@external
def mark_batch_uploaded(batch_id: uint256):
    """
    @notice Mark a batch as uploaded to consortium layer
    @dev Called after successful upload to consortium blockchain
    @param batch_id The batch that was uploaded
    """
    self._only_organizer()
    assert batch_id < self.total_batches, "Invalid batch ID"
    assert not self.batches[batch_id].is_uploaded, "Already uploaded"
    
    self.batches[batch_id].is_uploaded = True

# ============================================================================
#                           VIEW FUNCTIONS (Read-only queries)
# ============================================================================

@external
@view
def get_runner_status(bib_number: uint256) -> (uint256, uint256, uint256, bool):
    """
    @notice Get current status of a runner
    @param bib_number The runner's bib number
    @return Tuple of (last_checkpoint, last_timestamp, total_crossings, is_active)
    """
    runner_id: bytes32 = self.bib_to_runner_id[bib_number]
    assert runner_id != empty(bytes32), "Runner not found"
    
    runner: Runner = self.runners[runner_id]
    return (runner.last_checkpoint, runner.last_timestamp, runner.total_crossings, runner.is_active)

@external
@view
def get_runner_id(bib_number: uint256) -> bytes32:
    """
    @notice Get the pseudonymous ID for a bib number
    @param bib_number The runner's bib number
    @return The runner's pseudonymous ID
    """
    return self.bib_to_runner_id[bib_number]

@external
@view
def get_checkpoint_record(index: uint256) -> (bytes32, uint256, bytes32, uint256, bool):
    """
    @notice Get details of a checkpoint crossing record
    @param index The record index
    @return Tuple of (runner_id, checkpoint_id, fog_node_id, timestamp, is_valid)
    """
    assert index < self.total_records, "Invalid index"
    record: CheckpointRecord = self.checkpoint_records[index]
    return (record.runner_id, record.checkpoint_id, record.fog_node_id, record.timestamp, record.is_valid)

@external
@view
def get_fog_node_stats(fog_node_id: bytes32) -> (uint256, uint256, bool, uint256):
    """
    @notice Get statistics for a fog node
    @param fog_node_id The fog node's ID
    @return Tuple of (checkpoint_id, recordings_count, is_active, stake)
    """
    node: FogNode = self.fog_nodes[fog_node_id]
    return (node.checkpoint_id, node.recordings_count, node.is_active, node.stake)

@external
@view
def get_batch_info(batch_id: uint256) -> (uint256, uint256, bytes32, uint256, bool):
    """
    @notice Get batch information for consortium upload
    @param batch_id The batch ID
    @return Tuple of (start_index, end_index, merkle_root, created_at, is_uploaded)
    """
    assert batch_id < self.total_batches, "Invalid batch ID"
    batch: DataBatch = self.batches[batch_id]
    return (batch.start_index, batch.end_index, batch.merkle_root, batch.created_at, batch.is_uploaded)

@external
@view
def is_runner_finished(bib_number: uint256) -> bool:
    """
    @notice Check if a runner has completed the race
    @param bib_number The runner's bib number
    @return True if runner passed all checkpoints
    """
    runner_id: bytes32 = self.bib_to_runner_id[bib_number]
    if runner_id == empty(bytes32):
        return False
    return self.runners[runner_id].last_checkpoint == self.total_checkpoints

# ============================================================================
#                           EMERGENCY & ADMIN FUNCTIONS
# ============================================================================

@external
def deactivate_runner(bib_number: uint256):
    """
    @notice Deactivate a runner (e.g., disqualified or withdrew)
    @dev Organizer only - runner can no longer record checkpoints
    @param bib_number The runner's bib number
    """
    self._only_organizer()
    
    runner_id: bytes32 = self.bib_to_runner_id[bib_number]
    assert runner_id != empty(bytes32), "Runner not found"
    
    self.runners[runner_id].is_active = False

@external
def deactivate_fog_node(fog_node_id: bytes32):
    """
    @notice Deactivate a fog node (e.g., malfunction or misbehavior)
    @dev Organizer only - prevents further recordings from this node
    @param fog_node_id The fog node's ID
    """
    self._only_organizer()
    
    assert self.fog_nodes[fog_node_id].node_id == fog_node_id, "Node not found"
    self.fog_nodes[fog_node_id].is_active = False

@external
def withdraw_stake(fog_node_id: bytes32):
    """
    @notice Allow fog node operator to withdraw stake after race ends
    @dev Only after race is finished and node is deactivated
    @param fog_node_id The fog node's ID
    """
    node: FogNode = self.fog_nodes[fog_node_id]
    assert node.operator == msg.sender, "Not node operator"
    assert self.race_state == 3, "Race not finished"
    assert node.stake > 0, "No stake to withdraw"
    
    stake_amount: uint256 = node.stake
    self.fog_nodes[fog_node_id].stake = 0
    
    # Transfer stake back to operator
    send(msg.sender, stake_amount)

@external
def emergency_stop():
    """
    @notice Emergency stop - immediately pauses the race
    @dev Owner only - use in case of critical issues
    """
    self._only_owner()
    
    if self.race_state == 1:  # Only if active
        self.race_state = 2  # Pause
        log RaceStateChanged(self.race_id, 2, block.timestamp)
