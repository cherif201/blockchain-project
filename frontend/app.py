"""
Race Event Blockchain - Streamlit Dashboard
============================================

A beautiful web interface for the Race Event Blockchain System.
Run with: streamlit run frontend/app.py
"""

import streamlit as st
from pathlib import Path
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from web3 import Web3
from eth_tester import EthereumTester
from web3.providers.eth_tester import EthereumTesterProvider
import vyper

# ============================================================================
#                           PAGE CONFIG
# ============================================================================

st.set_page_config(
    page_title="Race Event Blockchain",
    page_icon="🏃",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
#                           HELPER FUNCTIONS
# ============================================================================

CONTRACTS_DIR = PROJECT_ROOT / "contracts"


@st.cache_resource
def compile_contract(contract_path: Path):
    """Compile a Vyper contract (cached)."""
    with open(contract_path, 'r') as f:
        source = f.read()
    compiled = vyper.compile_code(source, output_formats=['bytecode', 'abi'])
    return compiled['bytecode'], compiled['abi']


@st.cache_resource
def init_blockchain():
    """Initialize the in-memory blockchain (cached)."""
    tester = EthereumTester()
    w3 = Web3(EthereumTesterProvider(tester))
    return w3, w3.eth.accounts


@st.cache_resource
def deploy_contracts(_w3, deployer):
    """Deploy both contracts (cached)."""
    # Deploy Fog Layer Contract
    fog_bytecode, fog_abi = compile_contract(CONTRACTS_DIR / "FogLayerRaceContract.vy")
    FogContract = _w3.eth.contract(abi=fog_abi, bytecode=fog_bytecode)
    tx_hash = FogContract.constructor("City Marathon 2025", 5).transact({
        'from': deployer,
        'gas': 8000000
    })
    fog_receipt = _w3.eth.wait_for_transaction_receipt(tx_hash)
    fog_contract = _w3.eth.contract(address=fog_receipt.contractAddress, abi=fog_abi)
    
    # Deploy Consortium Contract
    consortium_bytecode, consortium_abi = compile_contract(CONTRACTS_DIR / "ConsortiumRaceContract.vy")
    ConsortiumContract = _w3.eth.contract(abi=consortium_abi, bytecode=consortium_bytecode)
    tx_hash = ConsortiumContract.constructor("Global Race Consortium", 2).transact({
        'from': deployer,
        'gas': 8000000
    })
    consortium_receipt = _w3.eth.wait_for_transaction_receipt(tx_hash)
    consortium_contract = _w3.eth.contract(address=consortium_receipt.contractAddress, abi=consortium_abi)
    
    return fog_contract, consortium_contract


# ============================================================================
#                           INITIALIZE
# ============================================================================

# Initialize blockchain and contracts
w3, accounts = init_blockchain()
deployer = accounts[0]
fog_contract, consortium_contract = deploy_contracts(w3, deployer)

# Session state for tracking registered items
if 'registered_runners' not in st.session_state:
    st.session_state.registered_runners = []
if 'registered_fog_nodes' not in st.session_state:
    st.session_state.registered_fog_nodes = []
if 'transaction_history' not in st.session_state:
    st.session_state.transaction_history = []


# ============================================================================
#                           SIDEBAR
# ============================================================================

with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/running--v1.png", width=80)
    st.title("🏃 Race Blockchain")
    st.markdown("---")
    
    # Contract Info
    st.subheader("📋 Contract Info")
    st.code(f"Fog Layer:\n{fog_contract.address[:20]}...")
    st.code(f"Consortium:\n{consortium_contract.address[:20]}...")
    
    st.markdown("---")
    
    # Quick Stats
    st.subheader("📊 Quick Stats")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Runners", fog_contract.functions.registered_runner_count().call())
        st.metric("Fog Nodes", fog_contract.functions.registered_fog_node_count().call())
    with col2:
        race_state = fog_contract.functions.race_state().call()
        state_names = ["Setup", "Active", "Paused", "Finished"]
        st.metric("Race State", state_names[race_state])
        st.metric("CSPs", consortium_contract.functions.total_csps().call())
    
    st.markdown("---")
    st.caption("Built with Streamlit + Web3.py")


# ============================================================================
#                           MAIN CONTENT
# ============================================================================

st.title("🏁 Race Event Blockchain Dashboard")
st.markdown("Manage your marathon event on the blockchain")

# Create tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🏠 Overview", 
    "👥 Runners", 
    "🌫️ Fog Nodes", 
    "🏁 Race Control",
    "☁️ Consortium"
])

