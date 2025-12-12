"""
Deployment Script for Race Event Blockchain System
===================================================

This script deploys the two-layer blockchain architecture:
1. Fog Layer Contract - For real-time checkpoint validation
2. Consortium Layer Contract - For aggregated data storage

Requirements:
- Python 3.8+
- web3.py installed (pip install web3)
- vyper installed (pip install vyper)
- Access to Ethereum node (local or remote)

Usage:
    python deploy.py --network <network_name>
    
    Networks: local, sepolia, mainnet
"""

import json
import os
import sys
from pathlib import Path
from typing import Tuple, Optional
from dataclasses import dataclass

# Web3 imports
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

# Vyper compiler
import vyper


# ============================================================================
#                           CONFIGURATION
# ============================================================================

@dataclass
class NetworkConfig:
    """Configuration for different networks"""
    name: str
    rpc_url: str
    chain_id: int
    is_poa: bool = False  # Proof of Authority chains need middleware


# Network configurations
NETWORKS = {
    "local": NetworkConfig(
        name="Local Ganache",
        rpc_url="http://127.0.0.1:8545",
        chain_id=1337,
        is_poa=False
    ),
    "sepolia": NetworkConfig(
        name="Sepolia Testnet",
        rpc_url="https://rpc.sepolia.org",
        chain_id=11155111,
        is_poa=False
    ),
    "goerli": NetworkConfig(
        name="Goerli Testnet",
        rpc_url="https://rpc.goerli.mudit.blog",
        chain_id=5,
        is_poa=True
    ),
}

# Contract paths
CONTRACTS_DIR = Path(__file__).parent.parent / "contracts"
FOG_CONTRACT_PATH = CONTRACTS_DIR / "FogLayerRaceContract.vy"
CONSORTIUM_CONTRACT_PATH = CONTRACTS_DIR / "ConsortiumRaceContract.vy"

# Output directory for compiled contracts
BUILD_DIR = Path(__file__).parent.parent / "build"


# ============================================================================
#                           COMPILER FUNCTIONS
# ============================================================================

def compile_vyper_contract(contract_path: Path) -> Tuple[str, str]:
    """
    Compile a Vyper contract and return bytecode and ABI.
    
    Args:
        contract_path: Path to the .vy file
        
    Returns:
        Tuple of (bytecode, abi_json)
    
    Example:
        bytecode, abi = compile_vyper_contract(Path("contracts/MyContract.vy"))
    """
    print(f"📝 Compiling {contract_path.name}...")
    
    # Read the contract source
    with open(contract_path, 'r') as f:
        source_code = f.read()
    
    try:
        # Compile to bytecode
        bytecode = vyper.compile_code(source_code, output_formats=['bytecode'])['bytecode']
        
        # Compile to ABI
        abi = vyper.compile_code(source_code, output_formats=['abi'])['abi']
        
        print(f"✅ Successfully compiled {contract_path.name}")
        return bytecode, json.dumps(abi)
        
    except vyper.exceptions.VyperException as e:
        print(f"❌ Compilation error in {contract_path.name}:")
        print(f"   {str(e)}")
        sys.exit(1)


def save_compiled_contract(
    contract_name: str, 
    bytecode: str, 
    abi: str,
    build_dir: Path = BUILD_DIR
) -> Path:
    """
    Save compiled contract artifacts to build directory.
    
    Args:
        contract_name: Name of the contract
        bytecode: Compiled bytecode
        abi: Contract ABI as JSON string
        build_dir: Directory to save artifacts
        
    Returns:
        Path to the saved artifact file
    """
    # Create build directory if it doesn't exist
    build_dir.mkdir(parents=True, exist_ok=True)
    
    # Create artifact object
    artifact = {
        "contractName": contract_name,
        "bytecode": bytecode,
        "abi": json.loads(abi)
    }
    
    # Save to file
    artifact_path = build_dir / f"{contract_name}.json"
    with open(artifact_path, 'w') as f:
        json.dump(artifact, f, indent=2)
    
    print(f"💾 Saved artifact to {artifact_path}")
    return artifact_path


# ============================================================================
#                           WEB3 CONNECTION
# ============================================================================

