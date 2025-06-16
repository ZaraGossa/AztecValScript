import time
import logging
from datetime import datetime
from web3 import Web3
from eth_account import Account

# === Настройки ===
RPC_URL = "ТВОЙ_RPC"
PRIVATE_KEY = "ТВОЙ_ПРИВАТНИК"
FROM_ADDRESS = Web3.to_checksum_address("ТВОЙ_КОШЕЛЕК")
CONTRACT_ADDRESS = Web3.to_checksum_address("0xF739D03e98e23A7B65940848aBA8921fF3bAc4b2")
CHAIN_ID = 11155111
TARGET_TIMESTAMP = timestamp

PREPARE_AT = TARGET_TIMESTAMP - 20
SEND_AT = TARGET_TIMESTAMP - 4
MIN_RBF_DELAY = 2  # через сколько секунд отправлять RBF
GAS_LIMIT = 1_200_000
SAFETY_INCREMENT = Web3.to_wei(500, 'gwei')

TARGET_PROTOCOL = FROM_ADDRESS
VALIDATOR_ADDRESS = Web3.to_checksum_address("PROPOSER_ADDRESS")

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

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[
        logging.FileHandler("tx_execution.log"),
        logging.StreamHandler()
    ]
)

# Подключение
w3 = Web3(Web3.HTTPProvider(RPC_URL))
account = Account.from_key(PRIVATE_KEY)
assert w3.is_connected(), "Ошибка подключения к RPC"

logging.info(f"Скрипт запущен. Ждём до подготовки @ {datetime.utcfromtimestamp(PREPARE_AT)}")

while time.time() < PREPARE_AT:
    time.sleep(0.1)

logging.info("Подготовка транзакции...")

contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=contract_abi)
nonce = w3.eth.get_transaction_count(FROM_ADDRESS)

while time.time() < SEND_AT:
    time.sleep(0.01)

logging.info("Анализируем pending-блок...")

try:
    block = w3.eth.get_block("pending", full_transactions=True)
    priority_fees = [
        tx["maxPriorityFeePerGas"]
        for tx in block.transactions
        if "maxPriorityFeePerGas" in tx
    ]
    max_seen_fee = max(priority_fees) if priority_fees else Web3.to_wei(10_000, 'gwei')
    my_priority_fee = max_seen_fee + SAFETY_INCREMENT
except Exception as e:
    logging.warning(f"Ошибка анализа pending-блока: {e}")
    my_priority_fee = Web3.to_wei(1_002_000, 'gwei')

balance = w3.eth.get_balance(FROM_ADDRESS)
max_affordable_fee = balance // GAS_LIMIT

logging.info(f"Баланс: {Web3.from_wei(balance, 'ether')} ETH")
logging.info(f"Priority fee: {Web3.from_wei(my_priority_fee, 'gwei')} Gwei")
logging.info(f"Макс. допустимая цена газа: {Web3.from_wei(max_affordable_fee, 'gwei')} Gwei")

if my_priority_fee > max_affordable_fee:
    logging.error("❌ Отмена: недостаточно средств даже для priority fee.")
    exit(0)

max_fee = min(my_priority_fee + SAFETY_INCREMENT, max_affordable_fee)

# Первая транзакция
tx1 = contract.functions.addValidator(TARGET_PROTOCOL, VALIDATOR_ADDRESS).build_transaction({
    "chainId": CHAIN_ID,
    "from": FROM_ADDRESS,
    "nonce": nonce,
    "gas": GAS_LIMIT,
    "maxFeePerGas": max_fee,
    "maxPriorityFeePerGas": my_priority_fee,
    "type": 2,
})
signed_tx1 = w3.eth.account.sign_transaction(tx1, PRIVATE_KEY)

logging.info("Первая попытка отправки...")
tx1_send_start = datetime.utcnow()
tx1_hash = w3.eth.send_raw_transaction(signed_tx1.raw_transaction)
tx1_send_end = datetime.utcnow()
logging.info(f"TX1 отправлена: {tx1_hash.hex()}")
logging.info(f"⏱ Время отправки TX1: {tx1_send_start} → {tx1_send_end} ({(tx1_send_end - tx1_send_start).total_seconds():.3f} сек)")

# Задержка перед RBF
time.sleep(MIN_RBF_DELAY)

# Повторный анализ перед RBF
try:
    logging.info("[RBF] Повторный анализ pending-блока...")
    block_rbf = w3.eth.get_block("pending", full_transactions=True)
    priority_fees_rbf = [
        tx["maxPriorityFeePerGas"]
        for tx in block_rbf.transactions
        if "maxPriorityFeePerGas" in tx
    ]
    max_seen_fee_rbf = max(priority_fees_rbf) if priority_fees_rbf else Web3.to_wei(10_000, 'gwei')
    new_priority_fee = max_seen_fee_rbf + SAFETY_INCREMENT
except Exception as e:
    logging.warning(f"[RBF] Ошибка анализа мемпула: {e}")
    new_priority_fee = my_priority_fee + Web3.to_wei(500, 'gwei')

new_max_fee = min(new_priority_fee + SAFETY_INCREMENT, balance // GAS_LIMIT)

# Сборка и отправка RBF
tx2 = tx1.copy()
tx2['maxFeePerGas'] = new_max_fee
tx2['maxPriorityFeePerGas'] = new_priority_fee
signed_tx2 = w3.eth.account.sign_transaction(tx2, PRIVATE_KEY)

logging.info(f"[RBF] Вторая попытка (адаптивная) через {MIN_RBF_DELAY} сек...")
tx2_send_start = datetime.utcnow()
tx2_hash = w3.eth.send_raw_transaction(signed_tx2.raw_transaction)
tx2_send_end = datetime.utcnow()

logging.info(f"TX2 (RBF) отправлена: {tx2_hash.hex()}")
logging.info(f"⏱ Время отправки TX2: {tx2_send_start} → {tx2_send_end} ({(tx2_send_end - tx2_send_start).total_seconds():.3f} сек)")

# Подтверждение
logging.info("Ожидаем подтверждение...")
receipt = w3.eth.wait_for_transaction_receipt(tx2_hash, timeout=60)
block = w3.eth.get_block(receipt.blockNumber)
logging.info(f"✅ Подтверждено в блоке {receipt.blockNumber} (время блока: {datetime.utcfromtimestamp(block.timestamp)})")
logging.info("Завершено. Смотри лог в: tx_execution.log")
