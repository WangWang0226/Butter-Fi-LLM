from web3 import Web3
from eth_account import Account
import json

# Connect to Anvil
RPC_URL = "http://127.0.0.1:8545"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Contract config
STAKE_CONTRACT_ADDRESS = "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"
ERC20_ADDRESS = "0x5FbDB2315678afecb367f032d93F642f64180aa3"
CONTRACT_ABI = [
    {
        "inputs": [{"internalType": "uint256", "name": "amount", "type": "uint256"}],
        "name": "stake",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]

ERC20_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "spender", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]

# Account config (use one of Anvil's default private keys: 0x70997..)
PRIVATE_KEY = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d" 
account = Account.from_key(PRIVATE_KEY)


def approve(spender_address: str, amount: int):
    try:
        token_contract = w3.eth.contract(address=ERC20_ADDRESS, abi=ERC20_ABI)

        # Build approve tx
        nonce = w3.eth.get_transaction_count(account.address)
        approve_tx = token_contract.functions.approve(
            spender_address, amount
        ).build_transaction(
            {
                "from": account.address,
                "gas": 100000,
                "gasPrice": w3.eth.gas_price,
                "nonce": nonce,
            }
        )

        # Sign and send
        signed_tx = w3.eth.account.sign_transaction(approve_tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"Approve successful! Hash: {tx_hash.hex()}")
        return receipt
    except Exception as e:
        print(f"Approve Error: {str(e)}")
        return None


def stake(amount: int):
    amountWei = w3.to_wei(amount, "ether")
    try:
        # First approve
        approve_tx = approve(STAKE_CONTRACT_ADDRESS, amountWei)
        if not approve_tx:
            return None

        # Create contract instance
        contract = w3.eth.contract(address=STAKE_CONTRACT_ADDRESS, abi=CONTRACT_ABI)

        # Build transaction
        nonce = w3.eth.get_transaction_count(account.address)
        tx = contract.functions.stake(amountWei).build_transaction(
            {
                "from": account.address,
                "gas": 200000,
                "gasPrice": w3.eth.gas_price,
                "nonce": nonce,
            }
        )

        # Sign transaction
        signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)

        # Send transaction
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        # Wait for transaction receipt
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"Transaction successful! Hash: {tx_hash.hex()}")
        return tx_hash.hex()

    except Exception as e:
        print(f"Error: {str(e)}")
        return None


if __name__ == "__main__":
    # Example: Stake 1 ETH (amount in wei)
    stake(100)