def connect_to_network(network_name: str) -> Web3:
    """
    Connect to the specified blockchain network.
    
    Args:
        network_name: Name of the network (local, sepolia, etc.)
        
    Returns:
        Connected Web3 instance
    """
    if network_name not in NETWORKS:
        print(f"❌ Unknown network: {network_name}")
        print(f"   Available networks: {', '.join(NETWORKS.keys())}")
        sys.exit(1)
    
    config = NETWORKS[network_name]
    print(f"🌐 Connecting to {config.name}...")
    
    # Create Web3 instance
    w3 = Web3(Web3.HTTPProvider(config.rpc_url))
    
    # Add POA middleware if needed (for networks like Goerli)
    if config.is_poa:
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    
    # Check connection
    if not w3.is_connected():
        print(f"❌ Failed to connect to {config.name}")
        print(f"   RPC URL: {config.rpc_url}")
        sys.exit(1)
    
    print(f"✅ Connected to {config.name}")
    print(f"   Chain ID: {w3.eth.chain_id}")
    print(f"   Latest block: {w3.eth.block_number}")
    
    return w3


def get_account(w3: Web3, private_key: Optional[str] = None) -> str:
    """
    Get the deployment account.
    
    For local networks, uses the first account.
    For testnets/mainnet, requires a private key.
    
    Args:
        w3: Web3 instance
        private_key: Optional private key for signing
        
    Returns:
        Account address
    """
    if private_key:
        account = w3.eth.account.from_key(private_key)
        return account.address
    
    # For local networks, use first account
    if w3.eth.accounts:
        return w3.eth.accounts[0]
    
    print("❌ No account available for deployment")
    print("   Set PRIVATE_KEY environment variable or use a local network")
    sys.exit(1)


# ============================================================================
#                           DEPLOYMENT FUNCTIONS
# ============================================================================

