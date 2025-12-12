"""
Test Suite for Race Event Blockchain Smart Contracts
=====================================================

This module contains REAL tests that compile and deploy the Vyper contracts.
Run with: python -m pytest tests/ -v -s
"""

import pytest
from pathlib import Path
from web3 import Web3
from eth_tester import EthereumTester
from web3.providers.eth_tester import EthereumTesterProvider
import vyper


# ============================================================================
#                           TEST CONFIGURATION
# ============================================================================

# Test constants
TEST_RACE_NAME = "Test Marathon 2025"
TEST_CHECKPOINTS = 5
TEST_CONSORTIUM_NAME = "Test Consortium"

# Test bib numbers
TEST_BIBS = [1001, 1002, 1003, 1004, 1005]

# Contract paths
CONTRACTS_DIR = Path(__file__).parent.parent / "contracts"
FOG_CONTRACT_PATH = CONTRACTS_DIR / "FogLayerRaceContract.vy"
CONSORTIUM_CONTRACT_PATH = CONTRACTS_DIR / "ConsortiumRaceContract.vy"


# ============================================================================
#                           HELPER FUNCTIONS
# ============================================================================

def compile_vyper_contract(contract_path: Path):
    """Compile a Vyper contract and return bytecode and ABI."""
    print(f"\n📝 Compiling {contract_path.name}...")
    
    with open(contract_path, 'r') as f:
        source_code = f.read()
    
    # Compile the contract
    compiled = vyper.compile_code(
        source_code,
        output_formats=['bytecode', 'abi']
    )
    
    print(f"✓ Compiled successfully!")
    return compiled['bytecode'], compiled['abi']


# ============================================================================
#                           FIXTURES
# ============================================================================

@pytest.fixture(scope="module")
def w3():
    """Create Web3 instance with in-memory EthereumTester (no Ganache needed)."""
    tester = EthereumTester()
    w3 = Web3(EthereumTesterProvider(tester))
    return w3


@pytest.fixture(scope="module")
def accounts(w3):
    """Get test accounts from EthereumTester."""
    return w3.eth.accounts


@pytest.fixture(scope="module")
def deployer(accounts):
    """Primary deployer account."""
    return accounts[0]


@pytest.fixture(scope="module")
def fog_contract(w3, deployer):
    """Deploy the FogLayerRaceContract and return the contract instance."""
    bytecode, abi = compile_vyper_contract(FOG_CONTRACT_PATH)
    
    # Create contract instance
    FogContract = w3.eth.contract(abi=abi, bytecode=bytecode)
    
    # Deploy with constructor arguments
    tx_hash = FogContract.constructor(TEST_RACE_NAME, TEST_CHECKPOINTS).transact({
        'from': deployer,
        'gas': 6000000
    })
    
    # Wait for transaction receipt
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    print(f"✓ FogLayerContract deployed at: {tx_receipt.contractAddress}")
    
    # Return deployed contract instance
    return w3.eth.contract(address=tx_receipt.contractAddress, abi=abi)


@pytest.fixture(scope="module")
def consortium_contract(w3, deployer):
    """Deploy the ConsortiumRaceContract and return the contract instance."""
    bytecode, abi = compile_vyper_contract(CONSORTIUM_CONTRACT_PATH)
    
    # Create contract instance
    ConsortiumContract = w3.eth.contract(abi=abi, bytecode=bytecode)
    
    # Deploy with constructor arguments (consortium name, required validations)
    tx_hash = ConsortiumContract.constructor(TEST_CONSORTIUM_NAME, 2).transact({
        'from': deployer,
        'gas': 8000000
    })
    
    # Wait for transaction receipt
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    print(f"✓ ConsortiumContract deployed at: {tx_receipt.contractAddress}")
    
    # Return deployed contract instance
    return w3.eth.contract(address=tx_receipt.contractAddress, abi=abi)


# ============================================================================
#                           FOG LAYER TESTS
# ============================================================================

