"""
Interaction Script for Race Event Blockchain System
====================================================

This script provides helper functions to interact with the deployed contracts.
Use this to:
- Register runners and fog nodes
- Record checkpoint crossings
- Upload batches to consortium
- Query race status and results

Usage:
    from interact import RaceEventManager
    
    manager = RaceEventManager("local")
    manager.register_runner(1234)  # Register runner with bib #1234
"""

import json
import os
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware


# ============================================================================
#                           CONFIGURATION
# ============================================================================

BUILD_DIR = Path(__file__).parent.parent / "build"

@dataclass
class NetworkConfig:
    """Network configuration"""
    name: str
    rpc_url: str
    chain_id: int
    is_poa: bool = False

NETWORKS = {
    "local": NetworkConfig("Local Ganache", "http://127.0.0.1:8545", 1337),
    "sepolia": NetworkConfig("Sepolia Testnet", "https://rpc.sepolia.org", 11155111),
}


# ============================================================================
#                           RACE EVENT MANAGER CLASS
# ============================================================================

class RaceEventManager:
    """
    Manager class for interacting with the Race Event Blockchain System.
    
    This class provides easy-to-use methods for all contract interactions,
    suitable for beginners learning blockchain development.
    
    Example:
        manager = RaceEventManager("local")
        
        # Register runners
        runner_id = manager.register_runner(1234)
        
        # Start race
        manager.start_race()
        
        # Record checkpoint crossing
        manager.record_crossing(bib=1234, checkpoint=1, fog_node_id="0x...")
    """
    
    def __init__(self, network: str = "local", private_key: Optional[str] = None):
        """
        Initialize the Race Event Manager.
        
        Args:
            network: Network name (local, sepolia, etc.)
            private_key: Optional private key for signing transactions
        """
        self.network = network
        self.private_key = private_key or os.environ.get("PRIVATE_KEY")
        
        # Connect to network
        self.w3 = self._connect(network)
        
        # Load deployment info
        self._load_deployment()
        
        # Load contract instances
        self._load_contracts()
    
    def _connect(self, network: str) -> Web3:
        """Connect to the blockchain network."""
        if network not in NETWORKS:
            raise ValueError(f"Unknown network: {network}")
        
        config = NETWORKS[network]
        w3 = Web3(Web3.HTTPProvider(config.rpc_url))
        
        if config.is_poa:
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        
        if not w3.is_connected():
            raise ConnectionError(f"Failed to connect to {config.name}")
        
        print(f"✅ Connected to {config.name}")
        return w3
    
    def _load_deployment(self):
        """Load deployment information from build directory."""
        deployment_path = BUILD_DIR / "deployment.json"
        
        if not deployment_path.exists():
            raise FileNotFoundError(
                "Deployment info not found. Run deploy.py first."
            )
        
        with open(deployment_path, 'r') as f:
            self.deployment = json.load(f)
        
        self.fog_address = self.deployment["fog_layer"]["address"]
        self.consortium_address = self.deployment["consortium_layer"]["address"]
        
        print(f"📄 Loaded deployment info")
        print(f"   Fog Layer: {self.fog_address}")
        print(f"   Consortium: {self.consortium_address}")
    
    def _load_contracts(self):
        """Load contract ABIs and create contract instances."""
        # Load Fog Layer contract
        fog_artifact_path = BUILD_DIR / "FogLayerRaceContract.json"
        with open(fog_artifact_path, 'r') as f:
            fog_artifact = json.load(f)
        
        self.fog_contract = self.w3.eth.contract(
            address=self.fog_address,
            abi=fog_artifact["abi"]
        )
        
        # Load Consortium contract
        consortium_artifact_path = BUILD_DIR / "ConsortiumRaceContract.json"
        with open(consortium_artifact_path, 'r') as f:
            consortium_artifact = json.load(f)
        
        self.consortium_contract = self.w3.eth.contract(
            address=self.consortium_address,
            abi=consortium_artifact["abi"]
        )
        
        print(f"📝 Loaded contract ABIs")
    
    def _get_account(self) -> str:
        """Get the account for transactions."""
        if self.private_key:
            return self.w3.eth.account.from_key(self.private_key).address
        if self.w3.eth.accounts:
            return self.w3.eth.accounts[0]
        raise ValueError("No account available")
    
    def _send_transaction(self, tx_func, value: int = 0):
        """Helper to send transactions."""
        account = self._get_account()
        
        tx = tx_func.build_transaction({
            'from': account,
            'nonce': self.w3.eth.get_transaction_count(account),
            'gas': 500000,
            'gasPrice': self.w3.eth.gas_price,
            'value': value
        })
        
        if self.private_key:
            signed = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        else:
            tx_hash = self.w3.eth.send_transaction(tx)
        
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        return receipt

    # ========================================================================
    #                       FOG LAYER FUNCTIONS
    # ========================================================================
    
    def register_runner(self, bib_number: int) -> bytes:
        """
        Register a new runner with a bib number.
        
        Args:
            bib_number: The runner's physical bib number
            
        Returns:
            The runner's pseudonymous ID (bytes32)
            
        Example:
            runner_id = manager.register_runner(1234)
            print(f"Runner registered: {runner_id.hex()}")
        """
        print(f"📝 Registering runner with bib #{bib_number}...")
        
        receipt = self._send_transaction(
            self.fog_contract.functions.register_runner(bib_number)
        )
        
        # Get the runner ID from the event
        runner_id = self.fog_contract.functions.get_runner_id(bib_number).call()
        
        print(f"✅ Runner registered!")
        print(f"   Bib: #{bib_number}")
        print(f"   ID: {runner_id.hex()}")
        
        return runner_id
    
    def batch_register_runners(self, bib_numbers: List[int]) -> List[bytes]:
        """
        Register multiple runners in one transaction (gas efficient).
        
        Args:
            bib_numbers: List of bib numbers to register
            
        Returns:
            List of runner IDs
            
        Example:
            ids = manager.batch_register_runners([1001, 1002, 1003, 1004])
        """
        print(f"📝 Batch registering {len(bib_numbers)} runners...")
        
        receipt = self._send_transaction(
            self.fog_contract.functions.batch_register_runners(bib_numbers)
        )
        
        # Get all runner IDs
        runner_ids = []
        for bib in bib_numbers:
            runner_id = self.fog_contract.functions.get_runner_id(bib).call()
            if runner_id != b'\x00' * 32:
                runner_ids.append(runner_id)
        
        print(f"✅ Registered {len(runner_ids)} runners")
        return runner_ids
    
    def register_fog_node(self, checkpoint_id: int, stake_eth: float = 0.1) -> bytes:
        """
        Register a fog node for a checkpoint.
        
        Args:
            checkpoint_id: The checkpoint this node will monitor
            stake_eth: Amount of ETH to stake (default 0.1)
            
        Returns:
            The fog node's ID
            
        Example:
            node_id = manager.register_fog_node(checkpoint_id=2, stake_eth=0.1)
        """
        print(f"🖥️  Registering fog node for checkpoint #{checkpoint_id}...")
        
        stake_wei = self.w3.to_wei(stake_eth, 'ether')
        
        receipt = self._send_transaction(
            self.fog_contract.functions.register_fog_node(checkpoint_id),
            value=stake_wei
        )
        
        # Extract fog node ID from event (simplified - in production parse logs)
        print(f"✅ Fog node registered for checkpoint #{checkpoint_id}")
        print(f"   Stake: {stake_eth} ETH")
        
        # Return a placeholder - in real implementation, parse from event logs
        return receipt['transactionHash']
    
    def start_race(self):
        """
        Start the race (moves from Setup to Active state).
        
        Example:
            manager.start_race()
        """
        print("🏁 Starting race...")
        
        receipt = self._send_transaction(
            self.fog_contract.functions.start_race()
        )
        
        print("✅ Race started!")
        return receipt
    
    def pause_race(self):
        """Pause the race temporarily."""
        print("⏸️  Pausing race...")
        receipt = self._send_transaction(
            self.fog_contract.functions.pause_race()
        )
        print("✅ Race paused")
        return receipt
    
    def resume_race(self):
        """Resume a paused race."""
        print("▶️  Resuming race...")
        receipt = self._send_transaction(
            self.fog_contract.functions.resume_race()
        )
        print("✅ Race resumed")
        return receipt
    
    def finish_race(self):
        """End the race."""
        print("🏆 Finishing race...")
        receipt = self._send_transaction(
            self.fog_contract.functions.finish_race()
        )
        print("✅ Race finished!")
        return receipt
    
    def record_crossing(
        self, 
        bib_number: int, 
        checkpoint_id: int, 
        fog_node_id: bytes,
        timestamp: Optional[int] = None
    ) -> bool:
        """
        Record a runner crossing a checkpoint.
        
        This is the main function called when RFID sensors detect a bib.
        
        Args:
            bib_number: The bib number detected by RFID
            checkpoint_id: The checkpoint where crossing occurred
            fog_node_id: ID of the recording fog node
            timestamp: Optional timestamp (uses current time if not provided)
            
        Returns:
            True if valid crossing, False if invalid
            
        Example:
            is_valid = manager.record_crossing(
                bib_number=1234,
                checkpoint_id=2,
                fog_node_id=node_id
            )
        """
        import time
        
        if timestamp is None:
            timestamp = int(time.time())
        
        print(f"📍 Recording checkpoint crossing...")
        print(f"   Bib: #{bib_number}")
        print(f"   Checkpoint: #{checkpoint_id}")
        
        receipt = self._send_transaction(
            self.fog_contract.functions.record_checkpoint_crossing(
                bib_number,
                checkpoint_id,
                fog_node_id,
                timestamp
            )
        )
        
        # Check if valid from runner status
        status = self.get_runner_status(bib_number)
        is_valid = status['last_checkpoint'] == checkpoint_id
        
        print(f"{'✅' if is_valid else '❌'} Crossing {'valid' if is_valid else 'invalid'}")
        return is_valid
    
    def get_runner_status(self, bib_number: int) -> dict:
        """
        Get the current status of a runner.
        
        Args:
            bib_number: The runner's bib number
            
        Returns:
            Dictionary with runner status
            
        Example:
            status = manager.get_runner_status(1234)
            print(f"Last checkpoint: {status['last_checkpoint']}")
        """
        result = self.fog_contract.functions.get_runner_status(bib_number).call()
        
        return {
            'last_checkpoint': result[0],
            'last_timestamp': result[1],
            'total_crossings': result[2],
            'is_active': result[3]
        }
    
    def is_runner_finished(self, bib_number: int) -> bool:
        """Check if a runner has completed the race."""
        return self.fog_contract.functions.is_runner_finished(bib_number).call()
    
    def create_batch(self) -> int:
        """
        Create a batch of checkpoint records for consortium upload.
        
        Returns:
            The batch ID
        """
        print("📦 Creating data batch for consortium upload...")
        
        receipt = self._send_transaction(
            self.fog_contract.functions.create_batch()
        )
        
        batch_id = self.fog_contract.functions.total_batches().call() - 1
        print(f"✅ Batch #{batch_id} created")
        
        return batch_id
    
    def get_race_info(self) -> dict:
        """Get current race information from fog layer."""
        return {
            'race_id': self.fog_contract.functions.race_id().call().hex(),
            'race_name': self.fog_contract.functions.race_name().call(),
            'total_checkpoints': self.fog_contract.functions.total_checkpoints().call(),
            'race_state': self.fog_contract.functions.race_state().call(),
            'registered_runners': self.fog_contract.functions.registered_runner_count().call(),
            'registered_fog_nodes': self.fog_contract.functions.registered_fog_node_count().call(),
            'total_records': self.fog_contract.functions.total_records().call(),
            'total_batches': self.fog_contract.functions.total_batches().call()
        }

    # ========================================================================
    #                       CONSORTIUM LAYER FUNCTIONS
    # ========================================================================
    
    def register_csp(self, name: str, stake_eth: float = 1.0):
        """
        Register as a Cloud Service Provider (CSP).
        
        Args:
            name: Human-readable name for the CSP
            stake_eth: Amount of ETH to stake (minimum 1.0)
        """
        print(f"☁️  Registering CSP: {name}...")
        
        stake_wei = self.w3.to_wei(stake_eth, 'ether')
        
        receipt = self._send_transaction(
            self.consortium_contract.functions.register_csp(name),
            value=stake_wei
        )
        
        print(f"✅ CSP registered: {name}")
        print(f"   Stake: {stake_eth} ETH")
        return receipt
    
    def register_race_in_consortium(
        self, 
        race_id: bytes,
        race_name: str,
        fog_contract: str,
        total_checkpoints: int
    ):
        """
        Register a race in the consortium layer.
        
        Args:
            race_id: Race ID from fog layer
            race_name: Human-readable name
            fog_contract: Address of fog layer contract
            total_checkpoints: Number of checkpoints
        """
        print(f"📋 Registering race in consortium: {race_name}...")
        
        receipt = self._send_transaction(
            self.consortium_contract.functions.register_race(
                race_id,
                race_name,
                fog_contract,
                total_checkpoints
            )
        )
        
        print(f"✅ Race registered in consortium")
        return receipt
    
    def upload_batch_to_consortium(
        self,
        race_id: bytes,
        fog_batch_id: int,
        merkle_root: bytes,
        record_count: int
    ) -> int:
        """
        Upload a data batch from fog layer to consortium.
        
        Args:
            race_id: Associated race
            fog_batch_id: Batch ID from fog layer
            merkle_root: Merkle root from fog layer
            record_count: Number of records in batch
            
        Returns:
            Consortium batch ID
        """
        print(f"📤 Uploading batch #{fog_batch_id} to consortium...")
        
        receipt = self._send_transaction(
            self.consortium_contract.functions.upload_batch(
                race_id,
                fog_batch_id,
                merkle_root,
                record_count
            )
        )
        
        batch_id = self.consortium_contract.functions.total_batches().call() - 1
        print(f"✅ Batch uploaded to consortium as #{batch_id}")
        
        return batch_id
    
    def validate_batch(self, batch_id: int, is_valid: bool = True):
        """
        Validate a batch as a CSP (part of PoSV consensus).
        
        Args:
            batch_id: Batch to validate
            is_valid: Whether the batch is valid
        """
        print(f"🔍 Validating batch #{batch_id}...")
        
        receipt = self._send_transaction(
            self.consortium_contract.functions.validate_batch(batch_id, is_valid)
        )
        
        print(f"✅ Batch #{batch_id} validated")
        return receipt
    
    def add_stakeholder(
        self,
        address: str,
        role: int,
        race_id: bytes = b'\x00' * 32
    ):
        """
        Add a stakeholder to the consortium.
        
        Role types:
        1 = Organizer (administrators)
        2 = Referee (validators)
        3 = Sponsor (data consumers)
        4 = Health Team (emergency responders)
        5 = Betting Company (analytics users)
        
        Args:
            address: Stakeholder's address
            role: Role type (1-5)
            race_id: Race ID (empty for global)
        """
        role_names = {
            1: "Organizer",
            2: "Referee",
            3: "Sponsor",
            4: "Health Team",
            5: "Betting Company"
        }
        
        print(f"👤 Adding stakeholder as {role_names.get(role, 'Unknown')}...")
        
        receipt = self._send_transaction(
            self.consortium_contract.functions.add_stakeholder(
                address,
                role,
                race_id
            )
        )
        
        print(f"✅ Stakeholder added")
        return receipt
    
    def get_consortium_race_info(self, race_id: bytes) -> dict:
        """Get race information from consortium layer."""
        result = self.consortium_contract.functions.get_race_info(race_id).call()
        
        return {
            'race_name': result[0],
            'organizer': result[1],
            'race_status': result[2],
            'total_checkpoints': result[3],
            'batches_received': result[4]
        }