def deploy_contract(
    w3: Web3,
    bytecode: str,
    abi: str,
    constructor_args: list,
    account: str,
    private_key: Optional[str] = None,
    gas_limit: int = 5000000
) -> str:
    """
    Deploy a contract to the blockchain.
    
    Args:
        w3: Web3 instance
        bytecode: Contract bytecode
        abi: Contract ABI
        constructor_args: Arguments for constructor
        account: Deployer account address
        private_key: Private key for signing (required for non-local networks)
        gas_limit: Maximum gas for deployment
        
    Returns:
        Deployed contract address
    """
    # Create contract instance
    contract = w3.eth.contract(abi=json.loads(abi), bytecode=bytecode)
    
    # Build constructor transaction
    construct_txn = contract.constructor(*constructor_args).build_transaction({
        'from': account,
        'nonce': w3.eth.get_transaction_count(account),
        'gas': gas_limit,
        'gasPrice': w3.eth.gas_price
    })
    
    # Sign and send transaction
    if private_key:
        signed_txn = w3.eth.account.sign_transaction(construct_txn, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
    else:
        # For local networks without private key
        tx_hash = w3.eth.send_transaction(construct_txn)
    
    print(f"⏳ Waiting for deployment transaction: {tx_hash.hex()}")
    
    # Wait for receipt
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    if receipt['status'] == 1:
        print(f"✅ Contract deployed at: {receipt['contractAddress']}")
        print(f"   Gas used: {receipt['gasUsed']}")
        return receipt['contractAddress']
    else:
        print(f"❌ Deployment failed!")
        sys.exit(1)


def deploy_fog_layer(
    w3: Web3,
    account: str,
    race_name: str,
    total_checkpoints: int,
    private_key: Optional[str] = None
) -> str:
    """
    Deploy the Fog Layer Race Contract.
    
    Args:
        w3: Web3 instance
        account: Deployer account
        race_name: Name of the race
        total_checkpoints: Number of checkpoints
        private_key: Optional private key
        
    Returns:
        Deployed contract address
    """
    print("\n" + "="*50)
    print("🌫️  DEPLOYING FOG LAYER CONTRACT")
    print("="*50)
    
    # Compile contract
    bytecode, abi = compile_vyper_contract(FOG_CONTRACT_PATH)
    
    # Save artifact
    save_compiled_contract("FogLayerRaceContract", bytecode, abi)
    
    # Deploy
    address = deploy_contract(
        w3=w3,
        bytecode=bytecode,
        abi=abi,
        constructor_args=[race_name, total_checkpoints],
        account=account,
        private_key=private_key
    )
    
    return address


def deploy_consortium_layer(
    w3: Web3,
    account: str,
    consortium_name: str,
    required_validations: int,
    private_key: Optional[str] = None
) -> str:
    """
    Deploy the Consortium Blockchain Contract.
    
    Args:
        w3: Web3 instance
        account: Deployer account
        consortium_name: Name of the consortium
        required_validations: Number of CSP validations required
        private_key: Optional private key
        
    Returns:
        Deployed contract address
    """
    print("\n" + "="*50)
    print("☁️  DEPLOYING CONSORTIUM LAYER CONTRACT")
    print("="*50)
    
    # Compile contract
    bytecode, abi = compile_vyper_contract(CONSORTIUM_CONTRACT_PATH)
    
    # Save artifact
    save_compiled_contract("ConsortiumRaceContract", bytecode, abi)
    
    # Deploy
    address = deploy_contract(
        w3=w3,
        bytecode=bytecode,
        abi=abi,
        constructor_args=[consortium_name, required_validations],
        account=account,
        private_key=private_key
    )
    
    return address


# ============================================================================
#                           MAIN DEPLOYMENT SCRIPT
# ============================================================================

def main():
    """
    Main deployment function.
    
    Usage:
        python deploy.py                    # Deploy to local network
        python deploy.py --network sepolia  # Deploy to Sepolia testnet
    """
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Deploy Race Event Blockchain Contracts")
    parser.add_argument(
        "--network", 
        default="local",
        choices=list(NETWORKS.keys()),
        help="Network to deploy to (default: local)"
    )
    parser.add_argument(
        "--race-name",
        default="City Marathon 2025",
        help="Name of the race (default: City Marathon 2025)"
    )
    parser.add_argument(
        "--checkpoints",
        type=int,
        default=5,
        help="Number of checkpoints (default: 5)"
    )
    parser.add_argument(
        "--consortium-name",
        default="Global Marathon Consortium",
        help="Name of the consortium (default: Global Marathon Consortium)"
    )
    parser.add_argument(
        "--validations",
        type=int,
        default=2,
        help="Required CSP validations (default: 2)"
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("🏃 RACE EVENT BLOCKCHAIN DEPLOYMENT")
    print("="*60)
    print(f"Network: {args.network}")
    print(f"Race: {args.race_name}")
    print(f"Checkpoints: {args.checkpoints}")
    print(f"Consortium: {args.consortium_name}")
    print(f"Required Validations: {args.validations}")
    print("="*60 + "\n")
    
    # Get private key from environment (for testnets)
    private_key = os.environ.get("PRIVATE_KEY")
    
    # Connect to network
    w3 = connect_to_network(args.network)
    
    # Get deployment account
    account = get_account(w3, private_key)
    print(f"📍 Deploying from account: {account}")
    print(f"   Balance: {w3.from_wei(w3.eth.get_balance(account), 'ether')} ETH")
    
    # Deploy Fog Layer Contract
    fog_address = deploy_fog_layer(
        w3=w3,
        account=account,
        race_name=args.race_name,
        total_checkpoints=args.checkpoints,
        private_key=private_key
    )
    
    # Deploy Consortium Layer Contract
    consortium_address = deploy_consortium_layer(
        w3=w3,
        account=account,
        consortium_name=args.consortium_name,
        required_validations=args.validations,
        private_key=private_key
    )
    
    # Save deployment info
    deployment_info = {
        "network": args.network,
        "fog_layer": {
            "address": fog_address,
            "race_name": args.race_name,
            "total_checkpoints": args.checkpoints
        },
        "consortium_layer": {
            "address": consortium_address,
            "consortium_name": args.consortium_name,
            "required_validations": args.validations
        },
        "deployer": account
    }
    
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    deployment_path = BUILD_DIR / "deployment.json"
    with open(deployment_path, 'w') as f:
        json.dump(deployment_info, f, indent=2)
    
    print("\n" + "="*60)
    print("✅ DEPLOYMENT COMPLETE!")
    print("="*60)
    print(f"\n🌫️  Fog Layer Contract:        {fog_address}")
    print(f"☁️  Consortium Layer Contract: {consortium_address}")
    print(f"\n💾 Deployment info saved to: {deployment_path}")
    print("\n📋 Next steps:")
    print("   1. Register fog nodes at each checkpoint")
    print("   2. Register runners with their bib numbers")
    print("   3. Register CSPs in the consortium layer")
    print("   4. Link the fog contract to consortium")
    print("   5. Start the race!")
    print("="*60 + "\n")
    
    return deployment_info


if __name__ == "__main__":
    main()