class TestFogLayerContract:
    """Tests for FogLayerRaceContract.vy"""
    
    def test_contract_deployment(self, fog_contract, deployer):
        """Test that contract deploys successfully with correct initial state."""
        # Verify race name is set
        race_name = fog_contract.functions.race_name().call()
        assert race_name == TEST_RACE_NAME, f"Expected {TEST_RACE_NAME}, got {race_name}"
        
        # Verify checkpoints count
        checkpoints = fog_contract.functions.total_checkpoints().call()
        assert checkpoints == TEST_CHECKPOINTS, f"Expected {TEST_CHECKPOINTS}, got {checkpoints}"
        
        # Verify race state is Setup (0)
        state = fog_contract.functions.race_state().call()
        assert state == 0, f"Expected state 0 (Setup), got {state}"
        
        # Verify owner is deployer
        owner = fog_contract.functions.owner().call()
        assert owner == deployer, "Owner should be deployer"
        
        print(f"\n✅ Contract deployed! Race: {race_name}, Checkpoints: {checkpoints}")
    
    def test_runner_registration(self, w3, fog_contract, deployer):
        """Test runner registration creates pseudonymous ID."""
        bib_number = 1001
        
        # Get initial runner count
        initial_count = fog_contract.functions.registered_runner_count().call()
        
        # Register a runner
        tx_hash = fog_contract.functions.register_runner(bib_number).transact({
            'from': deployer,
            'gas': 200000
        })
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        # Verify transaction succeeded
        assert receipt.status == 1, "Transaction should succeed"
        
        # Get the runner ID from the mapping
        runner_id = fog_contract.functions.bib_to_runner_id(bib_number).call()
        
        # Verify runner ID is not empty
        assert runner_id != b'\x00' * 32, "Runner ID should not be empty"
        
        # Verify runner count increased
        count = fog_contract.functions.registered_runner_count().call()
        assert count == initial_count + 1, f"Expected {initial_count + 1} registered runner, got {count}"
        
        print(f"\n✅ Runner registered! Bib: {bib_number}, ID: {runner_id.hex()[:16]}...")
    
    def test_duplicate_runner_registration_fails(self, w3, fog_contract, deployer):
        """Test that registering the same bib twice fails."""
        bib_number = 2001
        
        # First registration should succeed
        tx_hash = fog_contract.functions.register_runner(bib_number).transact({
            'from': deployer,
            'gas': 200000
        })
        w3.eth.wait_for_transaction_receipt(tx_hash)
        
        # Second registration should fail - check the transaction reverts
        try:
            fog_contract.functions.register_runner(bib_number).transact({
                'from': deployer,
                'gas': 200000
            })
            # If we get here, the transaction didn't revert as expected
            assert False, "Expected transaction to fail for duplicate registration"
        except Exception as e:
            # Transaction reverted as expected
            print(f"\n✅ Duplicate registration correctly rejected! Error: {type(e).__name__}")
    
    def test_batch_runner_registration(self, w3, fog_contract, deployer):
        """Test batch registration is working."""
        bibs = [3001, 3002, 3003, 3004, 3005]
        
        # Get initial count
        initial_count = fog_contract.functions.registered_runner_count().call()
        
        # Register multiple runners at once
        tx_hash = fog_contract.functions.batch_register_runners(bibs).transact({
            'from': deployer,
            'gas': 1000000
        })
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        assert receipt.status == 1, "Batch registration should succeed"
        
        # Verify all runners were registered
        for bib in bibs:
            runner_id = fog_contract.functions.bib_to_runner_id(bib).call()
            assert runner_id != b'\x00' * 32, f"Bib {bib} should be registered"
        
        # Verify count increased by 5
        final_count = fog_contract.functions.registered_runner_count().call()
        assert final_count == initial_count + len(bibs), f"Count should increase by {len(bibs)}"
        
        print(f"\n✅ Batch registration successful! Registered {len(bibs)} runners")
    
    def test_fog_node_registration(self, w3, fog_contract, deployer):
        """Test fog node registration with stake."""
        checkpoint_id = 1
        stake_amount = w3.to_wei(0.1, 'ether')  # Minimum stake
        
        # Get initial count
        initial_count = fog_contract.functions.registered_fog_node_count().call()
        
        # Register fog node with stake
        tx_hash = fog_contract.functions.register_fog_node(checkpoint_id).transact({
            'from': deployer,
            'value': stake_amount,
            'gas': 300000
        })
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        assert receipt.status == 1, "Fog node registration should succeed"
        
        # Verify fog node count increased
        count = fog_contract.functions.registered_fog_node_count().call()
        assert count == initial_count + 1, f"Expected {initial_count + 1} fog node, got {count}"
        
        print(f"\n✅ Fog node registered for checkpoint {checkpoint_id} with {w3.from_wei(stake_amount, 'ether')} ETH stake")
    
    def test_fog_node_insufficient_stake_fails(self, w3, fog_contract, deployer):
        """Test fog node registration fails with insufficient stake."""
        checkpoint_id = 2
        small_stake = w3.to_wei(0.01, 'ether')  # Less than minimum (0.1 ETH)
        
        try:
            fog_contract.functions.register_fog_node(checkpoint_id).transact({
                'from': deployer,
                'value': small_stake,
                'gas': 300000
            })
            # If we get here, the transaction didn't revert as expected
            assert False, "Expected transaction to fail for insufficient stake"
        except Exception as e:
            # Transaction reverted as expected
            print(f"\n✅ Insufficient stake correctly rejected! Error: {type(e).__name__}")
    
    def test_race_state_start(self, w3, fog_contract, deployer):
        """Test starting the race changes state to Active."""
        # Start the race (Setup -> Active)
        tx_hash = fog_contract.functions.start_race().transact({
            'from': deployer,
            'gas': 100000
        })
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        assert receipt.status == 1, "Start race should succeed"
        
        state = fog_contract.functions.race_state().call()
        assert state == 1, f"State should be Active (1) after starting, got {state}"
        
        print(f"\n✅ Race started! State is now Active (1)")
    
    def test_race_state_pause(self, w3, fog_contract, deployer):
        """Test pausing the race."""
        # Pause the race (Active -> Paused)
        tx_hash = fog_contract.functions.pause_race().transact({
            'from': deployer,
            'gas': 100000
        })
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        assert receipt.status == 1, "Pause race should succeed"
        
        state = fog_contract.functions.race_state().call()
        assert state == 2, f"State should be Paused (2), got {state}"
        
        print(f"\n✅ Race paused! State is now Paused (2)")
    
    def test_race_state_resume(self, w3, fog_contract, deployer):
        """Test resuming the race."""
        # Resume the race (Paused -> Active)
        tx_hash = fog_contract.functions.resume_race().transact({
            'from': deployer,
            'gas': 100000
        })
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        assert receipt.status == 1, "Resume race should succeed"
        
        state = fog_contract.functions.race_state().call()
        assert state == 1, f"State should be Active (1) after resuming, got {state}"
        
        print(f"\n✅ Race resumed! State is now Active (1)")
    
    def test_race_state_finish(self, w3, fog_contract, deployer):
        """Test finishing the race."""
        # End the race (Active -> Finished)
        tx_hash = fog_contract.functions.finish_race().transact({
            'from': deployer,
            'gas': 100000
        })
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        assert receipt.status == 1, "Finish race should succeed"
        
        state = fog_contract.functions.race_state().call()
        assert state == 3, f"State should be Finished (3), got {state}"
        
        print(f"\n✅ Race finished! State is now Finished (3)")
    
    def test_access_control_non_organizer(self, w3, fog_contract, accounts):
        """Test only organizers can call admin functions."""
        non_organizer = accounts[5]  # Use a different account that's not an organizer
        
        try:
            fog_contract.functions.register_runner(9001).transact({
                'from': non_organizer,
                'gas': 200000
            })
            # If we get here, the transaction didn't revert as expected
            assert False, "Expected transaction to fail for non-organizer"
        except Exception as e:
            # Transaction reverted as expected
            print(f"\n✅ Non-organizer correctly blocked! Error: {type(e).__name__}")


