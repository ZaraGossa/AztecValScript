import time
from datetime import datetime
from web3 import Web3
from eth_account import Account

# === Settings ===
RPC_URL = "RPC"
PRIVATE_KEY = "private_key"
FROM_ADDRESS = Web3.to_checksum_address("evm_wallet")
CONTRACT_ADDRESS = Web3.to_checksum_address("0xF739D03e98e23A7B65940848aBA8921fF3bAc4b2")
CHAIN_ID = 11155111
TARGET_TIMESTAMP = 1747864152  # 2025-05-20 21:49:12 UTC

PREPARE_AT = TARGET_TIMESTAMP - 20  
SEND_AT = TARGET_TIMESTAMP - 8      
GAS_LIMIT = 245_000
SAFETY_INCREMENT = Web3.to_wei(500, 'gwei')

# Function arguments
TARGET_PROTOCOL = FROM_ADDRESS
VALIDATOR_ADDRESS = Web3.to_checksum_address("proposer_address")

# ABI
contract_abi = [{
    "name": "addValidator",
    "type": "function",
    "stateMutability": "nonpayable",
    "inputs": [
        {"name": "targetProtocol", "type": "address"},
        {"name": "validatorAddress", "type": "address"}
    ],
    "outputs": []
}]

# Connect
w3 = Web3(Web3.HTTPProvider(RPC_URL))
account = Account.from_key(PRIVATE_KEY)
assert w3.is_connected(), "Error connecting to RPC"

print(f"[{datetime.utcnow()}] The script is running. Waiting until {datetime.utcfromtimestamp(PREPARE_AT)}")

# Waiting for the preparations to begin
while time.time() < PREPARE_AT:
    time.sleep(0.1)

print(f"[{datetime.utcnow()}] Transaction preparation...")

# Preliminary data
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=contract_abi)
nonce = w3.eth.get_transaction_count(FROM_ADDRESS)

# Waiting to be send
while time.time() < SEND_AT:
    time.sleep(0.01)

print(f"[{datetime.utcnow()}] Analyzing the pending block...")

# Analys mempool
try:
    block = w3.eth.get_block("pending", full_transactions=True)
    priority_fees = [
        tx["maxPriorityFeePerGas"]
        for tx in block.transactions
        if "maxPriorityFeePerGas" in tx and tx["maxPriorityFeePerGas"] < Web3.to_wei(10, 'ether')
    ]
    max_seen_fee = max(priority_fees) if priority_fees else Web3.to_wei(1_000_000, 'gwei')
    my_priority_fee = max_seen_fee + SAFETY_INCREMENT
except Exception as e:
    print(f"[{datetime.utcnow()}] Error analyzing pending block: {e}")
    my_priority_fee = Web3.to_wei(1_002_000, 'gwei')

# Checking the balance and maximum allowable gas price
balance = w3.eth.get_balance(FROM_ADDRESS)
max_affordable_fee = balance // GAS_LIMIT

print(f"[{datetime.utcnow()}] Balance: {Web3.from_wei(balance, 'ether')} ETH")
print(f"[{datetime.utcnow()}] Priority fee: {Web3.from_wei(my_priority_fee, 'gwei')} Gwei")
print(f"[{datetime.utcnow()}] Max. permissible gas price: {Web3.from_wei(max_affordable_fee, 'gwei')} Gwei")

if my_priority_fee > max_affordable_fee:
    print(f"[{datetime.utcnow()}] Cancellation: insufficient funds even for priority fee.")
    exit(0)

max_fee = min(my_priority_fee + SAFETY_INCREMENT, max_affordable_fee)

print(f"[{datetime.utcnow()}] Final priorityFee: {Web3.from_wei(my_priority_fee, 'gwei')} Gwei")
print(f"[{datetime.utcnow()}] Final maxFeePerGas: {Web3.from_wei(max_fee, 'gwei')} Gwei")

# Assembly and sent
try:
    tx = contract.functions.addValidator(TARGET_PROTOCOL, VALIDATOR_ADDRESS).build_transaction({
        "chainId": CHAIN_ID,
        "from": FROM_ADDRESS,
        "nonce": nonce,
        "gas": GAS_LIMIT,
        "maxFeePerGas": max_fee,
        "maxPriorityFeePerGas": my_priority_fee,
        "type": 2,
    })

    signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

    print(f"[{datetime.utcnow()}] Transaction sent: {tx_hash.hex()}")
    print(f"https://sepolia.etherscan.io/tx/{tx_hash.hex()}")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    if receipt.status == 1:
        print(f"[{datetime.utcnow()}] Confirmed! Gas: {receipt.gasUsed}")
    else:
        print(f"[{datetime.utcnow()}] Transaction declined.")

except Exception as e:
    print(f"[{datetime.utcnow()}] Sending error: {e}")
