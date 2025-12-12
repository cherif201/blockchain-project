# Race Event Blockchain System
## Two-Layer Architecture for Marathon/Running Events

A production-ready blockchain solution for managing race events like marathons, using a hierarchical two-layer architecture with fog computing and consortium blockchain.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         EDGE IoT LAYER                                   │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │  RFID   │  │  RFID   │  │  RFID   │  │  RFID   │  │  RFID   │       │
│  │ Sensor  │  │ Sensor  │  │ Sensor  │  │ Sensor  │  │ Sensor  │       │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘       │
│       │            │            │            │            │             │
└───────┼────────────┼────────────┼────────────┼────────────┼─────────────┘
        │            │            │            │            │
        ▼            ▼            ▼            ▼            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   FOG-ENABLED PRIVATE BLOCKCHAIN                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │Fog Node 1│◄─►│Fog Node 2│◄─►│Fog Node 3│◄─►│Fog Node 4│◄─►│Fog Node 5│  │
│  │  START   │  │  5km     │  │  10km    │  │  15km    │  │  FINISH  │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│                                                                         │
│  • Real-time checkpoint validation       • PoSV Consensus               │
│  • Low-latency edge processing           • Sequential order checking    │
│  • Pseudonymous runner IDs (GDPR)        • Batch aggregation           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Batched Data Upload
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   CLOUD-ENABLED CONSORTIUM BLOCKCHAIN                    │
│                                                                         │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐             │
│  │  CSP 1  │◄──►│  CSP 2  │◄──►│  CSP 3  │◄──►│  CSP 4  │             │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘             │
│                                                                         │
│  • Federated ledger                    • Cross-organization sharing     │
│  • Extended PoSV consensus             • Immutable audit trails         │
│  • Stakeholder access control          • Dispute resolution             │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         APPLICATION LAYER                                │
│                                                                         │
│  👔 Organizers    🏃 Runners    🎯 Sponsors    ⚕️ Health Teams          │
│  👨‍⚖️ Referees     📊 Analytics   🎰 Betting     📱 Race Tracking App     │
└─────────────────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
blockchain/
├── contracts/
│   ├── FogLayerRaceContract.vy      # Private blockchain (edge)
│   └── ConsortiumRaceContract.vy    # Consortium blockchain (cloud)
├── scripts/
│   ├── deploy.py                    # Deployment script
│   └── interact.py                  # Interaction helpers
├── tests/
│   └── (test files)
├── build/
│   └── (compiled artifacts)
└── README.md
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10 or higher
- Node.js (optional, for Ganache)

### 1. Set Up Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# On Windows (CMD):
.\venv\Scripts\activate.bat

# On macOS/Linux:
source venv/bin/activate
```

### 2. Install Dependencies

```bash
# Install required Python packages
pip install web3 pytest eth-tester py-evm vyper==0.3.10
```

> ⚠️ **Important:** Use `vyper==0.3.10` as the contracts are written for this version.

### 3. Run Tests

The tests use an in-memory Ethereum blockchain (no Ganache needed):

```bash
# Run all tests with verbose output
python -m pytest tests/ -v -s
```

Expected output:
```
tests/test_contracts.py::TestFogLayerContract::test_contract_deployment PASSED
tests/test_contracts.py::TestFogLayerContract::test_runner_registration PASSED
tests/test_contracts.py::TestFogLayerContract::test_duplicate_runner_registration_fails PASSED
...
====== 15 passed ======
```

### 4. Deploy to Local Ganache (Optional)

If you want to deploy to a persistent local blockchain:

```bash
# Install Ganache CLI
npm install -g ganache

# Start Ganache
ganache --host 127.0.0.1 --port 8545

# In another terminal, deploy contracts
python scripts/deploy.py --network local --race-name "City Marathon 2025" --checkpoints 5
```

### 5. Interact with Contracts

```python
from interact import RaceEventManager

# Initialize
manager = RaceEventManager("local")

# Register runners
manager.batch_register_runners([1001, 1002, 1003, 1004, 1005])

# Start race
manager.start_race()

# Check status
status = manager.get_runner_status(1001)
print(f"Runner 1001 - Last checkpoint: {status['last_checkpoint']}")
```

## 📋 Smart Contract Features

### Fog Layer Contract (`FogLayerRaceContract.vy`)

**Purpose:** Real-time checkpoint validation at the edge

| Feature | Description |
|---------|-------------|
| Runner Registration | Pseudonymous IDs for GDPR compliance |
| Fog Node Registration | Stake-based participation (PoSV) |
| Checkpoint Recording | Sequential validation, timestamp checks |
| Batch Aggregation | Package data for consortium upload |
| Access Control | Organizer-only administrative functions |

**Key Functions:**
- `register_runner(bib_number)` - Register runner with privacy protection
- `register_fog_node(checkpoint_id)` - Register fog node with stake
- `record_checkpoint_crossing(...)` - Validate and record crossing
- `create_batch()` - Create batch for consortium upload

### Consortium Contract (`ConsortiumRaceContract.vy`)

**Purpose:** Aggregated storage and cross-organizational sharing

| Feature | Description |
|---------|-------------|
| Race Management | Multi-race support with full lifecycle |
| CSP Management | Cloud Service Provider registration |
| Batch Validation | Multi-CSP consensus (PoSV) |
| Stakeholder Roles | Organizers, Referees, Sponsors, etc. |
| Dispute Resolution | File and resolve disputes |
| Result Certification | Immutable final results |

**Stakeholder Roles:**
| Role | Permissions |
|------|-------------|
| Organizer | Full admin access, manage race |
| Referee | Review disputes, validate results |
| Sponsor | Read access to verified data |
| Health Team | Monitor runner anomalies |
| Betting Company | Access verified results |

## 🔐 Security Features

1. **Access Control**
   - Role-based permissions
   - Organizer-only admin functions
   - CSP stake requirements

2. **Data Validation**
   - Sequential checkpoint enforcement
   - Minimum time between checkpoints
   - Timestamp sanity checks
   - Duplicate detection

3. **Privacy Compliance (GDPR)**
   - Pseudonymous runner IDs
   - Hashed identifiers
   - No personal data on-chain

4. **Consensus Mechanism (PoSV)**
   - Stake-based participation
   - Multi-validator confirmation
   - Selfish CSP detection

## 📊 Example Workflow

```
1. REGISTRATION (Before Race)
   ├── Fog Layer: Register runners & fog nodes
   └── Consortium: Register race & CSPs