# ============================================================================
#                           EXAMPLE USAGE
# ============================================================================

def example_workflow():
    """
    Example workflow demonstrating the complete race management process.
    
    This shows how organizers would use the system from start to finish.
    """
    print("\n" + "="*60)
    print("🏃 RACE EVENT BLOCKCHAIN - EXAMPLE WORKFLOW")
    print("="*60 + "\n")
    
    # Initialize manager
    manager = RaceEventManager("local")
    
    # 1. Register runners
    print("\n--- STEP 1: Register Runners ---")
    runner_ids = manager.batch_register_runners([1001, 1002, 1003])
    
    # 2. Register fog nodes
    print("\n--- STEP 2: Register Fog Nodes ---")
    # Note: In real deployment, each fog node would register itself
    # This is simplified for demonstration
    
    # 3. Start race
    print("\n--- STEP 3: Start Race ---")
    manager.start_race()
    
    # 4. Simulate checkpoint crossings
    print("\n--- STEP 4: Record Checkpoint Crossings ---")
    # In reality, these would come from RFID sensors
    
    # 5. Check race status
    print("\n--- STEP 5: Check Race Status ---")
    race_info = manager.get_race_info()
    print(f"   Race Name: {race_info['race_name']}")
    print(f"   State: {['Setup', 'Active', 'Paused', 'Finished'][race_info['race_state']]}")
    print(f"   Runners: {race_info['registered_runners']}")
    print(f"   Total Records: {race_info['total_records']}")
    
    print("\n" + "="*60)
    print("✅ WORKFLOW COMPLETE")
    print("="*60 + "\n")


if __name__ == "__main__":
    example_workflow()