# ============================================================================
#                           TAB 1: OVERVIEW
# ============================================================================

with tab1:
    st.header("Race Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("### 🏃 Race Info")
        st.info(f"**Name:** {fog_contract.functions.race_name().call()}")
        st.info(f"**Checkpoints:** {fog_contract.functions.total_checkpoints().call()}")
    
    with col2:
        st.markdown("### 📊 Registration")
        runners = fog_contract.functions.registered_runner_count().call()
        nodes = fog_contract.functions.registered_fog_node_count().call()
        st.success(f"**Runners:** {runners}")
        st.success(f"**Fog Nodes:** {nodes}")
    
    with col3:
        st.markdown("### 🚦 Race State")
        race_state = fog_contract.functions.race_state().call()
        state_names = ["🔧 Setup", "▶️ Active", "⏸️ Paused", "🏁 Finished"]
        state_colors = ["blue", "green", "orange", "red"]
        st.markdown(f"### {state_names[race_state]}")
    
    with col4:
        st.markdown("### ☁️ Consortium")
        csps = consortium_contract.functions.total_csps().call()
        races = consortium_contract.functions.total_races().call()
        st.warning(f"**CSPs:** {csps}")
        st.warning(f"**Races:** {races}")
    
    st.markdown("---")
    
    # Transaction History
    st.subheader("📜 Recent Transactions")
    if st.session_state.transaction_history:
        for tx in reversed(st.session_state.transaction_history[-5:]):
            st.markdown(f"- {tx}")
    else:
        st.caption("No transactions yet. Register some runners or fog nodes!")


# ============================================================================
#                           TAB 2: RUNNERS
# ============================================================================

with tab2:
    st.header("👥 Runner Management")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Register Runner")
        
        bib_number = st.number_input("Bib Number", min_value=1, max_value=99999, value=101)
        
        if st.button("🏃 Register Runner", type="primary"):
            try:
                tx = fog_contract.functions.register_runner(bib_number).transact({
                    'from': deployer,
                    'gas': 200000
                })
                receipt = w3.eth.wait_for_transaction_receipt(tx)
                runner_id = fog_contract.functions.bib_to_runner_id(bib_number).call()
                
                st.session_state.registered_runners.append({
                    'bib': bib_number,
                    'id': runner_id.hex()[:16] + "..."
                })
                st.session_state.transaction_history.append(f"✅ Registered runner #{bib_number}")
                st.success(f"Runner #{bib_number} registered!")
                st.code(f"Runner ID: {runner_id.hex()[:32]}...")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {str(e)[:50]}")
        
        st.markdown("---")
        
        st.subheader("Batch Register")
        batch_input = st.text_input("Bib numbers (comma-separated)", "201, 202, 203")
        
        if st.button("📋 Batch Register"):
            try:
                bibs = [int(b.strip()) for b in batch_input.split(",")]
                tx = fog_contract.functions.batch_register_runners(bibs).transact({
                    'from': deployer,
                    'gas': 1000000
                })
                w3.eth.wait_for_transaction_receipt(tx)
                
                for bib in bibs:
                    runner_id = fog_contract.functions.bib_to_runner_id(bib).call()
                    st.session_state.registered_runners.append({
                        'bib': bib,
                        'id': runner_id.hex()[:16] + "..."
                    })
                
                st.session_state.transaction_history.append(f"✅ Batch registered {len(bibs)} runners")
                st.success(f"Registered {len(bibs)} runners!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {str(e)[:50]}")
    
    with col2:
        st.subheader("Registered Runners")
        
        total = fog_contract.functions.registered_runner_count().call()
        st.metric("Total Registered", total)
        
        if st.session_state.registered_runners:
            st.dataframe(
                st.session_state.registered_runners,
                use_container_width=True,
                column_config={
                    "bib": "Bib #",
                    "id": "Pseudonymous ID"
                }
            )
        else:
            st.info("No runners registered in this session. Register some above!")
        
        # Lookup runner
        st.markdown("---")
        st.subheader("🔍 Lookup Runner")
        lookup_bib = st.number_input("Enter Bib Number", min_value=1, key="lookup")
        if st.button("Search"):
            runner_id = fog_contract.functions.bib_to_runner_id(lookup_bib).call()
            if runner_id != b'\x00' * 32:
                st.success(f"Found! Runner ID: {runner_id.hex()}")
            else:
                st.warning("Runner not found")


# ============================================================================
#                           TAB 3: FOG NODES
# ============================================================================

with tab3:
    st.header("🌫️ Fog Node Management")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Register Fog Node")
        
        checkpoint_id = st.selectbox(
            "Checkpoint",
            options=list(range(1, fog_contract.functions.total_checkpoints().call() + 1)),
            format_func=lambda x: f"Checkpoint {x}" if x < fog_contract.functions.total_checkpoints().call() else f"Checkpoint {x} (Finish)"
        )
        
        stake_amount = st.slider("Stake Amount (ETH)", 0.1, 1.0, 0.1, 0.1)
        
        if st.button("🌫️ Register Fog Node", type="primary"):
            try:
                stake_wei = w3.to_wei(stake_amount, 'ether')
                tx = fog_contract.functions.register_fog_node(checkpoint_id).transact({
                    'from': deployer,
                    'value': stake_wei,
                    'gas': 300000
                })
                receipt = w3.eth.wait_for_transaction_receipt(tx)
                
                st.session_state.registered_fog_nodes.append({
                    'checkpoint': checkpoint_id,
                    'stake': f"{stake_amount} ETH"
                })
                st.session_state.transaction_history.append(f"✅ Registered fog node at CP{checkpoint_id}")
                st.success(f"Fog node registered for Checkpoint {checkpoint_id}!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {str(e)[:50]}")
        
        st.markdown("---")
        st.caption("⚠️ Minimum stake: 0.1 ETH")
    
    with col2:
        st.subheader("Registered Fog Nodes")
        
        total_nodes = fog_contract.functions.registered_fog_node_count().call()
        st.metric("Total Nodes", total_nodes)
        
        if st.session_state.registered_fog_nodes:
            st.dataframe(
                st.session_state.registered_fog_nodes,
                use_container_width=True,
                column_config={
                    "checkpoint": "Checkpoint",
                    "stake": "Stake"
                }
            )
        else:
            st.info("No fog nodes registered in this session.")
        
        # Visual checkpoint map
        st.markdown("---")
        st.subheader("🗺️ Checkpoint Map")
        
        checkpoints = fog_contract.functions.total_checkpoints().call()
        cols = st.columns(checkpoints)
        
        for i, col in enumerate(cols):
            cp_num = i + 1
            with col:
                if cp_num == 1:
                    label = "🚀 START"
                elif cp_num == checkpoints:
                    label = "🏁 FINISH"
                else:
                    label = f"📍 CP{cp_num}"
                
                st.markdown(f"**{label}**")


# ============================================================================
#                           TAB 4: RACE CONTROL
# ============================================================================

with tab4:
    st.header("🏁 Race Control")
    
    # Current State
    race_state = fog_contract.functions.race_state().call()
    state_names = ["🔧 Setup", "▶️ Active", "⏸️ Paused", "🏁 Finished"]
    
    st.subheader(f"Current State: {state_names[race_state]}")
    
    # State indicator
    cols = st.columns(4)
    for i, col in enumerate(cols):
        with col:
            if i == race_state:
                st.success(state_names[i])
            else:
                st.caption(state_names[i])
    
    st.markdown("---")
    
    # Control buttons
    st.subheader("🎮 Race Controls")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("▶️ Start Race", disabled=(race_state != 0), type="primary"):
            try:
                tx = fog_contract.functions.start_race().transact({'from': deployer, 'gas': 100000})
                w3.eth.wait_for_transaction_receipt(tx)
                st.session_state.transaction_history.append("▶️ Race started!")
                st.success("Race started!")
                st.rerun()
            except Exception as e:
                st.error(str(e)[:50])
    
    with col2:
        if st.button("⏸️ Pause Race", disabled=(race_state != 1)):
            try:
                tx = fog_contract.functions.pause_race().transact({'from': deployer, 'gas': 100000})
                w3.eth.wait_for_transaction_receipt(tx)
                st.session_state.transaction_history.append("⏸️ Race paused!")
                st.success("Race paused!")
                st.rerun()
            except Exception as e:
                st.error(str(e)[:50])
    
    with col3:
        if st.button("▶️ Resume Race", disabled=(race_state != 2)):
            try:
                tx = fog_contract.functions.resume_race().transact({'from': deployer, 'gas': 100000})
                w3.eth.wait_for_transaction_receipt(tx)
                st.session_state.transaction_history.append("▶️ Race resumed!")
                st.success("Race resumed!")
                st.rerun()
            except Exception as e:
                st.error(str(e)[:50])
    
    with col4:
        if st.button("🏁 Finish Race", disabled=(race_state != 1)):
            try:
                tx = fog_contract.functions.finish_race().transact({'from': deployer, 'gas': 100000})
                w3.eth.wait_for_transaction_receipt(tx)
                st.session_state.transaction_history.append("🏁 Race finished!")
                st.success("Race finished!")
                st.rerun()
            except Exception as e:
                st.error(str(e)[:50])
    
    st.markdown("---")
    
    # State Flow Diagram
    st.subheader("📊 State Flow")
    st.markdown("""
    ```
    ┌─────────┐     start()     ┌─────────┐
    │  Setup  │ ──────────────► │ Active  │
    └─────────┘                 └─────────┘
                                    │  ▲
                              pause │  │ resume
                                    ▼  │
                                ┌─────────┐
                                │ Paused  │
                                └─────────┘
                                    
    ┌─────────┐     finish()    ┌──────────┐
    │ Active  │ ──────────────► │ Finished │
    └─────────┘                 └──────────┘
    ```
    """)


# ============================================================================
#                           TAB 5: CONSORTIUM
# ============================================================================

with tab5:
    st.header("☁️ Consortium Layer")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Register CSP")
        
        csp_name = st.text_input("CSP Name", "AWS Cloud Provider")
        csp_stake = st.slider("Stake Amount (ETH)", 1.0, 10.0, 1.0, 0.5)
        csp_account = st.selectbox(
            "Account",
            options=accounts[1:6],
            format_func=lambda x: f"{x[:10]}...{x[-6:]}"
        )
        
        if st.button("☁️ Register CSP", type="primary"):
            try:
                stake_wei = w3.to_wei(csp_stake, 'ether')
                tx = consortium_contract.functions.register_csp(csp_name).transact({
                    'from': csp_account,
                    'value': stake_wei,
                    'gas': 300000
                })
                w3.eth.wait_for_transaction_receipt(tx)
                st.session_state.transaction_history.append(f"☁️ CSP '{csp_name}' registered")
                st.success(f"CSP '{csp_name}' registered!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {str(e)[:50]}")
    
    with col2:
        st.subheader("Consortium Stats")
        
        st.metric("Consortium Name", consortium_contract.functions.consortium_name().call())
        
        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("Total CSPs", consortium_contract.functions.total_csps().call())
        with col_b:
            st.metric("Total Races", consortium_contract.functions.total_races().call())
        
        st.markdown("---")
        
        st.subheader("Stakeholder Roles")
        st.markdown("""
        | Role | Description |
        |------|-------------|
        | 👔 Organizer | Full admin access |
        | 👨‍⚖️ Referee | Validate & resolve disputes |
        | 🎯 Sponsor | Read access to data |
        | ⚕️ Health Team | Monitor runner health |
        | 🎰 Betting | Access verified results |
        | ☁️ CSP | Network peer / validator |
        """)


# ============================================================================
#                           FOOTER
# ============================================================================

st.markdown("---")
st.markdown(
    """
    <div style='text-align: center'>
        <p>🏃 <strong>Race Event Blockchain System</strong> | Built with Streamlit + Web3.py + Vyper</p>
        <p style='color: gray; font-size: 12px;'>Using in-memory blockchain (EthereumTester) - Data resets on refresh</p>
    </div>
    """,
    unsafe_allow_html=True
)