2. DATA CAPTURE (During Race)
   ├── RFID sensors detect bibs
   ├── Fog nodes validate crossings
   └── Data stored on local blockchain

3. LOCAL VALIDATION (Real-time)
   ├── Smart contract checks sequence
   ├── Nearby nodes reach consensus
   └── Invalid crossings flagged

4. AGGREGATION (Periodic)
   ├── Batch verified data
   ├── Calculate Merkle root
   └── Mark ready for upload

5. UPLOAD (Post-stage)
   ├── Send batches to consortium
   ├── CSPs validate via PoSV
   └── Update federated ledger

6. AUDITING (Post-race)
   ├── Certify final results
   ├── Resolve disputes
   └── Generate reports
```

## 🧪 Testing

### Run All Tests

```bash
# Activate virtual environment first
.\venv\Scripts\Activate.ps1  # Windows PowerShell

# Run tests with verbose output
python -m pytest tests/ -v -s
```

### Test Coverage

| Test Suite | Tests | Description |
|------------|-------|-------------|
| **Fog Layer** | 11 | Contract deployment, runner registration, fog nodes, race states, access control |
| **Consortium** | 3 | Contract deployment, CSP registration, race registration |
| **Summary** | 1 | Final status overview |

### What the Tests Verify

- ✅ Contracts compile with Vyper 0.3.10
- ✅ Contracts deploy to in-memory blockchain
- ✅ Runner registration creates pseudonymous IDs
- ✅ Duplicate registrations are rejected
- ✅ Batch registration works efficiently
- ✅ Fog nodes require minimum stake (0.1 ETH)
- ✅ Race state transitions (Setup → Active → Paused → Finished)
- ✅ Access control blocks non-organizers
- ✅ CSP registration with stake (1 ETH)
- ✅ Race registration in consortium

## 🌐 Network Deployment

### Local Development
```bash
python scripts/deploy.py --network local
```

### Sepolia Testnet
```bash
# Set your private key
$env:PRIVATE_KEY="your_private_key"  # PowerShell
# OR
export PRIVATE_KEY=your_private_key  # Bash

python scripts/deploy.py --network sepolia
```

## 📖 API Reference

### RaceEventManager Methods

```python
# Fog Layer
register_runner(bib_number: int) -> bytes
batch_register_runners(bibs: List[int]) -> List[bytes]
register_fog_node(checkpoint: int, stake: float) -> bytes
start_race() -> receipt
pause_race() -> receipt
resume_race() -> receipt
finish_race() -> receipt
record_crossing(bib, checkpoint, node_id, timestamp) -> bool
get_runner_status(bib: int) -> dict
create_batch() -> int

# Consortium Layer
register_csp(name: str, stake: float)
register_race_in_consortium(race_id, name, fog_addr, checkpoints)
upload_batch_to_consortium(race_id, batch_id, merkle_root, count) -> int
validate_batch(batch_id: int, is_valid: bool)
add_stakeholder(address, role, race_id)
```

## 🔧 Configuration

Environment variables:
```bash
PRIVATE_KEY=0x...      # For testnet/mainnet deployment
RPC_URL=http://...     # Custom RPC endpoint
```

## ❓ Troubleshooting

### Common Issues

**1. Vyper Version Mismatch**
```
vyper.exceptions.VersionException: Version specification "~=0.3.10" is not compatible with compiler version "0.4.x"
```
**Solution:** Install the correct Vyper version:
```bash
pip install vyper==0.3.10
```

**2. Module Not Found Errors**
```
ModuleNotFoundError: No module named 'web3'
```
**Solution:** Make sure your virtual environment is activated and packages are installed:
```bash
.\venv\Scripts\Activate.ps1
pip install web3 pytest eth-tester py-evm vyper==0.3.10
```

**3. Ganache Connection Failed**
```
AssertionError: Failed to connect to Ganache
```
**Solution:** The tests now use in-memory EthereumTester (no Ganache needed). Just run:
```bash
python -m pytest tests/ -v -s
```

**4. Python/Anaconda Conflicts**
If you have both Python and Anaconda installed, use a virtual environment:
```bash
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install web3 pytest eth-tester py-evm vyper==0.3.10
```

### Verify Installation

Run this to check everything is installed correctly:
```bash
python -c "import web3; import vyper; import eth_tester; print('All packages installed!')"
```

## 📝 License

MIT License

## 👥 Contributors

Race Event Blockchain System - Built for marathon and running event management.

---

**Note:** This is an educational/demonstration implementation. For production use, conduct thorough security audits and testing.