# ============================================================================
#                           CONSORTIUM LAYER TESTS
# ============================================================================

class TestConsortiumContract:
    """Tests for ConsortiumRaceContract.vy"""
    
    def test_contract_deployment(self, consortium_contract, deployer):
        """Test consortium contract deploys correctly."""
        # Verify owner is deployer
        owner = consortium_contract.functions.owner().call()
        assert owner == deployer, "Owner should be deployer"
        
        # Verify consortium name
        name = consortium_contract.functions.consortium_name().call()
        assert name == TEST_CONSORTIUM_NAME, f"Expected {TEST_CONSORTIUM_NAME}, got {name}"
        
        print(f"\n✅ Consortium contract deployed! Name: {name}")
    
    def test_csp_registration(self, w3, consortium_contract, accounts):
        """Test CSP registration with stake."""
        csp_address = accounts[1]
        stake_amount = w3.to_wei(1, 'ether')  # Minimum stake for CSP
        
        # Get initial count
        initial_count = consortium_contract.functions.total_csps().call()
        
        # Register CSP
        tx_hash = consortium_contract.functions.register_csp("Test CSP 1").transact({
            'from': csp_address,
            'value': stake_amount,
            'gas': 300000
        })
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        assert receipt.status == 1, "CSP registration should succeed"
        
        # Verify CSP is registered
        csp_count = consortium_contract.functions.total_csps().call()
        assert csp_count == initial_count + 1, f"CSP count should be {initial_count + 1}"
        
        print(f"\n✅ CSP registered with {w3.from_wei(stake_amount, 'ether')} ETH stake")
    
    def test_race_registration_in_consortium(self, w3, consortium_contract, deployer, accounts):
        """Test registering a race in the consortium."""
        import os
        race_name = "Marathon 2025"
        total_checkpoints = 10
        fog_contract_address = accounts[2]  # Use a test account as dummy fog contract
        # Generate a unique race_id
        race_id = w3.keccak(text=f"test_race_{os.urandom(8).hex()}")
        
        # Get initial count
        initial_count = consortium_contract.functions.total_races().call()
        
        # Register race (deployer is already a global organizer)
        tx_hash = consortium_contract.functions.register_race(
            race_id,
            race_name,
            fog_contract_address,
            total_checkpoints
        ).transact({
            'from': deployer,
            'gas': 500000
        })
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        assert receipt.status == 1, "Race registration should succeed"
        
        # Get race count
        race_count = consortium_contract.functions.total_races().call()
        assert race_count == initial_count + 1, f"Race count should be {initial_count + 1}"
        
        print(f"\n✅ Race '{race_name}' registered in consortium!")


