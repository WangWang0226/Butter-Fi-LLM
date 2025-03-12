from web3 import Web3
from eth_account import Account
import json

RPC_URL = "https://monad-testnet.g.alchemy.com/v2/c-AQewOSQs5I0eHIMgX_94jD90XucnjU"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

AGGREGATOR_CONTRACT_ADDRESS = "0x12C61b22b397a6D72AD85f699fAf2D75f50D556C"

CONTRACT_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "strategyId", "type": "uint256"},
            {"internalType": "address", "name": "user", "type": "address"},
        ],
        "name": "getPendingRewards",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "strategyId", "type": "uint256"},
            {"internalType": "address", "name": "user", "type": "address"},
        ],
        "name": "getStakedBalance",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    }
]

# 4. 建立合約實例
aggregator_contract = w3.eth.contract(
    address=AGGREGATOR_CONTRACT_ADDRESS, abi=CONTRACT_ABI
)

def getPendingRewards(strategyId: int, userAddress: str) -> int:
    try:
        pendingRewards = aggregator_contract.functions.getPendingRewards(
            strategyId, userAddress
        ).call()
        pendingRewards = w3.from_wei(pendingRewards, "ether")

        print(
            f"Pending Rewards for user {userAddress} in strategy {strategyId}: {pendingRewards}"
        )
        return pendingRewards
    except Exception as e:
        print(f"Error calling getPendingRewards: {str(e)}")
        return 0


def getStakedBalance(strategyId: int, userAddress: str) -> int:
    try:
        staked = aggregator_contract.functions.getStakedBalance(
            strategyId, userAddress
        ).call()
        staked = w3.from_wei(staked, "ether")
        print(
            f"Staked Balance for user {userAddress} in strategy {strategyId}: {staked}"
        )
        return staked
    except Exception as e:
        print(f"Error calling getStakedBalance: {str(e)}")
        return 0


def query_all_positions(userAddress: str):
    protocol_mapping = [
        {"name": "SimpleStake", "strategyId": 1, "staking_token": "WMOD", "reward_token": "sWMOD"},
        {"name": "HappyStake", "strategyId": 2, "staking_token": "WMOD", "reward_token": "sWMOD"},
        {"name": "EasyStake", "strategyId": 3, "staking_token": "WMOD", "reward_token": "sWMOD"},
        {"name": "CakeStake", "strategyId": 4, "staking_token": "WMOD", "reward_token": "sWMOD"},
    ]

    results = []
    for protocol in protocol_mapping:
        sid = protocol["strategyId"]
        protocol_name = protocol["name"]
        staking_token = protocol["staking_token"]
        reward_token = protocol["reward_token"]

        staked = float(getStakedBalance(sid, userAddress))  
        pending = float(getPendingRewards(sid, userAddress)) 

        results.append({
            "protocol": protocol_name, 
            "staking_token": staking_token, 
            "reward_token": reward_token, 
            "amount_staked": staked, 
            "pending_rewards": pending
        })
    json_output = json.dumps(results, indent=4)
    return json_output


if __name__ == "__main__":
    # 測試：指定使用者地址
    testUser = "0x563a73211b9A0b777d6CE3944DcB1447a9833C2d"

    positions = query_all_positions(testUser)
    # 將結果格式化成 JSON 輸出

    print("Positions:")
    print(positions)
