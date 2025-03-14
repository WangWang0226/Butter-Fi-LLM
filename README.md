# **Butter Finance - Backend & LLM Agent System**  

This repository contains the backend and LLM agent system of **Butter Finance**, where we integrate **LangChain** to build an AI agent that assists users with staking and yield farming strategies.  

### **Overview**  
We leverage **OpenAI GPT-4o-mini** as the core reasoning engine and use **Retrieval-Augmented Generation (RAG)** to fetch up-to-date DeFi protocol data. Our system enables users to interact with an **AI-powered chatbot** to:  
- Get recommendations for staking strategies.  
- Stake tokens seamlessly.  
- Check, withdraw, and claim rewards from existing positions.  

### **User Flow & System Architecture**  
![Architecture](/demo/architecture.png)

1. **User Interaction**  
   - Users interact with the AI bot through the frontend UI, asking questions about staking, yields, or specific protocols.  
   - They can request **strategy recommendations, stake tokens, check their positions, withdraw funds, or claim rewards**.  

2. **Backend Processing (LLM Agent & Tool Execution)**  
   - The backend processes user queries and determines the appropriate action:  
     - General questions → Answered directly by GPT-4o-mini.  
     - Staking recommendations → Uses **retrieve_defi_info()** to fetch protocol data from **Pinecone Vector Store**.  
     - Position tracking → Calls **check_user_position()** to retrieve user positions from the **Aggregator Contract**.  

3. **Execution & Smart Contract Integration**  
   - Based on the intent, the AI agent responds in **JSON format** with one of the following types to the frontend:  
     - **`EXECUTE_TRANSACTION`** → Frontend will trigger the `investInStrategy()` function to deposit funds.  
     - **`WITHDRAW_POSITION`** → Frontend will call `withdrawPosition()` to retrieve staked funds.  
     - **`CLAIM_REWARD`** → Frontend will execute `claimReward()` to collect pending rewards.  
     - **`PURE_STRING_RESPONSE`** → Frontend provides a general text-based answer.  
   - Transactions are routed through the **Aggregator.sol** contract, which interacts with multiple staking protocols via adapters.  

### **Phase 2: Real-time Monitoring**  
Currently, all protocol data in the **Pinecone Vector DB** is mocked. In the next phase, we will integrate a **real-time monitoring system** to fetch **APR, TVL, and other metrics** dynamically from blockchain data sources.  



## Test in Local Environment
1. Configure .env 
   ```
   OPENAI_API_KEY=
   PINECONE_API_KEY=
   PINECONE_INDEX_NAME=
   QUICKNODE_API_KEY=
   AGGREGATOR_CONTRACT_ADDRESS=
   ```
2. Simply run `python main.py` to start the FastAPI server
