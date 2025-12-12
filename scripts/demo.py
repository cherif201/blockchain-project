"""
Interactive Demo for Race Event Blockchain System
==================================================

This script lets you interact with the smart contracts directly.
No Ganache needed - uses in-memory blockchain.

Run with: python scripts/demo.py
"""

import sys
from pathlib import Path
from web3 import Web3
from eth_tester import EthereumTester
from web3.providers.eth_tester import EthereumTesterProvider
import vyper

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
CONTRACTS_DIR = PROJECT_ROOT / "contracts"


def compile_contract(contract_path: Path):
    """Compile a Vyper contract."""
    print(f"📝 Compiling {contract_path.name}...")
    with open(contract_path, 'r') as f:
        source = f.read()
    compiled = vyper.compile_code(source, output_formats=['bytecode', 'abi'])
    print(f"   ✓ Compiled successfully!")
    return compiled['bytecode'], compiled['abi']


def deploy_contract(w3, deployer, bytecode, abi, *args):
    """Deploy a contract and return the instance."""
    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx_hash = Contract.constructor(*args).transact({
        'from': deployer,
        'gas': 8000000
    })
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return w3.eth.contract(address=receipt.contractAddress, abi=abi)


def print_separator():
    print("\n" + "="*60 + "\n")


def main():
    print("""
╔═══════════════════════════════════════════════════════════════╗
║     🏃 RACE EVENT BLOCKCHAIN - INTERACTIVE DEMO 🏃            ║
╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # =========================================================================
    # SETUP: Create in-memory blockchain
    # =========================================================================
    print("🔧 SETUP: Creating in-memory Ethereum blockchain...")
    tester = EthereumTester()
    w3 = Web3(EthereumTesterProvider(tester))
    
    accounts = w3.eth.accounts
    deployer = accounts[0]
    fog_operator = accounts[1]
    runner_registrar = accounts[2]
    
    print(f"   Deployer account: {deployer[:20]}...")
    print(f"   Account balance: {w3.from_wei(w3.eth.get_balance(deployer), 'ether')} ETH")
    
    print_separator()
    
    # =========================================================================
    # DEPLOY: Fog Layer Contract
    # =========================================================================
    print("🚀 DEPLOYING FOG LAYER CONTRACT...")
    fog_bytecode, fog_abi = compile_contract(CONTRACTS_DIR / "FogLayerRaceContract.vy")
    
    race_name = "City Marathon 2025"
    total_checkpoints = 5
    
    fog_contract = deploy_contract(w3, deployer, fog_bytecode, fog_abi, race_name, total_checkpoints)
    print(f"   ✅ Deployed at: {fog_contract.address}")
    print(f"   Race Name: {fog_contract.functions.race_name().call()}")
    print(f"   Checkpoints: {fog_contract.functions.total_checkpoints().call()}")
    print(f"   State: Setup (0)")
    
    print_separator()
    
    # =========================================================================
    # REGISTER RUNNERS
    # =========================================================================
    print("👥 REGISTERING RUNNERS...")
    
    bib_numbers = [101, 102, 103, 104, 105]
    
    for bib in bib_numbers:
        tx = fog_contract.functions.register_runner(bib).transact({
            'from': deployer,
            'gas': 200000
        })
        w3.eth.wait_for_transaction_receipt(tx)
        runner_id = fog_contract.functions.bib_to_runner_id(bib).call()
        print(f"   ✓ Bib #{bib} → Runner ID: {runner_id.hex()[:16]}...")
    
    total_runners = fog_contract.functions.registered_runner_count().call()
    print(f"\n   📊 Total registered runners: {total_runners}")
    
    print_separator()
    
    # =========================================================================
    # REGISTER FOG NODES
    # =========================================================================
    print("🌫️ REGISTERING FOG NODES (with stake)...")
    
    stake_amount = w3.to_wei(0.1, 'ether')
    
    for checkpoint in range(1, 4):  # Checkpoints 1, 2, 3
        tx = fog_contract.functions.register_fog_node(checkpoint).transact({
            'from': deployer,
            'value': stake_amount,
            'gas': 300000
        })
        w3.eth.wait_for_transaction_receipt(tx)
        print(f"   ✓ Checkpoint {checkpoint}: Fog node registered with 0.1 ETH stake")
    
    total_nodes = fog_contract.functions.registered_fog_node_count().call()
    print(f"\n   📊 Total fog nodes: {total_nodes}")
    
    print_separator()
    
    # =========================================================================
    # RACE LIFECYCLE
    # =========================================================================
    print("🏁 RACE LIFECYCLE DEMONSTRATION...")
    
    # Start race
    print("\n   [1] Starting race...")
    tx = fog_contract.functions.start_race().transact({'from': deployer, 'gas': 100000})
    w3.eth.wait_for_transaction_receipt(tx)
    state = fog_contract.functions.race_state().call()
    print(f"       State: {['Setup', 'Active', 'Paused', 'Finished'][state]} ({state})")
    
    # Pause race
    print("\n   [2] Pausing race...")
    tx = fog_contract.functions.pause_race().transact({'from': deployer, 'gas': 100000})
    w3.eth.wait_for_transaction_receipt(tx)
    state = fog_contract.functions.race_state().call()
    print(f"       State: {['Setup', 'Active', 'Paused', 'Finished'][state]} ({state})")
    
    # Resume race
    print("\n   [3] Resuming race...")
    tx = fog_contract.functions.resume_race().transact({'from': deployer, 'gas': 100000})
    w3.eth.wait_for_transaction_receipt(tx)
    state = fog_contract.functions.race_state().call()
    print(f"       State: {['Setup', 'Active', 'Paused', 'Finished'][state]} ({state})")
    
    # Finish race
    print("\n   [4] Finishing race...")
    tx = fog_contract.functions.finish_race().transact({'from': deployer, 'gas': 100000})
    w3.eth.wait_for_transaction_receipt(tx)
    state = fog_contract.functions.race_state().call()
    print(f"       State: {['Setup', 'Active', 'Paused', 'Finished'][state]} ({state})")
    
    print_separator()
    
    # =========================================================================
    # DEPLOY: Consortium Contract
    # =========================================================================
    print("🚀 DEPLOYING CONSORTIUM CONTRACT...")
    consortium_bytecode, consortium_abi = compile_contract(CONTRACTS_DIR / "ConsortiumRaceContract.vy")
    
    consortium_name = "Global Race Consortium"
    required_validations = 2
    
    consortium_contract = deploy_contract(w3, deployer, consortium_bytecode, consortium_abi, 
                                          consortium_name, required_validations)
    print(f"   ✅ Deployed at: {consortium_contract.address}")
    print(f"   Consortium Name: {consortium_contract.functions.consortium_name().call()}")
    
    print_separator()
    
    # =========================================================================
    # REGISTER CSP
    # =========================================================================
    print("☁️ REGISTERING CLOUD SERVICE PROVIDER...")
    
    csp_stake = w3.to_wei(1, 'ether')
    tx = consortium_contract.functions.register_csp("AWS Cloud Provider").transact({
        'from': accounts[3],
        'value': csp_stake,
        'gas': 300000
    })
    w3.eth.wait_for_transaction_receipt(tx)
    print(f"   ✓ CSP 'AWS Cloud Provider' registered with 1 ETH stake")
    
    total_csps = consortium_contract.functions.total_csps().call()
    print(f"   📊 Total CSPs: {total_csps}")
    
    print_separator()
    
    # =========================================================================
    # FINAL SUMMARY
    # =========================================================================
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                    📊 FINAL SUMMARY                           ║
╚═══════════════════════════════════════════════════════════════╝
    """)
    
    print("🔶 FOG LAYER CONTRACT")
    print(f"   Address: {fog_contract.address}")
    print(f"   Race: {fog_contract.functions.race_name().call()}")
    print(f"   Checkpoints: {fog_contract.functions.total_checkpoints().call()}")
    print(f"   Runners: {fog_contract.functions.registered_runner_count().call()}")
    print(f"   Fog Nodes: {fog_contract.functions.registered_fog_node_count().call()}")
    print(f"   State: {['Setup', 'Active', 'Paused', 'Finished'][fog_contract.functions.race_state().call()]}")
    
    print("\n🔷 CONSORTIUM CONTRACT")
    print(f"   Address: {consortium_contract.address}")
    print(f"   Name: {consortium_contract.functions.consortium_name().call()}")
    print(f"   CSPs: {consortium_contract.functions.total_csps().call()}")
    print(f"   Races: {consortium_contract.functions.total_races().call()}")
    
    print("\n" + "="*60)
    print("✅ DEMO COMPLETED SUCCESSFULLY!")
    print("="*60)
    
    # =========================================================================
    # INTERACTIVE MODE
    # =========================================================================
    print("\n💡 TIP: You can now interact with the contracts in Python:")
    print("""
    # Example commands you could run in a Python shell:
    
    # Check runner status
    runner_id = fog_contract.functions.bib_to_runner_id(101).call()
    print(f"Runner 101 ID: {runner_id.hex()}")
    
    # Check fog node count
    nodes = fog_contract.functions.registered_fog_node_count().call()
    print(f"Fog nodes: {nodes}")
    
    # Check consortium CSPs
    csps = consortium_contract.functions.total_csps().call()
    print(f"CSPs: {csps}")
    """)
    
    return fog_contract, consortium_contract, w3


if __name__ == "__main__":
    fog_contract, consortium_contract, w3 = main()