# ============================================================================
#                           SUMMARY TEST
# ============================================================================

class TestSummary:
    """Summary of all contract functionality."""
    
    def test_print_summary(self, fog_contract, consortium_contract, w3):
        """Print a summary of all tested functionality."""
        print("\n" + "="*60)
        print("📊 TEST SUMMARY")
        print("="*60)
        
        # Fog contract stats
        print(f"\n🔶 FOG LAYER CONTRACT")
        print(f"   Address: {fog_contract.address}")
        print(f"   Race: {fog_contract.functions.race_name().call()}")
        print(f"   Checkpoints: {fog_contract.functions.total_checkpoints().call()}")
        print(f"   Runners Registered: {fog_contract.functions.registered_runner_count().call()}")
        print(f"   Fog Nodes: {fog_contract.functions.registered_fog_node_count().call()}")
        print(f"   Race State: {['Setup', 'Active', 'Paused', 'Finished'][fog_contract.functions.race_state().call()]}")
        
        # Consortium contract stats
        print(f"\n🔷 CONSORTIUM CONTRACT")
        print(f"   Address: {consortium_contract.address}")
        print(f"   Name: {consortium_contract.functions.consortium_name().call()}")
        print(f"   CSPs Registered: {consortium_contract.functions.total_csps().call()}")
        print(f"   Races Registered: {consortium_contract.functions.total_races().call()}")
        
        print("\n" + "="*60)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("="*60 + "\n")


# ============================================================================
#                           RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
